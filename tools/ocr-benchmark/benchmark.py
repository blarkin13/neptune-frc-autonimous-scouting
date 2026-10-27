"""Measured OCR benchmark: bumper team numbers and scoreboard clock/scores on hand-read frames.

Usage (repository root, a Python with OpenCV; RapidOCR for --backend rapidocr):
  python tools/ocr-benchmark/benchmark.py --images ../../local --backend apple-vision --out local/ocr-benchmark/av.json

--images is the folder holding robot-labels/ and the other saved frames named in truth.json (normally the
main checkout's local/). Every image is checked against its SHA-256 before use. Nothing here trains or tunes on
Q7, and official results are not used: the truth is what a person reads on the frame.

Bumper methods
  track-crop   the tracker's per-detection crop before 2026-10-26 (chassis included, 2x upscale), first
               roster_match token
  tiles        the facts pipeline's six overlapping wide-shot tiles (2x), reads attributed to the labelled box
  bumper       neptune_ocr.bumper_crop + read_team (tight strip crop enlarged to a fixed strip height, white-digit
               map first and the coloured crop for bumpers without an exact read, digit fragments joined,
               roster-constrained)
Scoreboard: the top 30% of the frame (as the facts pipeline crops it), each layout profile of the season in
order, the same parse and context rules as overlay_samples; then the colour-anchored fallback
(neptune_facts.parse_overlay_generic) for frames no profile accepts.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Built-in game rules only: an installed game pack in ~/.neptune-helper/games replaces the season's layout list.
os.environ.setdefault('NEPTUNE_GAMES_HOME', tempfile.mkdtemp(prefix='ocr-benchmark-games-'))
sys.path.insert(0, str(ROOT / 'engine'))
import cv2  # noqa: E402
import neptune_facts  # noqa: E402
import neptune_ocr  # noqa: E402

TRUTH = Path(__file__).with_name('truth.json')


def load(images, rel, sha):
    path = Path(images) / rel
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise SystemExit('Image changed since it was labelled: %s' % path)
    return path


def old_track_crop(W, H, box, upscale=2):
    """neptune_tracking.crop_box geometry around a bumper box (pixels of the source frame)."""
    x, y, w, h = box
    x0, x1 = x - 0.35 * w - 2, x + w + 0.35 * w + 2
    y0, y1 = y - 1.2 * h - 2, y + h + 0.6 * h + 1.5
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))
    return (x0, y0, x1, y1), upscale


def old_track_decide(items, crop, box, teams):
    (x0, y0, x1, y1), _ = crop
    w, h = x1 - x0, y1 - y0
    inner = ((box[0] - x0) / w, (box[1] - y0) / h, (box[0] + box[2] - x0) / w, (box[1] + box[3] - y0) / h)
    found = []
    for item in items:
        cx, cy = item['x'] + item['w'] / 2, item['y'] + item['h'] / 2
        mx = 0.15 * (inner[2] - inner[0]) + 0.05
        if not (inner[0] - mx <= cx <= inner[2] + mx and inner[1] - (inner[3] - inner[1]) * 1.2 - 0.05 <= cy <= inner[3] + 0.08):
            continue
        for token in re.findall(r'\S+', item['t']):
            m = neptune_facts.roster_match(token, teams)
            if m and m[0] in ('exact', 'corrected'):
                found.append((m[1], m[0]))
    return found


def score_bumpers(rows):
    """rows: [(truth dict, [(team, kind)])] -> counts. A box's answer is its exact read if any, else corrected."""
    out = Counter()
    for b, found in rows:
        teams = {t for t, k in found if k == 'exact'} or {t for t, k in found}
        answer = next(iter(teams)) if len(teams) == 1 else (None if not teams else 'conflict')
        g = b['legible']
        out[g + ' boxes'] += 1
        if answer is None:
            out[g + ' unread'] += 1
        elif answer == b['team']:
            out[g + ' correct'] += 1
        else:
            out[g + ' wrong'] += 1
    return dict(out)


