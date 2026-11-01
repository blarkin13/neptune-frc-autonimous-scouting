import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('release_prune',Path(__file__).with_name('release_prune.py'))
prune=importlib.util.module_from_spec(spec);spec.loader.exec_module(prune)

class ReleasePrune(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        prune.DOWNLOADS=self.root/'downloads';prune.BACKUPS=self.root/'backups';prune.STATE=self.root/'state';prune.PLAN=prune.STATE/'plan.json';prune.LOCK=self.root/'lock'
        prune.BACKUPS.mkdir()
    def tearDown(self):self.temp.cleanup()
    def backup(self,name,t,sql=False):
        p=prune.BACKUPS/name;p.mkdir();(p/('database.sql' if sql else 'code.py')).write_text('preserve' if sql else 'old code');os.utime(p,(t,t));return p
    def test_epoch_and_date_backups_share_one_retention_limit(self):
        old=self.backup('site-backup-20261030',100)
        previous=self.backup('site-backup-1793492004',200)
        newest=self.backup('site-backup-1793492465',300)
        database=self.backup('data-backup-20260101',50,sql=True)
        installer=self.backup('neptune-backup-install',25)
        r=prune.inventory();self.assertEqual([x['path'] for x in r['items']],[str(old)])
        scan=prune.handle('scan',{});prune.handle('prune',{'digest':scan['digest'],'confirmation':'REMOVE OLD RELEASES'})
        self.assertFalse(old.exists());self.assertTrue(previous.exists());self.assertTrue(newest.exists());self.assertTrue(database.exists());self.assertTrue(installer.exists())
    def test_linux_feed_and_two_newest_updates_are_preserved(self):
        d=prune.DOWNLOADS/'linux';d.mkdir(parents=True)
        for n in (26,27,47,48):(d/f'Neptune-Training-Helper-6.6.{n}-update.zip').write_bytes(b'package')
        (d/'latest.json').write_text(json.dumps({'archive_url':'https://example.com/Neptune-Training-Helper-6.6.26-update.zip'}))
        rows=prune.inventory()['items'];self.assertEqual([Path(r['path']).name for r in rows],['Neptune-Training-Helper-6.6.27-update.zip'])
    def test_changed_preview_does_not_delete(self):
        old=self.backup('site-backup-20261001',100)
        self.backup('site-backup-1793492004',200);self.backup('site-backup-1793492465',300)
        scan=prune.handle('scan',{});(old/'code.py').write_text('changed by another deployment')
        with self.assertRaisesRegex(ValueError,'changed'):prune.handle('prune',{'digest':scan['digest'],'confirmation':'REMOVE OLD RELEASES'})
        self.assertTrue(old.exists())

if __name__=='__main__':unittest.main()
