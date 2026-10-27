# Persistent robot identity prototype

`engine/neptune_persistent_identity.py` adds source-bound identity records to the current tracker. Fresh tracking returns them under `persistent_identity`; the cached-tracking path computes the new layer from saved observations without rerunning detection. The original localizations, action training eligibility and release gates remain unchanged. This source change has not been built into or deployed as a helper release.

## Behavior

Each of the verified roster's six teams has a stable ID derived from the source-video fingerprint and team number. Observed tracklets are split at missing intervals, recycled tracker IDs, camera/scene boundaries and implausible jumps. OCR-supported tracklets reconnect to that record across long gaps. Conflicting reads and simultaneous duplicate identities block propagation. Appearance proposals compare camera-local median color descriptors against OCR-supported exemplars, require separation from competing teammates and reject competing targets. They never seed further exemplars or become training labels.

`state_at` reports visible or not-observed states. It keeps last-seen time but does not invent a box, position, action or scoring evidence during a gap. Camera-specific returns and returns after gaps in supported assignments across all views are recorded separately. An assignment gap is not proof of physical absence from the video.

The appearance feature is the existing 24-value color descriptor. This is not a newly trained robot-specific ReID network, whole-robot detector, or Ollama integration. Offline processing can use later anchors; it is not a claim of online performance.

## Q4 development test — October 25, 2026

The test reuses the exact 5,336 raw observations from the fresh Q4 baseline, so detector variation does not explain the comparison. Saved human corrections are withheld from matching. Q7 is excluded.

| Result | Value |
|---|---:|
| Persistent roster records | 6 |
| Tracklets | 1,059 |
| OCR-supported return events after gaps across all assigned views | 28 |
| OCR-supported returns to individual cameras | 26 |
| Camera-return appearance proposals | 17 |
| Baseline identity availability | 380 / 966 samples (39%) |
| Persistent OCR-supported availability | 308 / 966 samples (32%) |
| Including unverified visual proposals | 325 / 966 samples (34%) |

**It did not improve overall Q4 identity availability.** The record/reconnection machinery works, but these results do not establish improved identity accuracy or continuous whole-match tracking. The baseline includes existing roster/motion inferences; the new layer is more conservative. It does not replace the baseline localizations.

Of 224 existing human-corrected points, 32 could be matched to assigned crops and all 32 agreed; 192 remained unassigned. This is a nonrandom development check, not an independent full-match accuracy benchmark. The 28 return events have OCR support, not independent verification of correctness.

111 tests pass across persistent identities, existing identity/review tests, tracking, review-learning, temporal clips and training integrity. Tests cover long gaps, duplicate identities, recycled IDs, ambiguous same-looking teammates, competing visual targets, conflicting reads and camera separation.

Artifacts and reproduction scripts: `local/q4-persistent-identity-20261025/`. The source-native quality revision is 1920×1080 at 60 fps, with a five-second intro and eight-second result card. Tracking remains sampled at 3 fps. Video source times therefore map to journal playback time +5 seconds.

Next experiment: preserve the baseline's useful assignments while adding independently checked appearance-based reconnection. Compare a trained robot-specific visual representation and selected Ollama bumper reads on unresolved tracklets; do not promote unverified proposals into training or claim off-screen actions.

## Constant identity layer — October 26, 2026

`engine/neptune_constant_identity.py` (`constant-identity-v2`) carries each robot's number along tracker tracklets, and its labels feed scoring attribution as `identity_method: constant_identity`. They are never training labels: `neptune_training` and `neptune_temporal` do not accept them.

- **Seeds** are existing trusted labels only: OCR-verified tracker segments, the roster solver's OCR-verified points and same-number-through-contact points. A roster-only guess seeds a tracklet only in the wide view (all six robots on screen) or when the tracklet has a number read.
- **Tracklets** end at gaps over 1 s, jumps, scene cuts and same-alliance contact. A tracker swap during a collision therefore cannot carry a number out. A contact stretch keeps its number only if the same tracker track leaves contact with the same OCR team.
- **Links** join an unlabeled tracklet to a labeled one that ended (or starts) within 1.5 s in the same camera shot. The link must pass the motion and size gate, match colour (≤ .11) and agree with every number read. No other tracklet may be a near-equal match, whether it is named, unnamed or in contact. Nothing is linked across a camera cut. After a cut, only OCR or the roster can name the robot.
- **Elimination** in the wide view names the third robot of an alliance when the other two are labeled for that tracklet's whole life. The tracklet must move, with no other unlabeled same-alliance box.
- **Exclusivity**: two tracklets claiming one team in one camera at the same time both lose the carried label.

`with_roster_inferred` also changed. In a close-up, a roster-only inference now needs a number read on its track. A close-up shows only part of the field, so elimination there labeled a still box that the reviewer had marked "not a robot": 60 boxes in QM3.

### Measured on the two reviewed matches (Q7 never used)

`neptune_identity_metrics.evaluate` scores labels against saved human review points (corrected = expected team, excluded = not a robot). The review points are never an input. A switch is a change of assigned team between consecutive labeled sightings of one reviewed robot in one camera. Lost-track seconds are 1/3 s samples in the match window with no labeled box for that robot in any camera. They include genuinely off-screen time.

| | QM4 before | QM4 after | QM3 before | QM3 after |
|---|---:|---:|---:|---:|
| Reviewed robot boxes correctly labeled | 21 / 224 | **46 / 224** | 0 / 23 | 0 / 23 |
| Wrong team | 0 | 0 | 0 | 0 |
| Identity switches | 0 | 0 | 0 | 0 |
| Human-excluded non-robot boxes given a team | 0 | 0 | 60 | **0** |
| Lost-track seconds per robot (of 164 s) | 99.2 | 97.5 | 113.2 | 117.1 |

