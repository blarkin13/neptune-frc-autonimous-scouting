"""Platform support and the shared OCR interface."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import neptune_ocr
import neptune_setup


class PlatformTests(unittest.TestCase):
    def key(self, system, machine):
        with patch('neptune_setup.platform.system', return_value=system), patch('neptune_setup.platform.machine', return_value=machine):
            return neptune_setup.platform_key()

    def test_platform_keys(self):
        self.assertEqual(self.key('Darwin', 'arm64'), 'macos-arm64')
        self.assertEqual(self.key('Darwin', 'x86_64'), 'macos-x86_64')
        self.assertEqual(self.key('Windows', 'AMD64'), 'windows-x86_64')
        self.assertEqual(self.key('Linux', 'aarch64'), 'linux-aarch64')
        self.assertEqual(self.key('Linux', 'x86_64'), 'linux-x86_64')

    def test_intel_mac_and_windows_arm_clearly_unsupported(self):
        for system, machine in (('Darwin', 'x86_64'), ('Windows', 'ARM64')):
            with patch('neptune_setup.platform.system', return_value=system), patch('neptune_setup.platform.machine', return_value=machine):
                with self.assertRaisesRegex(ValueError, 'not supported'):
                    neptune_setup.check_platform()
        self.assertIn('macos-x86_64', neptune_setup.REQUIREMENTS['unsupported_platforms'])

    def test_every_supported_platform_names_an_installer_and_ocr_backend(self):
        for key, spec in neptune_setup.REQUIREMENTS['platforms'].items():
            self.assertIn(spec['ocr_backend'], neptune_ocr.BACKENDS)
            self.assertTrue((Path(neptune_setup.__file__).parent / spec['installer']).is_file(), spec['installer'])

    def test_ai_engine_is_opt_in(self):
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('NEPTUNE_HELPER_PIPELINE', None)
            self.assertEqual(neptune_setup.wanted_pipeline(), 'facts')
        with patch.dict('os.environ', {'NEPTUNE_HELPER_PIPELINE': 'ai'}):
            self.assertEqual(neptune_setup.wanted_pipeline(), 'ai')


class FakeResult:
    def __init__(self, boxes, txts, scores):
        self.boxes, self.txts, self.scores = boxes, txts, scores


class OcrInterfaceTests(unittest.TestCase):
    def test_rapidocr_items_use_the_shared_format(self):
        backend = neptune_ocr.RapidOcrBackend()

        class Image:
            shape = (100, 200, 3)

        class CV2:
            @staticmethod
            def imread(path):
                return Image()
        backend._cv2 = CV2
        backend._engine = lambda image: FakeResult([[[20, 10], [60, 10], [60, 30], [20, 30]]], ['6369'], [0.97])
        out = backend.recognize(['/x/a.jpg'])
        item = out['/x/a.jpg'][0]
        self.assertEqual(item['t'], '6369')
        self.assertAlmostEqual(item['x'], 0.1)
        self.assertAlmostEqual(item['y'], 0.1)
        self.assertAlmostEqual(item['w'], 0.2)
        self.assertAlmostEqual(item['h'], 0.2)
        backend._engine = lambda image: FakeResult(None, None, None)
        self.assertEqual(backend.recognize(['/x/b.jpg']), {'/x/b.jpg': []})

    def test_unknown_or_missing_backend_fails_clearly(self):
        with patch('neptune_ocr.shutil.which', return_value='/usr/bin/ffmpeg'):
            with self.assertRaisesRegex(neptune_ocr.OcrUnavailable, 'Unknown text reader'):
                neptune_ocr.select_backend('tesseract')
            with patch.object(neptune_ocr.AppleVisionBackend, 'available', return_value=False), patch.object(neptune_ocr.RapidOcrBackend, 'available', return_value=False):
                with self.assertRaisesRegex(neptune_ocr.OcrUnavailable, 'No text reader'):
                    neptune_ocr.select_backend()
        with patch('neptune_ocr.shutil.which', return_value=None):
            with self.assertRaisesRegex(neptune_ocr.OcrUnavailable, 'FFmpeg'):
                neptune_ocr.select_backend()

    @unittest.skipUnless(neptune_ocr.AppleVisionBackend.available(), 'Apple Vision reader not built on this computer')
    def test_same_file_names_in_one_batch_do_not_collide(self):
        import shutil
        import subprocess
        import tempfile
        if not shutil.which('ffmpeg'):
            self.skipTest('ffmpeg missing')
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'a', Path(d) / 'b'
            a.mkdir(); b.mkdir()
            for folder, colour in ((a, 'white'), (b, 'black')):
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=%s:s=64x64' % colour, '-frames:v', '1', str(folder / 'same.jpg')], check=True)
            out = neptune_ocr.AppleVisionBackend().recognize([a / 'same.jpg', b / 'same.jpg'])
            self.assertEqual(set(out), {str(a / 'same.jpg'), str(b / 'same.jpg')})

    @unittest.skipUnless(neptune_ocr.AppleVisionBackend.available(), 'Apple Vision reader not built on this computer')
    def test_apple_vision_reports_its_version(self):
        v = neptune_ocr.AppleVisionBackend().describe()
        self.assertEqual(v['backend'], 'apple-vision')
        self.assertIn('request_revision', v)


if __name__ == '__main__':
    unittest.main()
