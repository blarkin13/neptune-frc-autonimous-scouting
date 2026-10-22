import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_games as games
import neptune_training as training
import neptune_video_labels as labels
from test_checkpoints import Checkpoints

class OutsideScouting(unittest.TestCase):
 def row(self):
  return {'id':'a'*32,'schema_version':2,'evidence_type':'external_scouting_label','time_basis':'phase_elapsed_ms','match_id':1,'match_key':'2026week0_qm1','source_url':'https://www.youtube.com/watch?v=AAAAAAAAAAA','video_id':'AAAAAAAAAAA','roster':{'red':[1,2,3],'blue':[4,5,6]},'team_number':1,'tag_key':'scoring','tag_label':'Scoring','tag_category':'Scoring','definition_version':'viper-2026-activity-v1','label_scope':'moment','start_ms':2000,'end_ms':2000,'video_duration_ms':0,'certainty':'observed','polarity':'present','scoring':None,'note':'Counted activity, not a scoring start','review_state':'contributed','created_at':1,'external':{'provider':'viperscout','adapter_version':'viper-2026-activity-v1','phase':'auto','kind':'counted_scoring_activity','quantity':5,'weak_supervision':True}}
 def test_import_preserves_source_clock_and_cannot_forge_other_targets(self):
  r=self.row();rows,problems=labels.read_export(json.dumps(r));self.assertFalse(problems);self.assertEqual(rows[0]['start_ms'],2000)
  r['tag_key']='auto_failed';rows,problems=labels.read_export(json.dumps(r));self.assertFalse(rows);self.assertTrue(problems)
 def test_video_is_verified_without_inventing_a_reported_video_duration(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);store=labels.Store(root/'labels');r=self.row();store.ingest('fixture',[r],'fixture');videos=root/'videos';videos.mkdir();(videos/'AAAAAAAAAAA.mp4').write_bytes(b'fixture')
   with patch.object(labels,'probe_duration_ms',return_value=180000):sources=labels.verify_sources(store,videos)
   self.assertEqual(sources['AAAAAAAAAAA']['label_checks'][r['id']],'ok');self.assertEqual(store.load('ledger.json',{})[r['id']]['original']['video_duration_ms'],0)
 def facts(self):
  return {'source':{'sha256':'b'*64,'duration_s':180},'identity':{'checks':{'match_number':{'status':'match'},'roster':{'status':'match'}}},'periods':{'auto':{'start':8,'end':28,'clock_samples':[{'t':10,'remaining':18},{'t':11,'remaining':17}],'length_rule':20,'start_observed':True,'end_observed':True}},'bumpers':{'identities':{'1':{'status':'confirmed','alliance':'red'}},'reads':[{'team':1,'t':10,'kind':'exact','background':'red','frame_box':[.2,.2,.05,.02],'frame':'frame'}]}}
 def test_match_whose_clock_join_is_excluded_contributes_no_outside_rows(self):
  facts=self.facts();src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000}}
  good=self.row();bad=[dict(self.row(),id=c*32,start_ms=15000,end_ms=15000) for c in 'cd']
  examples,skips=training.labeled_examples([good]+bad,{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.0]*1296)
  self.assertFalse(examples);self.assertEqual(skips['external_clock_match_excluded'],1);self.assertEqual(skips['external_clock_no_local_clock_bracket'],2)
 def test_source_time_joins_verified_phase_and_keeps_weak_provenance(self):
  row=self.row();facts=self.facts();src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'AAAAAAAAAAA.mp4'}}
  examples,skipped=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.0]*1296)
  self.assertEqual(len(examples),1);self.assertEqual(examples[0]['t_ms'],10000);self.assertEqual(examples[0]['external_sources'][0]['quantity'],5);self.assertEqual(row['start_ms'],2000);self.assertEqual(examples[0]['y'],1)
  facts['periods']['auto']['start_observed']=False;facts['periods']['auto']['clock_samples']=[];examples,skipped=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'));self.assertFalse(examples);self.assertEqual(skipped['external_clock_no_local_clock_bracket'],1)
 def test_outside_scoring_row_outside_scoring_zone_is_dropped(self):
  row=self.row();facts=self.facts();src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'AAAAAAAAAAA.mp4'}}
  zone={'id':'z','kind':'scoring_zone','camera_view':'wide','alliance':'red','points':[[.8,.8],[.95,.8],[.95,.95],[.8,.95]],'start_ms':0,'reference_ms':0,'end_ms':10**9,'event_template':True,'game_key':'2026-rebuilt','reviewed':True}
  far={'regions':[zone],'source_sha256':'b'*64}
  examples,skipped=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.0]*1296,field_regions={'AAAAAAAAAAA':far})
  self.assertFalse(examples);self.assertEqual(skipped['external_scoring_away_from_scoring_area'],1)
  near=dict(zone,points=[[0,0],[1,0],[1,1],[0,1]])
  examples,skipped=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.0]*1296,field_regions={'AAAAAAAAAAA':{'regions':[near],'source_sha256':'b'*64}})
  self.assertEqual(len(examples),1)
 def test_source_failure_report_does_not_blame_human_tags(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);snapshot=Checkpoints().snapshot(root)
   with patch('neptune_video_labels.verify_sources',return_value={v:{'status':'retrieval_failed','reason':'Provider blocked this server'} for v in ('AAAAAAAAAAA','BBBBBBBBBBB')}):
    report=training.run(root/'job',2026,export_path=snapshot,progress=lambda s:None)
   self.assertEqual(len(report['inventory']['source_errors']),2);self.assertEqual(report['inventory']['labels'],4);self.assertIn('Provider blocked',report['inventory']['source_errors'][0]['reason'])
 def test_failed_video_alignment_reason_survives_cached_run(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);fixture=Checkpoints();snapshot=fixture.snapshot(root)
   with patch('neptune_video_labels.verify_sources',side_effect=fixture.verify),patch('neptune_facts.analyze_video',side_effect=ValueError('Unsupported broadcast layout: example')) as reader:
    first=training.run(root/'job',2026,export_path=snapshot,cache_root=root/'cache',progress=lambda s:None)
    second=training.run(root/'job2',2026,export_path=snapshot,cache_root=root/'cache',progress=lambda s:None)
   self.assertEqual(reader.call_count,2)
   self.assertEqual(len(second['inventory']['localization_errors']),2)
   self.assertIn('Unsupported broadcast layout',second['inventory']['localization_errors'][0]['reason'])
 def test_nearby_clock_samples_handle_drift_without_extrapolating(self):
  phase={'start':30,'end':170,'start_observed':False,'end_observed':False,'clock_samples':[{'t':80,'remaining':91},{'t':82,'remaining':89}]}
  row=dict(self.row(),start_ms=50000)
  self.assertEqual(training.outside_video_time(row,phase,140),81000)
  row['start_ms']=1000;self.assertIsNone(training.outside_video_time(row,phase,140))
  phase['clock_samples'][1]['t']=90;row['start_ms']=50000
  self.assertIsNone(training.outside_video_time(row,phase,140))
 def test_local_clock_can_join_when_global_boundaries_are_unobserved(self):
  row=self.row();facts=self.facts();facts['rules']={'auto_seconds':20}
  facts['periods']['auto'].update(start_observed=False,end_observed=False,clock_samples=[{'t':10,'remaining':18},{'t':11,'remaining':17}])
  src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'AAAAAAAAAAA.mp4'}}
  examples,skips=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.0]*1296)
  self.assertEqual(len(examples),1);self.assertEqual(examples[0]['external_sources'][0]['aligned_video_ms'],10000)
 def test_late_click_uses_one_weak_clip_and_preserves_original_time(self):
  row=dict(self.row(),start_ms=6000,end_ms=6000);facts=self.facts()
  facts['periods']['auto']['clock_samples']=[{'t':14,'remaining':14},{'t':15,'remaining':13}]
  src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'video.mp4'}}
  spots=[{'team':1,'t':t,'box':[.2,.2,.1,.1]} for t in (11.,12.5,14.)]
  with patch.object(training,'sightings',return_value=spots),patch('neptune_temporal.plan',return_value={'start':10.5,'end':14.5}):
   examples,skips=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.]*512,temporal_required=True)
  self.assertFalse(skips);self.assertEqual(len(examples),1);self.assertEqual(examples[0]['t_ms'],12500)
  evidence=examples[0]['external_sources'][0]
  self.assertEqual(evidence['aligned_video_ms'],14000);self.assertFalse(evidence['exact_action_time_known'])
  self.assertEqual(evidence['action_time_window']['start_ms'],11000)
  self.assertTrue(evidence['action_time_window']['assumed_not_measured']);self.assertEqual(row['start_ms'],6000)
 def test_reference_excludes_earlier_action_even_when_click_is_late(self):
  row=dict(self.row(),start_ms=6000,end_ms=6000);facts=self.facts()
  facts['periods']['auto']['clock_samples']=[{'t':14,'remaining':14},{'t':15,'remaining':13}]
  aligned,reason=training.aligned_record(row,facts);self.assertIsNone(reason)
  self.assertTrue(training.reference_overlaps_label({'t':9.,'temporal_clip':{'start':8.,'end':11.}},aligned))
  self.assertFalse(training.reference_overlaps_label({'t':20.,'temporal_clip':{'start':18.,'end':22.}},aligned))
 def test_imported_clip_must_cover_reaction_window(self):
  row=self.row();facts=self.facts();src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'video.mp4'}}
  with patch('neptune_temporal.plan',return_value={'start':9.5,'end':13.5}):
   examples,skips=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=lambda *a:[1.]*512,temporal_required=True)
  self.assertFalse(examples);self.assertEqual(skips,{'external_reaction_window_not_covered':1})
 def test_reaction_allowance_stays_in_phase_and_leaves_human_labels_unchanged(self):
  row=self.row();aligned,reason=training.aligned_record(row,self.facts())
  self.assertEqual(aligned['action_time_window']['start_ms'],8000)
  human=dict(row,evidence_type='human_video_label',definition_version='legacy',time_basis='video_elapsed_ms')
  same,reason=training.aligned_record(human,self.facts())
  self.assertIs(same,human);self.assertNotIn('action_time_window',same)
if __name__=='__main__':unittest.main()
