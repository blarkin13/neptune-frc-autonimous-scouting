"""Learned scoreboard layouts, replayed on saved matches (raw OCR plus the overlay frames kept beside it).

For every saved match folder (raw-overlay.jsonl, overlay/ov_*.jpg and facts.json for the roster):
  reference  the sides a passing roster vote gives (generic_layout with the roster).
  learn      settle_generic with the roster, in match order, into a fresh learned-layout store.
  blind      the same frames with team numbers and RED/BLUE words removed (a broadcast that never shows
             them): settled with no store, then with the store from `learn`.
Also prints thumbnail distances within and across events, so MATCH_DISTANCE can be judged.

    python3 tools/ocr-benchmark/learned_layouts.py [--root ~/.neptune-trainer]
Official results are not read. Q7 (2026txcmp1_qm7) is never used.
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine'))
import neptune_facts   # noqa: E402
import neptune_layouts   # noqa: E402

EXCLUDED = {'2026txcmp1_qm7'}


def roster_of(folder):
    facts = folder / 'facts.json'
    if not facts.is_file():
        return None
    stations = json.loads(facts.read_text()).get('identity', {}).get('checks', {}).get('roster', {}).get('stations', [])
    roster = {'red': [], 'blue': []}
    for s in stations:
        roster[s['station'].split()[0]].append(s['claimed'])
    return roster if roster['red'] and roster['blue'] else None


def load(folder):
    rows = [json.loads(l) for l in (folder / 'raw-overlay.jsonl').read_text().splitlines() if l.strip()]
    frames = [(r['t'], str(folder / r['frame'])) for r in rows]
    return frames, {str(folder / r['frame']): r['items'] for r in rows}


def blind(texts):
    hide = lambda t: re.fullmatch(r'\d{3,5}', t.strip()) or t.strip().upper() in ('RED', 'BLUE')
    return {k: [i for i in v if not hide(i['t'])] for k, v in texts.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(Path.home() / '.neptune-trainer'))
    args = ap.parse_args()
    matches = []
    for raw in sorted(Path(args.root).glob('*/*/raw-overlay.jsonl')):
        folder = raw.parent
        roster = roster_of(folder)
        if folder.name in EXCLUDED or not roster or not (folder / 'overlay').is_dir():
            continue
        matches.append((folder.name, folder, roster))
    rows, sigs = [], {}
    with tempfile.TemporaryDirectory() as home:
        for key, folder, roster in matches:
            frames, texts = load(folder)
            season = int(key[:4])
            ref = neptune_facts.generic_layout(frames, texts, roster, 0.30)
            got = neptune_facts.settle_generic(frames, texts, roster, 0.30, season, key, home)
            row = {'match': key, 'reference': ref and ref[0], 'learn': got and got[0]}
            if got and got[3] and got[2]['signature']:
                sigs[key] = got[2]['signature']
                e = neptune_layouts.learn(season, got[2]['signature'], got[2]['clock'], got[0], got[1], key, home)
                row['entry'] = '%s (%d matches%s)' % (e['id'], len(e['matches']), ', conflicts' if e['conflicts'] else '')
            rows.append(row)
        for row, (key, folder, roster) in zip(rows, matches):
            frames, texts = load(folder)
            hidden = blind(texts)
            with tempfile.TemporaryDirectory() as empty:
                cold = neptune_facts.settle_generic(frames, hidden, None, 0.30, int(key[:4]), key, empty)
            warm = neptune_facts.settle_generic(frames, hidden, None, 0.30, int(key[:4]), key, home)
            row['blind_no_store'] = cold and cold[0]
            row['blind_with_store'] = warm and warm[0]
            row['blind_entry'] = warm and warm[2].get('learned_layout', {}).get('id')
    print('%-18s %-10s %-10s %-34s %-10s %-10s' % ('match', 'reference', 'learn', 'entry', 'blind', 'blind+store'))
    tally = {'right': 0, 'wrong': 0, 'unread': 0}
    for r in rows:
        print('%-18s %-10s %-10s %-34s %-10s %-10s' % (r['match'], r['reference'], r['learn'], r.get('entry', '-'), r['blind_no_store'], r['blind_with_store']))
        if r['reference']:
            tally['unread' if not r['blind_with_store'] else 'right' if r['blind_with_store'] == r['reference'] else 'wrong'] += 1
    print('blind with store vs reference:', tally)
    # A learned entry decides sides, so the margin that matters is between overlays with opposite sides.
    sides = {r['match']: r['learn'] for r in rows}
    keys = sorted(sigs)
    same, opposite = [], []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            (same if sides[a] == sides[b] else opposite).append((neptune_layouts.distance(sigs[a], sigs[b]), a, b))
    if opposite:
        print('thumbnail distance between opposite-side overlays: min %.1f (%s, %s); MATCH_DISTANCE %.1f' % (min(opposite) + (neptune_layouts.MATCH_DISTANCE,)))
    if same:
        print('thumbnail distance between same-side matches: max %.1f (%s, %s)' % max(same))

if __name__ == '__main__':
    main()
