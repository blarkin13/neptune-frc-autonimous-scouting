# Auto Scout robot tracking prototype — October 19, 2026

Prototype of continuous robot tracking in the broadcast wide shot (`helper/neptune_tracking.py`, tests in
`helper/test_tracking.py`). It was measured offline on the same 17 cached matches as
[auto-scout-quality.md](auto-scout-quality.md): 15 Week 0 matches and 2 Texas championship matches.
Inputs were scratch copies of `facts.json` from `~/.neptune-trainer/cache/7c3b85dfdb685839b584aeb4`. The videos
were read in place and not modified. ViperScout references came from the original export
(`2026week0.dat.json`), aligned exactly as Neptune's adapter does it. Nothing is wired into the facts pipeline,
training, the trainer app or the server. Nothing was deployed or committed.

## How it works

Pure Python and FFmpeg. No numpy: the macOS helper reads text with Apple Vision and has no numpy
(`requirements.json`).

1. **Detect.** FFmpeg decodes the wide shot, between the overlay and the close-up cameras, at 3 fps and 640 px
   wide as YUV planes. Byte lookup tables and big-integer masks classify red bumpers, blue bumpers and yellow fuel.
   This takes about 30 s per match.
2. **Background.** Red/blue pixels present in ≥ 20% of frames are static: hub ramps, alliance walls and
   driver-station signs. The field floor is the band of rows where fuel *comes and goes*. This excludes the audience
   and the static yellow banners. Moving red/blue blobs on the floor are re-joined where a bumper number splits them.
   Only bumper-shaped strips are kept, which rejects shirts and posts.
3. **Track.** Detections are linked greedily by colour, predicted position and blob size, with gaps of up to 1.5 s.
4. **Identify.** Two read sources vote for a track: the existing facts-pipeline wide-shot reads (every 2 s), and
   **track-guided OCR**, which crops each track's bumper from 2× full-resolution frames once a second (about 3,000
   crops per match). Each moment votes once. By default a track needs two moments. A team holds at most one track
   at a time. Unread fragments that continue an identified fragment within 1 s inherit its identity. Gaps of up to
   3 s are bridged.
5. **Position.** The static hub and bump ramps of each alliance trace that hub's line across the field in
   perspective, and the code fits a line per alliance. A robot's floor point gives `u`: 0 on its own hub line,
   1 on the opponent's. Its zone is own (< 0), neutral or opponent (> 1). Along-field distance to the own hub line is
   `|u| × 8.48 m`. Lateral offset is not modelled.

`track_match()` runs all of this for one match in **74 s on an Apple Silicon Mac** (single process) and returns
a JSON block of about 120 KB.

## Identity coverage (102 robot-match slots)

| | Slots with an identified track | of the 50 OCR-confirmed | newly identified | Coverage per slot, median / mean | Slots ≥ 50% covered |
|---|---|---|---|---|---|
| Today (bumper OCR, close-ups + wide) | 50 confirmed | — | — | median 22 sightings, every 2 s | — |
| Tracks + facts wide-shot reads only | 47 | — | 4 | 0.00 / 0.19 | 17 |
| **Tracks + track-guided OCR (default, 2 moments)** | **58** | 46 | 12 | 0.10 / 0.24 | 22 |
| Tracks + track-guided OCR, 1 moment | 68 | 48 | 20 | 0.30 / 0.31 | 33 |

Coverage is the share of match seconds in which the robot has an identified position, observed or bridged
across ≤ 3 s.

Coverage over match time is flat, which rules out a start-up or end-of-match artefact. Mean over all 102 slots per
10 s, default rule: 0.16 at 0–10 s, then 0.22–0.28 through 20–150 s, then 0.18 at the end. With the 1-moment rule
it is 0.23–0.36.

Per match (default rule; * = OCR-confirmed today):

