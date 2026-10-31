#!/usr/bin/env python3
"""Scoreboard-constrained robot points and geometry rules against hand labels, per match. Read-only.

  python3 evaluate_rules.py <delay_s> <facts.json>... [--out report.json]

Hand labels come from the helper's label exports (~/.neptune-trainer/jobs/*/labels.ndjson). Robot points are
compared as each robot's share of its alliance against its share of hand score clicks, beside an even split.
Defense is compared per robot (any hand defense click) and per click (inside a rule interval). The reserved
benchmark is refused.
"""
import argparse
import collections
import glob
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import neptune_field_regions as regions  # noqa: E402
import neptune_games as games  # noqa: E402
import neptune_geometry_rules as rules  # noqa: E402
import neptune_score_labels as sl  # noqa: E402
import neptune_training as training  # noqa: E402

SCORE_TAGS = ('gb:score_1_fuel', 'gb:score_2_fuel', 'scoring')
DEFENSE_TAGS = ('gb:defense', 'attempted_defense')


def hand_labels():
    out = {}
    for f in glob.glob(str(Path.home()/'.neptune-trainer/jobs/*/labels.ndjson')):
        for line in open(f):
            r = json.loads(line)
            if r.get('polarity') == 'present' and r.get('evidence_type') == 'human_video_label':
                out[r['id']] = r
    by = collections.defaultdict(list)
    for r in out.values():
        by[r['match_key']].append(r)
    return by


def auc(pos, neg):
    if not pos or not neg:
        return None
    return round(sum((p > n) + .5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg)), 3)


def match_report(facts, labels, delay):
    key = sl_key(facts)
    if key in training.HELD_OUT_MATCHES or facts['source']['sha256'] in training.HELD_OUT_SOURCES:
        raise ValueError('The reserved benchmark is never evaluated here.')
    game = games.select(key); d = regions.load(facts, game['game_key'])
    roster = {int(t): i['alliance'] for t, i in ((facts.get('bumpers') or {}).get('identities') or {}).items() if i.get('alliance') in ('red', 'blue')}
    sights = training.sightings(facts)
    alloc = sl.allocate(sl.score_events(facts), facts, sights, lambda s: regions.scoring_reach(s, d, facts), delay)
    clicks = collections.Counter(r['team_number'] for r in labels if r['tag_key'] in SCORE_TAGS)
    share_err, even_err = [], []
    for side in ('red', 'blue'):
        teams = [t for t, a in roster.items() if a == side]
        assigned = sum(alloc['robots'].get(t, 0) for t in teams); hand = sum(clicks[t] for t in teams)
        if not assigned or not hand:
            continue
        for t in teams:
            truth = clicks[t] / hand
            share_err.append(abs(alloc['robots'].get(t, 0) / assigned - truth)); even_err.append(abs(1 / len(teams) - truth))
    row = {'match_key': key, 'allocation': alloc, 'hand_score_clicks': dict(clicks),
           'share_mae': round(statistics.mean(share_err), 3) if share_err else None, 'even_split_share_mae': round(statistics.mean(even_err), 3) if even_err else None,
           'assigned_fraction': {s: round(1 - alloc['unassigned'].get(s, 0) / v, 3) for s, v in alloc['displayed'].items() if v}}
    dfn = rules.defense(facts, d); row['defense'] = dfn
    dclicks = [r for r in labels if r['tag_key'] in DEFENSE_TAGS]
    if dfn['status'] == 'measured' and dclicks:
        robots = dfn['robots']; marked = {r['team_number'] for r in dclicks}
        row['defense_robot_auc'] = auc([robots[t]['seconds'] for t in robots if t in marked], [robots[t]['seconds'] for t in robots if t not in marked])
        inside = [any(a - 2 <= r['start_ms'] / 1000 <= b + 2 for a, b in robots.get(r['team_number'], {}).get('intervals', [])) for r in dclicks]
        row['defense_click_recall'] = round(sum(inside) / len(inside), 3); row['defense_clicks'] = len(dclicks)
        spans = [(t, a, b) for t, v in robots.items() for a, b in v['intervals']]
        row['defense_interval_precision'] = round(sum(any(r['team_number'] == t and a - 2 <= r['start_ms'] / 1000 <= b + 2 for r in dclicks) for t, a, b in spans) / len(spans), 3) if spans else None
    row['climb'] = rules.climb(facts, d)
    return row


def sl_key(facts):
    return facts.get('identity', {}).get('checks', {}).get('match_number', {}).get('claimed_key')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('delay', type=float); p.add_argument('facts', nargs='+'); p.add_argument('--out')
    a = p.parse_args(); labels = hand_labels()
    rows = []
    for f in a.facts:
        facts = json.loads(Path(f).read_text())
        rows.append(match_report(facts, labels.get(sl_key(facts), []), a.delay))
    text = json.dumps({'version': rules.VERSION, 'delay_s': a.delay, 'matches': rows}, indent=1, default=str)
    Path(a.out).write_text(text) if a.out else print(text)


if __name__ == '__main__':
    main()
