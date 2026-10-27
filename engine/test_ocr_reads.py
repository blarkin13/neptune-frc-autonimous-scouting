import json
import tempfile
import unittest
from pathlib import Path

import neptune_facts
import neptune_games
import neptune_ocr

ROSTER = {'red': [9492, 10340, 5417], 'blue': [9444, 6377, 4734]}


def item(t, x=0.3, y=0.4, w=0.3, h=0.2, c=0.9):
    return {'t': t, 'c': c, 'x': x, 'y': y, 'w': w, 'h': h}


class ReadTeam(unittest.TestCase):
    def test_exact(self):
        r = neptune_ocr.read_team([item('9492')], ROSTER, 'red')
        self.assertEqual((r['team'], r['kind']), (9492, 'exact'))

    def test_split_pieces_join_exactly(self):
        r = neptune_ocr.read_team([item('94 4 4')], ROSTER, 'blue')
        self.assertEqual((r['team'], r['kind']), (9444, 'exact'))
        r = neptune_ocr.read_team([item('10', x=0.2, w=0.1), item('340', x=0.32, w=0.15)], ROSTER, 'red')
        self.assertEqual((r['team'], r['kind']), (10340, 'exact'))

    def test_number_printed_twice(self):
        r = neptune_ocr.read_team([item('47344734')], ROSTER, 'blue')
        self.assertEqual((r['team'], r['kind']), (4734, 'exact'))

    def test_lookalike_and_one_digit_are_corrected_within_alliance(self):
        r = neptune_ocr.read_team([item('S417')], ROSTER, 'red')
        self.assertEqual((r['team'], r['kind']), (5417, 'corrected'))
        r = neptune_ocr.read_team([item('6371')], ROSTER, 'blue')
        self.assertEqual((r['team'], r['kind']), (6377, 'corrected'))

    def test_short_or_foreign_reads_give_nothing(self):
        self.assertIsNone(neptune_ocr.read_team([item('94')], ROSTER, 'blue'))
        self.assertIsNone(neptune_ocr.read_team([item('1234')], ROSTER, 'red'))
        self.assertIsNone(neptune_ocr.read_team([item('FIRST')], ROSTER, 'red'))
        self.assertIsNone(neptune_ocr.read_team([], ROSTER, 'red'))

    def test_two_teams_is_ambiguous(self):
        r = neptune_ocr.read_team([item('9492', x=0.1), item('9444', x=0.6, y=0.0)], ROSTER, 'red')
        self.assertEqual(r['kind'], 'ambiguous')
        self.assertIsNone(r['team'])

    def test_read_off_the_bumper_is_ignored(self):
        inner = (0.2, 0.5, 0.8, 0.8)
        self.assertIsNone(neptune_ocr.read_team([item('9492', x=0.85, y=0.0, w=0.14, h=0.1)], ROSTER, 'red', inner))
        self.assertEqual(neptune_ocr.read_team([item('9492', x=0.3, y=0.55, w=0.3, h=0.2)], ROSTER, 'red', inner)['team'], 9492)

    def test_three_digit_teams_only_exact(self):
        roster = {'red': [716, 1099, 4909], 'blue': [228, 7127, 2785]}
        self.assertEqual(neptune_ocr.read_team([item('716')], roster, 'red')['team'], 716)
        self.assertIsNone(neptune_ocr.read_team([item('71')], roster, 'red'))


class BumperWindow(unittest.TestCase):
    def test_window_enlarges_small_strips_and_keeps_bounds(self):
        (x0, y0, x1, y1), scale, inner = neptune_ocr.bumper_window((100, 200, 80, 24), 1920, 1080)
        self.assertEqual(scale, 4)
        self.assertTrue(x0 < 100 and x1 > 180 and y0 < 200 and y1 > 224)
        self.assertTrue(0 < inner[0] < inner[2] < 1 and 0 < inner[1] < inner[3] < 1)
        (x0, y0, x1, y1), scale, _ = neptune_ocr.bumper_window((0, 1000, 200, 200), 1920, 1080)
        self.assertEqual((x0, y1, scale), (0, 1080, 1))


class WhiteRows(unittest.TestCase):
    def test_white_digits_turn_dark_and_fabric_light(self):
        red, white = bytes([30, 30, 220]), bytes([240, 245, 250])
        self.assertEqual(neptune_ocr.white_rows([red + white]), [bytes([225] * 3 + [15] * 3)])