```
Q3   *4909 .11  *5422 .38  *2423 .00  *2877 .40    811 .00   5813 .00   (wide shot shows only the far half)
Q6   *1073 .55    88 .00   1768 .00   2423 .00   6328 .09   2877 .09
Q15  *2877 .36   5687 .00  *5962 .80   2079 .00   1735 .62   6328 .07
Q11   *190 .12   5813 .00  *1119 .73  *1153 .33   4041 .00   6328 .00
Q4   *1119 .00   1153 .00   *151 .65    131 .00   5000 .30   2079 .00
Q13  *2342 .40   *131 .65    811 .00  *3566 .64  *1073 .26  *8724 .45
Q2   *2881 .32  *5829 .25 *10014 .16   2468 .00  *1296 .15  *2728 .21   (championship)
Q1     88 .00    501 .00  *3566 .48   1768 .00  *5962 .49   *190 .00
Q7   5813 .00  *3566 .71   9644 .00  *1735 .44   1119 .38   5000 .04
Q5  *8724 .45    190 .09  *2342 .32   1512 .05   1721 .00  *5687 .31
Q1  *3481 .58  *3735 .27 *11242 .65  *6672 .26  10032 .00   5261 .00   (championship)
Q10   811 .00   1768 .00  *1512 .83   5687 .46   9644 .00   *131 .12
Q14  5000 .00  *1512 .80  *5422 .82     78 .00  *4909 .69     88 .00
Q12   151 .00  *2877 .62   1721 .00    501 .00   2423 .00  *1735 .24
Q9   1721 .58  *8724 .53  *4909 .48  *5962 .61   *151 .66     78 .00
Q8  *4041 .56  *2342 .51    501 .00   5422 .00   2079 .06  *1153 .62
Q2   6328 .00     78 .00  *1073 .48   9644 .00  *1735 .00   4041 .00
```

Why slots stay empty:

- Some Week 0 videos (Q3) frame the wide shot high, so the near half of the field is hidden behind the close-up seam.
- Week 0 staff stand at the rail in front of the field.
- Robots behind the hubs are hidden.
- Some bumpers are dark navy or have small numbers that OCR never reads in the wide shot. Q14's 5000, 78 and 88
  are visible but never read.
- Close-up camera reads, 805 exact reads on the right colour, are **not** used: they cannot be placed in the wide
  shot without a camera mapping.

## Identity spot-check against frames

Random identified detections were cropped from full-resolution frames and the bumper was read by eye.

| Sample | Correct (number readable and matching) | Wrong | Unreadable (right colour, number not legible) |
|---|---|---|---|
| Voted tracks, default rule (36) | 23 | 4 | 9 |
| Inherited fragments (12) | 4 (+4 plausible) | 3 | 1 |
| Tracks that only qualify under the 1-moment rule (12) | 8 | 2 | 2 |

About 85% of readable voted detections are correct. The errors come from three causes:

- **ID switches** between two same-colour robots driving close together: a 1512 robot labelled 5422 for a while.
- **Week 0 FTA's navy shirt:** one remaining case.
- **Blue ramp edges** next to a robot whose number was read.

Inherited fragments are only 6% of identified detections (657 of 10,320) and are the weakest part. The first
iteration had no shape filter, used a 35% static threshold and allowed one-moment votes. It made many more
person/ramp errors (8 wrong of 24). Those findings drove the final rules.

## Alliance-relative positions

**Zone check against ViperScout zone times** (teleop, 46 Week 0 robots with ≥ 30 identified positions, about 10 s):

| Zone | ViperScout share | Track share | Pearson r | MAE |
|---|---|---|---|---|
| Own alliance zone | 0.66 | 0.53 | 0.57 | 0.22 |
| Neutral | 0.33 | 0.44 | 0.60 | 0.21 |
| Opponent | 0.01 | 0.03 | 0.21 | 0.03 |

The dominant zone agrees for 32/46 robots. Tracks under-count time in the own zone. Two likely reasons: robots
near the alliance walls are more often hidden by staff and hub structures, and the zone boundary is drawn through
the hub centre line.

**Fuel activity.** The target is a ViperScout fuel entry for that robot within ±2 s, using
`outside_video_time` alignment and the same 23 s teleop offset as the adapter. Data: 3,250 identified robot-seconds,
266 positive, 49 robots, 15 matches. The fuel rate is 0.11 in the own zone, 0.04 in neutral and 0.00 in the
opponent zone. Leave-one-match-out logistic regression, AUC within each held-out match (weighted by positives):

| Features | Held-out AUC |
|---|---|
| Time only (phase, match time) | 0.46 |
| **Position** (zone, u, hub distance, speed) | **0.66** |
| Position + time | 0.62 |
| Untrained −u (closer to / inside own zone) | 0.66; > 0.5 in 10/14 matches; robot-bootstrap 90% interval 0.57–0.72 |
| Baseline: video action head (auto-scout-quality.md) | 0.509 |

