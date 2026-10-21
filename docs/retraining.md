# Retrainable tag scouting and game packs — helper v5

## What shipped

The uploaded community.zip and nested helper matched the current repository. The former learning modules retained examples but did not fit a model. Helper v5 adds an actual local training/feature/inference pipeline and Learning & games controls. Mac, Windows and Linux packages include the same code. No paid API, GPU or new Python dependency is required.

The goal is robot-level tag scouting measured across all six robots. That goal has not been achieved or demonstrated by this release. The current live corpus contains 97 contributed, observed labels across two Mercury matches, predominantly scoring starts. It has no explicit counterexamples. One end-completed label and seven end-no-attempt labels are insufficient to fit even that binary head. The real readiness run correctly produced an empty candidate and a needs-data report, without extracting video. No automatic scout model was activated.

## Data and annotation

`community_video_labels` remains the source table. The additive `community.video.tags.learning.v3` migration adds `polarity` (`present` by default; `absent` for explicit counterexamples). Existing labels keep their meaning. Counterexamples are entered through an optional advanced checkbox in the public tagger. They use the existing tag keys and never masquerade as positive scouting events. The 19 tags and their keyboard shortcuts remain unchanged. All contributions remain immediately available, with no review queue. Withdrawals remain excluded. Export still excludes contributor, account and network identifiers.

Schema-2 NDJSON remains backward-compatible and adds season, known game_key and polarity. Unknown future games have a null game key until configured. Season comes from the immutable match key, not the user's currently selected season. The helper defaults old records to present, retains originals and withdrawals, and understands explicit negatives. Scoring still means the start of a scoring sequence, not points, pieces or completed cycles. No robot scoring contribution is inferred from alliance score deltas.

The trainer excludes uncertain, unavailable, unsupported-definition, withdrawn and conflicting contributions. Same-frame duplicates are merged with original label IDs retained. Unlabeled moments are unknown. Whole-match no-scoring/no-defense and phase no-attempt assessments provide explicit negatives only for corresponding actions. A positive action's presence never implicitly labels other actions absent.

## First feature and model backend

The model is a genuine but experimental supervised baseline: a diagonal linear discriminant learned separately for each action from robot-localized RGB and short temporal-difference features. It uses three 12×12 RGB crops at −0.5/0/+0.5 seconds via the bundled PPM-capable FFmpeg. There is no trained motion tracker or neural video encoder yet. Low-resolution appearance features may be inadequate for defense, climbing, or distinguishing scoring from transit. This is an extensible initial backend, not evidence of six-scout equivalence.

Localization uses exact alliance-colored bumper readings, a confirmed robot identity, and normalized crops around that bumper. Corrected-only, unconfirmed and mixed-robot crops are excluded. No score, team number, timestamp or tag is included in the feature vector. Video hashes and durations must agree with the labels and localization evidence. Camera gaps remain unknown. The full benchmark counts missed actions during these gaps as false negatives rather than hiding them behind visible-only accuracy.

Each candidate records the feature version, game-pack fingerprint, used label IDs, source/group provenance, model ID, per-tag train/calibration/test counts and held-out metrics. Source videos and event groups cannot cross partitions. Calibration chooses thresholds without reading the test partition. Model decision margins are not percentages or probabilities. Artifacts are validated JSON, never executable pickle files. Changing model contents invalidates its ID.

## Local workflow

Open Learning & games, choose the game, refresh counts, and retrain. Original data and each new candidate remain separately stored at `~/.neptune-helper/training/`. Downloads and OCR are skipped when the corpus cannot fit any head. Otherwise sources are verified, OCR localizations cached by source and game-pack hash, and examples extracted locally. A game model can contribute uncertain tag predictions to helper drafts only after explicit activation. Model predictions are stored separately from human tags and sealed with the run evidence. The main summary is concise; the full original OCR report remains in `evidence-report.txt`.

Activation requires an independent complete six-robot benchmark: at least ten matches from two held-out events, at least ten true events per trained tag, precision ≥ .90 and recall ≥ .80 for each trained tag, plus the per-robot gate. These are release engineering criteria, not an assertion that .90/.80 equals human accuracy. Reported benchmark labels themselves need accurate source-aligned annotation. No such benchmark has been supplied. Sparse public tags cannot substitute for complete coverage.

