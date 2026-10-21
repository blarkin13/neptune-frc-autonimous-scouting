import unittest
from unittest.mock import patch
from pathlib import Path
import neptune_clock as clock
import neptune_events as events
import neptune_training as training
import neptune_tracking as tracking
from test_external_scouting import OutsideScouting


class ClockAlignment(unittest.TestCase):
    def test_local_clock_join_and_replay_ambiguity(self):
        p={'clock_samples':[{'t':10,'remaining':19},{'t':12,'remaining':17}]}
        self.assertEqual(clock.align(p,2000,20)['video_ms'],11000)
        p['clock_samples'] += [{'t':100,'remaining':19},{'t':102,'remaining':17}]
        self.assertEqual(clock.align(p,2000,20)['status'],'ambiguous')
    def test_freeze_jump_and_legacy_nominal_start_are_not_alignment(self):
        p={'start':8,'end':28,'start_observed':True,'end_observed':True}
        self.assertNotEqual(clock.align(p,2000,20)['status'],'aligned')
        p['clock_samples']=[{'t':10,'remaining':18},{'t':18,'remaining':18}]
        self.assertEqual(clock.align(p,2000,20)['reason'],'clock_repeated_or_frozen')
        p['clock_samples']=[{'t':10,'remaining':19},{'t':25,'remaining':17}]
        self.assertNotEqual(clock.align(p,2000,20)['status'],'aligned')
    def test_positive_and_unlabelled_pool_use_identical_import_join(self):
        fixture=OutsideScouting();row=fixture.row();facts=fixture.facts()
        source={row['video_id']:{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'unused.mp4'}}
        extract=lambda *args:[0.]*1296
        positives,_=training.labeled_examples([row],{row['video_id']:facts},source,Path('/unused'),extractor=extract)
        refs=training.unlabeled_examples([row],{row['video_id']:facts},source,Path('/unused'),extractor=extract)
        self.assertEqual(len(positives),1)
        self.assertEqual(refs,[]) # video 10s is the positive, not source-clock 2s
        facts['periods']['auto']['clock_samples']=[]
        self.assertEqual(training.unlabeled_examples([row],{row['video_id']:facts},source,Path('/unused'),extractor=extract),[])


class Episodes(unittest.TestCase):
    def facts(self):
        return {'rules':{'endgame':{'seconds':30}},'periods':{'auto':{'start':5,'end':25},'teleop':{'start':30,'end':170}}}
    def rows(self,tag,times,scores=None):
        return [dict(team=1,tag_key=tag,t=t,score=(scores[i] if scores else .9),threshold=.5,identity_evidence='frame') for i,t in enumerate(times)]
    def test_sustained_activity_is_one_candidate_not_a_tag_every_four_seconds(self):
        out=events.decode(self.rows('scoring',range(30,100)),self.facts(),'id')
        self.assertEqual(len(out),1);self.assertEqual(out[0]['certainty'],'uncertain')
    def test_two_crops_of_one_moment_do_not_supply_temporal_support(self):
        self.assertEqual(events.decode(self.rows('scoring',[30,30,30.1]),self.facts(),'id'),[])
    def test_observed_quiet_rearms_but_missing_footage_does_not(self):
        rows=self.rows('scoring',[30,31,50,51,52,53,54,55],[.9,.9,.9,.9,.1,.1,.9,.9])
        self.assertEqual(len(events.decode(rows,self.facts(),'id')),2)
    def test_autonomous_outcomes_never_occur_in_teleop_and_are_once_per_phase(self):
        rows=self.rows('auto_partial',[6,7,10,11,12,13,40,41],[.8,.8,.1,.1,.8,.8,.9,.9])
        out=events.decode(rows,self.facts(),'id')
        self.assertEqual(len(out),1);self.assertLess(out[0]['start_ms'],25000)
    def test_successful_climb_is_candidate_in_correct_window_and_not_observed_points(self):
        rows=self.rows('end_completed',[50,51,150,151,155,156])
        out=events.decode(rows,self.facts(),'id')
        self.assertEqual(len(out),1);self.assertGreaterEqual(out[0]['start_ms'],140000)
        self.assertEqual(out[0]['assessment'],'candidate_requires_video_confirmation')
    def test_isolated_disabled_sighting_is_not_a_disabled_event(self):
        self.assertEqual(events.decode(self.rows('disabled',[105]),self.facts(),'id'),[])
    def test_feeding_motion_is_not_verified_scoring(self):
        out=events.decode(self.rows('scoring',[30,31]),self.facts(),'id')
        self.assertEqual(out[0]['certainty'],'uncertain')
        self.assertNotIn('robot_points',out[0]) # classifier cannot certify transferred fuel as points


class IdentitySafety(unittest.TestCase):
    def detection(self,x):return dict(colour='red',cx=x,cy=20,x0=x-5,x1=x+5,y0=17,y1=20,n=20)
    def test_scene_cut_breaks_identity_continuity(self):
        frames=[(i,[self.detection(20)]) for i in range(6)]
        tr=tracking.link(frames,1,min_len=2,scene_cuts=[3])
        self.assertEqual(len(tr),2);self.assertNotEqual(tr[0]['scene'],tr[1]['scene'])
        inherited=tracking.extend_identities(tr,{tr[0]['id']:{'team':1,'votes':3,'other_votes':0}})
        self.assertNotIn(tr[1]['id'],inherited)
    def test_same_colour_crossing_does_not_greedily_transfer_identity(self):
        frames=[(0,[self.detection(10),self.detection(30)]),(1,[self.detection(20)])]
        tr=tracking.link(frames,1,min_len=1)
        self.assertEqual(len(tr),3) # ambiguous middle detection starts an unassigned track


if __name__=='__main__':unittest.main()
