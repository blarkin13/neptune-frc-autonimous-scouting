import unittest
from select_candidates import validate

class CandidateResponseTests(unittest.TestCase):
 def test_missing_candidate_is_not_silently_accepted(self):
  with self.assertRaises(ValueError):validate({'verdicts':[{'candidate_id':'A','digits':'1234','alliance':'red'}]},{'A','B'})
 def test_duplicate_or_invented_ids_rejected(self):
  for ids in [('A','A'),('A','C')]:
   with self.subTest(ids=ids),self.assertRaises(ValueError):
    validate({'verdicts':[{'candidate_id':i,'digits':'1234','alliance':'red'} for i in ids]},{'A','B'})
 def test_invalid_color_and_nontext_digits_rejected(self):
  for row in [dict(candidate_id='A',digits=1234,alliance='red'),dict(candidate_id='A',digits='1234',alliance='green')]:
   with self.subTest(row=row),self.assertRaises(ValueError):validate({'verdicts':[row]},{'A'})
 def test_unknown_result_stays_explicit(self):
  value=validate({'verdicts':[{'candidate_id':'A','digits':'','alliance':'unknown'}]},{'A'})
  self.assertEqual(value['A']['alliance'],'unknown')

if __name__=='__main__':unittest.main()
