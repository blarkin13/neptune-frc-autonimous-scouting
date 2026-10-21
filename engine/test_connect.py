import io
import json
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch
from neptune_connect import connect_account
from neptune_helper import request


class ConnectTests(unittest.TestCase):
    def test_loopback_browser_approval_and_pkce(self):
        session={}
        def api(url,payload):
            if url.endswith('connect_start'):
                session.update(payload)
                return {'request_id':'a'*32,'user_code':'ABCD-1234','expires_in':600}
            self.assertTrue(url.endswith('connect_exchange'))
            import base64,hashlib
            challenge=base64.urlsafe_b64encode(hashlib.sha256(payload['verifier'].encode()).digest()).decode().rstrip('=')
            self.assertEqual(challenge,session['challenge'])
            self.assertEqual(payload['code'],'c'*64)
            return {'access_token':'d'*64,'display_name':'Scout','expires_at':123}
        threads=[]
        def browser(url,new):
            self.assertIn('request='+'a'*32,url)
            self.assertNotIn('verifier',url)
            def approve():
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                base='http://127.0.0.1:'+str(session['port'])+'/neptune-connect?'
                try:
                    opener.open(base+urllib.parse.urlencode({'state':'wrong','code':'c'*64}),timeout=5)
                    self.fail('Wrong state accepted')
                except urllib.error.HTTPError as exc:self.assertEqual(exc.code,400)
                with opener.open(base+urllib.parse.urlencode({'state':session['state'],'code':'c'*64}),timeout=5) as response:
                    self.assertEqual(response.status,200)
            t=threading.Thread(target=approve);t.start();threads.append(t)
            return True
        progress=[]
        with patch('neptune_connect.public_https',side_effect=lambda x:x),patch('neptune_connect.request',side_effect=api),patch('neptune_connect.webbrowser.open',side_effect=browser):
            result=connect_account('https://neptunefrc.com',progress.append,threading.Event())
        for t in threads:t.join(timeout=5)
        self.assertEqual(result['access_token'],'d'*64)
        self.assertTrue(any('ABCD-1234' in text for text in progress))

    def test_server_access_error_is_visible(self):
        error=urllib.error.HTTPError('https://neptunefrc.com',403,'Forbidden',{},io.BytesIO(json.dumps({'error':'The Neptune owner has not enabled contributor access for your account.'}).encode()))
        with patch('neptune_helper.public_https',side_effect=lambda x:x),patch('neptune_helper.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=error
            with self.assertRaisesRegex(ValueError,'owner has not enabled contributor access'):
                request('https://neptunefrc.com/api/community-analysis.php')


if __name__=='__main__':unittest.main()
