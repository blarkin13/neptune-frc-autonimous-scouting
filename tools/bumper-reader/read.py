"""Read bumper crops with local Ollama; suggestions never become identity anchors.

python3 tools/bumper-reader/read.py --manifest local/robot-labels/manifest.json \
    --match 2026txcmp1_qm4 --output local/ollama-bumpers --limit 6
"""
import argparse
import base64
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ENDPOINT = 'http://127.0.0.1:11434'
SCHEMA = {'type': 'object', 'properties': {
    'digits': {'type': 'string'},
    'complete': {'type': 'boolean'},
    'readable': {'type': 'boolean'},
}, 'required': ['digits', 'complete', 'readable'], 'additionalProperties': False}
PROMPT = ('Transcribe the white printed team-number digits on the central FRC robot bumper. '
          'Use only visible pixels. Do not infer missing digits, use team knowledge, or read overlay text. '
          'If blurred or unreadable, digits must be empty and readable false. '
          'If some digits are cut off or obscured, complete must be false. '
          'Return JSON with digits (string), complete (boolean), readable (boolean).')


def suggestion(raw):
    if (not isinstance(raw, dict) or type(raw.get('complete')) is not bool
            or type(raw.get('readable')) is not bool or not isinstance(raw.get('digits'), str)):
        raise ValueError('Malformed vision result')
    digits = raw['digits'].strip()
    full = bool(raw['complete'] and raw['readable'] and re.fullmatch(r'[1-9][0-9]{0,4}', digits))
    return {'visible_digits': digits, 'suggested_team': int(digits) if full else None,
            'status': 'needs_human_review' if full else 'unknown',
            'training_eligible': False, 'identity_anchor': False}


def request(image, model, timeout):
    body = {'model': model, 'stream': False, 'format': SCHEMA,
            'messages': [{'role': 'user', 'content': PROMPT,
                          'images': [base64.b64encode(image.read_bytes()).decode()]}],
            'options': {'temperature': 0, 'num_ctx': 2048, 'num_predict': 96}, 'keep_alive': '2m'}
    req = urllib.request.Request(ENDPOINT+'/api/chat', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        result = json.load(response)
    if not result.get('done') or result.get('done_reason') == 'length':
        raise ValueError('Incomplete vision result')
    raw = json.loads(result['message']['content'])
    return {**suggestion(raw), 'raw': raw, 'model': result['model'],
            'duration_seconds': round(result.get('total_duration', 0)/1e9, 3)}


def crops(args):
    if args.image:
        yield args.image.resolve(), {'input_image': str(args.image.resolve())}
        return
    manifest = args.manifest.resolve()
    m = json.loads(manifest.read_text())
    count = 0
    for frame in m['frames']:
        match = frame['match_key']
        if match == '2026txcmp1_qm7' or match != args.match:
            continue
        image = (manifest.parent/frame['image']).resolve()
        if hashlib.sha256(image.read_bytes()).hexdigest() != frame['image_sha256']:
            raise ValueError('Source image hash mismatch: '+str(image))
        for index, box in enumerate(frame['boxes']):
            x,y,w,h = box['xywh']
            if not all(math.isfinite(v) for v in (x,y,w,h)) or w <= 0 or h <= 0:
                raise ValueError('Invalid bumper box')
            # xywh is center-based YOLO format. Pad slightly, preserving source pixels.
            left=max(0,x-w*.6);top=max(0,y-h*.65)
            width=min(1-left,w*1.2);height=min(1-top,h*1.3)
            dest=args.output/f'crop-{count:04d}.png'
            filt=f'crop=iw*{width}:ih*{height}:iw*{left}:ih*{top},scale=iw*3:ih*3:flags=lanczos'
            subprocess.run([args.ffmpeg,'-v','error','-i',str(image),'-vf',filt,
                            '-frames:v','1','-y',str(dest)],check=True)
            yield dest, {'match_key': match, 'source_sha256': frame['source_sha256'],
                         'frame_image': str(image), 'frame_image_sha256': frame['image_sha256'],
                         'box_index': index, 'box_xywh': box['xywh'], 'class_id':box['class_id']}
            count += 1
            if count >= args.limit:
                return


def report(output, rows):
    (output/'suggestions.json').write_text(json.dumps({'schema_version':1,
        'purpose':'Human review only; not verified identities or training labels',
        'results':rows},indent=2)+'\n')
    cards=[]
    for row in rows:
        src=html.escape(row['image'])
        label=html.escape(str(row.get('suggested_team') or 'Unknown'))
        detail=html.escape(json.dumps({k:row[k] for k in ('status','visible_digits','duration_seconds','error') if k in row}))
        cards.append(f'<article><img src="{src}"><h2>{label}</h2><p>{detail}</p></article>')
    (output/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Bumper readings</title>'
        '<style>body{font:16px system-ui;background:#eef2f6;padding:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}article{background:white;padding:18px;border-radius:12px}img{width:100%;max-height:220px;object-fit:contain}p{overflow-wrap:anywhere}</style>'
        '<h1>Ollama bumper suggestions</h1><p>Human review required. These readings do not change tracking or training labels.</p><main>'
        +''.join(cards)+'</main>')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--manifest',type=Path)
    source.add_argument('--image',type=Path,help='A single bumper crop, not a full match frame')
    p.add_argument('--match',default='2026txcmp1_qm4')
    p.add_argument('--output',type=Path,required=True,help='New directory for crops and review report')
    p.add_argument('--model',default='qwen2.5vl:3b')
    p.add_argument('--limit',type=int,default=6)
    p.add_argument('--timeout',type=float,default=180)
    p.add_argument('--ffmpeg',default=shutil.which('ffmpeg') or 'ffmpeg')
    args=p.parse_args()
    if args.match=='2026txcmp1_qm7':p.error('Q7 is reserved; use another match')
    if args.limit<1:p.error('--limit must be positive')
    # Pin local inference to a model already downloaded; never pull models implicitly.
    with urllib.request.urlopen(ENDPOINT+'/api/tags',timeout=10) as r:models=json.load(r)['models']
    model=next((m for m in models if m['name']==args.model),None)
    if model is None:p.error('Model is not installed locally')
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for image,meta in crops(args):
        dest=args.output/image.name
        if image!=dest:shutil.copyfile(image,dest)
        row={**meta,'image':dest.name,'image_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
             'model_digest':model['digest'],'training_eligible':False,'identity_anchor':False}
        start=time.monotonic()
        try:row.update(request(dest,args.model,args.timeout))
        except Exception as error:row.update(status='error',suggested_team=None,error=str(error))
        row['wall_seconds']=round(time.monotonic()-start,3)
        rows.append(row);report(args.output,rows)
        print(json.dumps({k:row[k] for k in ('image','status','suggested_team','wall_seconds')}),flush=True)
    if not rows:raise SystemExit('No matching crops found')
    print('Review:',args.output/'report.html',flush=True)
    if all(r['status']=='error' for r in rows):raise SystemExit('All inference requests failed')


if __name__=='__main__':main()
