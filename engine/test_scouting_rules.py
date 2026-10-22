import sys,unittest,copy
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent/'Neptune Detector Trial.app/Contents/Resources/engine'))
from neptune_scouting_rules import summarize,policy

def facts():
 return {'periods':{'teleop':{'start':0,'end':30,'clock_samples':[{'t':t,'remaining':30-t} for t in range(31)]}},'tracking':{'localizations':[{'team':1,'t':t,'box':[.1 if t<=6 else .2+(t-7)*.01,.2,.1,.1],'identity_method':'yolo_botsort_ocr','identity_segment':1,'camera':'wide','scene':0} for t in range(11)]}}
def absent(f):f['activity_assessments']=[{'team':1,'start_ms':0,'end_ms':6000,'assessment':'no_purposeful_activity','evidence_type':'human_review'}]
def keys(r):return [e['tag_key'] for e in r['events']]
class Rules(unittest.TestCase):
 def test_stationary_is_not_disabled(self):
  self.assertEqual(keys(summarize(facts(),[],'x')),['stationary'])
 def test_recovery_keeps_disabled_history(self):
  f=facts();absent(f);k=keys(summarize(f,[],'x'))
  self.assertCountEqual(k,['stationary','disabled','recovered','mechanical_issues'])
 def test_stationary_scoring_is_not_disabled(self):
  f=facts();absent(f)
  self.assertEqual(keys(summarize(f,[{'team':1,'tag_key':'scoring','start_ms':3000}],'x')),['stationary'])
 def test_tracking_loss_is_unknown(self):
  f=facts();f['tracking']['localizations']=[p for p in f['tracking']['localizations'] if p['t'] in [0,6,7,8]]
  self.assertEqual(keys(summarize(f,[],'x')),[])
 def test_frozen_clock_cannot_trigger_stationary(self):
  f=facts()
  for c in f['periods']['teleop']['clock_samples']:c['remaining']=30
  self.assertEqual(keys(summarize(f,[],'x')),[])
 def test_cut_cannot_prove_recovery(self):
  f=facts();absent(f)
  for p in f['tracking']['localizations']:
   if p['t']>6:p['scene']=1
  self.assertNotIn('recovered',keys(summarize(f,[],'x')))
 def test_visit_merge_and_measured_duration(self):
  tags=[{'team':1,'tag_key':k,'start_ms':t*1000} for k,t in [('scoring',1),('gb:score_1_fuel',2),('scoring',7),('gb:climb_lv_1',9)]]
  r=summarize(facts(),tags,'x')['robots'][0]
  self.assertEqual(r['scoring_visits'],2);self.assertEqual(r['observed_eligible_seconds'],10)
  self.assertEqual(r['observed_seconds_per_visit'],5);self.assertEqual(r['mean_cycle_seconds'],6)
 def test_no_scoring_no_divide_by_zero(self):
  r=summarize(facts(),[],'x')['robots'][0];self.assertIsNone(r['observed_seconds_per_visit'])
 def test_settings_validation(self):
  for v in [0,-1,float('nan'),True]:
   with self.assertRaises(ValueError):policy({'stationary_seconds':v})
 def test_autonomous_not_stationary_disabled(self):
  f=facts();f['periods']={'auto':f['periods']['teleop']}
  self.assertEqual(keys(summarize(f,[],'x')),[])
if __name__=='__main__':unittest.main()
