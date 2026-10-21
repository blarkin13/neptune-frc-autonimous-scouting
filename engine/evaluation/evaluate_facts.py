#!/usr/bin/env python3
"""Evaluate the facts pipeline on a manifest of matches with official alliance results.

  run        analyse each video with one OCR backend; records wall time and peak memory of the whole
             process tree (Python + FFmpeg + OCR), and any failure
  reference  phase-boundary reference from 10 fps clock reads around each estimated boundary
  sheets     contact sheets of robot-identity evidence for human review (writes a labels template)
  score      metrics: match verification (true and wrong claims), scoreboard errors and coverage,
             phase timing errors, identity recall and (with review labels) precision, runtime, memory

Example
  python3 evaluate_facts.py run --manifest apollo_2026.json --videos DIR --out OUT --backend apple-vision --split tuning
  python3 evaluate_facts.py score --manifest apollo_2026.json --out OUT --labels labels.json
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def claim(m, manifest):
    return {'key': m['key'], 'title': m['event'] + ' · Qualification ' + m['key'].split('qm')[-1], 'roster': m['roster']}


# ------------------------------------------------------------------ run

def tree_rss_kb(root_pid):
    """Sum of RSS for root_pid's process group (macOS and Linux ps)."""
    out = subprocess.run(['ps', '-A', '-o', 'pgid=,rss='], capture_output=True, text=True).stdout
    total = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == str(root_pid):
            total += int(parts[1])
    return total


def run_one(args):
    """Child process: analyse one match and write facts.json / payload.json / error.json."""
    import neptune_facts
    import neptune_ocr
    manifest = json.loads(Path(args.manifest).read_text())
    m = next(x for x in manifest['matches'] if x['key'] == args.key)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    video = Path(args.videos) / m['video']
    try:
        backend = neptune_ocr.select_backend(args.backend)
        facts = neptune_facts.analyze_video(video, claim(m, manifest), work, metadata_title=m.get('video_title'), backend=backend, source_sha256='eval:' + m['key'], every=args.every)
        import neptune_learning
        payload = neptune_facts.build_payload(facts, claim(m, manifest), 'eval:' + m['key'], int(facts['source']['duration_s'] * 1000))
        neptune_learning.seal(work, facts, payload, claim(m, manifest))
    except Exception as error:   # recorded as a failure in the report
        (work / 'error.json').write_text(json.dumps({'type': type(error).__name__, 'message': str(error)}))
        raise SystemExit(1)


def run(args):
    manifest = json.loads(Path(args.manifest).read_text())
    out = Path(args.out) / args.backend
    out.mkdir(parents=True, exist_ok=True)
    for m in manifest['matches']:
        if args.split and m['split'] != args.split or args.only and m['key'] not in args.only:
            continue
        work = out / m['key']
        if work.exists():
            shutil.rmtree(work)   # each run is a fresh bundle; sealed originals are read-only
        cmd = [args.python or sys.executable, __file__, 'run-one', '--manifest', args.manifest, '--key', m['key'], '--videos', args.videos,
               '--work', str(work), '--backend', args.backend, '--every', str(args.every)]
        started = time.time()
        child = subprocess.Popen(cmd, start_new_session=True)
        peak = [0]

        def sample():
            while child.poll() is None:
                peak[0] = max(peak[0], tree_rss_kb(child.pid))
                time.sleep(0.2)
        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        code = child.wait()
        sampler.join()
        work.mkdir(parents=True, exist_ok=True)
        record = {'key': m['key'], 'backend': args.backend, 'wall_s': round(time.time() - started, 1), 'peak_tree_rss_mb': round(peak[0] / 1024, 1), 'exit': code,
                  'machine': os.uname().machine, 'python': args.python or sys.executable}
        (work / 'run.json').write_text(json.dumps(record))
        print(json.dumps(record), flush=True)


# ------------------------------------------------------------------ phase reference

