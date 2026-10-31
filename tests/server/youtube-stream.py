"""A native-rate MP4 upload must stream successfully under a small PHP memory limit."""
import hashlib,json,subprocess,tempfile,threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
class Receiver(BaseHTTPRequestHandler):
    def do_PUT(self):
        remaining=int(self.headers['Content-Length']);digest=hashlib.sha256()
        while remaining:
            chunk=self.rfile.read(min(65536,remaining));assert chunk;digest.update(chunk);remaining-=len(chunk)
        self.server.received=digest.hexdigest();body=json.dumps({'id':'fixture','status':{'privacyStatus':'unlisted'}}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass
with tempfile.TemporaryDirectory() as td,HTTPServer(('127.0.0.1',0),Receiver) as server:
    path=Path(td)/'fixture.mp4';block=b'x'*(1024*1024)
    with path.open('wb') as f:
        for _ in range(20):f.write(block)
    thread=threading.Thread(target=server.handle_request,daemon=True);thread.start()
    php="require $argv[1]; $m=new ReflectionMethod('YouTubeUploader','putFile'); echo json_encode($m->invoke(null,$argv[2],$argv[3],['Content-Type: video/mp4']));"
    source=Path(__file__).resolve().parents[2]/'server/neptune_secure/youtube-uploader.php'
    r=subprocess.run(['php','-d','memory_limit=8M','-r',php,str(source),f'http://127.0.0.1:{server.server_port}/upload',str(path)],check=True,capture_output=True,text=True)
    thread.join(5);assert json.loads(r.stdout)['id']=='fixture';assert server.received==hashlib.sha256(block*20).hexdigest()
print('PASS 20 MiB uploaded with 8 MiB PHP memory limit and exact bytes verified')
