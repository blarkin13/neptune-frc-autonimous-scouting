# Neptune Auto Scout: independent computer-vision review

Reviewed: `Neptune_Training_Independent_Review.zip` (REVIEW_CONTEXT.md, report-5, engine 2.2.8-imported-timing-preview1). All engine files listed in `engine-manifest.json` matched their SHA-256. `neptune_helper.py`, `neptune_setup.py` and `neptune_shared_models.py` are in the ZIP but not in the manifest, so they were treated as unverified context only.

**Additional evidence used (not in the ZIP).** Report-5's own job is still on the Mac that produced it: `~/.neptune-trainer/jobs/9df8015cdc6ca57fbe77fa746816e153` (model `4e9f1007…`). Its label snapshot and its four prepared example bundles (`prepared/*/d962757b64…`, `4777fbd0f0…`, `70c55a2326…`, `89557faa31…`) contain:

- every label time;
- every accepted clip's track metadata (camera, phase, frames);
- the actual R3D embeddings.

Source videos and tracking `facts.json` had already been deleted by the media policy. Everything below that uses these bundles is marked **[bundle]**. The scripts are in `evidence/`. Nothing was trained, nothing was trained on Q7, and no labels or caches were modified.

## Summary

1. **Feeding and defense fail mainly upstream of any classifier: the engine loses verified robot identity in teleop.**
   - In qm3, the three robots carrying all 53 feed/defense labels (1255, 3005, 7691) have verified-identity clips only in a close-up camera, and almost only in autonomous. 7691 has none after 28 s, yet its 13 defense labels span 38–131 s. **[bundle]**
   - 22 of the 40 feed labels failed even though OCR read the robot's number within ±1.1 s. Those are tracker/identity losses, not unobservable footage.
   - The other 31 feed/defense rejections cannot be classified without frames; the specific requests are listed below.
2. **The clip representation cannot carry these distinctions as currently supervised.**
   - On 365 real report-5 clips, the frozen R3D embedding predicts camera (AUC 0.94) and alliance colour (0.97) on held-out matches, but robot motion only at 0.68. **[bundle]**
   - The labels are confounded with exactly those properties. Every `gb:score_2_fuel` positive is a blue robot, 95% of `gb:score_1_fuel` positives are red, and all are close-up shots.
   - A head using only camera, alliance and phase does better (0.54) than the R3D head (0.44) on generic scoring.
   - Quantity codes are not defensible visual classes at 4 fps.
