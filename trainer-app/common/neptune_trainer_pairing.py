"""One-use browser approval for a Neptune training computer."""
import base64
import hashlib
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import sys
import time
import urllib.parse
import webbrowser

def open_browser(url):
    """Windows' own opener first: webbrowser may start the browser through subprocess, which the helper starts hidden."""
    if sys.platform == 'win32':
        try:
            os.startfile(url); return True
        except OSError:
            pass
    return webbrowser.open(url, new=2)


from neptune_helper import public_https, request


def connect_account(site, progress, stop):
    site = site.rstrip('/')
    api = public_https(site + '/api/community-training.php')
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    state = secrets.token_hex(32)
    received = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if parsed.path != '/neptune-connect' or not secrets.compare_digest(params.get('state', [''])[0], state):
                self.send_error(400, 'Invalid connection response')
                return
            if len(params.get('code', [])) == 1:
                received['code'] = params['code'][0]
            elif len(params.get('error', [])) == 1:
                received['error'] = 'Connection canceled or not approved on Neptune.'
            else:
                self.send_error(400, 'Missing connection approval')
                return
            data = b'<!doctype html><title>Neptune Training Helper</title><h1>Connection approved</h1><p>Return to the helper window.</p>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = .5
        grant = request(api + '?action=connect_start',
                        {'challenge': challenge, 'state': state, 'port': server.server_port})
        deadline = time.monotonic() + min(int(grant['expires_in']), 600)
        url = site + '/community/connect-training.php?' + urllib.parse.urlencode({'request': grant['request_id']})
        progress('Approve this computer in your browser. Matching code: %s · If no page opened, open %s' % (grant['user_code'], url))
        if not open_browser(url):
            raise ValueError('Could not open your browser. Open %s yourself, or set a default browser and try again.' % url)
        while not received and time.monotonic() < deadline and not stop.is_set():
            server.handle_request()
    if stop.is_set(): raise ValueError('Connection canceled.')
    if not received: raise ValueError('Connection approval timed out. Try again.')
    if 'error' in received: raise ValueError(received['error'])
    result = request(api + '?action=connect_exchange',
                     {'request_id': grant['request_id'], 'code': received['code'], 'verifier': verifier})
    return result