def bumpers(truth, images, backend, work, methods):
    rosters = truth['rosters']
    frames = {}
    for b in truth['bumpers']:
        frames.setdefault(b['frame'], []).append(b)
    results = {m: [] for m in methods}
    jobs = []   # (method, path, payload)
    for fid, boxes in sorted(frames.items()):
        path = load(images, 'robot-labels/images/%s.jpg' % fid, boxes[0]['sha256'])
        image = cv2.imread(str(path))
        H, W = image.shape[:2]
        teams = set(rosters[boxes[0]['match_key']]['red'] + rosters[boxes[0]['match_key']]['blue'])
        if 'tiles' in methods:
            top = 0.24
            cam = image[int(H * top):]
            ch = cam.shape[0]
            for i, (x0, x1, y0, y1) in enumerate(neptune_facts.TILES):
                tile = cam[int(ch * y0):int(ch * y1), int(W * x0):int(W * x1)]
                tile = cv2.resize(tile, (tile.shape[1] * 2, tile.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
                p = work / ('tile_%s_%d.jpg' % (fid, i))
                cv2.imwrite(str(p), tile, [cv2.IMWRITE_JPEG_QUALITY, 90])
                jobs.append(('tiles', p, (fid, i, boxes, teams, top)))
        for b in boxes:
            x, y, w, h = b['xywh']
            box = (x * W, y * H, w * W, h * H)
            if 'track-crop' in methods:
                crop = old_track_crop(W, H, box)
                (x0, y0, x1, y1), s = crop
                c = cv2.resize(image[y0:y1, x0:x1], ((x1 - x0) * s, (y1 - y0) * s), interpolation=cv2.INTER_CUBIC)
                p = work / ('old_%s_%d.bmp' % (fid, b['box']))
                cv2.imwrite(str(p), c)
                jobs.append(('track-crop', p, (b, crop, box, teams)))
            if 'bumper' in methods:
                crop, inner = neptune_ocr.bumper_crop(image, box, white=True)
                p = work / ('new_%s_%d.bmp' % (fid, b['box']))
                cv2.imwrite(str(p), crop)
                cv2.imwrite(str(work / ('col_%s_%d.bmp' % (fid, b['box']))), neptune_ocr.bumper_crop(image, box)[0])
                jobs.append(('bumper', p, (b, inner, rosters[b['match_key']])))
    t0 = time.time()
    texts = backend.recognize([j[1] for j in jobs])
    # Second pass, as in neptune_tracking.track_reads: the coloured crop for bumpers without an exact read.
    retry = []
    for method, p, (b, inner, roster) in (j for j in jobs if j[0] == 'bumper'):
        r = neptune_ocr.read_team(texts.get(str(p), []), roster, alliance=b['alliance'], inner=inner)
        if not r or r['kind'] != 'exact':
            retry.append(work / p.name.replace('new_', 'col_'))
    second = backend.recognize(retry)
    seconds = time.time() - t0
    tile_reads = {}
    for method, p, payload in jobs:
        items = texts.get(str(p), [])
        if method == 'track-crop':
            b, crop, box, teams = payload
            results[method].append((b, old_track_decide(items, crop, box, teams)))
        elif method == 'bumper':
            b, inner, roster = payload
            r = neptune_ocr.read_team(items, roster, alliance=b['alliance'], inner=inner)
            col = str(work / p.name.replace('new_', 'col_'))
            if (not r or r['kind'] != 'exact') and col in second:
                r = neptune_ocr.read_team(items + second[col], roster, alliance=b['alliance'], inner=inner)
            results[method].append((b, [(r['team'], r['kind'])] if r and r['kind'] in ('exact', 'corrected') else []))
        else:
            fid, i, boxes, teams, top = payload
            x0, x1, y0, y1 = neptune_facts.TILES[i]
            for item in items:
                for token in re.findall(r'\S+', item['t']):
                    m = neptune_facts.roster_match(token, teams)
                    if not m or m[0] not in ('exact', 'corrected'):
                        continue
                    cx = x0 + (item['x'] + item['w'] / 2) * (x1 - x0)
                    cy = top + (1 - top) * (y0 + (item['y'] + item['h'] / 2) * (y1 - y0))
                    for b in boxes:   # attributed to the labelled box containing the read's centre
                        bx, by, bw, bh = b['xywh']
                        if bx - 0.1 * bw <= cx <= bx + 1.1 * bw and by - 0.5 * bh <= cy <= by + 1.5 * bh:
                            tile_reads.setdefault((fid, b['box']), []).append((m[1], m[0]))
    if 'tiles' in methods:
        results['tiles'] = [(b, tile_reads.get((b['frame'], b['box']), [])) for b in truth['bumpers']]
    return {m: score_bumpers(v) for m, v in results.items()}, seconds, {m: [[b['frame'], b['box'], b['team'], f] for b, f in v] for m, v in results.items()}


def scoreboard(truth, images, backend, work, generic=True, no_sides=False):
    frames = []
    for n, s in enumerate(truth['scoreboard']):
        image = cv2.imread(str(load(images, s['image'], s['sha256'])))
        p = work / ('ov_%03d.jpg' % n)
        cv2.imwrite(str(p), image[:int(image.shape[0] * 0.30)], [cv2.IMWRITE_JPEG_QUALITY, 90])
        frames.append((s, p))
    t0 = time.time()
    texts = backend.recognize([p for _, p in frames])
    seconds = time.time() - t0
    counts, detail = Counter(), []
    for s, p in frames:
        items = texts.get(str(p), [])
        season, rules = neptune_facts.season_rules(s['match_key'])
        got = {'clock': None, 'red': None, 'blue': None, 'profile': None}
        for pid, profile in rules.get('layout_profiles', neptune_facts.LAYOUTS).items():
            r = neptune_facts.parse_overlay(items, profile)
            if r['clock'] is None or not neptune_facts.overlay_clock_context(r, profile) or not r['marker']:
                continue
            if hasattr(neptune_facts, 'roster_sides') and not no_sides:   # as detect_layout with the match roster
                own, cross = neptune_facts.roster_sides(r, truth['rosters'][s['match_key']])
                if cross > own:
                    continue
            got = {'clock': r['clock_value'], 'profile': pid,
                   'red': int(r['red']['t']) if r['red'] is not None and r['labels'] else None,
                   'blue': int(r['blue']['t']) if r['blue'] is not None and r['labels'] else None}
            break
        if got['profile'] is None and generic and hasattr(neptune_facts, 'parse_overlay_generic'):
            g = neptune_facts.parse_overlay_generic(items, truth['rosters'][s['match_key']])
            if g:
                got = {'clock': g['clock_value'], 'red': g['red_value'], 'blue': g['blue_value'], 'profile': 'generic'}
        event = s['match_key'].split('_')[0]
        for field in ('clock', 'red', 'blue'):
            key = 'clock' if field == 'clock' else 'score'
            outcome = 'unread' if got[field] is None else 'correct' if got[field] == s[field] else 'wrong'
            counts['%s %s' % (key, outcome)] += 1
            counts['%s %s %s' % (event, key, outcome)] += 1
        detail.append({'image': s['image'], 'truth': [s['clock'], s['red'], s['blue']], 'read': [got['clock'], got['red'], got['blue']], 'profile': got['profile']})
    return dict(counts), seconds, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', required=True)
    ap.add_argument('--backend', default='auto')
    ap.add_argument('--methods', default='track-crop,tiles,bumper')
    ap.add_argument('--no-generic', action='store_true', help='scoreboard: layout profiles only, without the roster side check (the behaviour before 2026-10-26)')
    ap.add_argument('--out')
    a = ap.parse_args()
    truth = json.loads(TRUTH.read_text())
    backend = neptune_ocr.BACKENDS[a.backend]() if a.backend != 'auto' else neptune_ocr.select_backend()
    methods = [m for m in a.methods.split(',') if m]
    if 'bumper' in methods and not hasattr(neptune_ocr, 'bumper_crop'):
        methods.remove('bumper')
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        b, bs, bdetail = bumpers(truth, a.images, backend, work, methods)
        s, ss, sdetail = scoreboard(truth, a.images, backend, work, generic=not a.no_generic, no_sides=a.no_generic)
    report = {'backend': backend.describe(), 'bumpers': b, 'bumper_seconds': round(bs, 1), 'scoreboard': s, 'scoreboard_seconds': round(ss, 1),
              'bumper_detail': bdetail, 'scoreboard_detail': sdetail}
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('detail')}, indent=1, sort_keys=True))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
