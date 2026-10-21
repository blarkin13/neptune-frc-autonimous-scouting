# Build status — October 17, 2026

Branch: `feature/community-match-analysis`.

Built and locally checked: additive schema, global work catalog, transactional leases, ownership and stale-token checks, immutable submission/review/publication, public browser view, explicit pilot grants, helper credentials and revocation, and local-only CLI inference pipeline. No production deployment or schema mutation has been performed.

Local checks passed: PHP syntax for all six changed/new PHP files; 23 behavior checks on isolated SQLite; two Python tests including refusal of external inference endpoints; Python compilation and CLI help; whitespace checks. More than 200 independent reservations are covered by a behavior check, not a concurrency/load benchmark.

Production-dialect verification: a MariaDB 10.6 CI job installs the actual migration and runs the behavior suite plus a 16-process competing-claim test. This has not run locally. The local MySQL executable cannot start because a Homebrew library dependency is missing; no system installation was changed to work around it.

Backups: streamed deployed table definitions and compared selected app files; no production data was imported. Supplied app root omits private bootstrap/config. Production differs from repository main in existing scouting/sync files; those files were left unchanged.

Still required before a real rollout: verify deployed private bootstrap/config, run MariaDB tests, exercise staged authenticated HTTP/browser workflows, benchmark local vision quality on full matches, validate model licensing/hardware, and conduct a 200+ helper load test. Signed desktop installers, automated model setup, non-team signup, public revision/moderation tools, tags and scoring are future milestones. This pilot must not be represented as a finished public service.

Local model probe: the installed qwen2.5vl:3b accepted an image request and returned JSON, but the first response repeated example text rather than describing the frame. That is a failed semantic check, not a validated match analysis. A second probe correctly read Red 12 / Blue 3, but its explanation also misread team numbers 6369 / 9128 as points. Transport and image input work; semantic accuracy failed the approval gate. The pilot model is not approved for public unattended use.

A basic Tk desktop front end now lists available work and starts the selected match. Its syntax passes; visual/platform interaction testing is pending.


## Maintenance Console package (October 17, 2026)

A separate Neptune_Community_Analysis_Pilot_v1_Maintenance_Console.zip now supports the console in the supplied production backup. Eleven installed files plus expected-base metadata; no replacement of existing config/bootstrap/console. New strongly authenticated platform-owner admin/community-analysis.php initializes the seven additive tables, records the migration, and manages enabled state and explicit contributor/reviewer IDs. Database settings take precedence after initialization. The helper source ZIP is downloadable from the setup page.

Validated paths, metadata and syntax using extracted pure validation functions from the deployed console. Workflow 23 checks, helper two tests, and setup ID/settings checks pass. Actual MariaDB migration and HTTP authentication remain staging checks. The older developer archive is not the Maintenance Console installer.

## Double-click Mac setup launcher

Built `Neptune-Helper-Mac-Setup-v1.zip` (31.1 MiB) and `Neptune_Helper_Automatic_Setup_v1_Maintenance_Console.zip` (31.0 MiB). The website update contains three files: setup-page instructions, the authenticated download endpoint (also covers the earlier download fix), and the helper ZIP. No database migration or feature configuration change is required.

The launcher uses a requirements manifest, checks Python/Tk, opens the verified official Python.org installer if missing, creates a private environment, and installs its hash-pinned certificate dependency offline. It verifies all packaged files. The helper checks its private FFmpeg/FFprobe and official Ollama engine, then reuses the approved local model or downloads it with progress. Cloud features are disabled for the private engine. Apple Silicon/macOS 14+ only in this build. The launcher opens a Terminal progress window and then the helper GUI. Secure browser pairing is still not implemented; account connection uses a token.

Changed result handling: processing saves a local draft, shows summary/timestamped observations, renews the reservation during review, and submits only on an explicit Submit action. CLI also requires --submit for upload. The app prevents simultaneous local windows via a file lock.

Validation: seven Python tests pass (model reuse, model download/progress and disk gates, unknown model version, explicit submission, endpoint/result validation); 23 SQLite service checks pass. Bundled tools successfully read the actual match video and extracted an image. Official private runtime started/stopped, reused the existing model and returned a structured image response. Initial unrestricted JSON generation produced a malformed response; explicit JSON response format was added and its transport/structure test passed. This does not establish scouting accuracy. Tk window construction and the final package self-test passed. Offline dependency installation into an isolated environment passed. Deployed-console path/metadata/PHP checks and 50 MiB upload limit passed.

Not yet verified: installation on a clean Mac without Python, fresh 3.2 GB model download on a clean Mac (download branch covered with a simulated stream), downloaded-file Gatekeeper approval, full production match-to-review interaction, MariaDB staging/load tests, Windows/Intel builds, notarized distribution, and model accuracy. No production website or database was modified while building these artifacts.

## Facts pipeline, cross-platform helpers and learning data (October 18, 2026)

The helper's default pipeline is now **facts-3.2**: local OCR of the broadcast overlay, results screen and bumper numbers (`helper/neptune_facts.py`), no AI model. OCR goes through `helper/neptune_ocr.py`: Apple Vision (`bin/neptune-ocr`) on Apple Silicon, RapidOCR 3.10.0 / ONNX Runtime 1.31.0 on Windows and Linux. Raw readings, frames and crops, the draft and all versions are sealed per run (`neptune_learning.py`); reviewer corrections are a separate append-only file; `neptune_learning.py export` writes reviewed/unreviewed examples for evaluation and training. Nothing retrains automatically. Public human video tags (`community/training-labels.php?export=1`) are ingested by `neptune_video_labels.py`: append-only ledger with withdrawal handling, private SQL-dump columns dropped on read, source video retrieved and hashed before frames are extracted, no negatives from unlabeled time, splits by event or match. The tagging pages and their data were not changed.

Evaluation (`helper/evaluation/`, Apollo division, official TBA alliance results; outputs in `.helper-build/evaluation/`), Apple Silicon M2 8 GB:
- facts-3.1 on 16 matches, both backends: 16/16 identities verified; 64/64 true/wrong match claims handled correctly; final score 32/32 exact; results-screen auto exact where readable (Apple 25/32 fields readable, RapidOCR 32/32); all 63 measured phase boundaries within the stated uncertainty (mean error 0.31 s, max 1.2 s); robots confirmed Apple 78/96, RapidOCR 81/96.
- facts-3.2 on held-out set 3 (qm9, qm37, qm56, qm88, not inspected before the freeze): identity 4/4; final 8/8 exact; robots confirmed Apple 19/24, RapidOCR 21/24; provisional (model, not human) review found every confirmed claim showed the right robot; RapidOCR evidence for 1 claim mixed in driver-station display frames.
- Runtime per match: Apple Vision median 87 s (max 110 s), peak 0.55 GB for the process tree; RapidOCR median about 4.7 min (max 8.3 min), peak 0.85–1.5 GB.
- History kept honestly: facts-2 held-out crops showed driver-station number displays confirmed as robots (fixed in facts-3); facts-3 had a tile regression (fixed in 3.1, regression test added); RapidOCR still read red/blue displays, so facts-3.2 requires a close-up camera read to confirm a robot.

Not yet done: human review of the identity evidence (review pages in `.helper-build/evaluation/review/`), installers run on real Windows and Linux machines, schema v2 upload of evidence bundles and reviewer corrections to Neptune, and wider evaluation (other events, playoff overlays, other seasons). One pre-existing helper test (`test_existing_draft_requires_explicit_submit`) fails on the current and previous helper because the resume heartbeat was added after the test.
