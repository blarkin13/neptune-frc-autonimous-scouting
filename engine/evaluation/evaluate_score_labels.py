#!/usr/bin/env python3
"""How well scoreboard score changes line up with hand-labelled score clicks (neptune_score_labels).

Uses match facts that are still on this helper and the hand clicks in a prepared training cache. The delay is
measured on all matches but one and applied to that one, so no match is scored with a delay it helped choose.
The reserved benchmark is refused.

  python3 evaluate_score_labels.py <prepared folder> <facts.json>... [--out report.json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_actions  # noqa: E402
import neptune_field_regions as regions  # noqa: E402
import neptune_score_labels as sl  # noqa: E402
import neptune_training as training  # noqa: E402

SCORE_TAGS = ('gb:score_1_fuel', 'gb:score_2_fuel', 'scoring')


def hand_clicks(actions):
    out = {}
    for r in actions:
        if r['y'] != 1 or r.get('external_sources') or r['tag'] not in SCORE_TAGS:
            continue
        for m in r.get('label_metadata') or []:
            if m.get('label_scope') == 'moment' and m.get('start_ms') is not None:
                out[m['id']] = {'team': r['team'], 't': m['start_ms'] / 1000, 'tag': r['tag'], 'match_key': r['match_key'], 'sha': r['source_sha256']}
    return list(out.values())


def report(actions, facts_list, game_key, windows=(1., 2., 3., 5.)):
    clicks = hand_clicks(actions)
    matches = []
    for facts in facts_list:
        key = facts.get('identity', {}).get('checks', {}).get('match_number', {}).get('claimed_key')
        if key in training.HELD_OUT_MATCHES or facts['source']['sha256'] in training.HELD_OUT_SOURCES:
            raise ValueError('The reserved benchmark is never evaluated here.')
        mine = [c for c in clicks if c['sha'] == facts['source']['sha256']]
        events = sl.score_events(facts)
        matches.append({'facts': facts, 'key': key, 'clicks': mine, 'events': events, 'pairs': sl.click_event_pairs(mine, events, facts)})
    out = {'version': sl.VERSION, 'matches': []}
    for m in matches:
        others = [p for o in matches if o is not m for p in o['pairs']]
        delay = sl.measure_delay(others)
        d = regions.load(m['facts'], game_key)
        reach = (lambda s, d=d, f=m['facts']: regions.scoring_reach(s, d, f))
        sights = [s for s in training.sightings(m['facts'])]
        row = {'match_key': m['key'], 'clicks': len(m['clicks']), 'score_events': len(m['events']), 'points_in_events': sum(e['points'] for e in m['events']),
               'own_delay_s': sl.measure_delay(m['pairs']), 'delay_from_other_matches_s': delay, 'marked_zones': bool(d), 'sightings': len(sights)}
        if delay is not None and sights:
            row['by_window'] = {}
            for w in windows:
                attributed = sl.attribute(m['events'], m['facts'], sights, reach, delay, w)
                row['by_window'][str(w)] = dict(sl.attribution_metrics(attributed, m['clicks'], m['facts'], tolerance=w),
                                                reasons=dict(collections.Counter(e['reason'] for e in attributed)))
            m['weak'] = sl.attribute(m['events'], m['facts'], sights, reach, delay)
        out['matches'].append(row)
    out['weak_labels'] = weak_label_effect(actions, [m for m in matches if m.get('weak')])
    return out


def weak_label_effect(actions, matches, tags=SCORE_TAGS, max_offset=1.):
    """Held-out AUC on hand positives, without and with weak scoreboard labels in training.

    A weak label marks the unlabelled reference clip of its robot nearest the delay-corrected change (within
    `max_offset` s) as a positive at sl.WEIGHT. Folds, gates and the evaluation set (hand positives against the
    remaining unlabelled clips) are the ones validate_positive_unlabeled uses."""
    weak = {}
    for m in matches:
        for e in m['weak']:
            if e['team'] is not None:
                weak.setdefault(m['facts']['source']['sha256'], []).append(e)
    result = {}
    saved = training.EXTERNAL_WEIGHT
    try:
        for tag in tags:
            rows = [dict(r) for r in actions if r['tag'] == tag and r['split'] == 'training']
            if sum(r['y'] == 1 for r in rows) < 2:
                continue
            base, _ = training.validate_positive_unlabeled(rows)
            added = 0
            for sha, events in weak.items():
                for e in events:
                    pool = [r for r in rows if r['y'] is None and r['source_sha256'] == sha and r['team'] == e['team'] and abs(r['t_ms'] / 1000 - e['window'][1]) <= max_offset]
                    if pool:
                        r = min(pool, key=lambda r: abs(r['t_ms'] / 1000 - e['window'][1]))
                        r.update(y=1, external_sources=[{'provider': sl.SOURCE, 'weak_supervision': True}]); added += 1
            training.EXTERNAL_WEIGHT = sl.WEIGHT
            # Weak rows train, but only hand positives are scored: the human AUC is the comparison.
            withw, _ = training.validate_positive_unlabeled(rows)
            training.EXTERNAL_WEIGHT = saved
            pick = lambda d: {'status': d.get('status'), 'auc_hand_positives': (d.get('auc_by_source') or {}).get('human', {}).get('auc_vs_unlabeled'),
                              'nuisance_auc': d.get('nuisance_auc'), 'recall': d.get('held_out_positive_recall')}
            result[tag] = {'weak_positives_added': added, 'hand_only': pick(base), 'with_weak': pick(withw)}
    finally:
        training.EXTERNAL_WEIGHT = saved
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('prepared'); p.add_argument('facts', nargs='+'); p.add_argument('--out'); p.add_argument('--game-key', default='2026-rebuilt')
    a = p.parse_args()
    actions, _ = evaluate_actions.load(a.prepared)
    text = json.dumps(report(actions, [json.loads(Path(f).read_text()) for f in a.facts], a.game_key), indent=1)
    Path(a.out).write_text(text) if a.out else print(text)


if __name__ == '__main__':
    main()


def unlabelled_match_effect(actions, weak_folder, tags=SCORE_TAGS):
    """Held-out AUC on hand positives when weak-only matches (build_weak_matches.py rows) join training.

    Folds are the hand-labelled matches; weak-only matches are in every fold's training set and never scored.
    Arm A adds their unlabelled clips only; arm B adds their weak positives too (at sl.WEIGHT). Same learner, same
    folds, same held-out rows in both arms."""
    extra = []
    for p in sorted(Path(weak_folder).glob('*/rows.json')):
        d = json.loads(p.read_text())
        if d['match_key'] in training.HELD_OUT_MATCHES:
            raise ValueError('The reserved benchmark is never used here.')
        extra += [dict(r, match_key=d['match_key'], source_sha256=d['source_sha256'], weak=r['kind'] == 'weak') for r in d['rows']]
    out = {'weak_positives': sum(r['weak'] for r in extra), 'unlabelled_clips': sum(not r['weak'] for r in extra), 'tags': {}}
    saved = training.EXTERNAL_WEIGHT
    try:
        training.EXTERNAL_WEIGHT = sl.WEIGHT
        for tag in tags:
            rows = [r for r in actions if r['tag'] == tag and r['split'] == 'training']
            matches = sorted({training.fold_key(r) for r in rows if r['y'] == 1 and not r.get('external_sources')})
            if len(matches) < 2:
                continue
            arms = {}
            for arm in ('unlabelled_only', 'with_weak'):
                added = [dict(r, tag=tag, y=1 if r['weak'] and arm == 'with_weak' else None, label_ids=[],
                              external_sources=[{'provider': sl.SOURCE}] if r['weak'] else []) for r in extra if arm == 'with_weak' or not r['weak']]
                pos, unl = [], []
                for m in matches:
                    head = training.fit_positive_unlabeled([r for r in rows if training.fold_key(r) != m] + added)
                    for r in rows:
                        if training.fold_key(r) != m:
                            continue
                        if r['y'] == 1 and not r.get('external_sources'):
                            pos.append(training.score(head, r['x']))
                        elif r['y'] is None:
                            unl.append(training.score(head, r['x']))
                arms[arm] = round(training.pu_auc(pos, unl), 4)
            out['tags'][tag] = dict(arms, folds=len(matches))
    finally:
        training.EXTERNAL_WEIGHT = saved
    return out