def reference(args):
    """For each boundary, read the clock at 10 fps in ±4 s and find the display transitions.
    end ref = first frame showing 0:00 + 0.5 s; start ref = first frame showing L-1 − 0.5 s. Under either
    display convention (floor or ceiling) these equal the quantity the 1 fps estimator targets."""
    import neptune_facts
    import neptune_ocr
    manifest = json.loads(Path(args.manifest).read_text())
    backend = neptune_ocr.select_backend('apple-vision')
    profile = neptune_facts.LAYOUTS['frc-2026-field-overlay-v1']
    rules = neptune_facts.RULES['seasons']['2026']
    out = Path(args.out)
    refs = {}
    for m in manifest['matches']:
        f = out / args.backend / m['key'] / 'facts.json'
        if not f.is_file():
            continue
        facts = json.loads(f.read_text())
        video = Path(args.videos) / m['video']
        r = {}
        for name, length in (('auto', rules['auto_seconds']), ('teleop', rules['teleop_seconds'])):
            p = facts['periods'].get(name)
            if not p:
                continue
            for edge, guess, target in (('start', p['start'], length - 1), ('end', p['end'], 0)):
                folder = out / 'reference' / m['key'] / ('%s_%s' % (name, edge))
                neptune_facts.clear(folder, '*.jpg')
                t0 = max(0.0, guess - 4)
                neptune_facts.ffmpeg(['-ss', '%.3f' % t0, '-i', str(video), '-t', '8', '-vf', 'fps=10:round=up,crop=iw:ih*%g:0:0' % profile['band'], '-q:v', '3', str(folder / 'r_%05d.jpg')])
                frames = neptune_facts.frames_at(folder, 'r_*.jpg', t0, 10.0)
                texts = backend.recognize([p_ for _, p_ in frames])
                hit, seen_one = None, False
                for t, path in frames:
                    o = neptune_facts.parse_overlay(texts.get(str(path), []), profile)
                    if o['clock'] is None or not o['labels']:
                        continue
                    v = o['clock_value']
                    # The end of auto never shows 0:00 on this overlay (0:01 is followed by 2:20), so the
                    # first frame after 0:01 counts as the 0:00 transition.
                    if v == target or (target == 0 and seen_one and v != 1):
                        hit = t
                        break
                    seen_one = seen_one or v == 1
                r['%s_%s' % (name, edge)] = None if hit is None else round(hit + (0.5 if edge == 'end' else -0.5), 2)
        refs[m['key']] = r
        print(m['key'], r, flush=True)
    (out / 'phase_reference.json').write_text(json.dumps(refs, indent=1))


# ------------------------------------------------------------------ review sheets

