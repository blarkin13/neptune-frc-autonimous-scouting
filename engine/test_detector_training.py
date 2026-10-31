import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from neptune_detector_training import prepare


class DetectorData(unittest.TestCase):
    def fixture(self, root):
        rows = []
        for index, split in enumerate(('train', 'val')):
            image = root/(split+'.jpg'); image.write_bytes(('fixture-'+split).encode())
            rows.append(dict(image=image.name, image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                             source_sha256=str(index)*64, match_key='2026test_qm'+str(index+1), split=split,
                             reviewed=True, all_visible_bumpers_labeled=True,
                             boxes=[dict(class_id=index, xywh=[.5, .5, .2, .1])]))
        data = dict(schema_version=1, season=2026, names=['red', 'blue'], frames=rows)
        return data

    def run_data(self, root, data):
        manifest = root/'boxes.json'; manifest.write_text(json.dumps(data))
        return prepare(manifest, root/'prepared')

    def test_reviewed_boxes_create_separate_yolo_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.run_data(root, self.fixture(root))
            self.assertEqual(json.loads(config.read_text())['names'], ['red', 'blue'])
            self.assertEqual(len(list((root/'prepared/labels/train').glob('*.txt'))), 1)
            self.assertTrue((root/'prepared/provenance.json').is_file())

    def test_unreviewed_or_partial_boxes_never_become_negatives(self):
        for field in ('reviewed', 'all_visible_bumpers_labeled'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); data = self.fixture(root); data['frames'][0][field] = False
                with self.assertRaises(ValueError):self.run_data(root, data)
                self.assertFalse((root/'prepared').exists())

    def test_same_video_or_match_cannot_cross_splits(self):
        for field in ('source_sha256', 'match_key'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); data = self.fixture(root)
                data['frames'][1][field] = data['frames'][0][field]
                with self.assertRaises(ValueError):self.run_data(root, data)

    def test_matches_from_other_seasons_train_too(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = self.fixture(root); data['frames'][0]['match_key'] = '2023txhou_qm12'
            self.assertEqual(len(list((self.run_data(root, data).parent/'labels/train').glob('*.txt'))), 1)

    def test_match_key_must_start_with_a_year(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = self.fixture(root); data['frames'][0]['match_key'] = 'qm12'
            with self.assertRaisesRegex(ValueError, 'match and source-video'):self.run_data(root, data)

    def test_q7_reference_remains_reserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = self.fixture(root); data['frames'][0]['match_key'] = '2026txcmp1_qm7'
            with self.assertRaises(ValueError):self.run_data(root, data)

    def test_changed_image_or_outside_box_rejected(self):
        for change in ('fingerprint', 'box'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); data = self.fixture(root)
                if change == 'fingerprint':data['frames'][0]['image_sha256'] = 'f'*64
                else:data['frames'][0]['boxes'][0]['xywh'] = [.95, .5, .2, .1]
                with self.assertRaises(ValueError):self.run_data(root, data)


if __name__ == '__main__':
    unittest.main()
