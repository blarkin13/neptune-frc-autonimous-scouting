import unittest

from neptune_yolo import Identities

ROSTER = {'red': [9492, 10340, 5417], 'blue': [9444, 6377, 4734]}


def det(tid, x, alliance='red'):
    return {'id': tid, 'alliance': alliance, 'box': [x, 100, x+40, 130]}


def read(tid, team, kind='exact'):
    return {'track': tid, 'team': team, 'kind': kind}


class IdentityRules(unittest.TestCase):
    def confirmed(self, r):
        r.update(0, 0.0, [det(1, 100)], [read(1, 9492)])
        return r.update(0, 0.6, [det(1, 102)], [read(1, 9492)])

    def test_identity_survives_brief_contact_with_one_confirming_read(self):
        r = Identities(ROSTER)
        self.assertEqual([d['team'] for d in self.confirmed(r)], [9492])
        self.assertEqual(r.update(0, 0.8, [det(1, 104), det(2, 110)], []), [])          # contact: nothing labelled
        self.assertEqual(r.update(0, 1.0, [det(1, 106)], []), [])                       # apart, not yet confirmed
        out = r.update(0, 1.2, [det(1, 108)], [read(1, 9492)])                          # one read confirms
        self.assertEqual([d['team'] for d in out], [9492])

    def test_a_different_read_after_contact_drops_the_old_identity(self):
        r = Identities(ROSTER); self.confirmed(r)
        r.update(0, 0.8, [det(1, 104), det(2, 110)], [])
        self.assertEqual(r.update(0, 1.0, [det(1, 106)], [read(1, 10340)]), [])         # swapped: needs two reads again

    def test_partial_or_corrected_reads_need_an_exact_read_too(self):
        r = Identities(ROSTER)
        r.update(0, 0.0, [det(1, 100)], [read(1, 9492, 'partial')])
        self.assertEqual(r.update(0, 0.6, [det(1, 100)], [read(1, 9492, 'corrected')]), [])
        out = r.update(0, 1.2, [det(1, 100)], [read(1, 9492)])
        self.assertEqual([d['team'] for d in out], [9492])


if __name__ == '__main__':
    unittest.main()
