"""Weak scoring labels from scoreboard score changes, and the alliance-total check on robot points.

Score changes come from the video's own scoreboard (rule 1: from the video). They are weak, separate labels with
their own source tag and weight, never mixed into hand labels. An event is attributed to a robot only when exactly
one of the scoring alliance's tracked robots was in a marked scoring zone in the window before the change, after
the measured broadcast delay; otherwise it stays unattributed. Nothing here is game-specific: zones come from the
marked field regions and point rules from the game pack.
"""
import bisect
import collections
import statistics

VERSION = 'scoreboard-change-labels-v1'
SOURCE = 'scoreboard_change'
WEIGHT = .25            # below outside scouting (EXTERNAL_WEIGHT .5): timing and robot are both inferred
HOLD = 2                # a new value must be read this many times in a row
DELAY_RANGE = (-2., 10.)  # seconds from robot action to scoreboard change searched when measuring the delay
WINDOW = 3.             # seconds of robot presence before the (delay-corrected) change


def score_events(facts, hold=HOLD):
    """[{t, alliance, from, to, points}]: increases held for `hold` reads; drops and one-read jumps ignored."""
    out = []
    for side in ('red', 'blue'):
        reads = sorted((r for r in (facts.get('accepted_scores') or {}).get(side) or [] if isinstance(r.get('value'), int)), key=lambda r: r['t'])
        level = None; i = 0
        while i < len(reads):
            v = reads[i]['value']; j = i
            while j < len(reads) and reads[j]['value'] == v:
                j += 1
            if j - i >= hold:
                if level is not None and v > level:
                    out.append({'t': reads[i]['t'], 'alliance': side, 'from': level, 'to': v, 'points': v - level})
                if level is None or v > level:
                    level = v
            i = j
    return sorted(out, key=lambda e: (e['t'], e['alliance']))


def alliance_of(facts, team):
    return ((facts.get('bumpers') or {}).get('identities') or {}).get(str(team), {}).get('alliance')


def measure_delay(pairs, step=.5):
    """Broadcast delay from (click time, event time) pairs of the same alliance: the most common lag, by histogram.

    Returns None with fewer than 10 pairs inside DELAY_RANGE."""
    lags = [e - c for c, e in pairs if DELAY_RANGE[0] <= e - c <= DELAY_RANGE[1]]
    if len(lags) < 10:
        return None
    bins = collections.Counter(round(x / step) for x in lags)
    peak = max(bins, key=lambda b: (bins[b] + .5 * (bins[b - 1] + bins[b + 1]), -abs(b)))
    near = [x for x in lags if abs(x - peak * step) <= step]
    return round(statistics.median(near), 2)


def click_event_pairs(clicks, events, facts):
    """Every (click t, event t) pair of the same alliance within DELAY_RANGE, for measure_delay."""
    by_side = collections.defaultdict(list)
    for e in events:
        by_side[e['alliance']].append(e['t'])
    out = []
    for c in clicks:
        side = alliance_of(facts, c['team'])
        out += [(c['t'], t) for t in by_side.get(side, []) if DELAY_RANGE[0] <= t - c['t'] <= DELAY_RANGE[1]]
    return out


def attribute(events, facts, sightings, reach, delay, window=WINDOW):
    """Each event with `team` (one clearly responsible robot) or `team` None and a reason.

    reach(sight) -> True/False/None: in the alliance's marked scoring zone, outside it, or no zone applies."""
    seen = sorted(sightings, key=lambda s: s['t']); times = [s['t'] for s in seen]
    out = []
    for e in events:
        start, end = e['t'] - delay - window, e['t'] - delay
        near = seen[bisect.bisect_left(times, start):bisect.bisect_right(times, end)]
        teams = collections.defaultdict(list)
        for s in near:
            if alliance_of(facts, s['team']) == e['alliance']:
                teams[s['team']].append(reach(s))
        row = dict(e, window=[round(start, 2), round(end, 2)], candidates=sorted(teams), team=None, source=SOURCE, version=VERSION, weight=WEIGHT)
        if not teams:
            row['reason'] = 'no_alliance_robot_seen'
        else:
            inside = [t for t, r in teams.items() if any(x is True for x in r)]
            if any(x is None for r in teams.values() for x in r) and not inside:
                row['reason'] = 'no_marked_zone'
            elif len(inside) == 1:
                row['team'] = inside[0]; row['reason'] = 'only_robot_in_scoring_zone'
            else:
                row['reason'] = 'several_robots_in_zone' if inside else 'no_robot_in_zone'
        out.append(row)
    return out


