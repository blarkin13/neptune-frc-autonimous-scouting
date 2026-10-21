"""Browser approval with a loopback callback and one-use PKCE exchange."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import time
import urllib.parse
import webbrowser
from neptune_helper import request, public_https


def connect_account(site, progress, stop):
    site=site.rstrip('/')
    api=public_https(site+'/api/community-analysis.php')
    verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    state=secrets.token_hex(32)
    received={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Do not log authorization codes.
        def do_GET(self):
            parsed=urllib.parse.urlsplit(self.path)
            params=urllib.parse.parse_qs(parsed.query)
            valid=(parsed.path=='/neptune-connect' and secrets.compare_digest(params.get('state',[''])[0],state))
            if not valid:
                self.send_error(400,'Invalid connection response')
                return
            if 'code' in params and len(params['code'])==1:
                received['code']=params['code'][0]
            elif params.get('error'):
                received['error']={'access_denied':'Connection canceled in Neptune.','contributor_access_denied':'The Neptune owner has not enabled contributor access for your account.','account_unavailable':'Your Neptune account is unavailable or changed. Sign in again before connecting.'}.get(params['error'][0],'Neptune did not approve this connection. Connect again.')
            else:
                self.send_error(400,'Missing connection approval')
                return
            message=b'<!doctype html><html><meta charset="utf-8"><title>Neptune Helper</title><body style="font:20px system-ui;padding:40px"><h1>Neptune approval received</h1><p>Return to Neptune Helper to finish connecting.</p></body></html>'
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Length',str(len(message)))
            self.end_headers()
            self.wfile.write(message)
    with HTTPServer(('127.0.0.1',0),Callback) as server:
        server.timeout=.5
        grant=request(api+'?action=connect_start',{'challenge':challenge,'state':state,'port':server.server_port})
        deadline=time.monotonic()+min(int(grant['expires_in']),600)
        request_id=grant['request_id']
        progress('Approve the connection in your browser. Matching code: '+grant['user_code'])
        url=site+'/community/connect.php?'+urllib.parse.urlencode({'request':request_id})
        if not webbrowser.open(url,new=2):
            raise ValueError('Could not open your browser. Set a default web browser and click Connect to Neptune again.')
        while not received and time.monotonic()<deadline and not stop.is_set():
            server.handle_request()
    if stop.is_set():
        raise ValueError('Connection canceled. Click Connect to Neptune when ready.')
    if not received:
        raise ValueError('The approval timed out. Click Connect to Neptune and approve it in your browser.')
    if 'error' in received:
        raise ValueError(received['error'])
    result=request(api+'?action=connect_exchange',{'request_id':request_id,'code':received['code'],'verifier':verifier})
    credential=result.get('access_token','')
    if len(credential)!=64 or any(c not in '0123456789abcdef' for c in credential):
        raise ValueError('Neptune returned an invalid connection. Please try again.')
    return result
