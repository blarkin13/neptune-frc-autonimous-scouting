import unittest
from read import suggestion


class SuggestionValidation(unittest.TestCase):
    def test_complete_read_stays_unverified(self):
        r=suggestion(dict(digits='118',complete=True,readable=True))
        self.assertEqual(r['suggested_team'],118)
        self.assertEqual(r['status'],'needs_human_review')
        self.assertFalse(r['training_eligible'])
        self.assertFalse(r['identity_anchor'])

    def test_partial_unreadable_or_ambiguous_remains_unknown(self):
        cases=[('118',False,True),('118',True,False),('',False,False),
               ('118 or 148',True,True),('00118',True,True),('123456',True,True)]
        for digits,complete,readable in cases:
            with self.subTest(digits=digits,complete=complete,readable=readable):
                self.assertIsNone(suggestion(dict(digits=digits,complete=complete,readable=readable))['suggested_team'])

    def test_invalid_boolean_is_rejected(self):
        with self.assertRaises(ValueError):
            suggestion(dict(digits='118',complete='false',readable=True))


if __name__=='__main__':unittest.main()
