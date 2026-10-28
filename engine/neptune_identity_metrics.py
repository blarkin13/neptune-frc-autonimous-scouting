"""Measure identity constancy against human-reviewed tracking points (evaluation only).

Reviewed points are never inputs to the labeling being measured. A switch is a
change of assigned team between consecutive labeled sightings of the same
reviewed robot in one camera. Lost-track seconds are sampled times in the match
window when a roster robot has no labeled box in any camera.
"""
import collections

STEP = 1/3
TOLERANCE = .25


def iou(a, b):
    x = max(a[0], b[0]); y = max(a[1], b[1]); r = min(a[0]+a[2], b[0]+b[2]); d = min(a[1]+a[3], b[1]+b[3])
    v = max(0, r-x)*max(0, d-y)
    return v/max(1e-9, a[2]*a[3]+b[2]*b[3]-v)


def match(truth, labeled, max_dt=.09, min_iou=.3):
    """Return the labeled point that is the same box as a reviewed point, if any."""
    best = None
    rows = [p for dt in (-.01, 0, .01) for p in labeled.get((truth['camera'], round(truth['t']+dt, 2)), ())]
    for p in rows:
        if abs(p['t']-truth['t']) <= max_dt:
            score = iou(p['box'], truth['box'])
            # A labeled box wins a tie with its own unlabeled observation.
            if score >= min_iou and (best is None or score > best[0] or (score == best[0] and p.get('team') is not None)):
                best = (score, p)
    return best[1] if best else None


def evaluate(labeled_points, review, start, end, detections=()):
    """labeled_points: dicts with t, camera, box, team (None = unlabeled).
    detections: every tracker box (e.g. observations); those not labeled count as unlabeled."""
    index = collections.defaultdict(list)
    # Unlabeled boxes are indexed too: a reviewed box must match its own detection,
    # not an overlapping labeled neighbour.
    for p in list(labeled_points)+[dict(d, team=None) for d in detections]:
        index[(p['camera'], round(p['t'], 2))].append(p)
    rows = []
    for truth in review.get('points', []):
        status = truth.get('identity_status')
        if status not in ('corrected', 'excluded'):
            continue
        p = match(truth, index)
        rows.append({'t': truth['t'], 'camera': truth['camera'], 'expected': truth.get('team') if status == 'corrected' else None,
                     'assigned': p.get('team') if p else None})
    robots = [r for r in rows if r['expected'] is not None]
    switches = 0
    by_robot = collections.defaultdict(list)
    for r in sorted(robots, key=lambda r: r['t']):
        if r['assigned'] is not None:
            by_robot[(r['expected'], r['camera'])].append(r['assigned'])
    for labels in by_robot.values():
        switches += sum(a != b for a, b in zip(labels, labels[1:]))
    named = {(r['camera'], round(r['t'], 2), r['expected']) for r in robots}

    # A hidden box on a robot the reviewer named in the same frame is a duplicate, not a non-robot.
    def duplicate(r):
        return any((r['camera'], round(r['t']+dt, 2), r['assigned']) in named for dt in (-.01, 0, .01))
    teams = [t for c in ('red', 'blue') for t in review['roster'][c]]
    times = collections.defaultdict(list)
    for p in labeled_points:
        if p.get('team') is not None:
            times[p['team']].append(p['t'])
    for v in times.values():
        v.sort()
    import bisect
    grid = []
    t = start
    while t <= end+1e-9:
        grid.append(t); t += STEP
    lost = {}
    for team in teams:
        ts = times.get(team, [])
        missing = 0
        for g in grid:
            i = bisect.bisect_left(ts, g-TOLERANCE)
            if not (i < len(ts) and ts[i] <= g+TOLERANCE):
                missing += 1
        lost[str(team)] = round(missing*STEP, 1)
    return {'reviewed_robot_points': len(robots),
            'correct': sum(r['assigned'] == r['expected'] for r in robots),
            'wrong': sum(r['assigned'] is not None and r['assigned'] != r['expected'] for r in robots),
            'unlabeled': sum(r['assigned'] is None for r in robots),
            'identity_switches': switches,
            'labeled_non_robots': sum(r['expected'] is None and r['assigned'] is not None and not duplicate(r) for r in rows),
            'hidden_duplicates_named': sum(r['expected'] is None and r['assigned'] is not None and duplicate(r) for r in rows),
            'lost_track_seconds_per_robot': round(sum(lost.values())/len(teams), 1),
            'lost_track_seconds': lost, 'match_seconds': round(end-start, 1)}
