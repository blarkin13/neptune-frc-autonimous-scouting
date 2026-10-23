"""Score robot/bumper detectors against the labelled frames (local/robot-labels).

A labelled bumper counts as found when a detection matches it: for bumper detectors by IoU >= 0.3 (one-to-one),
for whole-robot detectors when the bumper's centre lies inside a robot box (one bumper per box). Precision is
the share of detections that matched a labelled bumper. Reported per match and per camera band.
"""
import json
from pathlib import Path

LABELS = Path(__file__).resolve().parents[2]/'local'/'robot-labels'
WIDE = (.24, .6506)          # wide-camera band of the 2026 broadcast layout (normalized y)


def iou(a, b):
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    w = max(0., min(ax1, bx1)-max(ax0, bx0)); h = max(0., min(ay1, by1)-max(ay0, by0))
    u = (ax1-ax0)*(ay1-ay0)+(bx1-bx0)*(by1-by0)-w*h
    return w*h/u if u > 0 else 0.


def xyxy(cx, cy, w, h):
    return [cx-w/2, cy-h/2, cx+w/2, cy+h/2]


def band(box):
    cy = (box[1]+box[3])/2
    return 'wide' if WIDE[0] <= cy <= WIDE[1] else 'closeup'


def score(truth, pred, kind='bumper'):
    """truth/pred: lists of xyxy boxes for one frame -> (matched, truth_count, pred_count) per band."""
    out = {}
    used = set()
    for t in truth:
        b = band(t); o = out.setdefault(b, [0, 0, 0]); o[1] += 1
        best = None
        for i, p in enumerate(pred):
            if i in used:
                continue
            if kind == 'bumper':
                v = iou(t, p)
                if v >= .3 and (best is None or v > best[0]):
                    best = (v, i)
            else:
                cx, cy = (t[0]+t[2])/2, (t[1]+t[3])/2
                if p[0] <= cx <= p[2] and p[1] <= cy <= p[3]:
                    area = (p[2]-p[0])*(p[3]-p[1])
                    if best is None or area < best[0]:
                        best = (area, i)
        if best:
            used.add(best[1]); o[0] += 1
    for p in pred:
        out.setdefault(band(p), [0, 0, 0])[2] += 1
    return out


def summarize(rows):
    total = {}
    for match, bands in rows:
        for b, (m, t, p) in bands.items():
            for key in ((match, b), (match, 'all'), ('all', b), ('all', 'all')):
                s = total.setdefault(key, [0, 0, 0]); s[0] += m; s[1] += t; s[2] += p
    return {'%s/%s' % k: {'recall': round(m/t, 3) if t else None, 'precision': round(m/p, 3) if p else None, 'bumpers': t, 'detections': p}
            for k, (m, t, p) in sorted(total.items())}


def labelled():
    m = json.loads((LABELS/'manifest.json').read_text())
    for f in m['frames']:
        yield f, [xyxy(*b['xywh']) for b in f['boxes']]
