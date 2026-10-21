# Auto Scout quality: diagnosis and fixes — October 19, 2026

The 17-match batch (`cc13970d…`: 2 human-tagged Mercury matches, 15 Week 0 matches with
ViperScout records) produced unusable test output. The causes were measured by
replaying that exact batch offline against the helper's saved videos, OCR and
features (`~/.neptune-trainer`), using leave-one-match-out checks. Nothing in the
database, the saved caches or the running helper was changed by the analysis.

## What was wrong

**Action tags were noise.** The scoring head fired on 1,035 of 1,100 robot sightings
(94%), so Qualification 35 got 105 "scoring" tags, one every 2–4 seconds for every
identified robot. The PU threshold was the *lowest* score of any training positive
(−40 on a scale where the median sighting scored −6). On matches it had not trained on,
the head ranked ViperScout-timed scoring activity at AUC 0.50, which is chance. Raw
pixels and an engineered colour/motion/position feature set scored 0.43–0.50. The other
three heads were each fitted from two examples in one match.

**Robot points did not add up and were worse than guessing.** The point regressor
learned from low-scoring Week 0 reports. On a 272-point championship alliance it
predicted 46/18/16, and the alliance constraint could only scale down, so 70% of the
score stayed unassigned.
Leave-one-match-out on Week 0 gave video MAE 20.4 points, against 16.9 for predicting
the training average and 9.8 for each team's average from its other matches.

**Half the robots are never identified.** Bumper numbers are OCR'd every 2 s in the
close-up cameras. Only 50 of 102 robot-match slots reach `confirmed` (29 candidate,
23 never read). Identified robots have a median of 22 sightings per match. 442 of 687
labels were lost because no confirmed sighting fell within 1.1 s of the label. This is
the main limit on video learning. More labels alone will not fix it.

## What changed

Helper (`neptune_training.py`, `neptune_scoring_model.py`; server copy synced):

- **Action heads must show held-out signal.** Each PU head is cross-fitted by match
  video. It ships only with ≥8 positives from ≥3 matches and a held-out P-vs-U
  ranking ≥ 0.60. Its threshold maximises the Lee & Liu PU criterion on held-out
  scores, flags at most 35% of footage, and is mapped onto the final head by quantile.
  Otherwise the report says `no_held_out_signal` or
  `needs_more_positive_examples_across_matches` and no head is shipped. Older
  heads with `provisional_training_positives` thresholds are skipped during prediction.
- **Known alliance totals are fully split.** Points always sum to the TBA final
  alliance score, using largest-remainder rounding. Shares come from team history:
  each team's share of its reported alliance sum, so Week 0 and championship scales
  agree, shrunk by n/(n+1). Missing history falls back to an equal split. EPA is not used. Video estimates adjust the split
  only when leave-one-match-out video error beats the training mean by 10%. Robots
  that were never identified still receive a split. Their `reason` records the basis,
  e.g. `allocated:equal_split;insufficient_robot_sightings`.
- The training report now includes `validation` for each PU head and for scoring
  (team history versus an equal split; video versus the training mean). The page
  shows these under **Held-out checks**.

Page: each allocation shows its basis (team history, equal split, video).

## Replay of the same 17-match batch

| | Before | After |
|---|---|---|
| Action heads shipped | 4 (scoring fires on 94% of sightings) | 0 (scoring held-out AUC 0.509) |
| Q35 action tags | 106 | 0 |
| Q35 red points (272 total) | 7506 46 · 7503 18 · 3005 16 | 91 · 91 · 90 (no history for these teams → equal split) |
| Q35 blue points (199 total) | 1477 48 · 5261 26 · 11200 unknown | 67 · 66 · 66 |
| Team-history share error (LOO, 29 alliances) | — | 0.221 vs 0.296 equal split |
| Video point error (LOO, 18 robots) | — | 30.7 vs 29.8 training mean → video weight 0 |

ViperScout totals are weak references. Their alliance sums are often far below the
broadcast score. These numbers compare methods; they are not accuracy claims.

## What would actually improve video scouting

1. **Robot tracking.** Detect red/blue bumpers in the wide shot, track them between
   frames, and attach OCR identities to whole tracks. This gives all six robots
   continuous positions, and positions give real features: zone, hub proximity,
   cycle timing.
2. **Score-timeline attribution.** The overlay already gives each alliance's score
   once per second. With tracks, fit each robot's contribution to score increases
   without labels, and use ViperScout to check it.
3. More human-tagged matches across ≥3 matches per action. The gate ships a head
   automatically once it beats chance on unseen matches.

Deploy: rebuild the trainer ZIPs, install the updated JS file (no server PHP change), then start a **new**
training batch. Existing candidates keep their saved heads. A new helper skips
their uncalibrated action heads and re-splits their scores.