def attribution_metrics(attributed, clicks, facts, tolerance):
    """Against hand clicks: precision = attributed events with a same-team click within `tolerance` seconds of the
    event (delay-corrected window end); recall = clicks with such an attributed event. Coverage = share attributed."""
    by_team = collections.defaultdict(list)
    for c in clicks:
        by_team[c['team']].append(c['t'])
    made = [e for e in attributed if e['team'] is not None]
    hit = sum(any(abs(t - e['window'][1]) <= tolerance for t in by_team[e['team']]) for e in made)
    found = sum(any(e['team'] == c['team'] and abs(c['t'] - e['window'][1]) <= tolerance for e in made) for c in clicks)
    # Chance: the same events credited to another robot of the alliance that was seen in the window.
    others = [(e, t) for e in made for t in e['candidates'] if t != e['team']]
    chance = sum(any(abs(c - e['window'][1]) <= tolerance for c in by_team[t]) for e, t in others)
    return {'events': len(attributed), 'attributed': len(made), 'coverage': round(len(made) / len(attributed), 3) if attributed else None,
            'precision': round(hit / len(made), 3) if made else None, 'precision_other_robot': round(chance / len(others), 3) if others else None, 'recall': round(found / len(clicks), 3) if clicks else None, 'tolerance_s': tolerance}


def final_scores(facts):
    """Last held scoreboard value per alliance, and the results-screen breakdown when one was read."""
    out = {}
    for side in ('red', 'blue'):
        ev = [e for e in score_events(facts) if e['alliance'] == side]
        reads = [r['value'] for r in (facts.get('accepted_scores') or {}).get(side) or [] if isinstance(r.get('value'), int)]
        out[side] = ev[-1]['to'] if ev else (max(reads) if reads else None)
    return out


def alliance_check(scores, facts, game):
    """Predicted robot points per alliance against the final displayed score, minus the parts the game pack marks as
    alliance-level (results_screen_components other than auto/teleop, e.g. penalties) when the results screen read them.

    scores: [{team, alliance, robot_points}]. Returns per-alliance rows and the mean absolute gap."""
    final = final_scores(facts)
    results = facts.get('results_screen') or {}
    alliance_level = [k for k in (game.get('results_screen_components') or {}) if k not in ('auto', 'teleop')]
    rows = []
    # One value per robot: several estimates of one robot (hand and imported) are averaged, never added.
    per_team = collections.defaultdict(list)
    for s in scores:
        per_team[(s.get('alliance'), s.get('team'))].append(s.get('robot_points'))
    merged = [{'alliance': a, 'team': t, 'robot_points': None if None in v else statistics.mean(v)} for (a, t), v in per_team.items()]
    for side in ('red', 'blue'):
        robots = [s for s in merged if s.get('alliance') == side]
        roster = [t for t, i in ((facts.get('bumpers') or {}).get('identities') or {}).items() if i.get('alliance') == side]
        if final[side] is None or not robots or any(s.get('robot_points') is None for s in robots):
            rows.append({'alliance': side, 'status': 'unavailable'}); continue
        if roster and {str(s['team']) for s in robots} != set(map(str, roster)):
            rows.append({'alliance': side, 'status': 'incomplete_robots', 'robots': len(robots), 'roster': len(roster)}); continue
        breakdown = (results.get('alliances') or {}).get(side) or {}
        removed = sum(v for k, v in breakdown.items() if k in alliance_level and isinstance(v, (int, float)))
        target = final[side] - removed
        predicted = sum(s['robot_points'] for s in robots)
        rows.append({'alliance': side, 'status': 'checked', 'robots': len(robots), 'final_displayed': final[side], 'alliance_level_removed': removed,
                     'alliance_level_known': bool(breakdown), 'target': target, 'predicted_robot_total': round(predicted, 1), 'gap': round(predicted - target, 1)})
    gaps = [abs(r['gap']) for r in rows if r['status'] == 'checked']
    return {'version': VERSION, 'alliances': rows, 'mean_abs_gap': round(statistics.mean(gaps), 2) if gaps else None,
            'note': 'Displayed totals include fouls and alliance bonuses unless the results screen was read; then the game pack\'s alliance-level parts are removed.'}


def weak_label_rows(attributed, facts, match_key, tag):
    """Attributed events as weak moment labels for `tag`, in the shape aligned outside-scouting rows take."""
    rows = []
    for e in attributed:
        if e['team'] is None:
            continue
        t_ms = round(e['window'][1] * 1000)
        rows.append({'team_number': e['team'], 'tag_key': tag, 'match_key': match_key, 'start_ms': round(e['window'][0] * 1000), 'end_ms': t_ms,
                     'label_scope': 'moment', 'polarity': 'present', 'weak_supervision': True, 'source': SOURCE, 'weight': WEIGHT,
                     'points': e['points'], 'scoreboard_t': e['t'], 'version': VERSION})
    return rows
