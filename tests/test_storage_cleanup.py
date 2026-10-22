"""Deletion allowlist and preview consistency for the owner storage control."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "server/root/neptune-helper-artifact-cleanup"
loader = importlib.machinery.SourceFileLoader("storage_cleanup", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
cleanup = importlib.util.module_from_spec(spec)
loader.exec_module(cleanup)


class StorageCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mac = self.root / "public_html/Neptune/community/downloads/mac"
        self.mac.mkdir(parents=True)
        (self.mac / "appcast.xml").write_text(
            "<sparkle:shortVersionString>3.2.5</sparkle:shortVersionString>"
            "Neptune-Training-Helper-3.2.5.zip"
        )
        (self.mac / "Neptune-Training-Helper.dmg").write_bytes(b"current dmg")
        for name in ("3.2.2", "3.2.3", "3.2.4", "3.2.5"):
            (self.mac / f"Neptune-Training-Helper-{name}.zip").write_bytes(name.encode())
        (self.mac / "notes.txt").write_bytes(b"keep")
        self.stage = self.root / "maintenance-uploads/helper-3.2.3"
        self.stage.mkdir(parents=True)
        old = self.stage / "Neptune-Training-Helper-3.2.3.zip"
        old.write_bytes(b"old stage")
        timestamp = time.time() - 7200
        import os
        os.utime(old, (timestamp, timestamp))

    def test_preview_preserves_current_rollback_and_unknown_files(self):
        preview = cleanup.plan(self.root)
        paths = {item["path"] for item in preview["items"]}
        self.assertEqual(len(paths), 3)
        self.assertTrue(any("3.2.2.zip" in p for p in paths))
        self.assertTrue(any("3.2.3.zip" in p for p in paths))
        self.assertTrue(any("maintenance-uploads/helper-3.2.3" in p for p in paths))
        self.assertNotIn("notes.txt", paths)
        self.assertGreater(preview["total_bytes"], 0)

    def test_delete_requires_matching_preview_and_rejects_changes(self):
        preview = cleanup.plan(self.root)
        with self.assertRaises(ValueError):
            cleanup.delete(self.root, "0" * 64)
        old = self.mac / "Neptune-Training-Helper-3.2.2.zip"
        old.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            cleanup.delete(self.root, preview["fingerprint"])
        fresh = cleanup.plan(self.root)
        result = cleanup.delete(self.root, fresh["fingerprint"])
        self.assertEqual(result["deleted_files"], 3)
        self.assertEqual(result["freed_bytes"], fresh["total_bytes"])
        self.assertTrue((self.mac / "Neptune-Training-Helper-3.2.5.zip").exists())
        self.assertTrue((self.mac / "Neptune-Training-Helper-3.2.4.zip").exists())
        self.assertTrue((self.mac / "notes.txt").exists())
        self.assertFalse(self.stage.exists())

    def test_symlink_is_never_offered(self):
        old = self.mac / "Neptune-Training-Helper-3.2.2.zip"
        old.unlink()
        old.symlink_to(self.mac / "Neptune-Training-Helper-3.2.5.zip")
        preview = cleanup.plan(self.root)
        self.assertFalse(any("3.2.2.zip" in item["path"] for item in preview["items"]))


if __name__ == "__main__":
    unittest.main()
