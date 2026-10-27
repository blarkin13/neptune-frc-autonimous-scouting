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