After a label refresh, a model whose training labels were withdrawn becomes unavailable. Retraining never replaces the active pointer by itself. Importing a changed game pack invalidates older model compatibility. Prior runs are retained and a previously passing run can be activated again if it remains compatible and eligible. Models are local to the helper; this release does not distribute a centrally hosted trained model to every contributor.

## Games

Match keys select game packs automatically. 2025 REEFSCAPE and 2026 REBUILT have separate keys, rules and model folders; 2027 remains explicitly unconfigured. The REEFSCAPE timing (15-second auto, 135-second teleop) comes from the official FIRST manual: https://firstfrc.blob.core.windows.net/frc2025/Manual/2025GameManual.pdf. No artificial Reefscape endgame phase or unverified scoreboard crop was invented. Representative 2025 footage is still needed to calibrate/verify the visual broadcast profile. Until then that reader stops with an actionable explanation. Existing 2026 layout remains available.

To configure a new game, copy that season's object from helper/season_rules.json to a standalone JSON file, add `season`, fill in verified timings/source, tag definitions, and calibrated normalized layout_profiles, then choose Import game pack. The parser validates the pack and fingerprints it. No rule or game name is invented for 2027.

## Benchmark format

Choose Evaluate complete-match benchmark in Learning & games. A JSON manifest contains:

```json
{
  "season": 2026,
  "game_key": "2026-rebuilt",
  "tags": ["scoring", "attempted_defense"],
  "matches": [{
    "match_key": "2026example_qm1",
    "video": "qm1.mp4",
    "facts": "qm1/facts.json",
    "source_sha256": "REPLACE_WITH_ACTUAL_VIDEO_SHA256",
    "duration_ms": 180000,
    "roster": {"red": [1, 2, 3], "blue": [4, 5, 6]},
    "complete_robot_labels": {"1": false, "2": false, "3": false, "4": false, "5": false, "6": false},
    "events": [{"team": 1, "tag_key": "scoring", "start_ms": 45000}]
  }]
}
```

Paths are relative to the manifest. Include every occurrence of every listed trained tag for all six robots over the video. Set completeness true only after finishing that annotation. Default false prevents sparse data from being presented as a complete benchmark. An empty events list can be correct when a fully watched robot never performs a trained action. Predictions and reference events match one-to-one within two seconds; duplicates are false positives and unmatched true actions are false negatives.

## Validation

Helper regression tests cover learning changed weights, no-negative abstention, source leakage rejection, cross-game model rejection, model tampering, uncertainty/withdrawal exclusion, robot crop requirements, temporal feature extraction, a complete synthetic six-robot benchmark, per-robot missed-action blocking, and invalidation after withdrawal. Synthetic test metrics are test fixtures, not real scouting accuracy. PHP tests cover explicit counterexample persistence/idempotency/export and the 2025 catalog boundary. Existing helper tests also pass, including the loopback login test outside the socket-restricted sandbox. Negative time formatting and per-alliance arithmetic checking are fixed.

Production deployment: initial feature backup `20261018-053105-d314`; final helper packages and setup-copy backup `20261018-053604-145f`. Live checks confirmed the counterexample toggle, 351 entries including the placeholder in the 2025 event selector, and the export’s 97 unchanged label IDs plus metadata. The initial download check exposed an owner-access bug: the old endpoint admitted contributors but rejected the owner. The endpoint now admits owners as well; contribution permissions are unchanged. Fresh authenticated Mac and Windows downloads completed, and their SHA-256 hashes match the rebuilt archives. An owner-only read-only health check confirms archive readability and fingerprints for all three platforms. Windows/Linux native installation was not tested on those operating systems.

Download-health patch backup: `20261018-053911-21a7`; owner download-access fix backup: `20261018-053958-b663`. The owner health check now confirms download_allowed=true, and actual Mac/Windows downloads were independently compared to the packaged SHA-256 hashes.
