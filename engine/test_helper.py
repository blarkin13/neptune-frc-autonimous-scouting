import unittest
from neptune_helper import local_endpoint, validate


class HelperTests(unittest.TestCase):
    def test_external_inference_refused(self):
        for endpoint in ['https://api.openai.com/v1/chat/completions', 'http://example.com', 'http://localhost.evil.test', 'http://127.0.0.1@evil.test']:
            with self.assertRaises(ValueError):
                local_endpoint(endpoint)
        self.assertEqual(local_endpoint('http://127.0.0.1:8080/v1/chat/completions'), 'http://127.0.0.1:8080/v1/chat/completions')

    def test_unknown_and_timestamp_validation(self):
        match = {'source_sha256': 'a' * 64, 'duration_ms': 10000, 'roster': {'red': [1, 2, 3], 'blue': [4, 5, 6]}}
        p = {'schema_version': 1, 'source_sha256': 'a' * 64, 'summary': 'Uncertain identity.', 'model': 'local', 'runtime': 'local', 'prompt_version': '1', 'inference_location': 'local', 'observations': [{'start_ms': 0, 'end_ms': 1000, 'team': None, 'certainty': 'uncertain', 'note': 'Identity obscured.'}]}
        validate(p, match)
        p['observations'][0]['end_ms'] = 11000
        with self.assertRaises(ValueError):
            validate(p, match)


if __name__ == '__main__':
    unittest.main()
