import json
import unittest
from pathlib import Path

import neptune_field_detector as fd

REF = json.loads((Path(__file__).with_name('field-detector')/'reference.json').read_text())


def moved(p):
    # A different camera position: shifted and zoomed.
    return [.1+.8*p[0], .05+.9*p[1]]


class FieldDetector(unittest.TestCase):
    def test_boundary_corners_are_ordered(self):
        tl, tr, br, bl = fd.boundary_corners(REF)
        self.assertLess(tl[0], tr[0]); self.assertLess(bl[0], br[0]); self.assertLess(tl[1], bl[1]); self.assertLess(tr[1], br[1])

    def test_labels_have_targets_and_four_corners(self):
        classes = [int(l.split()[0]) for l in fd.yolo_labels(REF)]
        self.assertEqual(classes.count(0), 4); self.assertEqual(classes.count(1), 4)

    def test_same_view_maps_regions_onto_themselves(self):
        corners = [{'view': 'wide', 'box': [x-.01, y-.01, x+.01, y+.01]} for x, y in fd.boundary_corners(REF)]
        regions, method = fd.transfer(REF, [], corners)
        self.assertEqual(method, 'field_plane')
        wide = [r for r in REF['regions'] if r['camera_view'] == 'wide']
        self.assertEqual(len(regions), len(wide))
        for a, b in zip(wide, regions):
            for p, q in zip(a['points'], b['points']):
                self.assertAlmostEqual(p[0], q[0], 4); self.assertAlmostEqual(p[1], q[1], 4)

    def test_moved_camera_moves_regions_through_field_plane(self):
        corners = [{'view': 'wide', 'box': [moved(c)[0]-.01, moved(c)[1]-.01, moved(c)[0]+.01, moved(c)[1]+.01]} for c in fd.boundary_corners(REF)]
        regions, method = fd.transfer(REF, [], corners)
        target = next(r for r in regions if r['kind'] == 'scoring_target' and r['alliance'] == 'red')
        original = next(r for r in REF['regions'] if r['kind'] == 'scoring_target' and r['alliance'] == 'red' and r['camera_view'] == 'wide')
        for p, q in zip(original['points'], target['points']):
            self.assertAlmostEqual(moved(p)[0], q[0], 4); self.assertAlmostEqual(moved(p)[1], q[1], 4)

    def test_two_targets_without_corners(self):
        wide = sorted([r for r in REF['regions'] if r['kind'] == 'scoring_target' and r['camera_view'] == 'wide'], key=lambda r: fd.centre(fd.box_of(r['points']))[0])
        targets = [{'view': 'wide', 'box': fd.box_of([moved(p) for p in r['points']])} for r in wide]
        regions, method = fd.transfer(REF, targets, [])
        self.assertEqual(method, 'two_targets'); self.assertTrue(regions)

    def test_nothing_found_places_nothing(self):
        self.assertEqual(fd.transfer(REF, [], []), ([], None))

    def test_closeup_regions_follow_their_own_target(self):
        ref = next(r for r in REF['regions'] if r['kind'] == 'scoring_target' and r['camera_view'] == 'closeup-left')
        box = fd.box_of(ref['points']); shifted = [box[0]+.05, box[1], box[2]+.05, box[3]]
        regions, _ = fd.transfer(REF, [{'view': 'closeup-left', 'box': shifted}], [])
        zone = next(r for r in regions if r['camera_view'] == 'closeup-left' and r['kind'] == 'scoring_zone')
        original = next(r for r in REF['regions'] if r['camera_view'] == 'closeup-left' and r['kind'] == 'scoring_zone')
        self.assertAlmostEqual(zone['points'][1][0], min(1., original['points'][1][0]+.05), 4)

    def test_aggregate_keeps_stable_detections_only(self):
        frame = [{'class': 'scoring_target', 'view': 'wide', 'box': [.1, .1, .2, .2]}, {'class': 'scoring_target', 'view': 'wide', 'box': [.6, .1, .7, .2]}]
        noise = [{'class': 'field_corner', 'view': 'wide', 'box': [.5, .5, .51, .51]}]
        found = fd.aggregate([frame]*10+[noise], REF)
        self.assertEqual(len(found['scoring_target']), 2); self.assertEqual(found['field_corner'], [])


if __name__ == '__main__':
    unittest.main()
