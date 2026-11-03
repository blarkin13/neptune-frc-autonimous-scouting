"""The full-height FIRST AGE overlay (Fort Worth 2026): read as an engine-side layout, game pack unchanged."""
import json
import unittest

import neptune_facts as nf
import neptune_games


def item(text, x, y, w, h):
    return {'t': text, 'x': x, 'y': y, 'w': w, 'h': h, 'c': 1.0}


def fort_worth_band(clock='0:57'):
    """OCR positions as Apple Vision read them on Fort Worth qm10 (band = top 30% of the frame)."""
    return [item('FIRST AGLO', .004, .033, .148, .185), item('9786', .047, .336, .038, .086), item('2714', .153, .336, .038, .086),
            item('2728', .259, .336, .036, .086), item('Qualification 10 of 48', .404, .061, .195, .129), item('BLUE', .359, .345, .044, .095),
            item('96', .353, .534, .052, .198), item('4/ 6', .45, .305, .05, .119), item(':02', .506, .31, .045, .112),
            item(clock, .453, .534, .094, .233), item('RED', .605, .336, .036, .103), item('45', .596, .534, .049, .198),
            item('7503', .732, .333, .035, .092), item('REBUILT', .849, .039, .096, .164), item('* 3676', .813, .327, .061, .105),
            item('7534', .943, .334, .035, .091)]


class AgeLargeLayout(unittest.TestCase):
    def test_reads_clock_scores_shift_and_whole_roster(self):
        r = nf.parse_overlay(fort_worth_band(), nf.EXTRA_LAYOUTS['frc-2026-age-large-v1'])
        self.assertEqual((r['clock_value'], r['red']['t'], r['blue']['t']), (57, '45', '96'))
        self.assertTrue(r['labels'] and r['marker']); self.assertEqual(r['shift']['shift'], 4)
        self.assertEqual([i['t'] for i in r['roster']['red']], ['7503', '3676', '7534'])
        self.assertEqual([i['t'] for i in r['roster']['blue']], ['9786', '2714', '2728'])

    def test_pack_layouts_do_not_match_it_but_the_extra_layout_does(self):
        frames = [(float(t), 'f%d' % t) for t in range(30)]
        texts = {'f%d' % t: fort_worth_band('1:%02d' % (59 - t)) for t in range(30)}
        pack = neptune_games.select('2026txfor_qm10')['layout_profiles']
        with self.assertRaises(nf.FactsError):
            nf.detect_layout(frames, texts, 2026, pack)
        pid, _, _ = nf.detect_layout(frames, texts, 2026, dict(pack, **nf.EXTRA_LAYOUTS))
        self.assertEqual(pid, 'frc-2026-age-large-v1')

    def test_game_fingerprint_is_unchanged(self):
        game = neptune_games.select('2026txfor_qm10')
        self.assertNotIn('frc-2026-age-large-v1', game['layout_profiles'])
        self.assertNotIn('frc-2026-age-large-v1', json.dumps(neptune_games.profiles()))

    def test_logo_glyph_before_a_team_number_only(self):
        self.assertEqual(nf.team_token(item('* 3676', 0, 0, 0, 0))['t'], '3676')
        self.assertEqual(nf.team_token(item('3676', 0, 0, 0, 0))['t'], '3676')
        self.assertIsNone(nf.team_token(item('Team 3676', 0, 0, 0, 0)))
        self.assertIsNone(nf.team_token(item('26 / 100', 0, 0, 0, 0)))


if __name__ == '__main__':
    unittest.main()


def oregon_bar(clock='1:51'):
    """OCR positions on the bottom bar of 2026orsal qm7 (band = bottom 24% of the frame)."""
    return [item('FIRST AGE', .01, .03, .14, .2), item('Qualification 7 of 70', .41, .06, .18, .14), item('REBUILT', .85, .04, .12, .16),
            item('846', .05, .43, .03, .1), item('1359', .14, .43, .035, .1), item('4692', .25, .43, .035, .1),
            item('RED', .36, .45, .04, .12), item('47', .35, .74, .05, .2), item('2 / 6', .45, .44, .04, .11), item(':06', .52, .44, .03, .11),
            item(clock, .455, .72, .09, .24), item('BLUE', .6, .45, .05, .12), item('23', .6, .74, .04, .2),
            item('847', .73, .43, .03, .1), item('5468', .82, .43, .035, .1), item('4043', .93, .43, .035, .1),
            item('47 / 100', .09, .78, .11, .17), item('23 / 100', .79, .78, .11, .17)]


class AgeBottomLayout(unittest.TestCase):
    def test_reads_the_bottom_bar(self):
        r = nf.parse_overlay(oregon_bar(), nf.EXTRA_LAYOUTS['frc-2026-age-bottom-v1'])
        self.assertEqual((r['clock_value'], r['red']['t'], r['blue']['t']), (111, '47', '23'))
        self.assertTrue(r['marker'])
        self.assertEqual([i['t'] for i in r['roster']['red']], ['846', '1359', '4692'])
        self.assertEqual([i['t'] for i in r['roster']['blue']], ['847', '5468', '4043'])

    def test_bottom_layout_is_matched_on_its_own_strip(self):
        frames = [(float(t), 'f%d' % t) for t in range(30)]
        texts = {'f%d' % t: oregon_bar('1:%02d' % (59 - t)) for t in range(30)}
        bottoms = {k: v for k, v in nf.EXTRA_LAYOUTS.items() if v.get('band_at') == 'bottom'}
        pid, _, _ = nf.detect_layout(frames, texts, 2026, bottoms, {'red': [846, 1359, 4692], 'blue': [847, 5468, 4043]})
        self.assertEqual(pid, 'frc-2026-age-bottom-v1')

    def test_camera_area_is_above_the_bar(self):
        import neptune_tracking as tr
        p = nf.EXTRA_LAYOUTS['frc-2026-age-bottom-v1']
        self.assertEqual(nf.camera_span(p), (0.0, 0.755))
        top, bottom = tr.wide_band(p)
        self.assertEqual(top, 0.0); self.assertLess(bottom, 0.755); self.assertGreater(bottom, 0.7)
        # a read at the bottom of the camera area lands just above the bar, not 24% lower
        x, y = tr.read_position({'frame_box': [.5, .95, .02, .02]}, (top, bottom), 0.0, 1000, 1000, 0.755)
        self.assertAlmostEqual(y / 1000 * bottom, 0.755 * .96, places=3)
