"""Robot actions from tracked positions and marked field regions, with no learned model.

Defense: a robot inside its alliance's marked defense_zone (else the opponent's scoring zone) for a sustained stretch.
Climb: a robot's last tracked position inside a marked climb_zone.
Nothing is game-specific: region kinds come from the marks and the game pack, and a rule whose regions are not
marked returns status 'unavailable' rather than a guess.
"""
import collections

import neptune_field_regions as regions

VERSION = 'geometry-rules-v1'
TRACK_METHODS = {'direct_vote_track', 'yolo_botsort_ocr', 'human_reviewed_track', 'roster_inferred'}
DEFENSE_MIN_S = 3.   # sustained presence before it counts
GAP_S = 1.5          # a stretch survives tracking gaps up to this long


def positions(facts):
    """Usable tracked foot positions: [{team, t, camera, foot, alliance}]."""
    ids = (facts.get('bumpers') or {}).get('identities') or {}; out = []
    for p in (facts.get('tracking') or {}).get('localizations') or []:
        box = p.get('box') or []
        if p.get('occluded') or p.get('box_source') == 'optical_flow' or p.get('identity_method') not in TRACK_METHODS or len(box) != 4:
            continue
        side = (ids.get(str(p['team'])) or {}).get('alliance')
        if side in ('red', 'blue'):
            out.append({'team': p['team'], 't': p['t'], 'camera': p.get('camera', 'wide'), 'foot': [box[0] + box[2] / 2, box[1] + box[3]], 'alliance': side})
    return sorted(out, key=lambda p: p['t'])


def in_kind(p, d, facts, kind, alliance):
    """True/False inside a marked `kind` region of `alliance`; None when no such region applies here."""
    zones = [r for r in d['regions'] if r['kind'] == kind and r['alliance'] == alliance and regions.active(r, p['t'], p['camera'], facts)]
    if not zones:
        return None
    return any(regions.inside(p['foot'], r['points']) for r in zones)


def stretches(times, gap=GAP_S):
    out = []
    for t in sorted(times):
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def defense(facts, d, min_s=DEFENSE_MIN_S):
    """{status, basis, robots: {team: {seconds, intervals}}}: sustained presence in the alliance's own marked
    defense_zone (where it defends), or, when none is marked, in the opponent's marked scoring zone."""
    if not d:
        return {'version': VERSION, 'status': 'unavailable', 'reason': 'no_marked_regions'}
    own = any(r['kind'] == 'defense_zone' for r in d['regions'])
    hits = collections.defaultdict(list); checked = set()
    for p in positions(facts):
        other = 'blue' if p['alliance'] == 'red' else 'red'
        inside = in_kind(p, d, facts, 'defense_zone', p['alliance']) if own else in_kind(p, d, facts, 'scoring_zone', other)
        if inside is None:
            continue
        checked.add(p['team'])
        if inside:
            hits[p['team']].append(p['t'])
    if not checked:
        return {'version': VERSION, 'status': 'unavailable', 'reason': 'no_robot_in_a_marked_view'}
    robots = {}
    for team in checked:
        spans = [s for s in stretches(hits[team]) if s[1] - s[0] >= min_s]
        robots[team] = {'seconds': round(sum(b - a for a, b in spans), 1), 'intervals': [[round(a, 1), round(b, 1)] for a, b in spans]}
    return {'version': VERSION, 'status': 'measured', 'basis': 'defense_zone' if own else 'opponent_scoring_zone', 'robots': robots}


def climb(facts, d, kind='climb_zone', end_s=None, last_s=5.):
    """{status, robots: {team: bool}}: last tracked position (within `last_s` of the end) inside a `kind` region."""
    if not kind or not d or not any(r['kind'] == kind for r in d['regions']):
        return {'version': VERSION, 'status': 'unavailable', 'reason': 'no_marked_%s' % (kind or 'climb_region')}
    pos = positions(facts)
    if not pos:
        return {'version': VERSION, 'status': 'unavailable', 'reason': 'no_tracking'}
    end = end_s if end_s is not None else pos[-1]['t']; robots = {}
    for p in pos:
        if end - last_s <= p['t'] <= end:
            inside = in_kind(p, d, facts, kind, p['alliance'])
            if inside is None:
                inside = in_kind(p, d, facts, kind, 'neutral')
            if inside is not None:
                robots[p['team']] = inside
    return {'version': VERSION, 'status': 'measured' if robots else 'unavailable', 'robots': robots}
