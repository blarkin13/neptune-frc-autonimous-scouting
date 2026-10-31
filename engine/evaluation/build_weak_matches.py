#!/usr/bin/env python3
"""Facts, tracking, scoreboard weak labels and R3D-18 clips for matches with no hand labels.

  facts   <out> <match_key>...          facts + tracking per match (video from the helper cache, roster from label exports)
  clips   <out> <delay_s> <match_key>...  weak positives (scoreboard changes credited to one robot) and unlabelled clips

Writes <out>/<match_key>/facts.json and rows.json. Run with NEPTUNE_GAMES_HOME at a job folder (the server's game
pack, which has every broadcast layout) and NEPTUNE_ROBOT_MODELS at the helper's robot-models. Q7 is refused.
"""
import collections
import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import neptune_facts  # noqa: E402
import neptune_field_regions as regions  # noqa: E402
import neptune_games as games  # noqa: E402
import neptune_score_labels as sl  # noqa: E402
import neptune_training as training  # noqa: E402
import neptune_video_labels as labels  # noqa: E402
from neptune_temporal import ClipUnavailable  # noqa: E402

HOME = Path.home()/'.neptune-trainer'


def exports():
    out = {}
    for f in glob.glob(str(HOME/'jobs/*/labels.ndjson')):
        for line in open(f):
            r = json.loads(line)
            if r.get('roster') and r.get('video_id'):
                out[r['match_key']] = (r['roster'], r['video_id'])
    return out


def facts(out, keys):
    known = exports(); game = games.select(keys[0])
    for key in keys:
        if key in training.HELD_OUT_MATCHES:
            raise ValueError('The reserved benchmark is never used here.')
        work = out/key; work.mkdir(parents=True, exist_ok=True); target = work/'facts.json'
        if target.exists():
            print(key, 'cached', flush=True); continue
        roster, vid = known[key]; video = HOME/'cache/videos'/(vid+'.mp4'); start = time.time()
        try:
            sha = labels.sha256_file(video)
            f = neptune_facts.analyze_video(video, {'key': key, 'title': key, 'roster': roster, 'source_url': 'https://www.youtube.com/watch?v='+vid, 'source_sha256': sha}, work, ['x'], source_sha256=sha)
            f = training.ensure_tracking(video, f, game, work, lambda s: None)
            training.write(target, f)
            print(key, 'ok', round(time.time()-start), 's', f['identity']['checks']['roster']['status'], f.get('tracking', {}).get('status'), flush=True)
        except Exception as error:
            print(key, 'FAILED', type(error).__name__, str(error)[:200], flush=True)


def clips(out, delay, keys, limit=96):
    known = exports()
    for key in keys:
        path = out/key/'facts.json'
        if not path.exists() or (out/key/'rows.json').exists():
            continue
        f = json.loads(path.read_text()); video = HOME/'cache/videos'/(known[key][1]+'.mp4'); duration = round(f['source']['duration_s']*1000)
        d = regions.load(f, games.select(key)['game_key']); sights = training.sightings(f)
        attributed = sl.attribute(sl.score_events(f), f, sights, lambda s: regions.scoring_reach(s, d, f), delay)
        rows = []

        def clip(s, kind, **extra):
            s = dict(s)
            try:
                x = training.action_features(video, s, duration, f, training.ACTION_FEATURE_VERSION)
            except ClipUnavailable:
                return
            rows.append(dict(extra, kind=kind, x=x, team=s['team'], t_ms=round(s['t']*1000), box=list(s['box']), camera=s.get('camera')))
        for e in attributed:
            near = [s for s in sights if s['team'] == e['team'] and abs(s['t']-e['window'][1]) <= 1.] if e['team'] is not None else []
            if near:
                clip(min(near, key=lambda s: abs(s['t']-e['window'][1])), 'weak', event={k: e[k] for k in ('t', 'alliance', 'points', 'reason', 'window')})
        weak = [(r['team'], r['t_ms']/1000) for r in rows]
        pool = sorted(sights, key=lambda s: (s['t'], s['team']))
        if len(pool) > limit:
            pool = [pool[i*(len(pool)-1)//(limit-1)] for i in range(limit)]
        for s in pool:
            if not any(t == s['team'] and abs(w-s['t']) <= sl.WINDOW+2 for t, w in weak):
                clip(s, 'unlabeled')
        (out/key/'rows.json').write_text(json.dumps({'match_key': key, 'source_sha256': f['source']['sha256'], 'delay': delay, 'events': len(attributed),
                                                     'reasons': collections.Counter(e['reason'] for e in attributed), 'rows': rows}))
        print(key, 'events', len(attributed), 'weak', sum(r['kind'] == 'weak' for r in rows), 'unlabeled', sum(r['kind'] == 'unlabeled' for r in rows), flush=True)


if __name__ == '__main__':
    mode, out = sys.argv[1], Path(sys.argv[2])
    if mode == 'facts':
        facts(out, sys.argv[3:])
    else:
        clips(out, float(sys.argv[3]), sys.argv[4:])
