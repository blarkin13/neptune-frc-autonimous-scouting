import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from neptune_identity import reconcile
import neptune_review_learning as learning
from neptune_temporal import plan,ClipUnavailable
R={'red':[1,2,3],'blue':[4,5,6]};SHA='a'*64

def point(t,track=1,team=None,x=.2):
    return {'t':t,'track_id':track,'box':[x,.3,.1,.2],'alliance':'red','scene':'wide:0','camera':'wide','camera_bounds':[0,.2,1,1],'verified_team':team,'appearance':[.125]*24}

def review(points):
    return dict(reconcile(points,R,SHA),match_key='2026test_qm1')

def approve(r,team=2):
    tracks={p['review_track'] for p in r['points']}
    return dict(r,corrections=[{'review_track':k,'start':min(p['t'] for p in r['points'] if p['review_track']==k),'end':max(p['t'] for p in r['points'] if p['review_track']==k),'team':team} for k in tracks])

def facts():
    return {'source':{'sha256':SHA,'duration_s':30},'periods':{'auto':{'start':0,'end':15}},'bumpers':{'identities':{str(t):{'alliance':c} for c,ts in R.items() for t in ts}},'tracking':{'band':[.2,1],'localizations':[],'continuity_revision':'reviewed-flow-continuity-v5'}}

