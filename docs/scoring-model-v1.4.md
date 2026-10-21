# Experimental scoring model — Trainer v1.4

## What changed

Saved whole-match community point estimates now train a scoring model. Scoring-start clicks continue to train action detection; they are not point labels. Existing game packs keep season rules and models separate. No paid API is used.

After fitting, the trainer’s Try a match tab loads Neptune’s linked match catalog for the selected season, runs the current scoring candidate on one selected video and uploads private experimental robot scores and action tags. Results appear under Try the model on the owner’s Train & test page. They do not enter the human-label table or public scouting totals. Six records are returned, with unknowns where evidence is inadequate. Browse more events links to the catalog to make further event matches available.

## Training targets and features

Eligible targets are active, current-source, whole-match human_video_contribution labels with alliance_share mode and a known positive full_final_alliance_score. Estimated labels remain uncertain; counted/observed labels are human assertions. Withdrawals and revisions are honored. Duplicate robot/video contributions are combined by median only when shares agree within ten percentage points; conflicts are excluded.

The scorer uses 288 pooled RGB/motion video features from up to 24 confirmed, exact, alliance-colored robot sightings. It requires matching roster/match identity, observed starts/ends for auto and teleop, six sightings, three temporal quarters and half-match sighting span. It does not use team ID, human score, human tags or the scoreboard as feature inputs. Final alliance totals convert predicted share to points after inference.

RBF kernel ridge regression is fitted on standardized features, with regularization and at most 256 support examples. Estimated targets receive lower weight than counted targets. At least two varied robot targets are needed for a development fit; this is not enough to establish useful generalization. This small appearance/motion baseline is not a continuous tracker, shot counter or six-scout replacement. It may learn appearance/camera correlations and miss off-camera actions. A stronger temporal tracking/action model remains future work.

Missing evidence and missing totals stay null. Predicted robot points cannot exceed the known alliance total in aggregate; surplus is scaled down. Unknown robots are not given a residual share. Full final alliance score includes penalties as requested, so share is a human contribution estimate rather than an official per-robot scoring breakdown.

## Evaluation and release

Source hashes and event splits prevent overlap between fitting and independent evaluation. Small-data development partitions are reported as such. Training previews are in-sample fits, never accuracy. Held-out agreement with human estimates is labelled separately from independently counted scoring reference data.

A score release requires ten independent complete matches from two events, all six robot references with counted complete point totals, at least 90% prediction coverage, point MAE at most 20 and share MAE at most 0.10. Combined action/scoring models must also pass the existing action evaluation. These are engineering checks, not proof of human performance. Remote reports are trusted from an authenticated owner-authorized training computer; the web host does not rerun video evaluation. The owner explicitly releases a passing candidate.

## Actual-data validation, October 18, 2026

The current public export contains three Mercury Q2 score estimates: team 2881=180, 5829=35, 10014=133. Actual video crops produced two usable training robots; 10014 was excluded for sparse sightings. A real CPU development fit completed. In-sample predictions were 159 and 56 points for the two usable robots, respectively. These numbers are fitting previews, not accuracy or six-robot test results. Q1 starts during teleop and cannot supply full-match scoring supervision. This validation did not create production labels, credentials or a released model.

## Delivery

Trainer v1.4 is supplied as updated Mac/Windows/Linux setup ZIPs. Native DMG/EXE/DEB signing and physical Windows/Linux GPU execution are not claimed. Existing prerequisite installers are reused. There is no new database table. Private trials reuse learning jobs and trainer reservations, preserve human labels and require the existing owner credential. The old summary publication flow remains retired.

## Validation and live deployment

121 helper tests passed: 120 in the restricted suite and the blocked localhost connection test passed when rerun with local socket access (the connection test file contains two cases). The scorer adds 15 tests covering weak-label eligibility, corrections/withdrawals, fitting, malformed artifacts, duplicate conflicts, event/source leakage, six-robot trial upload, trial failures, constrained predictions, unknowns and counted evaluation references. PHP integration tests passed for score-only fitting reports, snapshot provenance, old-client upgrade messages, trial reservations, totals and unchanged human labels.

The deployed Maintenance Console validated and installed 14 files with backup `20261018-204346-3306`. All Mac/Windows/Linux base archives passed source/manifest/integrity inspection and the live owner-only download preparation check. The live page shows 97 action tags, 3 scoring estimates, 2 matches, and explains that the previous action-only run needs v1.4 retraining. No new production training credential, human label, prediction record or released model was created during verification.
