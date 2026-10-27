#!/usr/bin/env python3
"""Held-out action and robot-score numbers from a helper's prepared training cache, without retraining.

Runs the same checks training runs (match-held-out P-vs-U AUC, the no-video stand-in, flag rate and recall at
the PU threshold; leave-one-match-out robot points), plus the error sources behind them: positives per match,
rows per click, and hand-label versus outside-scouting AUC. Read-only; the reserved benchmark is refused.

Example
  python3 evaluate_actions.py ~/.neptune-trainer/cache/<engine>/prepared/<selection> --out actions.json
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import neptune_scoring_model as scoring  # noqa: E402
import neptune_training as training  # noqa: E402


def load(folder, dimension=None):
    """Action and score examples from prepared match files, with their cached feature vectors."""
    actions, scores = [], []
    for path in sorted(Path(folder).glob('*.json')):
        doc = json.loads(path.read_text()); cached = doc.get('features') or {}
        for key, out in (('examples', actions), ('scoring_examples', scores)):
            for row in doc.get(key) or []:
                x = row.get('x') or cached.get(row.get('feature'))
                if x is not None:
                    out.append(dict(row, x=x))
    reserved = [r for r in actions+scores if r.get('match_key') in training.HELD_OUT_MATCHES or r.get('source_sha256') in training.HELD_OUT_SOURCES]
    if reserved:
        raise ValueError('The prepared cache contains the reserved benchmark; it is never evaluated here.')
    if dimension is None and actions:
        dimension = collections.Counter(len(r['x']) for r in actions).most_common(1)[0][0]
    return [r for r in actions if len(r['x']) == dimension], scores


def action_report(rows):
    """Per tag, on training-split rows exactly as train_actions validates them."""
    report = {}
    for tag in sorted({r['tag'] for r in rows}):
        part = [r for r in rows if r['tag'] == tag and r['split'] == 'training']
        positives = [r for r in part if r['y'] == 1]
        if len(positives) < 2:
            continue
        detail, _ = training.validate_positive_unlabeled(part)
        clicks = collections.Counter(tuple(r['label_ids']) for r in positives)
        report[tag] = {k: detail.get(k) for k in ('status', 'positive_examples', 'positive_sources', 'auc_vs_unlabeled', 'nuisance_auc',
                                                  'held_out_flag_rate', 'held_out_positive_recall', 'auc_by_source')}
        report[tag].update(unlabeled=sum(r['y'] is None for r in part), clicks=len(clicks), max_rows_per_click=max(clicks.values()),
                           positives_by_match=dict(collections.Counter(training.fold_key(r) for r in positives)))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('prepared'); parser.add_argument('--out'); parser.add_argument('--dimension', type=int)
    args = parser.parse_args()
    actions, scores = load(args.prepared, args.dimension)
    result = {'actions': action_report(actions), 'robot_points': scoring.validate_video(scores)[0] if scores else None,
              'action_examples': len(actions), 'score_examples': len(scores),
              'note': 'Held-out P-vs-U ranking and leave-one-match-out points. Not a complete six-robot benchmark.'}
    text = json.dumps(result, indent=1)
    Path(args.out).write_text(text) if args.out else print(text)


if __name__ == '__main__':
    main()
