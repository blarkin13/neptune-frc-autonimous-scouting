import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'trainer-app/windows'))
import neptune_windows_update as updater
import neptune_update_apply as apply_module


class WindowsUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.app=self.root/'Neptune Trainer'/'app'
        self.app.mkdir(parents=True)
        (self.app/'build-version.json').write_text('{"version":"6.2"}')
        (self.app/'trainer-connection.json').write_text('{"token":"kept-private"}')
        (self.app/'neptune_engine.py').write_text('old engine')
        self.release=ROOT/'trainer-app/releases/windows-6.3'
        self.feed=json.loads((self.release/'latest.json').read_text())
        self.data=(self.release/'Neptune-Training-Helper-6.3-update.zip').read_bytes()

    def prepare(self):
        with patch.object(updater,'_read_https',return_value=self.data):
            return updater.prepare(self.app,self.feed)

    def test_release_upgrades_code_and_preserves_connection(self):
        stage=self.prepare()
        apply_module.apply(self.app,stage)
        self.assertEqual(updater.installed_version(self.app),'6.3')
        self.assertEqual((self.app/'trainer-connection.json').read_text(),'{"token":"kept-private"}')
        self.assertEqual((stage/'rollback'/'neptune_engine.py').read_text(),'old engine')
        self.assertIn('2.4.6', (self.app/'neptune_engine.py').read_text())

    def test_rejects_wrong_archive_hash(self):
        tampered=dict(self.feed,archive_sha256='0'*64)
        with patch.object(updater,'_read_https',return_value=self.data):
            with self.assertRaisesRegex(updater.UpdateError,'SHA-256'):
                updater.prepare(self.app,tampered)
        self.assertEqual((self.app/'trainer-connection.json').read_text(),'{"token":"kept-private"}')

    def test_rejects_connection_or_traversal_members(self):
        for name in ('app/trainer-connection.json','app/../escape.py'):
            with self.subTest(name=name):
                archive=self.root/'evil.zip'
                with zipfile.ZipFile(archive,'w') as z:
                    z.writestr(name,b'bad')
                    z.writestr('files.json',json.dumps({name:hashlib.sha256(b'bad').hexdigest()}))
                payload=archive.read_bytes()
                release=dict(self.feed,archive_sha256=hashlib.sha256(payload).hexdigest(),archive_size=len(payload))
                with patch.object(updater,'_read_https',return_value=payload):
                    with self.assertRaises(updater.UpdateError):updater.prepare(self.app,release)

    def test_feed_does_not_follow_another_host(self):
        bad=dict(self.feed,archive_url='https://another.example/update.zip')
        with patch.object(updater,'_read_https',return_value=json.dumps(bad).encode()):
            with self.assertRaisesRegex(updater.UpdateError,'URL'):
                updater.check(self.app)

    def test_installer_package_has_no_credentials_and_current_engine(self):
        with zipfile.ZipFile(self.release/'Neptune-Trainer-Windows.zip') as z:
            names=z.namelist()
            self.assertFalse(any('trainer-connection.json' in name for name in names))
            self.assertEqual(json.loads(z.read('Neptune Trainer/app/build-version.json'))['version'],'6.3')
            self.assertIn(b'2.4.6-wide-tile-continuity-preview1',z.read('Neptune Trainer/app/neptune_engine.py'))
            self.assertIn('Neptune Trainer/app/Neptune.ico',names)
            self.assertIn(b'Check for updates',z.read('Neptune Trainer/app/neptune_trainer.py'))


    def test_linux_uses_its_own_feed_and_reopens_through_the_launcher(self):
        import importlib
        with patch.object(sys,'platform','linux'):
            linux=importlib.reload(updater)
            try:
                self.assertEqual(linux.FEED_URL,'https://neptunefrc.com/community/downloads/linux/latest.json')
                self.assertEqual(linux.relaunch_command(self.app),['/usr/bin/neptune-training-helper'])
                with patch.object(linux,'_read_https',return_value=json.dumps(self.feed).encode()):
                    with self.assertRaisesRegex(linux.UpdateError,'format'):linux.check(self.app)    # a Windows feed is refused on Linux
            finally:
                importlib.reload(updater)

    def test_linux_update_archive_installs_with_the_same_checks(self):
        import importlib,subprocess
        sys.path.insert(0,str(ROOT/'trainer-app/scripts'));build=importlib.import_module('build-linux-deb')
        new=self.root/'linux-app';(new/'robot-detector').mkdir(parents=True)
        (new/'build-version.json').write_text('{"version":"%s"}'%build.VERSION);(new/'neptune_engine.py').write_text('new engine')
        (new/'robot-detector'/'manifest.json').write_text('{}');(new/'robot-detector'/'model.pt').write_bytes(b'weights')
        (new/'trainer-connection.json').write_text('{"token":"never shipped"}')
        out=self.root/'linux-release';build.write_update(new,out,'engine-test')
        feed=json.loads((out/'latest.json').read_text());data=(out/feed['archive_url'].rsplit('/',1)[1]).read_bytes()
        self.assertEqual((feed['platform'],feed['version'],feed['archive_size']),('linux',build.VERSION,len(data)))
        names=zipfile.ZipFile(out/feed['archive_url'].rsplit('/',1)[1]).namelist()
        self.assertNotIn('app/trainer-connection.json',names);self.assertNotIn('app/robot-detector/model.pt',names)
        with patch.object(updater,'_read_https',return_value=data):stage=updater.prepare(self.app,feed)
        marker=self.root/'reopened'
        dead=subprocess.Popen([sys.executable,'-c','pass']);dead.wait()
        subprocess.run([sys.executable,'-I',str(ROOT/'trainer-app/windows/neptune_update_apply.py'),str(dead.pid),str(self.app),str(stage),
                        json.dumps([sys.executable,'-c','open(%r,"w").write("ok")'%str(marker)])],check=True,timeout=60)
        for _ in range(50):
            if marker.exists():break
            __import__('time').sleep(.1)
        self.assertEqual(updater.installed_version(self.app),build.VERSION)
        self.assertEqual((self.app/'trainer-connection.json').read_text(),'{"token":"kept-private"}')
        self.assertTrue(marker.exists(),'the helper is reopened after installing')

    def test_linux_launcher_keeps_a_newer_per_user_copy(self):
        sys.path.insert(0,str(ROOT/'trainer-app/linux'));import bootstrap
        self.assertTrue(bootstrap.newer('6.6.26','6.6.25'))
        self.assertFalse(bootstrap.newer('6.6.26','6.6.27'))
        self.assertFalse(bootstrap.newer('6.6.26','6.6.26'))
        self.assertTrue(bootstrap.newer('6.6.26','broken'))

if __name__=='__main__':unittest.main()
