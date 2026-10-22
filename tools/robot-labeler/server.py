"""Local robot-bumper labeler: complete red/blue bumper boxes on match frames, for robot-detector training.

Frames come from the helper's saved tracking reviews (~/.neptune-trainer/identity-reviews/<match>/), each
opened with the current detector's boxes pre-filled. The person fixes them, deletes wrong ones and draws the
bumpers the detector missed, then marks the frame complete. Export writes the reviewed-box manifest that
neptune_detector_training.prepare accepts. Serves only on 127.0.0.1 behind a random URL token.

    python3 tools/robot-labeler/server.py [--port 49530] [--every 4]
"""
import argparse
import hashlib
import json
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REVIEWS = Path.home()/'.neptune-trainer'/'identity-reviews'
OUT = HERE.parents[1]/'local'/'robot-labels'
FFMPEG_CANDIDATES = [Path('/Applications/Neptune Training Helper.app/Contents/Resources/engine/vendor/bin/ffmpeg'),
                     HERE.parents[1]/'engine'/'vendor'/'bin'/'ffmpeg']
LOCK = threading.Lock()


def ffmpeg():
    for p in FFMPEG_CANDIDATES:
        if p.is_file():
            return str(p)
    return 'ffmpeg'


def bumper_from_crop(box):
    """Undo neptune_yolo.crop_box (x-0.3w, y-2h, x+1.3w, y+1.4h) to recover the bumper box, normalized."""
    x, y, w, h = box
    bw, bh = w/1.6, h/3.4
    return [x+.3*bw, y+2*bh, bw, bh]


def frame_list(every):
    """(id, match, video, t, prefill) for frames every `every` seconds of in-match tracking."""
    frames = []
    for folder in sorted(REVIEWS.glob('*')):
        facts_file, media = folder/'facts.json', folder/'media'
        videos = sorted(media.glob('*.mp4')) if media.is_dir() else []
        if not facts_file.is_file() or not videos:
            continue
        facts = json.loads(facts_file.read_text())
        obs = facts.get('tracking', {}).get('observations') or []
        if not obs:
            continue
        by_t = {}
        for o in obs:
            by_t.setdefault(round(o['t'], 3), []).append(o)
        last = -1e9
        for t in sorted(by_t):
            if t-last < every:
                continue
            last = t
            boxes = []
            for o in by_t[t]:
                if o.get('box_source') == 'optical_flow' or o.get('alliance') not in ('red', 'blue'):
                    continue
                x, y, w, h = bumper_from_crop(o['box'])
                boxes.append({'alliance': o['alliance'], 'x': x, 'y': y, 'w': w, 'h': h, 'source': 'detector'})
            fid = hashlib.sha256(('%s:%s' % (folder.name, t)).encode()).hexdigest()[:16]
            frames.append({'id': fid, 'match_key': folder.name, 'video': str(videos[0]), 't': t,
                           'source_sha256': facts.get('source', {}).get('sha256'), 'prefill': boxes})
    return frames


def image_for(frame):
    path = OUT/'images'/(frame['id']+'.jpg')
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg(), '-v', 'error', '-y', '-ss', str(frame['t']), '-i', frame['video'], '-frames:v', '1', '-q:v', '2', str(path)], check=True)
    return path


def saved(fid):
    p = OUT/'labels'/(fid+'.json')
    return json.loads(p.read_text()) if p.is_file() else None


