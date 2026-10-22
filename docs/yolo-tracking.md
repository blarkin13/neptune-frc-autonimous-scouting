# YOLO robot tracking replacement — 2.1.0 preview 1

This preview replaces the production tracker entry point, not the human tagging interface. It retains public tags, scoring estimates, imported scouting, game rules, queue snapshots, reservations, and model-release checks. It does not turn bumper tracking into successful-scoring recognition.

## Supplied models and provenance

The owner supplied the private repository `Prosper-FRC/2026-Scouting-Robot-Tracking`. The integration pins commit `dfb1751cdeef43f2a2816668813fb9a2ff5a5181`.

- `best_bumper_model.pt`: YOLO11n Detect head; classes `{0: red, 1: blue}`. SHA256 `48195a88722649418f4533b1199ee434e46328ddb1196fdc9e1cb4cc6293018f`.
- `coco_model.pt`: standard 80 COCO classes, including person. SHA256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`. Used only for person-occlusion context; it is rejected as the primary FRC detector.

Models were inspected statically, then actually loaded in an isolated environment. The upstream distance-only linker is not copied. Neptune uses the installed Ultralytics BoT-SORT implementation with native detector appearance features. Neither GitHub credentials nor personal connection tokens are included in source or model packages. The upstream repository has no top-level license file; models remain in secure server storage and authenticated owner downloads, not public base ZIPs. This is not permission to redistribute the private models publicly. Ultralytics is a separately installed AGPL-3.0/enterprise-licensed dependency.

## Execution path

`neptune_training.ensure_tracking` -> `neptune_tracking.track_match` -> `neptune_yolo.track_match` -> pinned bumper model + BoT-SORT + person-context model + Neptune OCR -> robot localizations -> existing action/score example preparation.

The default entry point no longer calls the legacy color-blob detector or distance linker. Legacy functions remain solely for historical source compatibility and regression fixtures. There is no silent fallback. Missing models or dependencies return an explicit tracking-unavailable diagnostic.

Frames are streamed from FFmpeg rather than expanded into thousands of on-disk images. CPU mode uses one PyTorch thread and at most three sampled frames/second; GPU mode defaults to six. OCR runs once per second on detected bumper crops. Temporary images are reused and removed. The source video, clock mappings, human tags and import records are not changed.

The bumper class supplies alliance color; it never supplies a team number. Two exact, roster-consistent number reads at separate moments anchor the track. Consecutive detections maintain that identity while the number is hidden. Crowding, conflicting OCR, a detected camera cut, a color change, a person occlusion, duplicate team assignments, or a detection gap longer than 1.5 seconds clear identity and require new anchors. Future OCR does not retrospectively label earlier footage. Appearance features assist association; they are not proof of identity across broadcast cuts.

Bumper boxes are expanded into explicit approximate chassis crops. They are not full-robot segmentation. Existing overlap checks still exclude ambiguous training crops. Actual localizations/coverage and the detector fingerprint are saved with preparation. The detector fingerprint also invalidates cached preparation and is attached to newly trained action models, preventing accidental reuse with different detector weights.

## Server and helper delivery

- Both environments ship identical engine source bytes and `requirements-yolo.txt`.
- Private weights and `manifest.json` are under `neptune_secure/community-learning/robot-models/` on Neptune.
- `download-trainer.php` validates the private model hashes and adds the bundle only after platform-owner authentication, when generating a personalized ZIP. Public base ZIPs deliberately do not contain weights or tokens. Do not hand users a BASE ZIP as a connected installer.
- Helper setup checks the bundle, installs the pinned YOLO/runtime dependencies once, then reports `robot_tracking=yolo-botsort-1`. Existing helper authentication and the page-v2 queue protocol are retained.
- The website refuses new work from an older helper missing that capability; already-running jobs can still heartbeat and finish. A worker process must be restarted after a server code upgrade to load the new code.
- Server prerequisites are installed in its existing private virtual environment with `python server_run.py --setup-tracking`, then the existing managed worker is restarted. Setup chooses CPU PyTorch wheels on Linux CPU machines. Do not run setup in the middle of an active job.
- Existing tags/imports are reused on the next training run. Existing saved videos can be reused. New detector/engine fingerprints cause derived crops/examples to be rebuilt. Historical models and reports are retained; retrain before judging predictions from the new localizations.
- The supplied bundle is currently enabled for 2026. Other seasons require an explicitly configured, verified compatible bundle; no 2026 rules are applied to another game.

## Retraining the detector itself

Robot action labels and scouting imports train actions/scoring; they are not bounding-box annotations. `neptune_detector_training.py` provides a local reviewed-box preparation/training command for CPU, MPS (`mps`) or NVIDIA (`0`). It starts from the supplied bumper detector and writes a separate candidate, never automatically replacing the active bundle.

Input JSON has `schema_version: 1`, `season: 2026`, `names: ["red", "blue"]`, and a `frames` list. Each frame needs `image` (relative local path), `image_sha256`, `source_sha256`, `match_key`, `split` (`train` or `val`), `reviewed: true`, `all_visible_bumpers_labeled: true`, and `boxes`. Each box has `class_id` (0 red, 1 blue) and `xywh` (normalized center x/y, width/height). Fully reviewed empty frames can have an empty box list. Missing annotations never become verified empty frames. All source frames from a match or video remain in one split. Identical images cannot be duplicated across splits. Reserved Q7 match/source is rejected from both train and calibration. Dataset YAML is generated locally, so uploaded executable paths/download directives are not executed.

Example: `python neptune_detector_training.py reviewed-boxes.json new-detector-run --device mps --epochs 30`.

The existing Neptune web queue still queues action/scoring training using this detector. A browser box-label editor and a separate detector-training queue are not included in this preview; the detector retraining tool is local. The provided pretrained detector allows tracking integration without waiting for those tools.

## Actual verification and limits

- A real 15-second Q7 clip ran end to end on CPU: 45 sampled frames, four bumper anchors, one anchored team track, ~20.7 seconds including model loading/OCR.
- A real 45-second clip ran on Apple Metal: 270 sampled frames, 18 bumper anchors, two anchored team tracks, ~31.9 seconds including model loading/OCR.
- These are execution checks, not recognition-accuracy scores, and they do not demonstrate that all six robots can be followed. Upstream detector training-match provenance is unavailable, so these clips cannot establish independent detector accuracy.
- Python tests cover identity continuity, number conflicts, cuts, crossing/occlusion, missing numbers, duplicate identity, manifest integrity, dataset splits and reserved evaluation footage. PHP tests cover worker capabilities and private download insertion/integrity.
- Actual Windows/Linux installation, CUDA inference and Linux server execution still require their target machines. CPU inference was tested on macOS, not falsely described as Linux testing.
- No detector fine-tuning was run: reviewed bumper boxes are not yet available. Existing action/scoring learning remains its experimental baseline. Tracking does not by itself detect feeding, successful scoring, breakdowns or climbs. No numerical accuracy improvement is claimed.
- No production deployment or training/reset/import request is made by the build script.

Sources: https://docs.ultralytics.com/modes/track and the pinned Ultralytics 8.4.63 tracking callbacks/configuration; the owner-supplied Prosper repository.

## 2026-10-21 wide-view and short-gap update (engine 2.4.6 preview)

The wide camera now runs an additional native-resolution bumper pass about once per second. Its 960-pixel horizontal tiles overlap by 25%, cover the far edge, and add only boxes distinct from the existing full-panel detections. Those boxes enter the same optical-flow follower and OCR path. The saved tracking report includes `wide_tile_detection` frame, candidate and added-box counts. This uses the existing bumper weights; it is a detection-resolution change, not a newly trained model. The separate reviewed-box detector trainer now fits at 960 pixels. It still needs complete reviewed frames from training and validation matches before a new weight candidate can be made.

The offline identity review now proposes links between uniquely matched track fragments, including a tracker-ID change while other robots remain visible and a 1.5–3 second detection gap. It requires the same camera shot and alliance, roster compatibility, box motion/size and close appearance; same-alliance contact, competing teammate matches and ambiguous crowd frames block a link. A proposed link is marked `short_gap_visual_match_needs_review` and `training_eligible: false`; the review summary counts these suggestions. Only owner-confirmed corrections can turn them into reviewed training examples. This conservative link does not silently turn an uncertain robot into an action or score label.

The engine continuity revision invalidates stale tracking caches. Replaying saved Q3 observations produced 14 new review suggestions; that is a coverage diagnostic, not 14 verified correct identities or an accuracy gain. The change still needs an independent per-robot detection/identity comparison on held-out video. Q7 stays evaluation-only and cannot be used for detector fitting or threshold tuning.
