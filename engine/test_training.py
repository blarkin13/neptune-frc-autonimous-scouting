import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import neptune_games as g
import neptune_training as t
import neptune_facts as f
import neptune_video_labels as v

class Games(unittest.TestCase):
    def test_switching_and_future_game(self):
        a=g.select('2025test_qm1');b=g.select('2026test_qm1')
        self.assertEqual((a['game'],a['auto_seconds'],a['teleop_seconds']),('REEFSCAPE',15,135))
        self.assertNotEqual(a['game_key'],b['game_key'])
        self.assertEqual(g.select('2025test_qm1')['fingerprint'],a['fingerprint'])
        with self.assertRaisesRegex(ValueError,'not configured'):g.select('2027test_qm1')
        self.assertEqual(f.mmss(-22),'−0:22.0')
        self.assertIsNone(f.endgame_boundary({'teleop':{'end':150}},[],a))
    def test_new_pack_invalidates_old_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=g.select('2026test');pack=dict(p,season=2026,revision=p['revision']+1);pack.pop('fingerprint')
            file=Path(tmp)/'pack.json';file.write_text(json.dumps(pack));g.install(file,tmp)
            self.assertNotEqual(g.select('2026test',tmp)['fingerprint'],p['fingerprint'])
    def test_model_rejects_other_game(self):
        with self.assertRaises(ValueError):t.model_valid({'schema_version':1,'game_key':'2026-rebuilt','heads':{}},g.select('2025test'))

