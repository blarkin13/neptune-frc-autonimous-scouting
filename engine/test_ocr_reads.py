import unittest

import neptune_facts
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


if __name__ == '__main__':
    unittest.main()
