import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_facts as facts
import neptune_games as games
import neptune_temporal as temporal
import neptune_yolo as yolo
import neptune_training as training

class Regressions(unittest.TestCase):
 def test_title_and_roster_ocr_miss_does_not_erase_valid_countdown(self):
  game=json.loads(games.BUILTIN.read_text())['seasons']['2026'];p=game['layout_profiles']['frc-2026-age-blue-left-v1'];r=p['regions']
  def token(text,region):
   a,b,c,d=r[region];return {'t':text,'x':a,'y':c,'w':b-a,'h':d-c,'c':1}
  # Title OCR typo and only one clean roster number per side. The clock and
  # broadcast marker are still visible in fixed, already-detected layout regions.
  items=[token('2:19','clock'),token('FIRST AGE','marker'),token('2712','blue_roster'),token('558','red_roster')]
  parsed=facts.parse_overlay(items,p);self.assertFalse(parsed['labels'])
  samples,_=facts.overlay_samples([(31,Path('/w/overlay/a.jpg'))],{'/w/overlay/a.jpg':items},p,game,Path('/w'))
  self.assertEqual(samples[0]['clock'],139)
  self.assertNotIn('red',samples[0]) # Clock context never invents an alliance score.
  for missing in ('marker','blue_roster'):
   reduced=[i for i in items if i!=token('FIRST AGE' if missing=='marker' else '2712',missing)]
   rows,_=facts.overlay_samples([(31,Path('/w/overlay/a.jpg'))],{'/w/overlay/a.jpg':reduced},p,game,Path('/w'))
   self.assertNotIn('clock',rows[0])
 def test_all_broadcast_panels_have_separate_bounds(self):
  p=json.loads(games.BUILTIN.read_text())['seasons']['2026']['layout_profiles']['frc-2026-age-blue-left-v1'];views=yolo.camera_views(p)
  self.assertEqual([v['name'] for v in views],['wide','closeup-left','closeup-right'])
  self.assertEqual(views[1]['bounds'],[0.,.67,.5,1.]);self.assertEqual(views[2]['bounds'],[.5,.67,1.,1.])
 def test_closeup_clip_cannot_include_other_panel_or_wide_camera_cut(self):
  pts=[{'team':1,'t':i/4,'box':[.44,.72,.05,.05],'scene':'closeup-left:0','track_id':2,'camera':'closeup-left','camera_bounds':[0,.67,.5,1.],'identity_method':'yolo_botsort_ocr'} for i in range(81)]
  f={'source':{'duration_s':180},'periods':{'auto':{'start':0,'end':20}},'tracking':{'band':[.12,.655],'localizations':pts,'scene_cuts':[9],'camera_cuts':{'wide':[9],'closeup-left':[]}}}
  clip=temporal.plan(f,pts[40]);self.assertTrue(all(x['box'][0]+x['box'][2]<=.5 and x['box'][1]>=.67 for x in clip['frames']))
  f['tracking']['camera_cuts']['closeup-left']=[9]
  with self.assertRaises(temporal.ClipUnavailable):temporal.plan(f,pts[40])
 def test_old_trial_facts_replay_immutable_localization_ocr_and_preserve_backup(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);sha='a'*64;fp='b'*64;trial=base/'trials'/sha/fp/'model'/'facts.json';trial.parent.mkdir(parents=True);trial.write_text('{}')
   original=base/'localizations'/sha/fp/'facts.json';original.parent.mkdir(parents=True);original.write_text('{}');(original.parent/'raw-overlay.jsonl').write_text('')
   with patch('neptune_facts.replay_alliance_layout',return_value={'pipeline':facts.PIPELINE_VERSION}) as replay:
    result=training.refresh_cached_facts(trial,{'pipeline':'old'},{},{'fingerprint':fp},sha)
   self.assertEqual(replay.call_args.args[0],original);self.assertEqual(result['pipeline'],facts.PIPELINE_VERSION)
   self.assertTrue((trial.parent/'facts-before-old.json').exists())
