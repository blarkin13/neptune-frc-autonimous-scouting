import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_games as games
import neptune_training as training
import neptune_scoring_model as scoring
import neptune_video_labels as labels


def row(team=1,points=100):
    return dict(id=('%032x'%team),schema_version=2,evidence_type='human_video_label',time_basis='video_elapsed_ms',match_id=1,match_key='2026same_qm1',source_url='https://www.youtube.com/watch?v=AAAAAAAAAAA',video_id='AAAAAAAAAAA',roster={'red':[1,2,3],'blue':[4,5,6]},team_number=team,tag_key='scoring',tag_label='Scoring',tag_category='Scoring',definition_version='neptune-match-tags-v1',label_scope='match',start_ms=None,end_ms=None,video_duration_ms=200000,certainty='uncertain',polarity='present',note='',review_state='contributed',created_at=1,scoring=dict(schema_version=1,source='human_video_contribution',mode='alliance_share',method='estimated',robot_points=points,alliance_score=400,count_min=None,count_max=None,score_basis='full_final_alliance_score'))


def facts():
    return {'source':{'sha256':'a'*64,'duration_s':200},'identity':{'checks':{'match_number':{'status':'match'},'roster':{'status':'match'}}},
            'periods':{'auto':{'start':0,'end':20,'start_observed':True,'end_observed':True},'teleop':{'start':20,'end':160,'start_observed':True,'end_observed':True}},
            'bumpers':{'identities':{str(t):{'status':'confirmed','alliance':'red' if t<4 else 'blue'} for t in range(1,7)},
                       'reads':[dict(team=t,t=sec+t*.01,kind='exact',background='red' if t<4 else 'blue',frame_box=[.2,.2,.03,.02],frame=str(sec)) for t in range(1,7) for sec in (0,25,50,75,100,125,150)]}}


def feature(video,sight,duration):return [sight['team']/10+sight['t']/10000]*1296