3. **The current metrics establish nothing either way.** Generic scoring's P-vs-U AUC has a 95% source-bootstrap interval of 0.37–0.57 over 4 videos. Every event hashes to the `training` split, so calibration and test are empty. The unknown pools contain known positives of the same physical action: in qm3, 43% of `score_2` references contain a labelled `score_1` moment for the same robot.
4. **The VideoMAE loss does not indict VideoMAE.** The difference is within sampling noise and the supervision confound applies to any frozen encoder. I checked and ruled out one candidate confound (the head's variance floor).
5. **One next implementation: identity v2 for the full-field view.** Native-resolution wide-shot OCR plus bracket-verified identity through contact and occlusion, with clear-reason telemetry. It has a pre-registered audit that can falsify it. Four small confirmed defects are patched separately, with tests (`neptune-2.2.8-review-defect-fixes.patch`).

---

## 1. Why every labelled feeding/defense action fails

### Execution path

`labeled_examples` (`neptune_training.py:259`) does the following for a human moment label:

1. Takes `sightings(facts)` for that team that pass `neptune_clock.eligible` within ±1.1 s (`:282`, `:295–300`). `sightings` (`:114`) merges two sources:
   - facts bumper OCR reads, every 2 s;
   - tracker localizations with `identity_method == 'yolo_botsort_ocr'`, dropping any whose chassis crop overlaps another identified robot's by more than 0.3 within 0.2 s (`:139–140`).
2. Calls `neptune_temporal.plan` (`:84`) on candidates nearest-first. `plan` requires a verified tracker point within 0.25 s, then 16 points at 4 fps in one track, one identity segment, one camera and one phase (`:98–119`).

Identity comes from `neptune_yolo._track_camera` → `Identities.update` (`:112`) → `recover_segments` (`:165`). An identity needs two exact reads at least 0.5 s apart inside one uninterrupted segment. The tracker OCRs each bumper once per second (`read_every=1.0`); facts reads arrive every 2 s.

### What the data shows [bundle]

Verified clips per robot in qm3 (unique accepted plus reference clips):

| Robot | Labels at stake | Verified clips (camera · phase) |
|---|---|---|
| 7691 | 13 defense (38.5–130.7 s), 4 feed (150.9–158.8 s) | 14, close-up-right, **auto only** (9.8–28 s) |
| 1255 | 11 feed (36.7–168.8 s) | 11, close-up-left, **auto only** (8–28 s) |
| 3005 | 25 feed (34.5–60.9, 100.8–103.4 s) | 11 close-up-right auto + 13 close-up-right ≥152 s |
| 2582, 7506 (scorers) | score_1 | 53 close-up-left teleop clips — they shoot in front of a close-up camera |
| Wide shot, whole match | — | 4 of 119 clips |

Report-5 gives tracking coverage of exactly 0.158 for 1255, 3005 and 7691, which is consistent with identity held for about the autonomous period. In teleop, verified identity essentially exists only while a robot is inside a close-up panel. Feeders working the neutral zone and defenders are mostly outside those panels.

### Label outcomes, separated

| Outcome | Feed | Defense | Meaning (from the code path) |
|---|---|---|---|
| `temporal_robot_track_unavailable` | 17 | 0 | A confirmed-identity, own-alliance, exact facts read existed within ±1.1 s, but no verified tracker point within 0.25 s. **The number was readable; the tracker had no identity.** |
| `temporal_robot_identity_gap` | 5 | 0 | A verified tracker anchor existed, but its segment was shorter than 16 contiguous points. **The robot was identified; the segment was fragmented.** |
| `robot_not_localized_at_label` | 18 | 13 | No sighting from either source. **Undetermined:** wide-shot with an unreadable number, cleared identity, or truly occluded. |

**Confirmed implementation/policy loss:** at least 22 of 40 feed labels. Report-wide, the same two outcomes account for 152 of 368 rejections. The diagnostic reports the *last* candidate tried (defect D1), but both outcomes are tracker-side regardless.

### Confirmed mechanisms in the code

- **M1 – contact clears identity.** `Identities.update` deletes a track's state when its bumper box overlaps any other detection by more than 0.35, or a person box by more than 0.65 (`neptune_yolo.py:120–123`). The test `test_crossing_or_person_occlusion_clears_identity` pins this. Re-identification then needs two new reads (at best about 1–2 s). Any 4-s clip spanning the contact fails `plan`. Defense is contact.
- **M2 – line-of-sight overlap drops training sightings.** `sightings()` rejects tracker points whose expanded chassis crop (about 1.6 × 3.4 bumper sizes) overlaps another identified robot's by more than 0.3 (`neptune_training.py:139`). In a side-on broadcast, robots at different depths on the same sight line trigger this without touching.
- **M3 – the wide shot is OCR'd at roughly half resolution.** Downloads are capped at 1080p (`neptune_helper.py:174`). The wide band is decoded at `width=960` (`_track_camera` → `decode`), and OCR crops are cut from that frame (`:323–329`). Close-up panels (half width) decode at about native resolution. This matches identity surviving only in close-ups.
- **M4 – no cross-camera handoff.** Identities never jump panels (`camera_views`). A robot verified in a close-up loses its identity when it drives into the region only the wide shot covers.
- **M5 – the person test is depth-agnostic (hypothesis about impact).** Overlap is divided by the *smaller* area, so a bumper inside a standing person's bounding rectangle is "occluded" even when the person is behind it. People boxes persist for a full second between samples (`:303–307`).

### Genuinely unobservable?

The engine records no reason when identity is cleared, so the 31 undetermined labels cannot be split from the code and report alone. The bundles show the robots were trackable at other times, and 22 feed labels had a readable number at the label time. So the evidence does not support "unobservable footage" as the main explanation. Requests R1–R2 below settle the remainder.

### Climb

The single `gb:climb_lv_1` (3679, 175.5 s) is very likely **after the buzzer**. Auto clips start by 8.0 s **[bundle]**, so nominal teleop end is about 171 s. `eligible`/`phase_at` drop the label, and tracking and OCR stop at the phase end. The engine then reports this as "not localized" (defect D1). A climb outcome is usually confirmed visually after the buzzer, so Game Builder outcome actions need a declared confirmation window (see §4).

### Concrete defects (patched, with tests)

- **D1 (diagnostics)** – The reason reported is from the last candidate tried, i.e. the farthest from the label. Phase-gate rejections are reported as `robot_not_localized_at_label`. Patch: report the nearest candidate's reason, record all candidate reasons, and add `label_outside_eligible_phase` tested on the label window itself.
- **D2 (diagnostics)** – `direct_bumper_reads` counts OCR tokens. Overlapping tiles read one frame several times, wrong-background reads are included, and the field does not count moments. Patch: add `direct_read_moments` and `verified_track_seconds`, keeping the old field.
- **D3 (cache key)** – `ensure_tracking` reuses cached tracking without checking `continuity_revision`. Any identity-logic change is silently skipped for cached matches. Patch: add a `CONTINUITY_REVISION` constant and check it.
- **D4 (reference contamination)** – See §4. Patch: exclude same-category known moments of the same robot from an action's unknown pool, without merging labels.

---

## 2. Can tracked 4-s crops + frozen R3D + PU/discriminant heads distinguish the actions?

**Representation.** The bumper box is expanded to a chassis crop (`crop_box`), then to clip context (`plan`, ±0.5 w, −0.25/+0.25 h). That is about 3.2 bumper widths × 5.1 bumper heights. It is resized to 171×128 and centre-cropped to 112 by the R3D transform. Each clip is 16 frames at 4 fps over 4 s, through frozen Kinetics-400 weights.

**Measured on 365 real report-5 clips** (held-out-match logistic probes; labels derived from tracker metadata, not humans) **[bundle]**:

| Property | Held-out AUC |
|---|---|
| Close-up vs wide camera | 0.936 |
| Red vs blue bumper | 0.968 |
| Robot moving (top third of displacement) vs still (bottom third) | 0.676 |
| Autonomous vs teleop | 0.586 |

The embedding is dominated by static appearance. Motion is weak because the crop *follows* the robot, so its own displacement is largely removed. The labels are confounded with exactly the dominant properties:

| Action | Positives | Close-up share (P / unknown) | Red share (P / unknown) | Sources |
|---|---|---|---|---|
| `gb:score_1_fuel` | 92 (2 robots = 87) | 0.98 / 0.49 | 0.95 / 0.68 | 1 match |
| `gb:score_2_fuel` | 38 (3005, 3679) | 1.00 / 0.51 | **0.00** / 0.74 | 1 match |
| `scoring` | 23 | 0.57 / 0.56 | 0.87 / 0.66 | 3 matches |

On `scoring`, the same production validation run with only three indicator features (camera, alliance, phase) gives AUC 0.537. The R3D head gives 0.442 (my CPU-path replication; report-5 shows 0.4595 from MPS float32).

**Per action:**

- **Scoring.** Launch motion is partly in the crop. *Success* is not: the hub is far away, and REBUILT hubs are inactive on alternate shifts. Official per-shift hub counts in Neptune's stored match breakdowns show the alternation. At best, a robot-crop head can learn "launching".
- **Feeding.** It uses the same launch mechanics. The difference is the target and trajectory, which are outside the crop. Not separable from scoring in this representation.
- **Defense.** It is two-robot relative motion. Contact frames are removed by M1/M2, so defense is absent from training and inference by construction.
- **Autonomous outcomes.** These are period-level outcomes (did the preload score, did it reach Level 1), not 4-s appearances.
- **Successful climb.** This is an end state, plausibly visible. Neptune already stores **official per-robot tower results** (`autoTowerRobotN`, `endGameTowerRobotN` in the score breakdown, table `augur_epa_alliance_samples`). For Q7 they list 4295 (red station 1) at auto Level 1 and endgame Level 2, matching the human observation, and 8507 at endgame Level 1. These are independent references for climb evaluation, not EPA.

**Quantity codes.** `gb:score_1_fuel` and `gb:score_2_fuel` are not appropriate visual prediction targets. They are the same physical action; a one-versus-two-ball burst is not resolvable at 4 fps in a 112-px crop; and here they are perfectly separable by bumper colour, so a head would look good and mean nothing. Keep the exact codes as labels and provenance. Treat them as one launch family for clip learning, and derive quantity from counted evidence: the on-screen hub counter and score deltas, attributed with uncertainty and never forced to sum.

---

## 3. Incomplete scouting and delayed timestamps

**Missing marks** are treated as unknown, which is correct: `unlabeled_examples` never assigns `y=0`. But PU bagging and the Lee & Liu criterion assume labelled positives are selected at random (SCAR). Here they are selected by robot, match and camera, and the confound above shows the head learning that selection. The P-vs-U AUC is then not a monotone proxy for true AUC.

**Imported timing.** `aligned_record` (`neptune_training.py:238–256`) sets the window to [click − 3 s, click]. The 1.1-s clock-join uncertainty is recorded but not added. `labeled_examples` then requires *one* 4-s clip that covers the whole window (`:307`). Only clips starting in [click − 4, click − 3] qualify, which caused 18 `external_reaction_window_not_covered` rejections. Accepted positives place the action anywhere inside 4 s. The imports are also not single events: ViperScout activity rows carry `quantity` (e.g. 10 fuel in one click) at 1-s `source_seconds`.

**Defensible alternative, without labelling arbitrary frames positive:**

1. **Measure the delay instead of assuming it.**
   - For counted-scoring clicks, the facts pipeline already OCRs each alliance's score once per second (`accepted_scores`).
   - Per source, histogram *click time − nearest preceding own-alliance increment*, against a time-shuffled null. That gives an empirical delay distribution, its 95th percentile D95, and any constant source offset.
   - Validate it on matches that carry both human video labels and imports. **None of the 4 report-5 matches do.**
2. **Multiple-instance bags.** Turn each click into a bag of 1-s-stride clips over [click − D95 − u, click + u], where u is the join uncertainty.
   - Train with a bag-level objective: positive if at least one instance is positive (top-k mean or noisy-OR). No single clip is ever asserted positive.
   - Exclude the whole bag span from the unknown pool.
   - Use the click `quantity` only as a bag-level count target for a count model, never as a clip label.

---

## 4. Splits, contamination, phase gating, score attribution; what the metrics mean

- **Splits.** `split_group` hashes the event key. `2026ctwat` and `2026txcmp1` both land in `training` (hash mod 10 = 0), so calibration and test are empty. All evidence comes from `validate_positive_unlabeled`, grouped by source video over 3–4 positive sources.
  - Folds are not team-disjoint. The same robots recur across matches at an event (e.g. 7506 in qm3 and qm35), and the embedding encodes appearance strongly. Report team-disjoint results, or at least team overlap.
- **Reference contamination (measured [bundle]).** In qm3:
  - 26 of 60 `score_2` unknown references contain a labelled `score_1` moment of the same robot;
  - 10 of 44 `score_1` references contain a `score_2` moment;
  - 41 of 75 legacy `scoring` references contain a Game Builder score label.

  Known positives of the same physical action are being placed in U by construction, which directly depresses P-vs-U AUC. Patch D4 excludes same-category moments (Game Builder `tag_category`; legacy and imported scoring rows also carry `Scoring`) from an action's unknown pool. It merges nothing.
- **Phase gating.** `eligible` gates only legacy `auto_`/`end_` tags. Game Builder actions carry no allowed-phase metadata. Outcome actions confirmed after the buzzer are dropped (the climb above). Add `allowed_phases` and `confirmation_window_s` to the Game Builder action definition. Use them for the label join and for clip timing, never to label extra frames positive.
- **Score attribution.**
  - `neptune_scoring_model.descriptor` averages legacy 12×12 RGB crop features into a 288-d vector.
  - An RBF kernel ridge regresses mixed targets: imported "reported points" (e.g. 6328 = 372) and human contribution estimates.
  - Leave-one-match-out MAE is 83.6 versus 85.9 for the training mean, so `video_ready` is false and `vision_weight = 0`.
  - With that, `predict` returns *unknown* for every robot; no numbers are produced. That output is correct and honest.
  - `team_priors` is still computed and stored by `train()` (`:640–643`), but `predict` never reads it. Remove it to avoid implying history is used.
- **Challenge cases (5411 → 87, 8370 → 62).** A kernel ridge predicts bias + Σ cᵢ·k(x, xᵢ). For a robot unlike every training robot, k → 0 and the prediction collapses to the training-target mean. Report-5's target mean is 96.6, and even in-sample low scorers were pulled up (1255: 0 → 17; 2064: 1 → 36; 2785: 0 → 46). A large estimate for a robot that scored nothing is the expected failure mode, not evidence. R6 confirms this for the exact artifacts.
- **What the metrics do establish.** P-vs-U grouped AUC of 0.4595 on 23 positives from 3 sources; 95% source-bootstrap interval 0.37–0.57 **[bundle]**. Reports 3, 4 and 5 give 0.506, 0.503 and 0.460 on different match sets: consistently no detectable signal.
- **What they do not establish:** precision, recall, robot attribution or score accuracy. Observer point estimates are not official totals. A fitted score head is not validated accuracy.

---

## 5. VideoMAE versus R3D

**Evidence.** On identical crops (344 rows, 34 positives from 4 sources), R3D scored 0.536 and VideoMAE 0.429; neither passed. With 4 sources, the R3D interval on report-5 data spans about 0.2. A 0.11 difference cannot rank the encoders.

**Ruled out.** `fit_binary`'s absolute variance floor (0.01) is the only scale-dependent part of diagonal LDA. Only 1 of 512 R3D dimensions falls below it **[bundle]**, and VideoMAE's `fc_norm` output is unit-scale. It does not explain the gap.

**Most likely explanations (hypotheses, each testable):**

1. **Supervision confound.** Labels track alliance and camera, so any frozen encoder plus a linear head learns colour. This is supported by the metadata-only result.
2. **Crop representation.** The robot-following crop removes motion, target and hub context.
3. **Head.** Diagonal LDA in 512–768 dimensions from 25–34 positives, with no tuned shrinkage.
4. **VideoMAE input mismatch.** 16 frames over 4 s at 4 fps versus its pretraining sampling (about 2 s, tubelet 2), and a 171×128 → 224 upsample inherited from the R3D path.

**Discriminating tests:**

- AUC within same-alliance, same-camera strata;
- features residualized on camera and alliance;
- a cluster bootstrap of the paired AUC difference (R7);
- VideoMAE on the same tracks with native sampling.

This comparison does not test VideoMAE fine-tuning.

---

## 6. Recommended next implementation: identity v2 for the full-field view

**Why this one.** Every robot-specific output depends on knowing which robot is in the crop in teleop: tags, counted scoring attribution, traditional scouting counts. Today that holds almost only inside close-up panels. No encoder, head or extra match fixes that.

### Code changes

These touch `neptune_yolo.py`, two lines of `neptune_training.py`, and the engine version.

**A. Native-resolution OCR for downsampled panels.** In `_track_camera`:

```python
native = 2*round(source_width*(right-left)/2)
hires = decode(video, *band, start, end, 1/read_every, native, left=left, right=right) if native > 1.25*width else None
# on each sample frame (same grid: start + k*read_every):
th, W, H, y2, u2, v2 = next(hires); assert abs(th - t) < .5/fps
image_hi = cv2.cvtColor(np.stack([...], 2), cv2.COLOR_YUV2BGR); s = W / w
crop = image_hi[int(b*s):int(e*s), int(a*s):int(c*s)]   # then x2 upscale for OCR
```

Facts-read matching is unchanged. Cost is one extra 1-fps decode of the wide band.

**B. Bracket-verified contact episodes.** In `Identities.update`, on `crowded` or `occluded`:

- Do not delete the state.
- Open `contact = {pre: segment, start: t, with: overlapping ids, person: bool}`.
- Give contact frames a new segment; emit no team online.
- Ignore reads during contact (they may belong to the other robot).
- Cancel the episode if it lasts longer than 6 s, or on a cut or a gap of more than 1.5 s.
- When contact ends, open a post segment and append the episode `{track, pre, contact, post, with, start, end, scene, alliance}`.

In `recover_segments(points, confirmations, invalid, sha, episodes)`, verify a contact segment for team A only if:

1. the `pre` and `post` segments are each verified by the existing rule (two exact reads ≥ 0.5 s apart) to A;
2. every **same-alliance** participant has its own episode in the same window, with `pre` = `post` ≠ A;

   otherwise a swap cannot be excluded and nothing is verified. Opposite-alliance participants cannot swap, because a colour change already deletes the state.
3. Verified contact points get `identity_evidence.contact_bracket = {pre_anchors, post_anchors, participants}`.

The online behaviour that `test_crossing_or_person_occlusion_clears_identity` asserts is unchanged.

**C. Training sightings.** In `sightings()`, keep tracker points that carry `contact_bracket` even when they overlap another robot (marked `contact: True`). The overlap rule stays for facts-read crops.

**D. Telemetry.**

- Count identity clears by reason per camera and team: `crowded_robot`, `occluded_person`, `gap`, `jump`, `alliance_change`, `conflicting_read`, `duplicate_team`, `cut`.
- Add per-phase, per-camera verified seconds.
- For each rejected label, record the nearest verified point and the last clear reason before the label.

Set `CONTINUITY_REVISION = 'contact-bracketed-v4'`; D3 ensures cached tracking is rebuilt.

### Repeatable tests

Synthetic detections and reads, no video:

1. Teammates cross with matching brackets → contact frames verified for both.
2. A swap (post anchors exchanged) → contact rejected and the segment invalidated.
3. One participant lacks a post anchor → neither participant's contact frames are verified.
4. A contact longer than 6 s, or a cut inside contact → unverified.
5. Person occlusion with brackets → verified; without → unverified.
6. Opponent contact → each robot verified on its own bracket.
7. High-resolution reader stays frame-aligned with the sample grid; crop scaling is exact; low-resolution panels skip it.
8. `ensure_tracking` rebuilds on a revision change.
9. `sightings()` keeps bracketed contact points and still drops overlapping facts-read crops.
10. The existing suite passes.

### Platforms

No new dependencies: the existing ffmpeg, numpy, cv2 and ultralytics 8.4.63. Timing limits are in seconds, so CPU (capped at 3 fps), MPS and CUDA behave the same. Extra decode cost is about one 1-fps full-resolution band per camera. Measure helper runtime; the budget is ≤ 25%.

### Independent real-video evaluation that can prove it wrong

- **Matches:**
  - Mercury Q7 (reserved; evaluation only);
  - Apollo Q3;
  - two matches from an event and match list never selected for any training job.
- **Runs:** old engine, A only, B only, A+B.
- **Audit:** a reviewer who did not build the change audits 300 accepted identity points, stratified (150 newly gained or contact-bracketed, 150 baseline). The auditor sees the full-resolution frame and box and ±2 s of video, then records the bumper's team from the roster or "cannot tell".
- **Pre-registered pass criteria:**
  - identity precision on new points ≥ 99%, with Wilson 95% lower bound ≥ 97%, and not worse than baseline;
  - median per-robot verified teleop coverage at least 2× baseline;
  - at least half of the qm3 feed/defense labels whose robot the auditor marks visible yield a clip.
- **Falsifiers:**
  - any accepted swap rate above 1% rejects B;
  - a coverage gain below 1.2× means identity policy and resolution are not the bottleneck, and the detector (missed detections) is;
  - feed/defense clips still near zero with visible robots means the cause is elsewhere, and telemetry D will show where.

Action accuracy is evaluated afterwards on Q7's complete six-robot reference, never trained on.

### Next year's game

- Bumpers with team numbers are a standing FRC rule, so this layer is season-agnostic.
- The detector bundle is per season (`manifest.seasons`) and is retrained only if bumper appearance changes.
- Game Builder codes are untouched; categories drive D4.
- The contact bracket benefits interaction actions in any game.
- Per-broadcast layouts stay in `camera_views`.

### After identity v2 (not part of this recommendation)

Counted scoring from on-screen hub and score deltas attributed to launching robots, with intervals and unknown where ambiguous; multiple-instance imported labels with a measured delay; official per-robot tower results as climb references.

---

## Evidence requests

| # | Artifact | Question it resolves |
|---|---|---|
| R1 | Job `9df8015c…`, qm3 `localizations/<sha>/<fingerprint>/facts.json`, or a re-run with telemetry D | For each of the 53 feed/defense labels: camera, whether YOLO detected the robot, and the last identity-clear reason. Attributes losses among M1–M5. |
| R2 | Full-resolution frames at t−1, t, t+1 s for the 31 undetermined labels (times in Appendix) | Visible-and-readable, visible-but-unreadable (wide), occluded, or out of view: implementation versus unobservable. |
| R3 | qm2 facts for 2468 (40 exact reads, 0 localized) | Which tiles and cameras produced the reads; whether YOLO boxes contain the read centres. |
| R4 | qm3 `periods` and clock samples | Confirms whether the climb at 175.5 s is post-buzzer. |
| R5 | ctwat_qm6 facts (`accepted_scores`, clock samples) plus its 66 imported rows | Empirical observer-delay distribution and D95 for the multiple-instance window. |
| R6 | Model artifacts and trial results behind 5411 = 87 and 8370 = 62 | Confirms the regression-to-mean bias for those exact models. |
| R7 | Per-example out-of-fold scores of the R3D/VideoMAE comparison with camera and alliance | Stratified AUC and a paired cluster bootstrap: encoder versus supervision. |

## Constraints honoured

- No labels, imports, Game Builder codes or historical artifacts changed.
- No training on Q7.
- No alliance-sum normalization.
- Feeding is never treated as points.
- Evidence gates are not weakened. Contact verification requires anchors on both sides, which is stricter than today's backfill within a segment.
- Uncertain observations stay uncertain.

## Appendix: qm3 feed/defense label times (s) and current outcome [bundle]

- **7691 defense:** 38.5, 69.8, 72.3, 78.5, 81.3, 85.1, 92.9, 98.4, 103.5, 105.6, 121.8, 129.7, 130.7. All not localized.
- **7691 feed:** 150.9, 153.4, 156.2, 158.8. All not localized.
- **1255 feed:**
  - not localized: 36.7, 40.7, 65.5, 65.8, 158.1;
  - track unavailable: 41.9, 97.8, 100.4, 114.5, 156.4, 168.8.
- **3005 feed:**
  - identity gap: 34.5, 35.4, 35.6, 60.7, 60.9;
  - track unavailable: 45.2, 45.9, 46.1, 46.6, 46.8, 47.0, 58.2, 58.3, 103.0, 103.2, 103.4;
  - not localized: 100.8–102.8 (9 labels).
- **3679 climb Level 1:** 175.5 (likely post-buzzer).

Patch: `neptune-2.2.8-review-defect-fixes.patch` (D1–D4 plus `test_review_patches.py`). It applies to the packet's 2.2.8 files. Packet suite: 154 of 156 pass both before and after; the 2 remaining errors need Game Builder PHP files that are not in the ZIP. The new tests pass on the patched engine and 4 of 5 fail on the original.
