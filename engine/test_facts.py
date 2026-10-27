"""Regression tests for the facts pipeline: unknowns, outliers, identities, wrong matches, layouts, partial videos."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

import neptune_facts as nf
import neptune_learning as nl

RULES = nf.RULES['seasons']['2026']
PROFILE = nf.LAYOUTS['frc-2026-field-overlay-v1']
ROSTER = {'red': [6369, 2689, 127], 'blue': [9128, 11178, 5414]}


class OcrProgressTests(unittest.TestCase):
    def test_windows_ocr_reports_bounded_scoreboard_batches(self):
        class Reader:
            name='rapidocr'
            def __init__(self):self.calls=[]
            def recognize(self,paths):
                self.calls.append(list(paths))
                return {p:[] for p in paths}
        reader=Reader();stage=[''];updates=[]
        class Stage(list):
            def __setitem__(self,key,value):super().__setitem__(key,value);updates.append(value)
        stage=Stage([''])
        result=nf.recognize_with_progress(reader,list(range(35)),stage,'Reading the scoreboard')
        self.assertEqual([len(batch) for batch in reader.calls],[16,16,3])
        self.assertEqual(len(result),35)
        self.assertIn('frames 33–35 of 35',updates[-1])


def ev(t, text='0'):
    return {'t': t, 'frame': 'overlay/ov_%05d.jpg' % int(t), 'text': text, 'confidence': 1.0, 'box': [0, 0, 0, 0], 'correction': None}


def reading(t, v):
    return {'t': float(t), 'value': v, 'ev': ev(t, str(v))}


def item(text, cx, cy, w=0.05, h=0.08, c=1.0):
    return {'t': text, 'c': c, 'x': cx - w / 2, 'y': cy - h / 2, 'w': w, 'h': h}


def overlay_items(clock, red=None, blue=None, title='Qualification 7 of 90', roster=ROSTER, labels=True, marker=True, shift=None):
    items = [item(title, 0.5, 0.12, 0.18, 0.11), item(clock, 0.5, 0.64, 0.09, 0.21)]
    if red is not None:
        items.append(item(str(red), 0.38, 0.63, 0.07, 0.2))
    if blue is not None:
        items.append(item(str(blue), 0.62, 0.63, 0.07, 0.2))
    if labels:
        items += [item('RED', 0.38, 0.39), item('BLUE', 0.62, 0.39)]
    if marker:
        items.append(item('REBUILT', 0.92, 0.12, 0.15, 0.17))
    for k, team in enumerate(roster['red']):
        items.append(item(str(team), 0.07 + 0.1 * k, 0.38))
    for k, team in enumerate(roster['blue']):
        items.append(item(str(team), 0.75 + 0.1 * k, 0.38))
    if shift:
        items.append(item(shift, 0.5, 0.36, 0.1, 0.1))
    return items


def match_clock(auto_start=10.0, gap=4.0, end=None):
    """(t, clock text) for 1 fps samples of a full match: auto 0:20→0:01, a gap showing 2:20, teleop 2:20→0:00."""
    out = []
    for k in range(20):
        out.append((auto_start + k, '0:%02d' % (20 - k)))
    tele = auto_start + 20 + gap
    for k in range(int(gap)):
        out.append((auto_start + 20 + k, '2:20'))
    for k in range(141):
        c = 140 - k
        out.append((tele + k, '%d:%02d' % (c // 60, c % 60)))
    return [(t, c) for t, c in out if end is None or t <= end]


def samples_from(clock_pairs, scores=None):
    band = [(t, Path('/w/overlay/ov_%05d.jpg' % int(t))) for t, _ in clock_pairs]
    texts = {}
    for (t, c), (_, p) in zip(clock_pairs, band):
        r, b = (scores(t) if scores else (None, None))
        texts[str(p)] = overlay_items(c, r, b)
    return band, texts


def clock_seconds(text):
    m, s = text.split(':')
    return int(m) * 60 + int(s)


class ScoreTimelineTests(unittest.TestCase):
    def test_missing_score_is_unknown_not_zero(self):
        self.assertIsNone(nf.score_at([], 30.0))
        series = [reading(40, 12)]
        self.assertIsNone(nf.score_at(series, 30.0))          # nothing before t
        v = nf.value_at(series, 30.0, 1.0)
        self.assertEqual(v['status'], 'unknown')
        self.assertIsNone(v['value'])
        self.assertEqual(nf.difference(v, nf.value_at(series, 40.0, 1.0))['status'], 'unknown')

    def test_stale_reading_is_not_carried_forward(self):
        series = [reading(10, 50), reading(11, 52)]
        self.assertEqual(nf.score_at(series, 12.0)['value'], 52)
        self.assertIsNone(nf.score_at(series, 20.0))           # 9 s old: unknown
        cov = nf.coverage(series + [reading(30, 90)], 10, 30)
        self.assertEqual(cov['gaps'], [[14.0, 30.0]])
        self.assertLess(cov['share'], 0.5)

    def test_no_invented_runs_or_lead_changes_across_gaps(self):
        red = [reading(t, 10 + t) for t in range(0, 10)] + [reading(t, 200) for t in range(40, 50)]
        blue = [reading(t, 20 + t) for t in range(0, 10)] + [reading(t, 100) for t in range(40, 50)]
        lead = nf.lead_changes(red, blue, 0, 49)
        self.assertEqual(lead['unreadable_intervals'], [[11.0, 40.0]])   # fresh for 1.5 s after the last reading
        self.assertEqual(len(lead['changes']), 1)
        self.assertTrue(lead['changes'][0]['after_gap'])       # time of the change is not known
        self.assertIsNone(nf.largest_increase(red, 0, 49) and None)
        run = nf.largest_increase(red, 0, 49)
        self.assertTrue(run is None or run['value'] <= 15)     # the 10→40 s jump has no coverage

    def test_temporary_decrease_rejected_sustained_correction_kept(self):
        series = [reading(t, v) for t, v in enumerate([100, 104, 90, 108, 112])]
        acc, rej, dec = nf.filter_scores(series)
        self.assertEqual([r['value'] for r in acc], [100, 104, 108, 112])
        self.assertEqual(rej[0]['value'], 90)
        self.assertIn('not sustained', rej[0]['reason'])
        self.assertEqual(dec, [])
        series = [reading(t, v) for t, v in enumerate([100, 104, 99, 99, 101, 105])]
        acc, rej, dec = nf.filter_scores(series)
        self.assertEqual([r['value'] for r in acc], [100, 104, 99, 99, 101, 105])
        self.assertEqual([(d['from'], d['to']) for d in dec], [(104, 99)])

    def test_one_bad_high_reading_does_not_invalidate_the_match(self):
        series = [reading(t, 100 + 2 * t) for t in range(20)]
        series[5] = reading(5, 910)                            # 110 misread as 910
        acc, rej, _ = nf.filter_scores(series)
        self.assertEqual(len(acc), 19)
        self.assertEqual(rej[0]['value'], 910)
        self.assertIn('higher than the next accepted', rej[0]['reason'])
        series[19] = reading(19, 999)                          # a bad last reading
        acc, rej, _ = nf.filter_scores(series)
        self.assertEqual(acc[-1]['value'], 136)

    def test_boundary_change_is_uncertain(self):
        series = [reading(29, 117), reading(30, 119), reading(31, 120)]
        v = nf.value_at(series, 30.0, 1.0)
        self.assertEqual(v['status'], 'uncertain')
        self.assertEqual(v['range'], [117, 120])


class PhaseTests(unittest.TestCase):
    def periods(self, pairs, duration=200.0):
        samples = [{'t': t, 'clock': clock_seconds(c), 'frame': 'f', 'ev': ev(t, c)} for t, c in pairs]
        return nf.anchor_periods(samples, RULES, duration)

    def test_full_match(self):
        p, rejected = self.periods(match_clock(10.0))
        self.assertAlmostEqual(p['auto']['start'], 10.0, delta=1.0)
        self.assertAlmostEqual(p['teleop']['start'], 34.0, delta=1.0)
        self.assertEqual(p['teleop']['length_rule'], 140)
        self.assertTrue(p['auto']['start_observed'] and p['teleop']['end_observed'])

    def test_bad_first_reading_does_not_set_period_length(self):
        pairs = match_clock(10.0)
        pairs[0] = (10.0, '0:59')                              # misread first auto reading
        p, _ = self.periods(pairs)
        self.assertEqual(p['auto']['length_rule'], 20)
        self.assertAlmostEqual(p['auto']['end'], 30.0, delta=1.0)
        self.assertIn(10.0, [o['t'] for o in p['auto']['clock_outliers']])

    def test_clock_above_rule_length_never_sets_a_period(self):
        pairs = [(float(t), '2:59') for t in range(0, 6)] + match_clock(10.0)
        p, rejected = self.periods(pairs)
        self.assertEqual(p['auto']['length_rule'], 20)
        self.assertAlmostEqual(p['auto']['start'], 10.0, delta=1.0)
        self.assertEqual(len([o for o in p['auto']['clock_outliers'] if o['clock'] == 179]), 6)
        alone = [(float(t), '2:59') for t in range(0, 30)] + match_clock(40.0)
        p, rejected = self.periods(alone)
        self.assertTrue(rejected)                               # a frozen 2:59 never forms a countdown
        self.assertAlmostEqual(p['teleop']['start'], 64.0, delta=1.0)
        running = [(float(t), '%d:%02d' % ((179 - t) // 60, (179 - t) % 60)) for t in range(0, 30)] + match_clock(40.0)
        p, rejected = self.periods(running)                     # a 3:00 countdown is longer than any period
        self.assertTrue(any('teleop length' in r['reason'] for r in rejected))

    def test_two_transient_lows_then_recovery(self):
        series = [reading(t, v) for t, v in enumerate([100, 104, 108, 40, 112, 116, 120])]
        acc, rej, dec = nf.filter_scores(series)
        self.assertEqual([r['value'] for r in rej], [40])
        self.assertEqual(dec, [])

    def test_partial_video_starting_in_teleop(self):
        pairs = [(t, c) for t, c in match_clock(10.0) if t >= 100]
        p, _ = self.periods(pairs)
        self.assertIsNone(p['auto'])
        self.assertFalse(p['teleop']['start_observed'])
        self.assertTrue(p['teleop']['end_observed'])

    def test_partial_video_ending_early(self):
        p, _ = self.periods(match_clock(10.0, end=120), duration=121)
        self.assertFalse(p['teleop']['end_observed'])

    def test_short_countdown_without_teleop_is_not_auto(self):
        pairs = [(t, c) for t, c in match_clock(10.0) if t >= 160]  # last 15 s of teleop only
        with self.assertRaises(nf.FactsError):
            self.periods(pairs)

    def test_unknown_season_fails_clearly(self):
        with self.assertRaisesRegex(nf.FactsError, '2031 game is not configured'):
            nf.season_rules('2031txcmp2_qm7')

    def test_endgame_corroborated_by_shift_indicator(self):
        p, _ = self.periods(match_clock(10.0))
        samples = [{'t': p['teleop']['end'] - 30 + k, 'shift': {'shift': 6, 'of': 6, 'seconds_left': 30 - k}} for k in range(0, 30)]
        eg = nf.endgame_boundary(p, samples, RULES)
        self.assertEqual(eg['status'], 'corroborated')
        samples = [dict(s, t=s['t'] + 6) for s in samples]
        self.assertEqual(nf.endgame_boundary(p, samples, RULES)['status'], 'uncertain')


class LayoutAndIdentityTests(unittest.TestCase):
    def test_week0_layout_needs_title_both_rosters_and_season_marker(self):
        profile=RULES['layout_profiles']['frc-2026-week0-overlay-v1']
        items=[item('Qualification 1 of 15',.5,.12),item('REBUILT',.72,.12),item('0:17',.5,.30)]
        items += [item(str(n),x,.31) for n,x in [(88,.27),(501,.33),(3566,.39),(1768,.63),(5962,.69),(190,.75)]]
        frames=[(float(t),Path('/w/ov%d.jpg'%t)) for t in range(25)]
        texts={str(p):items for _,p in frames}
        result=nf.detect_layout(frames,texts,2026,{'week0':profile})
        self.assertEqual(result[0],'week0')
        with self.assertRaises(nf.FactsError):nf.detect_layout(frames,{str(p):[i for i in items if i['t']!='REBUILT'] for _,p in frames},2026,{'week0':profile})
        self.assertFalse(nf.parse_overlay([i for i in items if i['t'] not in ('5962','190')],profile)['labels'])

    def test_layout_with_alliances_on_the_other_sides_is_skipped(self):
        # Week 0 (red left) and AGE (blue left) share one geometry; the roster decides which one this video is.
        rules=RULES['layout_profiles'];layouts={k:rules[k] for k in ('frc-2026-week0-overlay-v1','frc-2026-age-blue-left-v1')}
        items=[item('Qualification 1 of 15',.5,.12),item('REBUILT',.72,.12),item('FIRST AGE',.28,.12),item('0:17',.5,.30)]
        items += [item(str(n),x,.31) for n,x in [(88,.27),(501,.33),(3566,.39),(1768,.63),(5962,.69),(190,.75)]]
        frames=[(float(t),Path('/w/ov%d.jpg'%t)) for t in range(25)]
        texts={str(p):items for _,p in frames}
        self.assertEqual(nf.detect_layout(frames,texts,2026,layouts)[0],'frc-2026-week0-overlay-v1')
        pid,_,stats=nf.detect_layout(frames,texts,2026,layouts,{'red':[1768,5962,190],'blue':[88,501,3566]})
        self.assertEqual((pid,stats['roster_numbers_on_other_side']),('frc-2026-age-blue-left-v1',0))
        with self.assertRaises(nf.FactsError) as error:
            nf.detect_layout(frames,texts,2026,{'w':layouts['frc-2026-week0-overlay-v1']},{'red':[1768,5962,190],'blue':[88,501,3566]})
        self.assertIn('other sides',str(error.exception))

    def test_joined_roster_numbers_are_split(self):
        profile=RULES['layout_profiles']['frc-2026-week0-overlay-v1']
        items=[item('Qualification 1 of 15',.5,.12),item('REBUILT',.72,.12),item('0:17',.5,.30),item('88 501 3566',.33,.31),item('1768 5962 190',.69,.31)]
        r=nf.parse_overlay(items,profile)
        self.assertTrue(r['labels'])
        self.assertEqual([i['t'] for i in r['roster']['red']],['88','501','3566'])

    def test_supported_layout_detected(self):
        band, texts = samples_from(match_clock(10.0), lambda t: (int(t), int(t)))
        pid, profile, stats = nf.detect_layout(band, texts, 2026)
        self.assertEqual(pid, 'frc-2026-field-overlay-v1')

    def test_unsupported_layout_fails_clearly(self):
        band = [(float(t), Path('/w/overlay/ov_%05d.jpg' % t)) for t in range(60)]
        texts = {str(p): [item('1:%02d' % (59 - int(t)), 0.1, 0.9), item('HOME', 0.2, 0.2)] for t, p in band}
        with self.assertRaisesRegex(nf.FactsError, 'Unsupported broadcast layout'):
            nf.detect_layout(band, texts, 2026)
        band, texts = samples_from(match_clock(10.0))
        texts = {k: [i for i in v if i['t'] != 'REBUILT'] for k, v in texts.items()}
        with self.assertRaisesRegex(nf.FactsError, 'Unsupported broadcast layout'):
            nf.detect_layout(band, texts, 2026)

    def test_layout_from_another_season_rejected(self):
        band, texts = samples_from(match_clock(10.0))
        with self.assertRaisesRegex(nf.FactsError, 'Wrong video or season'):
            nf.detect_layout(band, texts, 2027)

    def identity(self, claim, video_title='Qualification 7 - FIRST In Texas District Championship - Apollo Division - qm7'):
        band, texts = samples_from(match_clock(10.0), lambda t: (1, 1))
        samples, _ = nf.overlay_samples(band, texts, PROFILE, RULES, Path('/w'))
        return nf.verify_identity(samples, claim, video_title, None)

    def claim(self, **kw):
        c = {'key': '2026txcmp2_qm7', 'title': 'FIRST In Texas District Championship - Apollo Division · Qualification 7', 'roster': ROSTER}
        c.update(kw)
        return c

    def test_true_match_verified(self):
        self.assertEqual(self.identity(self.claim())['status'], 'verified')

    def test_wrong_match_number_rejected(self):
        with self.assertRaisesRegex(nf.FactsError, 'does not match 2026txcmp2_qm8'):
            self.identity(self.claim(key='2026txcmp2_qm8'))

    def test_same_number_other_event_rejected_by_roster(self):
        with self.assertRaisesRegex(nf.FactsError, 'roster'):
            self.identity(self.claim(key='2026txfar_qm7', title='FIT District Farmersville Event · Qualification 7',
                                     roster={'red': [10340, 5431, 9492], 'blue': [2582, 9105, 9034]}))

    def test_other_division_in_video_title_rejected(self):
        with self.assertRaisesRegex(nf.FactsError, 'video title'):
            self.identity(self.claim(), 'Qualification 7 - FIRST In Texas District Championship - Mercury Division - qm7')

    def test_missing_event_evidence_stays_incomplete(self):
        v = self.identity(self.claim(), None)
        self.assertEqual(v['status'], 'incomplete')
        self.assertEqual(v['missing'], ['event'])


class BumperTests(unittest.TestCase):
    teams = set(ROSTER['red'] + ROSTER['blue'])

    def test_exact_corrected_ambiguous(self):
        self.assertEqual(nf.roster_match('6369', self.teams), ('exact', 6369, None))
        kind, team, why = nf.roster_match('63G9', self.teams) or (None, None, None)
        self.assertIsNone(kind)                                  # G is not a known lookalike
        kind, team, why = nf.roster_match('2G89', {2689}) or (None, None, None)
        self.assertIsNone(kind)
        self.assertEqual(nf.roster_match('5414', self.teams)[0], 'exact')
        k, t, why = nf.roster_match('S414', self.teams)
        self.assertEqual((k, t), ('corrected', 5414))
        self.assertIn('S→5', why)
        k, t, why = nf.roster_match('9129', self.teams)
        self.assertEqual((k, t), ('corrected', 9128))
        self.assertEqual(nf.roster_match('1118', {11178, 11188})[0], 'ambiguous')
        self.assertIsNone(nf.roster_match('128', self.teams))    # too short to correct

    def raw(self, team, t, kind='exact', background=None, alliance=None):
        a = alliance or ('red' if team in ROSTER['red'] else 'blue')
        return {'t': t, 'team': team, 'kind': kind, 'background': background or a, 'alliance': a, 'confidence': 1.0, 'frame': 'bumpers/k3_%05d.jpg' % int(t)}

    def test_overlapping_crops_of_one_frame_are_one_observation(self):
        reads = [self.raw(127, 20.0), self.raw(127, 20.0), self.raw(127, 20.0)]
        ids = nf.decide_identities(reads, ROSTER)
        self.assertEqual(ids[127]['status'], 'candidate')
        ids = nf.decide_identities(reads + [self.raw(127, 22.0)], ROSTER)
        self.assertEqual(ids[127]['status'], 'confirmed')

    def test_corrected_reads_never_confirm(self):
        reads = [self.raw(9128, t, kind='corrected') for t in (10.0, 12.0, 14.0, 16.0)]
        self.assertEqual(nf.decide_identities(reads, ROSTER)[9128]['status'], 'candidate')

    def test_number_on_the_wrong_colour_is_rejected(self):
        # e.g. a queued or spectator item showing a roster number on the other alliance colour
        reads = [self.raw(6369, t, background='blue') for t in (10.0, 12.0)]
        ids = nf.decide_identities(reads, ROSTER)
        self.assertEqual(ids[6369]['status'], 'not_identified')

    def test_queued_robot_near_miss_stays_candidate(self):
        # Queued team 2683 read next to the field: one character from 2689, so only a candidate.
        k, t, why = nf.roster_match('2683', self.teams)
        self.assertEqual((k, t), ('corrected', 2689))
        reads = [self.raw(2689, s, kind='corrected', background='unclear') for s in (30.0, 32.0, 34.0)]
        self.assertEqual(nf.decide_identities(reads, ROSTER)[2689]['status'], 'candidate')

    def test_wide_shot_only_reads_stay_candidates(self):
        # Driver-station number displays appear only in the wide field shot; a close-up read is required.
        wide = [dict(self.raw(6369, t), frame_box=[0.28, 0.35, 0.05, 0.05]) for t in (24.0, 26.0, 28.0)]
        ids = nf.decide_identities(wide, ROSTER, closeup_top=0.56)
        self.assertEqual(ids[6369]['status'], 'candidate')
        self.assertIn('wide field shot', ' '.join(ids[6369]['reasons']))
        close = dict(self.raw(6369, 60.0), frame_box=[0.2, 0.8, 0.05, 0.05])
        ids = nf.decide_identities(wide + [close], ROSTER, closeup_top=0.56)
        self.assertEqual(ids[6369]['status'], 'confirmed')
        self.assertIn(60.0, [e['t'] for e in ids[6369]['evidence']])   # close-up evidence always included

    def test_unclear_colour_does_not_confirm(self):
        reads = [self.raw(5414, t, background='unclear') for t in (10.0, 12.0, 14.0)]
        self.assertEqual(nf.decide_identities(reads, ROSTER)[5414]['status'], 'candidate')

    def test_background_colour(self):
        w, h = 20, 10
        red = bytes([200, 30, 30] * (w * h))
        self.assertEqual(nf.background_colour((w, h, red), [0.3, 0.3, 0.4, 0.4])[0], 'red')
        navy = bytes([30, 35, 75] * (w * h))
        self.assertEqual(nf.background_colour((w, h, navy), [0.3, 0.3, 0.4, 0.4])[0], 'blue')
        grey = bytes([120, 120, 120] * (w * h))
        self.assertEqual(nf.background_colour((w, h, grey), [0.3, 0.3, 0.4, 0.4])[0], 'unclear')


class FrameExtractionTests(unittest.TestCase):
    @unittest.skipUnless(__import__('shutil').which('ffmpeg'), 'ffmpeg missing')
    def test_colour_sample_does_not_change_the_ocr_tiles(self):
        """The colour branch must not alter the JPEG tiles the text reader sees (facts-3 regression)."""
        import hashlib
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-t', '5', '-pix_fmt', 'yuv420p', str(d / 'v.mp4')], check=True)
            nf.bumper_frames(d / 'v.mp4', d / 'with', 0.24, 0.0, 4.0, 2.0)
            plain = d / 'plain'
            plain.mkdir()
            vf = 'fps=0.5:round=up,crop=iw:ih*%g:0:ih*%g,crop=iw*%g:ih*%g:iw*%g:ih*%g,scale=2*trunc(iw):-2' % ((0.76, 0.24) + (nf.TILES[3][1] - nf.TILES[3][0], nf.TILES[3][3] - nf.TILES[3][2], nf.TILES[3][0], nf.TILES[3][2]))
            subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0', '-t', '4', '-i', str(d / 'v.mp4'), '-vf', vf, '-q:v', '3', str(plain / 'k3_%05d.jpg')], check=True)
            md5 = lambda p: hashlib.md5(p.read_bytes()).hexdigest()
            with_tiles = sorted((d / 'with' / 'bumpers').glob('k3_*.jpg'))
            plain_tiles = sorted(plain.glob('k3_*.jpg'))
            self.assertTrue(with_tiles)
            self.assertEqual([md5(p) for p in with_tiles], [md5(p) for p in plain_tiles])
            self.assertTrue(list((d / 'with' / 'bumpers').glob('c_*.ppm')))


class ResultsScreenTests(unittest.TestCase):
    def screen(self, live_clock=False, penalty_red='5'):
        items = [item('WINNER', 0.18, 0.2), item('RED', 0.41, 0.13, 0.04, 0.034), item('BLUE', 0.59, 0.13, 0.05, 0.034),
                 item('542', 0.405, 0.23, 0.11, 0.09), item('414', 0.59, 0.23, 0.11, 0.09),
                 item('AUTO', 0.5, 0.32, 0.05, 0.03), item('FUEL', 0.5, 0.37, 0.05, 0.03), item('TOWER', 0.5, 0.42, 0.07, 0.03),
                 item('TELEOP', 0.5, 0.47, 0.07, 0.03), item('FUEL', 0.5, 0.52, 0.05, 0.03), item('TOWER', 0.5, 0.57, 0.07, 0.03),
                 item('PENALTY', 0.5, 0.62, 0.08, 0.03),
                 item('104', 0.35, 0.37, 0.05, 0.044), item('15', 0.35, 0.42, 0.03, 0.044), item('418', 0.35, 0.52, 0.05, 0.044),
                 item('0', 0.35, 0.57, 0.02, 0.044), item(penalty_red, 0.35, 0.62, 0.02, 0.044),
                 item('105', 0.65, 0.37, 0.05, 0.044), item('0', 0.65, 0.42, 0.02, 0.044), item('294', 0.65, 0.52, 0.05, 0.044),
                 item('0', 0.65, 0.57, 0.02, 0.044), item('15', 0.65, 0.62, 0.03, 0.044),
                 item('5414', 0.76, 0.62, 0.05, 0.034), item('22', 0.92, 0.62, 0.03, 0.034)]
        if live_clock:
            items.append(item('0:00', 0.5, 0.1, 0.09, 0.2))
        return items

    def test_breakdown_and_checksum(self):
        frames = [(200.0, Path('/w/results/rs_00001.jpg')), (201.0, Path('/w/results/rs_00002.jpg'))]
        texts = {str(p): self.screen() for _, p in frames}
        r = nf.read_results_screen(frames, texts, RULES, Path('/w'))
        self.assertEqual((r['red'], r['blue'], r['status'], r['checksum_ok']), (542, 414, 'accepted', True))
        self.assertEqual(r['components']['blue']['penalty']['value'], 15)   # not the team number 5414 on that row

    def test_live_overlay_after_buzzer_is_not_the_results_screen(self):
        self.assertIsNone(nf.parse_results(self.screen(live_clock=True), RULES))

    def test_single_frame_and_bad_arithmetic_stay_uncertain(self):
        frames = [(200.0, Path('/w/results/rs_00001.jpg'))]
        r = nf.read_results_screen(frames, {str(frames[0][1]): self.screen()}, RULES, Path('/w'))
        self.assertEqual(r['status'], 'uncertain')
        frames = [(200.0, Path('/w/results/rs_00001.jpg')), (201.0, Path('/w/results/rs_00002.jpg'))]
        r = nf.read_results_screen(frames, {str(p): self.screen(penalty_red='9') for _, p in frames}, RULES, Path('/w'))
        self.assertEqual((r['status'], r['checksum_ok']), ('uncertain', False))

    def test_missing_component_is_unknown_not_guessed(self):
        frames = [(200.0, Path('/w/results/rs_00001.jpg')), (201.0, Path('/w/results/rs_00002.jpg'))]
        texts = {str(p): [i for i in self.screen() if not (i['t'] == '0' and i['x'] > 0.6)] for _, p in frames}
        r = nf.read_results_screen(frames, texts, RULES, Path('/w'))
        self.assertIsNone(r['checksum_ok'])
        self.assertIn('auto tower', r['missing_components']['blue'])
        self.assertNotIn('auto tower', r['components']['blue'])


def facts_fixture(readable=1.0, confirmed=(6369,), candidates=(9128,)):
    ids = {t: {'status': 'confirmed' if t in confirmed else 'candidate' if t in candidates else 'not_identified', 'alliance': 'red' if t in ROSTER['red'] else 'blue',
               'verified_frames': [40.0, 42.0] if t in confirmed else [], 'evidence': [dict(ev(40.0, str(t)), kind='exact')], 'reasons': ['only 1 frame'] if t in candidates else [],
               'exact_reads': 1, 'corrected_reads': 0}
           for t in ROSTER['red'] + ROSTER['blue']}
    acc = lambda v: {'value': v, 'status': 'accepted', 'evidence': [ev(30.0, str(v))]}
    return {'pipeline': 'facts-2', 'season': 2026, 'ocr': {'backend': 'test', 'version': '1'},
            'identity': {'status': 'verified', 'missing': [], 'checks': {'match_number': {'status': 'match', 'overlay_title': 'Qualification 7'}, 'roster': {'status': 'match'}, 'event': {'status': 'match'}}},
            'periods': {'auto': {'start': 10.0, 'end': 30.0, 'uncertainty_s': 1.0, 'start_observed': True, 'end_observed': True, 'clock_readings': 20, 'length_rule': 20},
                        'teleop': {'start': 34.0, 'end': 174.0, 'uncertainty_s': 1.0, 'start_observed': True, 'end_observed': True, 'clock_readings': 140, 'length_rule': 140}},
            'endgame': {'start': 144.0, 'end': 174.0, 'uncertainty_s': 1.0, 'rule': 'last 30 s', 'status': 'corroborated'},
            'displayed': {s: {'at_teleop_start': acc(100), 'at_endgame_start': acc(300), 'at_teleop_end': acc(400), 'last_live': acc(400),
                              'teleop_increase_before_endgame': acc(200), 'endgame_increase': acc(100), 'largest_15s_increase': None} for s in ('red', 'blue')},
            'lead': {'changes': [], 'unreadable_intervals': [] if readable == 1.0 else [[60.0, 90.0]], 'readable_share': readable},
            'score_decreases': {'red': [], 'blue': []}, 'coverage': {s: {'share': readable, 'gaps': [] if readable == 1.0 else [[60.0, 90.0]]} for s in ('red', 'blue')},
            'results_screen': {'status': 'unknown'}, 'bumpers': {'identities': ids}}


class SummaryTests(unittest.TestCase):
    def test_no_lead_changes_wording_depends_on_coverage(self):
        self.assertIn('scores were readable throughout', nf.summarize(facts_fixture(1.0), ROSTER))
        s = nf.summarize(facts_fixture(0.8), ROSTER)
        self.assertIn('No lead changes were detected in the readable samples', s)
        self.assertNotIn('There were no lead changes', s)

    def test_candidates_never_appear_as_confirmed(self):
        s = nf.summarize(facts_fixture(), ROSTER)
        self.assertIn('Robots confirmed by bumper number on camera: 6369.', s)
        self.assertIn('Not confirmed on camera: 2689, 127, 9128, 11178, 5414.', s)

    def test_unknown_final_score_is_stated(self):
        self.assertIn('final score is unknown', nf.summarize(facts_fixture(), ROSTER))

    def test_no_penalty_explanation_for_live_vs_final(self):
        f = facts_fixture()
        f['results_screen'] = {'status': 'accepted', 'red': 410, 'blue': 400, 'components': None, 'checksum_ok': None, 'frames_agreeing': 3, 'evidence': [ev(200.0)] * 2}
        f['reconciliation'] = {'red': {'difference': 10}, 'blue': {'difference': 0}}
        s = nf.summarize(f, ROSTER)
        self.assertIn('does not determine why', s)
        self.assertNotIn('penalt', s.lower())

    def test_payload_marks_candidates_uncertain(self):
        match = {'roster': ROSTER}
        p = nf.build_payload(facts_fixture(), match, 'a' * 64, 220000)
        cand = [o for o in p['observations'] if o['team'] == 9128]
        self.assertTrue(cand and all(o['certainty'] == 'uncertain' for o in cand))
        self.assertTrue(all(o['team'] is None or o['team'] in ROSTER['red'] + ROSTER['blue'] for o in p['observations']))


class LearningDataTests(unittest.TestCase):
    def bundle(self, root):
        b = Path(root) / 'run'
        (b / 'bumpers').mkdir(parents=True)
        (b / 'bumpers' / 'k3_00001.jpg').write_bytes(b'jpeg')
        (b / 'raw-bumpers.jsonl').write_text('{}\n')
        f = facts_fixture()
        f['bumpers']['reads'] = [{'t': 40.0, 'frame': 'bumpers/k3_00001.jpg', 'token': '6369', 'kind': 'exact', 'team': 6369}]
        f['bumpers']['identities'][6369]['evidence'] = [{'t': 40.0, 'frame': 'bumpers/k3_00001.jpg'}]
        for t in f['bumpers']['identities']:
            f['bumpers']['identities'][t]['evidence'] = [{'t': 40.0, 'frame': 'bumpers/k3_00001.jpg'}]
        f['rejected'] = {'score_readings': {'red': [], 'blue': []}}
        f['accepted_scores'] = {'red': [], 'blue': []}
        f['layout'] = {'profile': 'frc-2026-field-overlay-v1'}
        payload = {'source_sha256': 'a' * 64, 'summary': 'Draft summary.', 'observations': [{'note': 'x'}]}
        nl.seal(b, f, payload, {'key': '2026txcmp2_qm7', 'roster': ROSTER})
        return b

    def test_originals_sealed_and_corrections_separate(self):
        with tempfile.TemporaryDirectory() as d:
            b = self.bundle(d)
            self.assertFalse(os.stat(b / 'facts.json').st_mode & stat.S_IWUSR)
            before = (b / 'facts.json').read_bytes()
            nl.add_correction(b, 'identity', {'team': 9128}, 'correct', 'Reviewer A')
            nl.add_correction(b, 'summary', {}, 'corrected', 'Reviewer A', corrected='Better summary.')
            self.assertEqual((b / 'facts.json').read_bytes(), before)
            self.assertEqual(nl.verify(b), [])
            self.assertEqual(nl.review_status(b), 'partially_reviewed')
            with self.assertRaises(ValueError):
                nl.add_correction(b, 'identity', {'team': 1}, 'correct', 'Reviewer A')
            with self.assertRaises(FileExistsError):
                nl.seal(b, {}, {}, {})
            nl.mark_reviewed(b, 'Reviewer A')
            self.assertEqual(nl.review_status(b), 'reviewed')

    def test_export_distinguishes_reviewed_from_unreviewed(self):
        with tempfile.TemporaryDirectory() as d:
            b = self.bundle(d)
            nl.add_correction(b, 'identity', {'team': 9128}, 'incorrect', 'Reviewer A', note='not a robot')
            out = Path(d) / 'export'
            nl.export([b], out, {'2026txcmp2_qm7': 'heldout'})
            rows = [json.loads(l) for l in (out / 'identities.jsonl').read_text().splitlines()]
            by_team = {r['team']: r for r in rows}
            self.assertEqual(by_team[9128]['label_status'], 'reviewed')
            self.assertEqual(by_team[9128]['verdict'], 'incorrect')
            self.assertEqual(by_team[6369]['label_status'], 'unreviewed')
            self.assertEqual(by_team[6369]['split'], 'heldout')
            self.assertIn('parser_sha256', by_team[6369]['versions'])
            self.assertTrue((out / by_team[6369]['images'][0]).is_file())
            drafts = [json.loads(l) for l in (out / 'drafts.jsonl').read_text().splitlines()]
            self.assertEqual(drafts[0]['original_summary'], 'Draft summary.')


if __name__ == '__main__':
    unittest.main()