class Scoring(unittest.TestCase):
    def examples(self):
        rows=[row(t,p) for t,p in [(1,30),(2,100),(3,200)]]
        return scoring.examples(rows,{'AAAAAAAAAAA':facts()},{'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':200000,'file':'video.mp4'}},Path('/not-accessed'),feature)[0]
    def test_estimated_labels_keep_uncertainty_and_do_not_enter_action_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=labels.Store(tmp);labels.ingest(store,path=self.snapshot(Path(tmp)))
            rows,_=scoring.label_rows(store,games.select('2026test'));self.assertEqual(len(rows),3);self.assertTrue(all(r['certainty']=='uncertain' for r in rows));self.assertEqual(training.corpus(store,games.select('2026test'))[0],[])
    def snapshot(self,root):
        p=root/'input.ndjson';p.write_text('\n'.join(json.dumps(row(t,points)) for t,points in [(1,30),(2,100),(3,200)]));return p
    def test_no_target_from_scoring_start_unknown_or_invalid_total(self):
        r=row();r['label_scope']='moment';self.assertIsNone(scoring.target(r))
        for score in [dict(robot_points=500),dict(alliance_score=None),dict(method='unknown'),dict(score_basis='without_penalties')]:
            r=row();r['scoring'].update(score);self.assertIsNone(scoring.target(r))
    def test_changed_scores_change_fitted_model_and_prediction(self):
        data=self.examples();a,report=scoring.fit(data);changed=copy.deepcopy(data);changed[0]['y']=.8;b,_=scoring.fit(changed)
        self.assertNotEqual(a['coefficients'],b['coefficients']);self.assertNotEqual(scoring.predict_share(a,data[0]['x']),scoring.predict_share(b,data[0]['x']));self.assertIsNone(report['evaluation']);self.assertFalse(a['release_ready'])
    def test_duplicates_combine_and_conflicts_are_excluded(self):
        r=row();other=copy.deepcopy(r);other['id']='f'*32
        args=({'AAAAAAAAAAA':facts()},{'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':200000,'file':'video.mp4'}},Path('/not-accessed'),feature)
        out,_=scoring.examples([r,other],*args);self.assertEqual(len(out),1);self.assertEqual(len(out[0]['label_ids']),2)
        other['scoring']['robot_points']=300;out,skip=scoring.examples([r,other],*args);self.assertFalse(out);self.assertEqual(skip['conflicting_score_estimates'],2)
    def test_incomplete_video_missing_identity_and_camera_gaps_abstain(self):
        f=facts();f['periods']['auto']=None;self.assertEqual(scoring.descriptor('none',f,1,200000,feature)[1],'incomplete_match_video')
        f=facts();f['identity']['checks']['roster']['status']='partial';self.assertEqual(scoring.descriptor('none',f,1,200000,feature)[1],'match_identity_incomplete')
        f=facts();f['bumpers']['identities']['1']['status']='candidate';self.assertEqual(scoring.descriptor('none',f,1,200000,feature)[1],'insufficient_robot_sightings')
    def test_same_source_and_event_never_cross_training_test(self):
        data=self.examples();data[-1]['split']='test' if data[0]['split']!='test' else 'training'
        with self.assertRaisesRegex(ValueError,'leakage'):scoring.fit(data)
    def test_unknowns_remain_null_without_held_out_video_validation(self):
        model,_=scoring.fit(self.examples(),point_mode=True)
        model['team_priors']={'1':{'share':.8,'matches':100}}
        output=scoring.predict('none',facts(),model,{'red':[1,2,3],'blue':[4,5,6]},{'red':400,'blue':300},feature)
        self.assertTrue(all(r['robot_points'] is None for r in output))
        self.assertTrue(all(not r['alliance_constraint_applied'] for r in output))
    def test_validated_video_preserves_unassigned_points_and_unidentified_robot(self):
        model,_=scoring.fit(self.examples(),point_mode=True);model['coefficients']=[0]*3;model['bias']=20.
        model['validation']={'video':{'status':'evaluated','robots':6,'point_mae_video':10,'point_mae_training_mean':20}}
        f=facts();f['bumpers']['identities']['2']['status']='candidate'
        output=scoring.predict('none',f,model,{'red':[1,2,3],'blue':[4,5,6]},{'red':272,'blue':199},feature)
        self.assertEqual([r['robot_points'] for r in output[:3]],[20,None,20])
        self.assertEqual(output[1]['reason'],'insufficient_robot_sightings')
        self.assertIsNone(output[0]['observed_points'])
        self.assertAlmostEqual(output[0]['share_percent'],100*20/272,places=3)
    def test_over_allocation_abstains_instead_of_renormalizing(self):
        model,_=scoring.fit(self.examples(),point_mode=True);model['coefficients']=[0]*3;model['bias']=150.
        model['validation']={'video':{'status':'evaluated','robots':6,'point_mae_video':10,'point_mae_training_mean':20}}
        output=scoring.predict('none',facts(),model,{'red':[1,2,3],'blue':[4,5,6]},{'red':300,'blue':300},feature)
        self.assertTrue(all(r['robot_points'] is None and r['reason']=='inconsistent_alliance_predictions' for r in output))
    def test_apportion_whole_points(self):
        self.assertEqual(scoring.apportion([1,1,1],100),[34,33,33]);self.assertEqual(sum(scoring.apportion([.2,.5,.3],7)),7)
    def test_scoring_only_training_checkpoint_and_model_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=self.snapshot(root)
            def verify(store,videos,download,only_video_ids):return {'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':200000,'file':'video.mp4'}}
            with patch('neptune_training.labels.verify_sources',side_effect=verify),patch('neptune_facts.analyze_video',return_value=facts()),patch('neptune_training.features',side_effect=feature):
                report=training.run(root/'job',2026,export_path=snapshot,cache_root=root/'cache',progress=lambda s:None)
            model=json.loads((Path(report['folder'])/'model.json').read_text());training.model_valid(model,games.select('2026test',root));self.assertEqual(model['heads'],{});self.assertIn('scoring_head',model);self.assertEqual(report['scoring']['training_robots'],3);self.assertIsNone(report['scoring']['evaluation']);self.assertEqual(len(report['scoring']['training_preview']),3)
            model['scoring_head']['bias']+=1
            with self.assertRaisesRegex(ValueError,'changed'):training.model_valid(model,games.select('2026test',root))
    def test_model_malformed_values_rejected(self):
        model,_=scoring.fit(self.examples());model['scale'][0]=0
        with self.assertRaises(ValueError):scoring.valid(model)
    def test_benchmark_misses_reduce_coverage_not_hidden_from_errors(self):
        rows=[{'expected':6,'predicted':1,'complete_reference':True,'point_errors':[0],'share_errors':[0]} for _ in range(10)]
        report=scoring.evaluation_report(rows,2);self.assertFalse(report['release_ready']);self.assertAlmostEqual(report['prediction_coverage'],1/6)
    def test_corrected_and_withdrawn_score_targets_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=labels.Store(tmp);original=row();corrected=copy.deepcopy(original);corrected['scoring']['robot_points']=150
            store.save('ledger.json',{'x':{'original':original,'state':'contributed','revisions':[{'record':corrected}]},'y':{'original':row(2),'state':'withdrawn'}})
            rows,_=scoring.label_rows(store,games.select('2026test'));self.assertEqual(len(rows),1);self.assertEqual(rows[0]['scoring']['robot_points'],150)

    def test_two_varied_robot_targets_can_fit_but_missing_provenance_is_invalid(self):
        head,report=scoring.fit(self.examples()[:2]);self.assertEqual(report['training_robots'],2);self.assertFalse(head['release_ready']);scoring.valid(head)
        head.pop('training_sources')
        with self.assertRaisesRegex(ValueError,'provenance'):scoring.valid(head)
    def test_complete_counted_score_reference_required_for_benchmark(self):
        head,_=scoring.fit(self.examples());ref={'match_key':'2026other_qm1','roster':{'red':[1,2,3],'blue':[4,5,6]},'alliance_scores':{'red':400,'blue':300},'score_basis':'full_final_alliance_score','robot_scores':{str(t):{'robot_points':50,'method':'counted','complete':True} for t in range(1,7)}}
        predictions=[{'team':t,'status':'predicted','robot_points':50} for t in range(1,7)]
        with patch.object(scoring,'predict',return_value=predictions):
            report=scoring.evaluate_match('none',facts(),head,ref);self.assertEqual(report['predicted'],6);self.assertEqual(report['point_errors'],[0]*6)
            ref['robot_scores']['1']['method']='estimated';report=scoring.evaluate_match('none',facts(),head,ref);self.assertFalse(report['complete_reference']);self.assertEqual(report['predicted'],0)
    def test_owner_trial_saves_six_scores_and_sends_no_human_labels_or_summary(self):
        import neptune_trainer as trainer
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game=games.select('2026test',root);training.train([],game,root/'model',{},self.examples())
            model=json.loads((root/'model/model.json').read_text());pack=json.loads(games.BUILTIN.read_text())['seasons']['2026']
            job={'id':'trial','lease':'local-fixture','game_pack':pack,'model':model,'request':{'title':'Example Qualification 1','match_key':'2026same_qm1','roster':{'red':[1,2,3],'blue':[4,5,6]},'source_url':'https://www.youtube.com/watch?v=AAAAAAAAAAA','alliance_scores':{'red':400,'blue':300}}}
            sent=[]
            def api(config,action,payload):
                sent.append((action,payload));return job if action=='trial_start' else {'ok':True,'report_url':'/admin/community-learning.php#scoring-trials'}
            def download(match,path,stage):path.write_bytes(b'fixture-only')
            with patch.object(trainer,'HOME',root/'home'),patch.object(trainer,'api',side_effect=api),patch('neptune_helper.download_video',side_effect=download),patch('neptune_video_labels.probe_duration_ms',return_value=200000),patch('neptune_video_labels.sha256_file',return_value='a'*64),patch('neptune_facts.analyze_video',return_value=facts()),patch('neptune_training.features',side_effect=feature):
                scoring.run_trial({'site':'https://example.org'},2026,1,lambda s:None)
            self.assertEqual([a for a,_ in sent],['trial_start','trial_finish']);result=sent[-1][1]['result'];self.assertEqual(len(result['scores']),6);self.assertEqual(result['tags'],[]);self.assertNotIn('summary',result);self.assertTrue((root/'home/trials/trial/result.json').exists());self.assertTrue(all(s['certainty']=='uncertain' for s in result['scores']))
    def test_trial_rejects_incompatible_candidate_and_reports_failure(self):
        import neptune_trainer as trainer
        pack=json.loads(games.BUILTIN.read_text())['seasons']['2026'];sent=[]
        job={'id':'trial','lease':'fixture','game_pack':pack,'model':{'model_id':'invalid'},'request':{}}
        def api(config,action,payload):sent.append((action,payload));return job if action=='trial_start' else {'ok':True}
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)),patch.object(trainer,'api',side_effect=api):
            with self.assertRaisesRegex(ValueError,'changed'):scoring.run_trial({'site':'https://example.org'},2026,1,lambda s:None)
        self.assertEqual(sent[-1][0],'trial_finish');self.assertIn('error',sent[-1][1])

if __name__=='__main__':unittest.main()