Pooled-across-folds AUCs are lower (0.56 for position, 0.35 for time). That is an artefact of fold intercepts:
a held-out match with many positives is trained on fewer positives. The per-match AUC ranks only within the unseen
match. Results with the 1-moment rule are the same (0.65 position, 0.46 time).

No ratings are used anywhere: no EPA, Statbotics or other rating-style features, priors or baselines. Every
method below uses only the video (overlay scoreboard and tracks) and the training matches. The exception is
**team history**: the team's ViperScout values from its other matches. It is scouting data, not video, and is shown
only as a reference.

**Traditional-form fields, per robot and phase** (all Week 0 ViperScout records, leave-one-match-out MAE).
"Displayed rise" is the alliance's on-screen score increase over the phase, read from the overlay. The
calibrated rows rescale it to ViperScout's counting using the training matches only. ViperScout totals run
below the broadcast scores.

| Method | Auto fuel (84 robots, mean 3.5) | Teleop fuel (90 robots, mean 16.5) |
|---|---|---|
| Training mean | 4.84 | 18.77 |
| Equal split of displayed rise, uncalibrated | 5.71 (n=69) | 21.65 (n=75) |
| Equal split of displayed rise, calibrated | 4.80 | 18.04 |
| Tracking split (own-zone share, shrunk to the training average) of displayed rise, calibrated | 4.88 | 17.96 |
| Team history from scouting (not video) | **3.62** | **10.43** |

- Only 12 robots have ≥ 30 tracked positions in auto, and 46 in teleop.
- On the tracked teleop robots, the alliance's displayed rise ÷ 3 correlates with fuel at r = 0.47. The
  own-zone share does not (r = −0.12).
- Tracking shows *when* a robot is likely shooting (activity AUC above). It does not yet say *how much* fuel
  it scores.

**Endgame climb:** this Week 0 ViperScout export records only 2 climbs among 90 robots: qm11 190 at level 3 in
teleop, and qm14 5000 at level 1 in auto. That is too few to evaluate any climb detector. The championship
matches have human climb tags, not ViperScout forms.

**Robot points** (ViperScout fuel + climb, 39 robots with ≥ 20 s identified), leave-one-match-out MAE:

| Method | MAE (points) |
|---|---|
| Training mean | 17.0 |
| Equal split of displayed final alliance score, calibrated | 17.6 |
| Position summaries, ridge (own-zone share, near-hub share, opponent share, mean hub distance) | 18.4 |
| Team history from scouting (not video) | **9.9** |
| Team history + ½ position adjustment (not video-only) | 10.7 |

With the 1-moment rule (48 robots), the training mean, position ridge, team history and combined rows give
18.2 / 17.8 / 10.6 / 10.6. Correlations of the position summaries with points are |r| ≤ 0.13.

## Conclusions

- Tracking with track-guided OCR identifies **58/102** robot-match slots by default (68 with a single-read rule),
  versus 50 confirmed today. Mean continuous coverage is only **24–31%** of match time. The limit is the wide shot
  itself (framing, occlusion, unreadable numbers), not the tracker's speed.
- Positions carry real signal for *timing*: the dominant zone matches ViperScout for 70% of robots. Position
  alone ranks ViperScout fuel activity at **AUC ≈ 0.66** on unseen matches, against 0.51 for the current video
  head. This is the first video feature here that beats chance on held-out matches.
- Video-only estimates of per-robot fuel counts and points are **not** yet better than the training mean.
  Scouting history is much better, but it is not video evidence. Getting counts from video needs per-robot
  attribution of each displayed score increase: next step 3.
- Climb cannot be evaluated from this ViperScout export.

## Suggested next steps (not done)

1. Wire `track_match()` into preparation behind a pipeline version bump. Use per-robot-second position features
   for the `scoring` activity head, gated by the existing held-out PU check.
2. Map close-up reads into the wide shot (a per-video homography learned from robots seen in both), and use the
   close-up cameras as a second tracking view. This targets the empty slots.
3. Attribute each displayed alliance score increase to the robots that were in their own zone, and active, in the
   seconds before it (item 2 of auto-scout-quality.md). Check the per-robot, per-phase fuel counts against
   ViperScout.
4. Reduce ID switches between same-colour robots: keep tracks apart when OCR disagrees mid-track, or split a track
   when its votes change team.

The evaluation scripts (`analysis.py`, `viper.py`, `spotcheck.py`) are in the session scratch folder, not the repo.