class Learning(unittest.TestCase):
    def game(self):return g.select('2026test',Path('/__neptune_test_without_user_packs__'))
    def rows(self):
        out=[]
        for split in ('training','calibration','test'):
            for y in (0,1):
                for i in range(4):
                    out.append({'tag':'scoring','x':[float(y)]*1296,'y':y,'label_ids':[split+str(y)+str(i)],'source_sha256':split,'group':split,'split':split,'match_key':'2026'+split+'_qm1','team':1,'t_ms':i*1000})
        return out
    def test_actual_fit_and_new_weights(self):
        rows=self.rows();head=t.fit_binary([r for r in rows if r['split']=='training'])
        self.assertLess(t.score(head,[0.0]*1296),t.score(head,[1.0]*1296))
        changed=copy.deepcopy(rows)
        for row in changed:row['y']=1-row['y']
        other=t.fit_binary(changed)
        self.assertNotEqual(head['weights'],other['weights'])
    def test_candidate_no_fake_accuracy_and_artifact_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';result=t.train(self.rows(),self.game(),run,{})
            self.assertEqual(result['tags']['scoring']['test']['precision'],1.0)
            self.assertFalse(result['release_ready'])
            model=json.loads((run/'model.json').read_text());t.model_valid(model,self.game())
            model['heads']['scoring']['weights'][0]+=1
            with self.assertRaisesRegex(ValueError,'changed'):t.model_valid(model,self.game())
    def test_full_benchmark_and_withdrawal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game=self.game();run=root/'models'/game['game_key']/'run'
            t.train(self.rows(),game,run,{})
            references=[];actions=[{'team':i,'tag_key':'scoring','start_ms':1000} for i in range(1,7)]
            for i in range(10):
                video=root/('video%d.mp4'%i);video.write_bytes(('video-%d'%i).encode());sha=v.sha256_file(video)
                facts=root/('facts%d.json'%i);facts.write_text(json.dumps({'source':{'sha256':sha,'duration_s':10}}))
                references.append({'match_key':'2026hold'+('a' if i<5 else 'b')+'_qm'+str(i+1),'source_sha256':sha,'duration_ms':10000,'video':video.name,'facts':facts.name,'roster':{'red':[1,2,3],'blue':[4,5,6]},'complete_robot_labels':{str(i):True for i in range(1,7)},'events':actions})
            manifest=root/'reference.json';manifest.write_text(json.dumps({'season':2026,'game_key':game['game_key'],'tags':['scoring'],'matches':references}))
            with patch('neptune_training.predict',return_value=actions):report=t.evaluate_benchmark(root,run,manifest,lambda s:None)
            self.assertTrue(report['release_ready'])
            ledger={id:{'state':'contributed'} for r in self.rows() for id in r['label_ids']};v.Store(root/'labels').save('ledger.json',ledger)
            t.activate(root,run);self.assertIsNotNone(t.active(root,game))
            ledger[next(iter(ledger))]['state']='withdrawn';v.Store(root/'labels').save('ledger.json',ledger);self.assertIsNone(t.active(root,game))
            with patch('neptune_training.predict',return_value=actions[:-1]):report=t.evaluate_benchmark(root,run,manifest,lambda s:None)
            self.assertFalse(report['all_six_robot_gate']);self.assertFalse(report['release_ready'])

    def test_no_negatives_means_untrained(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=t.train([r for r in self.rows() if r['y']],self.game(),Path(tmp)/'run',{})
            self.assertEqual(r['tags']['scoring']['status'],'needs_positive_and_negative_training_examples')
    def pu_rows(self,sources=4,signal=True):
        """Several matches from one event; each has tagged positives and mostly-ordinary unlabelled footage."""
        rows=[];base=self.rows()[0]
        for s in range(sources):
            sha='training-%d'%s;match='2026training_qm%d'%(s+1)
            for i in range(3):
                x=[1.0]*1296 if signal else [float((s+i)%2)]*1296
                rows.append(dict(base,x=x,y=1,label_ids=['p%d%d'%(s,i)],source_sha256=sha,match_key=match,t_ms=i*1000))
            for i in range(10):
                x=[float(i%10==0)]*1296 if signal else [float(i%2)]*1296
                rows.append(dict(base,x=x,y=None,label_ids=[],source_sha256=sha,match_key=match,t_ms=10000+i*1000,evidence_type='unlabeled_reference'))
        return rows
    def test_pu_fits_without_human_negatives_and_never_reports_unknown_as_accuracy(self):
        rows=self.pu_rows()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'run';result=t.train(rows,self.game(),folder,{})
            model=json.loads((folder/'model.json').read_text());head=model['heads']['scoring']
            self.assertEqual(head['learning_method'],'positive-unlabeled-bagging-v1')
            self.assertGreater(t.score(head,[1.0]*1296),t.score(head,[0.0]*1296))
            self.assertIsNone(result['tags']['scoring']['test'])
            # The threshold comes from match-held-out scores and leaves ordinary footage untagged.
            self.assertEqual(head['threshold_status'],'held_out_pu_calibrated')
            self.assertGreaterEqual(result['tags']['scoring']['validation']['auc_vs_unlabeled'],t.PU_MIN_HELD_OUT_AUC)
            self.assertGreaterEqual(t.score(head,[1.0]*1296),head['threshold']);self.assertLess(t.score(head,[0.0]*1296),head['threshold'])
            self.assertFalse(model['release_ready']);t.model_valid(model,self.game())
            provenance=json.loads((folder/'examples-provenance.json').read_text())
            unknown=[r for r in provenance if r.get('evidence_type')=='unlabeled_reference']
            self.assertTrue(all(r['y'] is None and not r['label_ids'] for r in unknown))
            self.assertFalse(any(r['y']==0 for r in provenance))
    def test_pu_development_group_is_whole_and_not_claimed_as_test(self):
        rows=self.pu_rows()
        for r in rows:r['split']='test'
        with tempfile.TemporaryDirectory() as tmp:
            result=t.train(rows,self.game(),Path(tmp)/'run',{})
            detail=result['tags']['scoring']
            self.assertTrue(detail['development_partition']);self.assertIsNone(detail['test'])
            self.assertFalse(result['release_ready'])
    def test_pu_development_group_cannot_be_reused_as_benchmark(self):
        rows=self.pu_rows()
        for r in rows:r['split']='test'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';t.train(rows,self.game(),run,{})
            manifest=root/'reference.json';manifest.write_text(json.dumps({'season':2026,'game_key':self.game()['game_key'],'tags':['scoring'],
                'matches':[{'match_key':'2026other_qm1','source_sha256':'training-0'}]}))
            with self.assertRaisesRegex(ValueError,'overlaps'):t.evaluate_benchmark(root,run,manifest,lambda s:None)
    def test_pu_head_without_held_out_signal_is_withheld(self):
        # Week 0 regression: a head that ranks unseen matches at chance used to ship with a
        # minimum-positive threshold and tag almost every robot sighting.
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'run';result=t.train(self.pu_rows(signal=False),self.game(),folder,{})
            detail=result['tags']['scoring'];self.assertEqual(detail['status'],'no_held_out_signal')
            self.assertLess(detail['validation']['auc_vs_unlabeled'],t.PU_MIN_HELD_OUT_AUC)
            self.assertEqual(json.loads((folder/'model.json').read_text())['heads'],{})
    def test_pu_head_needs_positives_from_several_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=t.train(self.pu_rows(sources=2),self.game(),Path(tmp)/'run',{})
            self.assertEqual(result['tags']['scoring']['status'],'needs_more_positive_examples_across_matches')
    def test_old_provisional_pu_heads_are_not_run(self):
        model={'heads':{'scoring':{'threshold_status':'provisional_training_positives'},'disabled':{'threshold_status':'held_out_pu_calibrated'},'end_failed':{'threshold':1.0}}}
        self.assertEqual(sorted(t.usable_heads(model)),['disabled','end_failed'])
    def test_pu_threshold_caps_flag_rate_and_auc_handles_ties(self):
        self.assertEqual(t.pu_auc([1,1],[0,0]),1.0);self.assertEqual(t.pu_auc([1],[1]),.5)
        threshold,rate,recall=t.pu_threshold([5,4,3],[5,0,0,0,0,0,0,0,0,0])
        self.assertEqual((threshold,recall),(3,1.0));self.assertLessEqual(rate,t.PU_MAX_FLAG_RATE)
        self.assertEqual(t.pu_threshold([1,1],[1,1,1,1])[0],None)
    def test_unknown_pool_does_not_enter_supervised_metrics(self):
        head=t.fit_binary(self.rows())
        self.assertEqual(t.metrics(self.rows(),head,0),t.metrics(self.rows()+[dict(self.rows()[0],y=None)],head,0))
    def test_shared_video_cannot_leak(self):
        rows=self.rows();rows[-1]['source_sha256']='training'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'leakage'):t.train(rows,self.game(),Path(tmp)/'run',{})
    def test_reference_missed_robot_is_false_negative(self):
        refs=[{'team':team,'tag_key':'scoring','start_ms':1000} for team in range(1,7)]
        m=t.event_metrics([refs[0]],refs)
        self.assertEqual((m['tp'],m['fn']),(1,5));self.assertAlmostEqual(m['recall'],1/6)
        m=t.event_metrics([refs[0],refs[0]],refs);self.assertEqual(m['fp'],1)
    def test_corpus_excludes_uncertainty_and_withdrawal(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=v.Store(tmp);good={'match_key':'2026test_qm1','certainty':'observed','definition_version':'neptune-match-tags-v1','tag_key':'scoring','id':'a'}
            s.save('ledger.json',{'a':{'original':good,'state':'contributed'},'b':{'original':dict(good,certainty='uncertain'),'state':'contributed'},'c':{'original':good,'state':'withdrawn'}})
            rows,rejected=t.corpus(s,self.game());self.assertEqual(len(rows),1);self.assertEqual(rejected,{'uncertain':1,'withdrawn_or_unavailable':1})
    def test_sighting_requires_confirmed_identity(self):
        facts={'bumpers':{'identities':{'1':{'status':'candidate','alliance':'red'}},'reads':[{'team':1,'t':1,'kind':'exact','background':'red','frame_box':[.1,.2,.1,.1]}]}}
        self.assertEqual(t.sightings(facts),[])
    def test_roi_three_frame_backend(self):
        ppm=b'P6\n12 12\n255\n'+bytes([128]*432)
        def emit(cmd,**kwargs):Path(cmd[-1]).write_bytes(ppm)
        with patch('neptune_training.subprocess.run',side_effect=emit) as ffmpeg:
            features=t.features('video.mp4',{'box':[.1,.2,.3,.4],'t':3},10000)
        self.assertEqual(len(features),1296);self.assertEqual(ffmpeg.call_count,3)
        self.assertTrue(all(x==0 for x in features[432:]))

if __name__=='__main__':unittest.main()
