"""Conservative temporal decoding of classifier candidates, not scoring facts."""
from neptune_clock import eligible

VERSION = 'phase-episode-decoder-v2'


def decode(samples, facts, model_id, action_definitions=None):
    """Require two nearby positives, emit an onset once, rearm only on observed lows.

    Missing sightings do not prove an action stopped. Outcome heads compete once
    per phase; generic appearance never proves a successful score or climb.
    """
    groups = {}
    for s in samples:
        if eligible(s['tag_key'], facts, s['t']):
            groups.setdefault((s['team'], s['tag_key']), []).append(s)
    out = []
    for (team, tag), rows in groups.items():
        active = False; positives = []; lows = []; emitted = []
        for row in sorted(rows, key=lambda r: r['t']):
            if row['score'] >= row['threshold']:
                lows = []
                if active:
                    continue
                if positives and row['t'] - positives[-1]['t'] > 3:
                    positives = []
                if positives and row['t']-positives[-1]['t']<.5:
                    continue # two crops of one video moment are not two observations
                positives.append(row)
                if len(positives) < 2:
                    continue
                first = positives[0]; active = True
                emitted.append(dict(first, support_samples=len(positives)))
            else:
                positives = []; lows.append(row['t'])
                if len(lows) >= 2 and lows[-1] - lows[0] >= 1:
                    active = False
        if tag.startswith(('auto_', 'end_')) and emitted:
            emitted = [max(emitted, key=lambda r: r['score'] - r['threshold'])]
        for row in emitted:
            out.append({'team': team, 'tag_key': tag, 'start_ms': round(row['t']*1000),
                        'end_ms': round(row['t']*1000), 'certainty': 'uncertain',
                        'model_id': model_id, 'identity_evidence': row['identity_evidence'],
                        'evidence_type': 'model_prediction', 'score': row['score'],
                        'score_is_probability': False, 'support_samples': row['support_samples'],
                        'decoder_version': VERSION, 'assessment': 'candidate_requires_video_confirmation'})
    # Mutually exclusive outcome heads cannot all be emitted for the same phase.
    winners = {}; actions = []
    for row in out:
        family = 'auto' if row['tag_key'].startswith('auto_') else 'end' if row['tag_key'].startswith('end_') else None
        if family:
            key = (row['team'], family)
            if key not in winners or row['score'] > winners[key]['score']: winners[key] = row
        else: actions.append(row)
    result=sorted(actions + list(winners.values()), key=lambda r: (r['start_ms'], r['team']))
    for row in result:
        definition=(action_definitions or {}).get(row['tag_key'])
        if definition:
            row.update(schema_version=2,game_key=definition['game_key'],label_scope='moment',time_basis='video_elapsed_ms',action_code=definition['action_code'],definition_variants=definition['variants'])
            if len(definition['variants'])==1:row.update(definition['variants'][0])
    return result