127 of QM4's 224 reviewed boxes have no matching detection in this detector run, so 46 of the 97 matchable boxes are now labeled (was 21). QM3's lost time rose because 60 false labels on a non-robot box no longer count as tracking. QM3's 23 reviewed robot boxes are contact or unread close-up boxes the layer deliberately leaves alone.

**Hidden-OCR check.** Every other OCR tracker segment is hidden. Its number reads are removed from the observations, the roster solver is rerun without them, and the layer relabels and is compared with the hidden OCR. QM4: 117 carried labels, all correct. QM3: 36, all correct.

An earlier version also had the rival rule ignore unnamed tracklets. It scored 430 of 430 on a weaker check, where the solver still saw the hidden reads. On this check it was 18 wrong of 381 on QM4: a scrum in the left close-up at 50–58 s carried 9492 onto 10340's track. A crowded-frame change was also tried and rejected: the roster solver kept three of the extra wide boxes instead of skipping the frame. That gave 5 wrong reviewed boxes and fewer correct ones.

Lost-track time barely moved. Most of it is detection and OCR coverage, not identity carrying. In QM4 wide frames, 1,595 of 3,115 boxes sit in frames with more than three same-alliance detections, which the roster solver skips. The next lever is detector false positives and duplicate boxes in the wide view. Then come longer-gap re-ID by bumper number after cuts and a trained appearance model.

### QM1 review and the 1.5 s link gap (v2)

The owner reviewed QM1 on October 26: 951 corrected robot boxes and 1,589 boxes marked "not a robot". With the 2 s link gap, the layer put 6672 on 11 close-up-right boxes that were really 5261, at 99–101 s. Two blue robots crossed there. Track 169 (5261) ended, and 1.83 s later track 180 started with a 6672 read. Colour (.108) only just passed, because both bumpers are blue. A 1.5 s gap removes those 11 labels and keeps every QM4 gain. Gaps of 1.0 s and a tighter colour limit for gaps over 1 s scored the same on QM1 and worse on QM4 lost time.

| v2 (1.5 s) | QM4 | QM3 | QM1 before | QM1 after |
|---|---:|---:|---:|---:|
| Reviewed robot boxes correctly labeled | 46 / 224 | 0 / 23 | 151 / 951 | **175 / 951** |
| Wrong team | 0 | 0 | 0 | 0 |
| Identity switches | 0 | 0 | 0 | 0 |
| Non-robot boxes given a team | 0 | 0 | 3 | 3 |
| Lost-track seconds per robot | 94.2 | 117.0 | 83.9 | 82.2 |

QM1 first appeared to have 11 wrong boxes and 6 switches from existing labels: 10 from wide-view OCR segments and 1 from the roster solver. All of them were metric errors. The metric searched only labeled boxes, so a reviewed robot with no label of its own was matched to an overlapping, correctly labeled neighbour. `evaluate` now takes every tracker detection (`detections=observations`), so each reviewed box matches its own detection. The hidden-OCR check is now 128 of 128 on QM4, 36 of 36 on QM3 and 145 of 145 on QM1. "Before" here is the same engine without the constant layer.

Scripts and outputs: `local/identity-constancy-20261026/` (also `sweep.py`, `with-qm1.json`) (`measure.py`, `holdout.py`, `before.json`, `after.json`, `holdout.json`). "Before" ran the HEAD `bdf580c` engine.

### Look-based re-identification — tested and rejected (October 27, 2026)

Question: can a robot be named by its look alone after occlusion, cuts or replays, without a new bumper read? The test named each reviewed QM1 or QM4 robot box only by comparing its crop with OCR-verified detections of the same three alliance robots from the same kind of camera view. Those detections were taken more than 3 s from the query. The answer is then checked against the owner's review. Chance is 33%.

| Look features | Wide: right | Wide, confident | Close-ups: right |
|---|---:|---:|---:|
| Handcrafted: bumper hue/saturation shade, chassis colour, chassis gradients | 186 / 352 | 32 / 32 at margin .05 | ~50% even when confident |
| Our bumper detector's backbone (YOLO embed) | 134 / 352 | 0 / 4 | chance |
| DINOv2 ViT-S/14, bumper + chassis crops | 218 / 352 | 14 / 14 at margin .1; 63 / 88 at .05 | ~35% |

None reaches the zero-wrong bar at a useful coverage, so nothing was added to tracking. Wide-view robots are about 60 px wide, and the close-up gallery comes from other shots and angles. A second limit: for 430 of QM1's reviewed boxes, some robot on that alliance had no bumper read at all in that kind of camera view, so there is no reference picture of it. A future attempt would need a model trained on FRC robot identity, with labelled crops from reviewed matches, and more bumper reads to build galleries. Scripts: `local/appearance-reid-20261027/`.

### Tracking at 12 fps instead of 6 — measured on QM1 (October 27, 2026)

QM1 was retracked with this engine at 6 and 12 fps, then went through the same roster solver and constant layer, scored against the owner's review:

| | 6 fps | 12 fps |
|---|---:|---:|
| Detections | 6,530 | 14,486 |
| Reviewed robot boxes correctly labeled | 175 / 951 | 156 / 951 |
| Wrong team / switches / non-robots labeled | 0 / 0 / 3 | 0 / 0 / 3 |
| Lost-track seconds per robot | 82.2 | 76.5 |

12 fps cuts lost time by about 6 s per robot and adds no wrong labels. The lower correct count is partly a measuring bias: the reviewed boxes were drawn from the 6 fps run's boxes, so 12 fps boxes match them less often. The default stays at 6 fps, since 12 fps roughly doubles detections and processing. It is a candidate for crowded stretches only, or for runs where time does not matter.