def sheets(args):
    """Contact sheets of identity evidence (one row per identity claim) and a labels template."""
    from PIL import Image, ImageDraw
    manifest = json.loads(Path(args.manifest).read_text())
    out = Path(args.out)
    sheet_dir = out / 'review' / args.backend
    sheet_dir.mkdir(parents=True, exist_ok=True)
    template, cards = {}, []
    import base64
    import io
    for m in manifest['matches']:
        work = out / args.backend / m['key']
        if not (work / 'facts.json').is_file():
            continue
        facts = json.loads((work / 'facts.json').read_text())
        rows = []
        for team, ident in sorted(facts['bumpers']['identities'].items()):
            if ident['status'] == 'not_identified':
                continue
            crops = []
            # Every confirming frame (one crop per frame), so a reviewer judges the whole claim.
            verified = [r for r in facts['bumpers']['reads'] if str(r.get('team')) == str(team) and r['kind'] == 'exact' and r.get('background') == ident['alliance']]
            shown, seen = [], set()
            for r in sorted(verified, key=lambda r: r['t']) or ident['evidence']:
                if r['t'] not in seen:
                    seen.add(r['t'])
                    shown.append(r)
            for e in shown[:12]:
                img = Image.open(work / e['frame'])
                W, H = img.size
                x, y, w, h = e['box']
                box = (max(0, int((x - 1.5 * w) * W)), max(0, int((y - 2.5 * h) * H)), min(W, int((x + 2.5 * w) * W)), min(H, int((y + 3.5 * h) * H)))
                c = img.crop(box)
                c.thumbnail((300, 200))
                crops.append((c, '%s t=%.0f "%s" %s %s' % (e.get('view'), e['t'], e.get('text'), e.get('kind'), e.get('background'))))
            rows.append(('%s %s %s' % (team, ident['alliance'], ident['status']), crops))
            encoded = []
            for c, cap in crops:
                buf = io.BytesIO()
                c.convert('RGB').save(buf, 'JPEG', quality=80)
                encoded.append((base64.b64encode(buf.getvalue()).decode(), cap))
            cards.append((m['key'], team, ident['status'], ident['alliance'], encoded))
            template.setdefault(m['key'], {})[str(team)] = {'status': ident['status'], 'label': None,
                                                           'choices': 'correct = this is the team\'s robot bumper on the field; wrong_robot; not_a_robot; unreadable'}
        if not rows:
            continue
        per_row = 6
        lines = sum((len(c) + per_row - 1) // per_row or 1 for _, c in rows)
        sheet = Image.new('RGB', (180 + per_row * 310, 30 + 230 * lines), 'white')
        d = ImageDraw.Draw(sheet)
        d.text((8, 8), '%s · %s' % (m['key'], args.backend), fill='black')
        line = 0
        for label, crops in rows:
            y = 30 + 230 * line
            d.text((8, y + 90), label, fill='black')
            for k, (c, cap) in enumerate(crops):
                yy = y + 230 * (k // per_row)
                sheet.paste(c, (180 + 310 * (k % per_row), yy))
                d.text((180 + 310 * (k % per_row), yy + 205), cap[:48], fill='black')
            line += (len(crops) + per_row - 1) // per_row or 1
        sheet.save(sheet_dir / ('%s.jpg' % m['key']), quality=85)
    (sheet_dir / 'labels-template.json').write_text(json.dumps(template, indent=1))
    (sheet_dir / 'review.html').write_text(review_page(cards, args.backend))
    print('sheets and review.html in', sheet_dir)


def review_page(cards, backend):
    """Self-contained page: one card per identity claim with its evidence crops; saves labels.json."""
    import html
    rows = []
    for key, team, status, alliance, crops in cards:
        imgs = ''.join('<figure><img src="data:image/jpeg;base64,%s"><figcaption>%s</figcaption></figure>' % (b64, html.escape(cap)) for b64, cap in crops)
        name = '%s|%s' % (key, team)
        opts = ''.join('<label><input type="radio" name="%s" value="%s"> %s</label>' % (html.escape(name), v, t) for v, t in
                       (('correct', 'Correct robot'), ('wrong_robot', 'Wrong robot'), ('not_a_robot', 'Not a robot'), ('unreadable', 'Cannot tell')))
        rows.append('<section><h2>%s · team %s <small>(%s, %s alliance)</small></h2><div class="crops">%s</div><div class="opts">%s</div></section>' % (
            html.escape(key), team, status, alliance, imgs, opts))
    return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot Identity Review</title><style>
:root{--bg:#fff;--fg:#111;--muted:#666;--line:#ddd;--accent:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--muted:#aaa;--line:#333;--accent:#6aa9ff}}
body{background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}
section{border-top:1px solid var(--line);padding:12px 0}h2{font-size:16px;margin:0 0 8px}small{color:var(--muted);font-weight:400}
.crops{display:flex;gap:8px;flex-wrap:wrap}figure{margin:0;max-width:260px}img{max-width:100%%;display:block}
figcaption{font-size:12px;color:var(--muted)}.opts{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px}
button{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:10px 16px;font-size:15px;position:sticky;top:8px}
</style></head><body><h1>Robot identity review · %s</h1>
<p>For each claim, look at the crops: is the number on the bumper of that team's robot, on the field? Then save the labels file and
give it to <code>evaluate_facts.py score --labels</code> and <code>neptune_learning.py import-labels</code>.</p>
<p><label>Reviewer name <input id="reviewer"></label> <button id="save">Save labels.json</button> <span id="count"></span></p>
%s
<script>
const save=document.getElementById('save'),count=document.getElementById('count');
function collect(){const out={};let n=0;document.querySelectorAll('input[type=radio]:checked').forEach(r=>{const [k,t]=r.name.split('|');(out[k]=out[k]||{})[t]={label:r.value};n++});return [out,n]}
document.addEventListener('change',()=>{count.textContent=collect()[1]+' labelled'});
save.onclick=()=>{const [out]=collect();out._reviewer=document.getElementById('reviewer').value;
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download='labels.json';a.click()};
</script></body></html>''' % (html.escape(backend), ''.join(rows))


# ------------------------------------------------------------------ score

def wrong_claim_tests(manifest, out, backend):
    """Re-run identity verification from the saved overlay readings against claims for other matches."""
    import neptune_facts
    results = []
    ms = manifest['matches']
    rules = neptune_facts.RULES['seasons']['2026']
    for i, m in enumerate(ms):
        work = out / backend / m['key']
        raw = work / 'raw-overlay.jsonl'
        if not raw.is_file():
            continue
        rows = [json.loads(l) for l in raw.read_text().splitlines()]
        band = [(r['t'], work / r['frame']) for r in rows]
        texts = {str(work / r['frame']): r['items'] for r in rows}
        profile = neptune_facts.LAYOUTS['frc-2026-field-overlay-v1']
        samples, _ = neptune_facts.overlay_samples(band, texts, profile, rules, work)
        other = ms[(i + 1) % len(ms)]
        cases = [('true claim', claim(m, manifest), m['video_title'], True),
                 ('other match, same event', claim(other, manifest), m['video_title'], False),
                 ('same number, other event', dict(manifest['other_event_claims'][0], title=manifest['other_event_claims'][0]['event'] + ' · Qualification 7',
                                                    key=m['key'].split('_')[0].replace('txcmp2', 'txfar') + '_' + m['key'].split('_')[1]), m['video_title'], False),
                 ('right roster, wrong number', dict(claim(m, manifest), key=m['key'].rsplit('qm', 1)[0] + 'qm' + str(int(m['key'].rsplit('qm', 1)[1]) + 1)), None, False)]
        for name, c, title, should_pass in cases:
            try:
                v = neptune_facts.verify_identity(samples, c, title, None)
                outcome = v['status']
            except neptune_facts.FactsError as error:
                outcome = 'rejected: ' + str(error)[:160]
            correct = (outcome == 'verified') if should_pass else outcome.startswith('rejected')
            results.append({'video': m['key'], 'case': name, 'claim': c['key'], 'outcome': outcome, 'correct': correct})
    return results


def score(args):
    manifest = json.loads(Path(args.manifest).read_text())
    out = Path(args.out)
    labels = json.loads(Path(args.labels).read_text()) if args.labels else {}
    refs = json.loads((out / 'phase_reference.json').read_text()) if (out / 'phase_reference.json').is_file() else {}
    report = {'backend': args.backend, 'matches': [], 'wrong_claims': wrong_claim_tests(manifest, out, args.backend)}
    for m in manifest['matches']:
        work = out / args.backend / m['key']
        runrec = json.loads((work / 'run.json').read_text()) if (work / 'run.json').is_file() else {}
        row = {'key': m['key'], 'split': m['split'], 'wall_s': runrec.get('wall_s'), 'peak_tree_rss_mb': runrec.get('peak_tree_rss_mb')}
        if (work / 'error.json').is_file() or not (work / 'facts.json').is_file():
            row['failure'] = json.loads((work / 'error.json').read_text()) if (work / 'error.json').is_file() else 'not run'
            report['matches'].append(row)
            continue
        f = json.loads((work / 'facts.json').read_text())
        off = m['official']
        row['identity'] = f['identity']['status']
        row['identity_missing'] = f['identity']['missing']
        R = f['results_screen']
        row['results_status'] = R.get('status')
        if R.get('status') != 'unknown':
            row['final_error'] = {s: R[s] - off[s]['total'] for s in ('red', 'blue')}
            comps = R.get('components') or {}
            row['results_auto_error'] = {}
            for s in ('red', 'blue'):
                c = comps.get(s, {})
                if 'auto fuel' in c and 'auto tower' in c:
                    row['results_auto_error'][s] = c['auto fuel']['value'] + c['auto tower']['value'] - off[s]['auto']
                else:
                    row['results_auto_error'][s] = None
            row['results_components_complete'] = R.get('components_complete')
            row['results_checksum'] = R.get('checksum_ok')
            row['penalty_vs_official'] = {s: (comps.get(s, {}).get('penalty', {}).get('value'), off[s]['foul_points_awarded']) for s in ('red', 'blue')}
        D = f['displayed']
        row['display_at_teleop_start_minus_official_auto'] = {s: (None if D[s].get('at_teleop_start', {}).get('value') is None else D[s]['at_teleop_start']['value'] - off[s]['auto']) for s in ('red', 'blue')}
        row['display_endgame_increase_minus_official_hub_endgame'] = {s: (None if D[s].get('endgame_increase', {}).get('value') is None else D[s]['endgame_increase']['value'] - off[s]['hub_endgame'] - off[s]['endgame_tower']) for s in ('red', 'blue')}
        row['last_live_minus_official_total_minus_fouls'] = {s: (None if D[s]['last_live']['value'] is None else D[s]['last_live']['value'] - (off[s]['total'] - off[s]['foul_points_awarded'])) for s in ('red', 'blue')}
        row['coverage'] = {s: f['coverage'][s]['share'] for s in ('red', 'blue')}
        row['coverage_gaps'] = {s: f['coverage'][s]['gaps'] for s in ('red', 'blue')}
        row['rejected_score_readings'] = {s: len(f['rejected']['score_readings'][s]) for s in ('red', 'blue')}
        row['score_decreases'] = {s: len(f['score_decreases'][s]) for s in ('red', 'blue')}
        row['lead_changes'] = len(f['lead']['changes'])
        row['lead_readable_share'] = f['lead']['readable_share']
        ref = refs.get(m['key'], {})
        row['phase_error_s'] = {}
        for name in ('auto', 'teleop'):
            p = f['periods'].get(name)
            for edge in ('start', 'end'):
                k = '%s_%s' % (name, edge)
                row['phase_error_s'][k] = None if not p or ref.get(k) is None else round(p[edge] - ref[k], 2)
        row['periods'] = {k: (None if not p else {'uncertainty_s': p['uncertainty_s'], 'start_observed': p['start_observed'], 'end_observed': p['end_observed']}) for k, p in f['periods'].items()}
        row['endgame'] = {k: f['endgame'][k] for k in ('status', 'shift_indicator')} if f['endgame'] else None
        ids = f['bumpers']['identities']
        row['identities'] = {t: {'status': i['status'], 'frames': len(i['verified_frames']), 'exact': i['exact_reads'], 'corrected': i['corrected_reads']} for t, i in ids.items()}
        row['confirmed'] = sum(i['status'] == 'confirmed' for i in ids.values())
        row['candidates'] = sum(i['status'] == 'candidate' for i in ids.values())
        lab = labels.get(m['key'], {}) if isinstance(labels.get(m['key']), dict) else {}
        row['review'] = {t: lab.get(t, {}).get('label') for t in ids if ids[t]['status'] != 'not_identified'}
        row['bumper_reads'] = {'exact': sum(r['kind'] == 'exact' for r in f['bumpers']['reads']), 'corrected': sum(r['kind'] == 'corrected' for r in f['bumpers']['reads']),
                               'ambiguous': sum(r['kind'] == 'ambiguous' for r in f['bumpers']['reads']), 'rejected': len(f['bumpers']['rejected'])}
        report['matches'].append(row)
    report['aggregate'] = aggregate(report)
    (out / ('report-%s.json' % args.backend)).write_text(json.dumps(report, indent=1))
    print(json.dumps(report['aggregate'], indent=1))


def aggregate(report):
    agg = {}
    for split in ('tuning', 'heldout', 'heldout2', 'heldout3', 'all'):
        rows = [r for r in report['matches'] if split == 'all' or r['split'] == split]
        if not rows:
            continue
        ok = [r for r in rows if 'failure' not in r]
        a = {'matches': len(rows), 'failures': [(r['key'], r['failure']) for r in rows if 'failure' in r]}
        if ok:
            a['identity_verified'] = sum(r['identity'] == 'verified' for r in ok)
            fe = [abs(v) for r in ok if 'final_error' in r for v in r['final_error'].values()]
            a['final_screen_found'] = sum('final_error' in r for r in ok)
            a['final_exact'] = sum(v == 0 for v in fe)
            a['final_alliances'] = len(fe)
            ae = [abs(v) for r in ok for v in (r.get('results_auto_error') or {}).values() if v is not None]
            a['results_auto_exact'] = '%d/%d' % (sum(v == 0 for v in ae), len(ae))
            de = [abs(v) for r in ok for v in r['display_at_teleop_start_minus_official_auto'].values() if v is not None]
            a['display_at_teleop_start_vs_official_auto_mae'] = round(statistics.mean(de), 2) if de else None
            ee = [abs(v) for r in ok for v in r['display_endgame_increase_minus_official_hub_endgame'].values() if v is not None]
            a['display_endgame_increase_vs_official_endgame_mae'] = round(statistics.mean(ee), 2) if ee else None
            cov = [v for r in ok for v in r['coverage'].values()]
            a['score_coverage_mean'] = round(statistics.mean(cov), 3)
            a['score_coverage_min'] = min(cov)
            pe = [abs(v) for r in ok for v in r['phase_error_s'].values() if v is not None]
            a['phase_error_abs_mean_s'] = round(statistics.mean(pe), 2) if pe else None
            a['phase_error_abs_max_s'] = max(pe) if pe else None
            a['phase_boundaries_measured'] = len(pe)
            within = [abs(r['phase_error_s'][k]) <= (r['periods'][k.split('_')[0]] or {}).get('uncertainty_s', 0) for r in ok for k in r['phase_error_s'] if r['phase_error_s'][k] is not None]
            a['phase_errors_within_stated_uncertainty'] = '%d/%d' % (sum(within), len(within))
            a['identity_recall_confirmed'] = '%d/%d' % (sum(r['confirmed'] for r in ok), 6 * len(ok))
            a['identity_recall_confirmed_or_candidate'] = '%d/%d' % (sum(r['confirmed'] + r['candidates'] for r in ok), 6 * len(ok))
            for status in ('confirmed', 'candidate'):
                labelled = [(r['review'][t], t) for r in ok for t in r['review'] if r['identities'][t]['status'] == status and r['review'][t]]
                a['precision_%s' % status] = ('%d/%d' % (sum(l == 'correct' for l, _ in labelled), len(labelled))) if labelled else 'not reviewed'
            w = [s for s in (r.get('wall_s') for r in ok) if s]
            a['wall_s_median'] = statistics.median(w) if w else None
            a['wall_s_max'] = max(w) if w else None
            mem = [s for s in (r.get('peak_tree_rss_mb') for r in ok) if s]
            a['peak_tree_rss_mb_max'] = max(mem) if mem else None
        agg[split] = a
    wc = report['wrong_claims']
    agg['match_verification'] = {'cases': len(wc), 'correct': sum(c['correct'] for c in wc),
                                 'by_case': {name: '%d/%d' % (sum(c['correct'] for c in wc if c['case'] == name), sum(c['case'] == name for c in wc)) for name in sorted({c['case'] for c in wc})}}
    return agg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['run', 'run-one', 'reference', 'sheets', 'score'])
    ap.add_argument('--manifest', default=str(HERE / 'apollo_2026.json'))
    ap.add_argument('--videos')
    ap.add_argument('--out')
    ap.add_argument('--backend', default='apple-vision')
    ap.add_argument('--python', help='Python for the analysis child (e.g. a venv with RapidOCR)')
    ap.add_argument('--split', choices=['tuning', 'heldout', 'heldout2', 'heldout3'])
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--labels')
    ap.add_argument('--every', type=float, default=2.0, help='bumper sampling interval in seconds')
    ap.add_argument('--key')
    ap.add_argument('--work')
    args = ap.parse_args()
    {'run': run, 'run-one': run_one, 'reference': reference, 'sheets': sheets, 'score': score}[args.command](args)


if __name__ == '__main__':
    main()