class GenericOverlay(unittest.TestCase):
    def test_blue_left_overlay_sides_from_roster(self):
        roster = {'red': [1148, 6764, 9772], 'blue': [5025, 10147, 2584]}
        items = [item('5025', x=0.25, y=0.3, w=0.03, h=0.05), item('10147', x=0.3, y=0.3, w=0.03, h=0.05),
                 item('49', x=0.42, y=0.25, w=0.04, h=0.12), item('1:00', x=0.47, y=0.25, w=0.06, h=0.12),
                 item('13', x=0.54, y=0.25, w=0.03, h=0.12), item('1148', x=0.6, y=0.3, w=0.03, h=0.05),
                 item('100', x=0.05, y=0.25, w=0.03, h=0.06)]
        r = neptune_facts.parse_overlay_generic(items, roster)
        self.assertEqual((r['clock_value'], r['red_value'], r['blue_value'], r['sides']), (60, 13, 49, 'blue-left'))

    def test_red_left_from_words_and_no_sides_without_evidence(self):
        items = [item('RED', x=0.35, y=0.3, w=0.05, h=0.05), item('141', x=0.33, y=0.45, w=0.08, h=0.2),
                 item('0:32', x=0.45, y=0.45, w=0.1, h=0.2), item('148', x=0.56, y=0.45, w=0.08, h=0.2)]
        r = neptune_facts.parse_overlay_generic(items)
        self.assertEqual((r['red_value'], r['blue_value']), (141, 148))
        r = neptune_facts.parse_overlay_generic(items[1:])
        self.assertEqual((r['clock_value'], r['red_value'], r['blue_value']), (32, None, None))
        self.assertIsNone(neptune_facts.parse_overlay_generic(items[1:2]))

    def test_unknown_overlay_settles_sides_and_reads_samples(self):
        roster = {'red': [1148, 6764, 9772], 'blue': [5025, 10147, 2584]}
        frames, texts = [], {}
        for k in range(25):
            p = '/v/ov_%05d.jpg' % k
            frames.append((float(k), p))
            texts[p] = [item('Qualification 9', x=0.4, y=0.02, w=0.2, h=0.08), item('5025', x=0.25, y=0.3, w=0.03, h=0.05),
                        item('49', x=0.42, y=0.25, w=0.04, h=0.12), item('1:%02d' % (50 - k), x=0.47, y=0.25, w=0.06, h=0.12),
                        item('13', x=0.54, y=0.25, w=0.03, h=0.12), item('1148', x=0.6, y=0.3, w=0.03, h=0.05)]
        sides, top, stats = neptune_facts.generic_layout(frames, texts, roster, 0.3)
        self.assertEqual((sides, stats['agreeing_frames']), ('blue-left', 25))
        self.assertAlmostEqual(top, 0.121)
        rules = {'teleop_seconds': 140}
        samples, _ = neptune_facts.generic_samples(frames, texts, sides, rules, '/v')
        s = samples[0]
        self.assertEqual((s['clock'], s['red']['value'], s['blue']['value'], s['title_text']), (110, 13, 49, 'Qualification 9'))
        self.assertEqual(([i['t'] for i in s['roster']['red']], [i['t'] for i in s['roster']['blue']]), (['1148'], ['5025']))
        self.assertIsNone(neptune_facts.generic_layout(frames[:10], texts, roster, 0.3))


class ScoreReread(unittest.TestCase):
    def test_lone_round_letter_is_zero_and_tallest_number_wins(self):
        self.assertEqual(neptune_facts.pick_score([item('O', h=0.5)])['t'], '0')
        self.assertEqual(neptune_facts.pick_score([item('3', h=0.2), item('13', h=0.6)])['t'], '13')
        self.assertIsNone(neptune_facts.pick_score([item('O:1'), item('KLD')]))

    def test_score_region_stays_inside_the_band(self):
        profile = neptune_facts.LAYOUTS['frc-2026-field-overlay-v1']
        x, y, w, h = neptune_facts.score_region(profile, 'red')
        self.assertTrue(0 <= x and 0 <= y and x + w <= 1 and y + h <= 1)
        self.assertAlmostEqual(x, 0.26)


class SavedGamePack(unittest.TestCase):
    def test_older_copy_of_the_same_game_gains_newer_layouts(self):
        built = json.loads(neptune_games.BUILTIN.read_text())['seasons']['2026']
        old = dict(built, season=2026, layout_profiles={k: v for k, v in built['layout_profiles'].items() if k == 'frc-2026-field-overlay-v1'})
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / 'games').mkdir()
            (Path(home) / 'games' / '2026.json').write_text(json.dumps(old))
            self.assertEqual(set(neptune_games.select('2026capoh_qm9', home)['layout_profiles']), set(built['layout_profiles']))
            other = dict(old, game_key='2026-other-game')
            (Path(home) / 'games' / '2026.json').write_text(json.dumps(other))
            self.assertEqual(list(neptune_games.select('2026capoh_qm9', home)['layout_profiles']), ['frc-2026-field-overlay-v1'])


if __name__ == '__main__':
    unittest.main()