def export(frames, holdout):
    """Write the reviewed-box manifest neptune_detector_training.prepare expects."""
    rows = []
    for f in frames:
        s = saved(f['id'])
        if not s or not s.get('complete'):
            continue
        image = image_for(f)
        boxes = []
        for b in s['boxes']:
            x0, y0 = max(0., b['x']), max(0., b['y']); x1, y1 = min(1., b['x']+b['w']), min(1., b['y']+b['h'])
            if x1 > x0 and y1 > y0:
                boxes.append({'class_id': 0 if b['alliance'] == 'red' else 1, 'xywh': [(x0+x1)/2, (y0+y1)/2, x1-x0, y1-y0]})
        rows.append({'match_key': f['match_key'], 'source_sha256': f['source_sha256'], 'split': 'val' if f['match_key'] in holdout else 'train',
                     'reviewed': True, 'all_visible_bumpers_labeled': True, 'image': 'images/'+image.name,
                     'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(), 'boxes': boxes})
    manifest = {'schema_version': 1, 'names': ['red', 'blue'], 'season': 2026, 'frames': rows,
                'exported_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=1))
    return {'frames': len(rows), 'train': sum(r['split'] == 'train' for r in rows), 'val': sum(r['split'] == 'val' for r in rows),
            'boxes': sum(len(r['boxes']) for r in rows), 'path': str(OUT/'manifest.json')}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=49530)
    ap.add_argument('--every', type=float, default=4.0, help='seconds between labelled frames')
    ap.add_argument('--holdout', default='2026txcmp1_qm1', help='comma-separated matches kept for validation')
    a = ap.parse_args()
    frames = frame_list(a.every); index = {f['id']: f for f in frames}
    holdout = set(filter(None, a.holdout.split(',')))
    token = secrets.token_urlsafe(18); page = (HERE/'index.html').read_text()
    OUT.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, kind='application/json'):
            body = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code); self.send_header('Content-Type', kind); self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def route(self):
            parts = urlsplit(self.path).path.strip('/').split('/')
            if not parts or parts[0] != token:
                self.send(404, {'error': 'not found'}); return None
            return parts[1:]

        def do_GET(self):
            p = self.route()
            if p is None:
                return
            if p in ([], ['']):
                return self.send(200, page.encode(), 'text/html; charset=utf-8')
            if p == ['api', 'frames']:
                out = []
                for f in frames:
                    s = saved(f['id'])
                    out.append({'id': f['id'], 'match_key': f['match_key'], 't': f['t'], 'complete': bool(s and s.get('complete')),
                                'boxes': len(s['boxes']) if s else len(f['prefill'])})
                return self.send(200, {'frames': out, 'holdout': sorted(holdout)})
            if len(p) == 3 and p[:2] == ['api', 'frame'] and p[2] in index:
                f = index[p[2]]; s = saved(f['id'])
                return self.send(200, {'id': f['id'], 'match_key': f['match_key'], 't': f['t'],
                                       'boxes': s['boxes'] if s else f['prefill'], 'complete': bool(s and s.get('complete')), 'prefilled': not s})
            if len(p) == 3 and p[:2] == ['api', 'image'] and p[2] in index:
                with LOCK:
                    path = image_for(index[p[2]])
                return self.send(200, path.read_bytes(), 'image/jpeg')
            self.send(404, {'error': 'not found'})

        def do_POST(self):
            p = self.route()
            if p is None:
                return
            n = int(self.headers.get('Content-Length', '0'))
            if n > 1_000_000:
                return self.send(413, {'error': 'too large'})
            body = json.loads(self.rfile.read(n) or b'{}')
            if len(p) == 3 and p[:2] == ['api', 'frame'] and p[2] in index:
                boxes = []
                for b in body.get('boxes', []):
                    if b.get('alliance') not in ('red', 'blue'):
                        return self.send(422, {'error': 'Each box needs red or blue.'})
                    vals = [float(b[k]) for k in ('x', 'y', 'w', 'h')]
                    if vals[2] <= 0 or vals[3] <= 0:
                        continue
                    boxes.append({'alliance': b['alliance'], 'x': vals[0], 'y': vals[1], 'w': vals[2], 'h': vals[3], 'source': b.get('source', 'person')})
                (OUT/'labels').mkdir(parents=True, exist_ok=True)
                record = {'id': p[2], 'boxes': boxes, 'complete': bool(body.get('complete')), 'saved_at': time.time()}
                tmp = OUT/'labels'/(p[2]+'.pending'); tmp.write_text(json.dumps(record)); tmp.replace(OUT/'labels'/(p[2]+'.json'))
                return self.send(200, {'ok': True})
            if p == ['api', 'export']:
                with LOCK:
                    return self.send(200, export(frames, holdout))
            self.send(404, {'error': 'not found'})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print('Robot labeler: http://127.0.0.1:%d/%s/  (%d frames)' % (a.port, token, len(frames)), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