class Learning(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.env=patch.dict(os.environ,{'NEPTUNE_REVIEW_LIBRARY':str(self.root)});self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_correction_persists_and_action_clip_uses_reviewed_fragments(self):
        # One robot, two detector IDs; reviewed positions join within one shot.
        r=approve(review([point(k/4,1 if k<8 else 99) for k in range(17)]))
        info=learning.publish(r);original=facts();out=learning.apply_to_facts(original)
        self.assertEqual(original['tracking']['localizations'],[])
        loc=out['tracking']['localizations'];self.assertEqual(len(loc),17);self.assertEqual(len({p['track_id'] for p in loc}),1)
        clip=plan(out,loc[8]);self.assertEqual(len(clip['frames']),16);self.assertEqual(clip['team'],2);self.assertEqual(clip['identity_supervision']['review_revision'],info['revision'])
    def test_only_explicitly_reviewed_interval_supplies_training_positions(self):
        r=review([point(k/4) for k in range(20)]);p=r['points'][0];r['corrections']=[{'review_track':p['review_track'],'start':2,'end':2.5,'team':2}]
        learning.publish(r);out=learning.apply_to_facts(facts());self.assertEqual([p['t'] for p in out['tracking']['localizations']],[2,2.25,2.5])
        with self.assertRaises(ClipUnavailable):plan(out,out['tracking']['localizations'][0])
    def test_unknown_suggestions_never_become_supervision(self):
        r=review([point(t,team=1 if t==0 else None) for t in (0,.5,1)])
        learning.publish(r);self.assertEqual(learning.apply_to_facts(facts())['tracking']['localizations'],[])
    def test_undo_replaces_old_reviewed_identity_and_changes_preparation_key(self):
        from neptune_training import prepared_signature
        r=approve(review([point(1)]));learning.publish(r);before=learning.revision(SHA);source={'sha256':SHA};game={'fingerprint':'test'}
        with patch('neptune_yolo.fingerprint',return_value='test'):key1=prepared_signature(source,[],[],game)
        out=learning.apply_to_facts(facts());r['corrections']=[];learning.publish(r)
        self.assertNotEqual(before,learning.revision(SHA));self.assertEqual(learning.apply_to_facts(out)['tracking']['localizations'],[])
        with patch('neptune_yolo.fingerprint',return_value='test'):self.assertNotEqual(key1,prepared_signature(source,[],[],game))
    def test_wrong_video_and_roster_cannot_reuse_corrections(self):
        learning.publish(approve(review([point(1)])));f=facts();f['source']['sha256']='b'*64;self.assertIs(learning.apply_to_facts(f),f)
        f=facts();f['bumpers']['identities']['7']=f['bumpers']['identities'].pop('1')
        with self.assertRaises(ValueError):learning.apply_to_facts(f)
    def test_human_correction_replaces_wrong_automatic_box_and_preserves_teammate(self):
        r=approve(review([point(1)]));learning.publish(r);f=facts();wrong=dict(point(1),team=1,identity_method='yolo_botsort_ocr');other=dict(point(1,track=2,x=.7),team=3,identity_method='yolo_botsort_ocr');f['tracking']['localizations']=[wrong,other]
        out=learning.apply_to_facts(f);self.assertEqual({p['team'] for p in out['tracking']['localizations']},{2,3})
    def test_scene_cut_and_visible_gap_do_not_join_training_tracks(self):
        pts=[point(0),point(.25),dict(point(.5,track=2),scene='wide:1'),dict(point(1.5,track=2),scene='wide:1')]
        learning.publish(approve(review(pts)));out=learning.apply_to_facts(facts());self.assertEqual(len({p['track_id'] for p in out['tracking']['localizations']}),3)
    def test_excluded_false_detection_overrides_old_automatic_track(self):
        r=review([point(1,team=1)]);r['corrections']=[{'review_track':r['points'][0]['review_track'],'start':1,'end':1,'team':None,'ignored':True}];learning.publish(r);f=facts();f['tracking']['localizations']=[dict(point(1),team=1)]
        self.assertEqual(learning.apply_to_facts(f)['tracking']['localizations'],[])
    def test_reserved_benchmark_can_be_reviewed_but_never_fit_association(self):
        from neptune_training import HELD_OUT_MATCHES
        r=approve(review([point(1)]));r['match_key']=next(iter(HELD_OUT_MATCHES));learning.publish(r);doc=learning.load(SHA);self.assertTrue(doc['evaluation_only']);self.assertEqual(learning.pairs(doc),[])
    def test_missing_examples_keeps_generalized_candidate_inactive(self):
        report=learning.train_association();self.assertFalse(report['active']);self.assertEqual(report['status'],'needs_reviewed_matches')
    def test_fit_reaches_the_link_threshold_on_separable_pairs(self):
        # The old fixed-step fit kept every same-robot pair below .9, so nothing ever linked.
        same=[{'x':[.02+.01*(k%3),.05,.3+.1*(k%5),0.,.04+.01*(k%4)],'y':1} for k in range(60)]
        other=[{'x':[.5+.1*(k%4),.6,.3+.1*(k%5),1.,.2+.02*(k%3)],'y':0} for k in range(60)]
        head=learning.fit(same+other)
        self.assertGreater(min(learning.probability(head,r['x']) for r in same),.95)
        self.assertLess(max(learning.probability(head,r['x']) for r in other),.05)
    def test_identity_check_holds_out_each_match_and_never_scores_reserved_ones(self):
        from neptune_training import HELD_OUT_MATCHES
        folder=self.root/'full'
        for match,sha in (('2026test_qm1','b'*64),('2026test_qm2','c'*64),(next(iter(HELD_OUT_MATCHES)),'d'*64)):
            r=approve(dict(reconcile([point(k/4,team=1 if k==0 else None) for k in range(8)],R,sha),match_key=match))
            (folder/match).mkdir(parents=True);(folder/match/'identity-review.json').write_text(json.dumps(r))
        learning.atomic(self.root/'association-candidate.json',{'model':None,'eligible_for_identity_benchmark':False})
        with self.assertRaises(ValueError):learning.identity_check(self.root,folder)
        learning.atomic(self.root/'association-candidate.json',{'model':{'weights':[0.]*5,'bias':0.},'eligible_for_identity_benchmark':True})
        same=[{'x':[.02,.05,.3,0.,.04],'y':1,'match_key':'2026test_qm9','source':'e'*64}]*20;other=[{'x':[.6,.7,.3,1.,.25],'y':0,'match_key':'2026test_qm9','source':'e'*64}]*20
        with patch.object(learning,'pairs',return_value=same+other):
            (self.root/'reviews').mkdir(exist_ok=True);learning.atomic(self.root/'reviews'/'x.json',{'version':learning.VERSION})
            result=learning.identity_check(self.root,folder,activate=True)
        self.assertEqual(result['matches'],['2026test_qm1','2026test_qm2'])
        # Eight boxes per match is far below 150 correct names, so nothing activates.
        self.assertFalse(result['passed']);self.assertFalse((self.root/'association-active.json').exists())
    def test_action_example_provenance_survives_actual_label_pipeline(self):
        from neptune_training import labeled_examples
        r=approve(review([point(k/4) for k in range(17)]));info=learning.publish(r);f=learning.apply_to_facts(facts());row={'id':1,'video_id':'v','match_key':'2026test_qm1','team_number':2,'tag_key':'feed','polarity':'present','label_scope':'moment','start_ms':2000,'end_ms':2000,'evidence_type':'human_video_label'}
        sources={'v':{'status':'verified','sha256':SHA,'file':'v.mp4','duration_ms':30000}}
        examples,skipped=labeled_examples([row],{'v':f},sources,self.root,extractor=lambda *a:[.1],temporal_required=True)
        self.assertEqual(len(examples),1,skipped);self.assertEqual(examples[0]['identity_supervision']['review_revision'],info['revision']);self.assertEqual(examples[0]['tag'],'feed')

class Flow(unittest.TestCase):
    def image(self,x=20):
        import numpy as np
        image=np.zeros((120,240),dtype=np.uint8);texture=np.random.default_rng(7).integers(0,255,(40,40),dtype=np.uint8);image[30:70,x:x+40]=texture;return image
    def det(self,x=20,tid=5):return {'id':tid,'box':[x,30,x+40,70],'alliance':'red','confidence':.9}
    def test_missing_detector_box_follows_visible_texture_and_reconnects_new_id(self):
        from neptune_box_follow import BoxFollower
        f=BoxFollower();f.update(self.image(),0,0,[self.det()]);out=f.update(self.image(24),.167,0,[])
        self.assertEqual(len(out),1);self.assertEqual(out[0]['box_source'],'optical_flow');self.assertAlmostEqual(out[0]['box'][0],24,delta=1)
        out=f.update(self.image(28),.333,0,[self.det(28,99)]);self.assertEqual(len(out),1);self.assertEqual(out[0]['id'],5);self.assertEqual(out[0]['box_source'],'detector')
    def test_flow_stops_on_shot_change_or_long_gap(self):
        from neptune_box_follow import BoxFollower
        for t,scene in ((.167,1),(1.,0)):
            f=BoxFollower();f.update(self.image(),0,0,[self.det()]);self.assertEqual(f.update(self.image(24),t,scene,[]),[])
    def test_initial_detection_without_botsort_id_is_retained(self):
        from neptune_box_follow import BoxFollower
        out=BoxFollower().update(self.image(),0,0,[self.det(tid=None)]);self.assertEqual(len(out),1);self.assertLess(out[0]['id'],0)
    def test_blank_background_does_not_invent_a_followed_box(self):
        from neptune_box_follow import BoxFollower
        import numpy as np
        image=np.zeros((120,240),dtype=np.uint8);f=BoxFollower();f.update(image,0,0,[self.det()]);self.assertEqual(f.update(image,.167,0,[]),[])

if __name__=='__main__':unittest.main()

class AdditionalGuards(unittest.TestCase):
    def test_other_review_cannot_silently_erase_shared_corrections(self):
        with tempfile.TemporaryDirectory() as root:
            original=approve(review([point(1)]));learning.publish(original,root)
            with self.assertRaises(ValueError):learning.publish(review([point(1)]),root,expected_revision=None)
            self.assertEqual(learning.load(SHA,root)['points'][0]['team'],2)
    def test_pair_learning_uses_explicit_same_alliance_supervision_only(self):
        rows=[dict(point(t,track=team,x=.1+.2*team),identity_status='corrected',team=team) for t in (0,.5,1) for team in (1,2)]
        doc={'match_key':'2026test_qm1','source_sha256':SHA,'points':rows}
        pairs=learning.pairs(doc);self.assertEqual({p['y'] for p in pairs},{0,1})
        self.assertTrue(all(p['match_key']=='2026test_qm1' for p in pairs))
        self.assertEqual(learning.pairs(dict(doc,points=[dict(p,identity_status='inferred') for p in rows])),[])
    def test_one_class_cannot_fit_association(self):self.assertIsNone(learning.fit([{'x':[0]*5,'y':1}]))
    def test_uncalibrated_candidate_cannot_be_activated(self):
        with tempfile.TemporaryDirectory() as root:
            learning.atomic(Path(root)/'association-candidate.json',{'model':{},'eligible_for_identity_benchmark':False})
            with self.assertRaises(ValueError):learning.evaluate_association(Path(root)/'audit.json',root,activate=True)
            self.assertIsNone(learning.active_association(root))
    def test_drawn_box_must_be_inside_camera_and_at_a_known_shot(self):
        from neptune_box_follow import propose
        r=review([point(1)]);r['points'][0]['camera_bounds']=[0,.2,1,1]
        for box,t in (([0,0,.2,.2],1),([.2,.3,.1,.2],20)):
            with self.assertRaises(ValueError):propose('missing.mp4',r,t,box,'red','wide')

class Transfer(unittest.TestCase):
    def test_reviewed_learning_transfers_to_another_helper_without_video_or_labels(self):
        with tempfile.TemporaryDirectory() as first,tempfile.TemporaryDirectory() as second:
            learning.publish(approve(review([point(k/4) for k in range(17)])),first);document=learning.load(SHA,first)
            learning.import_document(document,second);out=learning.apply_to_facts(facts(),second)
            self.assertEqual(plan(out,out['tracking']['localizations'][8])['team'],2)
            self.assertNotIn('video',document);self.assertNotIn('labels',document)
            learning.import_document(document,second) # idempotent repeat
    def test_import_rejects_inference_tampered_geometry_and_wrong_fingerprint(self):
        with tempfile.TemporaryDirectory() as first,tempfile.TemporaryDirectory() as second:
            learning.publish(approve(review([point(1)])),first);document=learning.load(SHA,first)
            for change in ({'identity_status':'inferred'},{'box':[.2,.3,2,.2]},{'point_id':'bad'}):
                bad=copy.deepcopy(document);bad['points'][0].update(change)
                with self.assertRaises(ValueError):learning.import_document(bad,second)

class Contact(unittest.TestCase):
    def test_matching_before_and_after_numbers_allow_review_suggestion_through_contact(self):
        pts=[point(0,1,1,x=.2),point(0,2,2,x=.6),point(.5,1,x=.3),point(.5,2,x=.36),point(1,1,1,x=.2),point(1,2,2,x=.6)]
        r=reconcile(pts,R,SHA);middle=[p for p in r['points'] if p['t']==.5]
        self.assertEqual([p['team'] for p in middle],[1,2]);self.assertTrue(all(p['identity_status']=='inferred' for p in middle))
        self.assertTrue(all(not p['identity_evidence']['training_eligible'] for p in middle))
    def test_unsafe_single_frame_seed_still_requires_independent_identity_audit(self):
        with tempfile.TemporaryDirectory() as root:
            learning.atomic(Path(root)/'association-active.json',{'version':learning.VERSION,'model':{'weights':[0]*5,'bias':0}})
            self.assertIsNone(learning.active_association(root))

class Reprepare(unittest.TestCase):
    def test_tracker_upgrade_does_not_drop_existing_human_corrections(self):
        from neptune_identity_review import prepare
        from neptune_video_labels import sha256_file
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);video=root/'v.mp4';video.write_bytes(b'video fixture');source=sha256_file(video)
            old=approve(dict(reconcile([point(1)],R,source),match_key='2026test_qm1'));(root/'identity-review.json').write_text(json.dumps(old))
            labels=root/'labels.ndjson';labels.write_text(json.dumps({'match_key':'2026test_qm1','roster':R}))
            fresh=dict(facts(),source={'sha256':source,'duration_s':30});fresh['tracking']['identity_review']=reconcile([point(1,track=99)],R,source)
            with patch('neptune_facts.analyze_video',return_value=fresh),patch('neptune_training.ensure_tracking',return_value=fresh),patch('neptune_games.select',return_value={}):path=prepare(video,labels,'2026test_qm1',root)
            saved=json.loads(path.read_text());from neptune_identity import apply_corrections
            corrected=apply_corrections(saved,saved['corrections']);self.assertEqual(corrected['points'][0]['team'],2);self.assertEqual(saved['corrections'],old['corrections'])

class Migration(unittest.TestCase):
    def test_empty_startup_record_does_not_block_existing_legacy_corrections(self):
        with tempfile.TemporaryDirectory() as root:
            learning.publish(review([point(1)]),root)
            result=learning.publish(approve(review([point(1)])),root,expected_revision=None)
            self.assertEqual(result['reviewed_samples'],1)
    def test_import_is_allowed_when_destination_only_has_an_empty_startup_record(self):
        with tempfile.TemporaryDirectory() as first,tempfile.TemporaryDirectory() as second:
            learning.publish(approve(review([point(1)])),first);learning.publish(review([point(1)]),second)
            result=learning.import_document(learning.load(SHA,first),second);self.assertEqual(result['reviewed_samples'],1)
    def test_undo_history_still_blocks_a_stale_review_restoring_old_labels(self):
        with tempfile.TemporaryDirectory() as root:
            r=approve(review([point(1)]));saved=learning.publish(r,root);r['corrections']=[]
            learning.publish(r,root,expected_revision=saved['revision'])
            with self.assertRaises(ValueError):learning.publish(approve(review([point(1)])),root,expected_revision=None)
