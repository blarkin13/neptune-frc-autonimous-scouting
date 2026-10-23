"""Robot-detector work done by a connected helper while it is idle (Auto Scout -> Robot labels).

  prepare  run the current detector on a match's labelling frames and upload its boxes as pre-fill
  train    train a wide-shot bumper detector from every completed robot label, score it against the current
           detector on a held-out match, and adopt it on Neptune only if it is better
Adopted detectors are shared through Neptune; every helper keeps a copy in ~/.neptune-trainer/robot-detector.
"""
import base64
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

VERSION = 'robot-detector-jobs-v1'
HOME = Path.home()/'.neptune-trainer'
SHARED = HOME/'robot-detector'
FRAME_STEP_S = 4.0
WIDE_BAND = (.24, .6506)          # 2026 broadcast wide-camera band (normalized y)
ADOPT_MARGIN = .02                # new detector must beat the current one's held-out F1 by this much
MIN_FRAMES_PER_MATCH = 8


def api(config, action, payload=None, timeout=120):
    import urllib.request
    from neptune_helper import public_https, NoRedirect
    url = public_https(config['site'].rstrip('/')+'/api/robot-detector.php')
    body = json.dumps(dict(payload or {}, action=action)).encode()
    request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+config['token']})
    with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
        return json.loads(response.read(80*1024*1024))


# ---------- the shared detector ----------

def sync_detector(config):
    """Download Neptune's adopted wide-shot detector when it differs from this computer's copy."""
    manifest = SHARED/'manifest.json'
    have = None
    if manifest.is_file():
        have = (json.loads(manifest.read_text()).get('by_camera', {}).get('wide') or {}).get('sha256')
    reply = api(config, 'current', {'have': have})
    current = reply.get('detector')
    if not current or not reply.get('weights_b64'):
        return {'status': 'unchanged' if current else 'none_adopted'}
    raw = base64.b64decode(reply['weights_b64'])
    row = current['by_camera']['wide']
    if hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Shared detector failed verification')
    SHARED.mkdir(parents=True, exist_ok=True)
    weights = SHARED/row['file']; tmp = weights.with_suffix('.pending'); tmp.write_bytes(raw); tmp.replace(weights)
    tmp = manifest.with_suffix('.pending'); tmp.write_text(json.dumps(current)); tmp.replace(manifest)
    for old in SHARED.glob('*.pt'):
        if old.name != row['file']:
            old.unlink()
    return {'status': 'updated', 'sha256': row['sha256']}


def current_wide_weights():
    from neptune_yolo import bundled_detectors
    row = bundled_detectors().get('wide')
    return Path(row['path']) if row else None


# ---------- frames ----------

def ffmpeg(name='ffmpeg'):
    vendored = Path(__file__).with_name('vendor')/'bin'/name
    return str(vendored) if vendored.is_file() else name


