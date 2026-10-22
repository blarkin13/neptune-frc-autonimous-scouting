import base64,gzip,hashlib,json,tempfile,unittest
from pathlib import Path
from neptune_review_cloud import ReviewCloud

SOURCE='a'*64
REVIEW={'schema_version':1,'source_sha256':SOURCE,'match_key':'2026test_qm1','video_id':'abcdefghijk',
        'roster':{'red':[1,2,3],'blue':[4,5,6]},'points':[],
        'corrections':[{'review_track':'x','start':1,'end':2,'team':1}]}

class CloudTests(unittest.TestCase):
    def setUp(self):
        self.saved={}
        def transport(action,p):
            if action=='review_list':return {'reviews':[{'source_sha256':source,'match_key':'2026test_qm1','video_id':'abcdefghijk'} for source in self.saved]}
            if action=='review_get':return self.saved.get(p['source_sha256'],{'found':False})
            if action=='review_put':
                old=self.saved.get(p['source_sha256']);raw=gzip.decompress(base64.b64decode(p['review_gzip_b64']))
                revision=hashlib.sha256(raw).hexdigest()
                if old and old['revision']!=p['expected_revision']:raise ValueError('newer cloud review')
                self.saved[p['source_sha256']]={'found':True,'revision':revision,'review_gzip_b64':p['review_gzip_b64']}
                return {'revision':revision}
            raise AssertionError(action)
        self.cloud=ReviewCloud({},transport)

    def test_round_trip_and_revision(self):
        revision=self.cloud.save(REVIEW)
        restored,remote_revision=self.cloud.fetch(SOURCE,'2026test_qm1')
        self.assertEqual(restored,REVIEW)
        self.assertEqual(remote_revision,revision)
        self.assertEqual(self.cloud.listing()[0]['video_id'],'abcdefghijk')
        changed={**REVIEW,'corrections':REVIEW['corrections']+[{'review_track':'y','start':3,'end':4,'team':2}]}
        with self.assertRaisesRegex(ValueError,'newer cloud'):
            self.cloud.save(changed)
        self.cloud.save(changed,revision)

    def test_backfill_keeps_existing_cloud_review(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'2026test_qm1'/'identity-review.json';path.parent.mkdir();path.write_text(json.dumps(REVIEW))
            self.assertEqual(self.cloud.backfill(temp)['backed_up'],1)
            self.assertEqual(self.cloud.backfill(temp)['backed_up'],0)
            different={**REVIEW,'corrections':[]}
            path.write_text(json.dumps(different))
            self.assertEqual(self.cloud.backfill(temp)['backed_up'],0)
            self.assertEqual(self.cloud.fetch(SOURCE)[0],REVIEW)

    def test_wrong_video_is_rejected(self):
        self.cloud.save(REVIEW)
        with self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
            self.cloud.validate(REVIEW,'b'*64)
        with self.assertRaisesRegex(ValueError,'match mismatch'):
            self.cloud.fetch(SOURCE,'2026test_qm2')

if __name__=='__main__':unittest.main()
