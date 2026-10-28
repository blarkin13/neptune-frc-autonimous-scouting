"""Owner-only training authorization, one-use PKCE and strict loopback callback."""
import base64,hashlib,secrets,time,urllib.parse,webbrowser
from http.server import BaseHTTPRequestHandler,HTTPServer
from neptune_helper import request,public_https

def connect(site,progress,stop,computer_id=None,name=None):
    """computer_id: this Mac's previous record, reused on reconnect. name: its own name for a first connection."""
    site=public_https(site.rstrip('/'));api=site+'/api/community-training.php'
    verifier=secrets.token_urlsafe(48);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=');state=secrets.token_hex(32);received={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            url=urllib.parse.urlsplit(self.path);params=urllib.parse.parse_qs(url.query)
            if url.path!='/neptune-connect' or not secrets.compare_digest(params.get('state',[''])[0],state):self.send_error(400);return
            if len(params.get('code',[]))==1:received['code']=params['code'][0]
            else:received['error']='Connection was canceled. Return to Neptune Training Helper.'
            self.send_response(200);self.send_header('Content-Type','text/plain');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b'Return to Neptune Training Helper. You can close this tab.')
    with HTTPServer(('127.0.0.1',0),Callback) as server:
        server.timeout=.5
        result=request(api+'?action=connect_start',{'challenge':challenge,'state':state,'port':server.server_port})
        progress('Approve this computer in your browser. Code: '+result['user_code'])
        emit_url=site+'/community/connect-training.php?request='+urllib.parse.quote(result['request_id'])
        webbrowser.open(emit_url)
        deadline=time.monotonic()+600
        while not received and not stop.is_set() and time.monotonic()<deadline:server.handle_request()
    if 'error' in received:raise ValueError(received['error'])
    if 'code' not in received:raise ValueError('Sign-in expired. Click Connect to try again.')
    details={'request_id':result['request_id'],'code':received['code'],'verifier':verifier}
    if computer_id:details['computer_id']=computer_id
    if name:details['name']=str(name)[:100]
    answer=request(api+'?action=connect_exchange',details)
    token=answer.get('access_token','')
    if len(token)!=64 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid training connection response.')
    return {'site':site,'token':token,'computer_id':answer['computer_id'],'expires_at':answer['expires_at']}
