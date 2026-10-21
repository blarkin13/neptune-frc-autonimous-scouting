import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from neptune_setup import video_js_runtime


class VideoRuntimeTests(unittest.TestCase):
    def test_existing_deno_prevents_bundled_execution(self):
        with patch('neptune_setup.installed_tool', return_value=Path('/existing/deno')) as installed, patch('neptune_setup.resources') as resources:
            self.assertEqual(video_js_runtime(), {'deno': {'path': '/existing/deno'}})
            installed.assert_called_once_with('deno', ['--version'])
            resources.assert_not_called()

    def test_existing_node_is_used_when_deno_is_absent(self):
        with patch('neptune_setup.installed_tool', side_effect=[None, Path('/existing/node')]):
            self.assertEqual(video_js_runtime(), {'node': {'path': '/existing/node'}})

    def test_quarantined_fallback_fails_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'vendor/bin').mkdir(parents=True);(root/'vendor/bin/qjs').write_bytes(b'test')
            with patch('neptune_setup.installed_tool',return_value=None), patch('neptune_setup.resources',return_value=root), patch('neptune_setup.os.getxattr',return_value=b'quarantined',create=True), patch('neptune_setup.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'macOS has not approved'):
                    video_js_runtime()
                run.assert_not_called()