def duration_s(video):
    out = subprocess.check_output([ffmpeg('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(video)], text=True, timeout=60)
    return float(out.strip())


def frame(video, t):
    import cv2
    import numpy as np
    raw = subprocess.run([ffmpeg(), '-v', 'error', '-ss', '%.3f' % t, '-i', str(video), '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'],
                         capture_output=True, timeout=120).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


def detect(model, image, conf=.25):
    """Bumper boxes {alliance,x,y,w,h} normalized to the full frame."""
    h, w = image.shape[:2]
    r = model.predict(image, imgsz=1280, conf=conf, verbose=False, device='cpu')[0]
    out = []
    for (x0, y0, x1, y1), cls in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist()):
        name = str(r.names[int(cls)]).lower()
        alliance = 'red' if 'red' in name else 'blue' if 'blue' in name else None
        if alliance:
            out.append({'alliance': alliance, 'x': x0/w, 'y': y0/h, 'w': (x1-x0)/w, 'h': (y1-y0)/h})
    return out


def match_video(video_id, folder):
    from neptune_robot_labels import local_video, youtube_download
    video = local_video(video_id)
    if video:
        return video
    video = Path(folder)/(video_id+'.mp4')
    if not video.is_file():
        youtube_download(video_id, video)
    return video


def prepare(config, req, progress):
    """Detector guesses on frames every FRAME_STEP_S seconds of the match video, uploaded for Robot labels."""
    import os
    os.environ.setdefault('YOLO_OFFLINE', '1')
    from ultralytics import YOLO
    weights = current_wide_weights()
    if not weights:
        raise ValueError('No robot detector is installed on this helper yet.')
    work = HOME/'robot-detector-work'/req['id']; work.mkdir(parents=True, exist_ok=True)
    progress('Downloading '+req['match_key'])
    video = match_video(req['video_id'], work)
    length = duration_s(video); model = YOLO(str(weights)); frames = {}
    times = [t for t in range(0, int(length*1000), int(FRAME_STEP_S*1000))][1:-1]
    for i, t in enumerate(times):
        image = frame(video, t/1000)
        if image is not None:
            frames[str(t)] = detect(model, image)
        if i % 10 == 0:
            progress('Finding bumpers: frame %d of %d' % (i+1, len(times)))
    api(config, 'prefill_put', {'request_id': req['id'], 'lease': req['lease'], 'video_id': req['video_id'], 'frames': frames,
                                'detector': hashlib.sha256(weights.read_bytes()).hexdigest()})
    return {'frames': len(frames), 'boxes': sum(len(b) for b in frames.values())}


# ---------- training ----------

def iou(a, b):
    w = max(0., min(a[2], b[2])-max(a[0], b[0])); h = max(0., min(a[3], b[3])-max(a[1], b[1]))
    u = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-w*h
    return w*h/u if u > 0 else 0.


def score(truth, pred):
    """One-to-one matches at IoU >= 0.3, split into the wide band and close-ups: {band: [matched, truth, pred]}."""
    band = lambda b: 'wide' if WIDE_BAND[0] <= (b[1]+b[3])/2 <= WIDE_BAND[1] else 'closeup'
    out = {'wide': [0, 0, 0], 'closeup': [0, 0, 0]}; used = set()
    for t in truth:
        out[band(t)][1] += 1
        best = max(((iou(t, p), i) for i, p in enumerate(pred) if i not in used), default=(0, None))
        if best[0] >= .3:
            used.add(best[1]); out[band(t)][0] += 1
    for p in pred:
        out[band(p)][2] += 1
    return out


def evaluate(weights, frames):
    """frames: [(image path, truth xyxy boxes)] -> recall/precision/F1 overall and per band."""
    import cv2
    from ultralytics import YOLO
    model = YOLO(str(weights)); tot = {'wide': [0, 0, 0], 'closeup': [0, 0, 0]}
    for path, truth in frames:
        image = cv2.imread(str(path))
        pred = [[b['x'], b['y'], b['x']+b['w'], b['y']+b['h']] for b in detect(model, image)]
        for k, v in score(truth, pred).items():
            tot[k] = [a+b for a, b in zip(tot[k], v)]
    def summary(m, t, p):
        r = m/t if t else 0.; pr = m/p if p else 0.
        return {'recall': round(r, 3), 'precision': round(pr, 3), 'f1': round(2*r*pr/(r+pr), 3) if r+pr else 0., 'bumpers': t, 'detections': p}
    all_ = [sum(v[i] for v in tot.values()) for i in range(3)]
    return dict(summary(*all_), wide=summary(*tot['wide']), closeup=summary(*tot['closeup']))


def train(config, req, progress):
    """Train from every completed robot label; adopt on Neptune only if better on a held-out match."""
    import os
    os.environ.setdefault('YOLO_OFFLINE', '1')
    from ultralytics import YOLO
    import neptune_robot_labels as labels
    from neptune_detector_training import prepare as prepare_dataset
    from neptune_yolo import bundle, bundle_path
    progress('Downloading robot labels')
    docs = labels.sync(config)
    counts = {d.get('match_key'): sum(1 for f in d.get('frames', {}).values() if f.get('complete')) for d in docs}
    usable = sorted(k for k, n in counts.items() if k and n >= MIN_FRAMES_PER_MATCH)
    if len(usable) < 2:
        raise ValueError('Label at least %d frames in two different matches first.' % MIN_FRAMES_PER_MATCH)
    holdout = usable[-1]               # the newest match key is checked, never trained on
    work = HOME/'robot-detector-work'/req['id']; work.mkdir(parents=True, exist_ok=True)
    built = labels.build(docs, work/'frames', holdout={holdout}, download=labels.youtube_download, progress=progress)
    config_yaml = prepare_dataset(Path(built['manifest']), work/'dataset')
    base = bundle_path()/bundle()['context']['file']
    model = YOLO(str(base)); epochs = int(req.get('epochs') or 80)
    def epoch_end(trainer):
        progress('Training robot detector: pass %d of up to %d' % (trainer.epoch+1, epochs))
    model.add_callback('on_fit_epoch_end', epoch_end)
    # CPU: Apple GPU training hangs with this PyTorch build.
    result = model.train(data=str(config_yaml), epochs=epochs, imgsz=1280, batch=4, device='cpu', workers=0, patience=20, seed=2026,
                         deterministic=True, plots=False, project=str(work/'runs'), name='bumper', exist_ok=True, verbose=False,
                         translate=.2, scale=.5, fliplr=.5, mosaic=1.0, close_mosaic=10)
    best = Path(result.save_dir)/'weights'/'best.pt'
    manifest = json.loads(Path(built['manifest']).read_text())
    check = [(work/'frames'/f['image'], [[b['xywh'][0]-b['xywh'][2]/2, b['xywh'][1]-b['xywh'][3]/2, b['xywh'][0]+b['xywh'][2]/2, b['xywh'][1]+b['xywh'][3]/2]
              for b in f['boxes']]) for f in manifest['frames'] if f['split'] == 'val']
    progress('Comparing new and current detector on %s' % holdout)
    new = evaluate(best, check)
    current = current_wide_weights(); old = evaluate(current, check) if current else None
    adopt = old is None or new['f1'] >= old['f1']+ADOPT_MARGIN
    report = {'engine': VERSION, 'holdout_match': holdout, 'frames': built['frames'], 'train_frames': built['train'], 'check_frames': built['val'],
              'bumpers': built['boxes'], 'matches': usable, 'new': new, 'current': old, 'adopted': adopt, 'margin': ADOPT_MARGIN, 'skipped': built['skipped']}
    if adopt:
        progress('Sharing the new detector with Neptune')
        api(config, 'adopt', {'request_id': req['id'], 'lease': req['lease'], 'weights_b64': base64.b64encode(best.read_bytes()).decode(), 'report': report}, timeout=600)
        sync_detector(config)
    return report


# ---------- polling ----------

def run_pending(config, progress, busy=lambda value: None):
    """Claim and run one queued request. Returns True when a request was handled."""
    req = api(config, 'claim').get('request')
    if not req:
        return False
    busy(True); last = [0.]
    def report(message):
        progress(message)
        if time.monotonic()-last[0] > 20:
            last[0] = time.monotonic()
            try:
                api(config, 'progress', {'request_id': req['id'], 'lease': req['lease'], 'message': str(message)[:300]})
            except Exception:
                pass
    try:
        result = prepare(config, req, report) if req['kind'] == 'prepare' else train(config, req, report)
        message = ('Prepared %d frames' % result['frames']) if req['kind'] == 'prepare' else \
            ('Adopted: held-out F1 %.2f vs %s' % (result['new']['f1'], '%.2f' % result['current']['f1'] if result['current'] else 'none')) if result['adopted'] else \
            ('Kept the current detector: new held-out F1 %.2f vs %.2f' % (result['new']['f1'], result['current']['f1']))
        api(config, 'finish', {'request_id': req['id'], 'lease': req['lease'], 'ok': True, 'message': message, 'report': result})
        progress(message)
    except Exception as error:
        try:
            api(config, 'finish', {'request_id': req['id'], 'lease': req['lease'], 'ok': False, 'message': str(error)[:400]})
        except Exception:
            pass
        progress('Robot detector request failed: '+str(error)[:200])
    finally:
        busy(False)
    return True
