# Work log (newest first)

## 2026-10-23 — Claude: helper 3.2.13 (engine 2.7.0-identity-coverage) + robot-detector jobs
- Measured with full re-tracks vs the hybrid detector alone (same clip-planner fix in both):
  QM3 named 1,860 -> 2,887, median coverage 0.22 -> 0.38, usable label clips 191 -> 209 of 379;
  QM4 named 2,501 -> 3,094, coverage 0.34 -> 0.41, clips 128 -> 136 of 316 (87 with 3.2.11 as shipped).
  Agreement with OCR-confirmed identities 99.9% on both.
- Robot detector jobs (`neptune_robot_jobs`, `api/robot-detector.php`, `neptune_secure/robot-detector-jobs.php`):
  the Robot labels page queues "Prepare frames" and "Train robot detector"; idle helpers claim them. Training
  uses every completed label (site + seeds), holds out the newest match, adopts on Neptune only if held-out F1
  beats the current detector by 0.02; helpers download the adopted detector hourly. Robot labels autosaves drafts.
- One failed Apple Vision call no longer aborts a match's tracking (skips that frame; >20% failures still fail).
- Clips continue across a confirmed contact (`carried_from`).
- Built from the 3.2.12 app; 442 tests pass on the bundled Python; appcast signature verified; DMG valid.

## 2026-10-23 — Claude: identity coverage (engine 2.7.0-identity-coverage-preview1)
1. Stopping a tracking review no longer saves "tracking unavailable" (InterruptedError is re-raised, so the
   match tracks next time). Training reports each match's tracking status/reason. Found and fixed: the clip
   planner did not know the tracker revision used since 3.2.8, so every clip took the strict fixed-window path
   (a large share of the "no usable tracking clip" losses); the current and 3.2.8+ revisions are now known.
   QM4 hand labels that become usable clips: 87 -> 128 (planner fix) -> 138 (+ roster inference).
2. Roster solver inferences ('bidirectional_motion_and_roster', 'same_number_before_and_after_contact') become
   `roster_inferred` localizations used by training, clips and predictions. Hidden-anchor test on QM3/QM4:
   1,132 of 1,132 inferred identities correct. Adds +30% (QM3) / +17% (QM4) named sightings on hybrid tracking.
   Short-gap visual suggestions stay review-only.
3. Brief contact keeps the identity: nothing is labelled during contact; one matching exact read afterwards
   confirms; a different read means a swap and the old identity is dropped.
4. Close-ups read bumpers every processed frame; OCR-corrected reads and unique 3+ digit partial reads count
   toward the two reads, but every identity still needs one exact read. Tracker revision
   `contact-carry-partial-reads-v7`.

## 2026-10-23 — Claude: helper 3.2.11 (engine 2.6.0-hybrid-detector-preview1)
- Engine ships its own detectors: `robot-detector/` (owner-trained wide-shot bumper detector, merged into the
  private bundle by `neptune_yolo.with_bundled_cameras`; close-ups keep the private Prosper detector) and
  `field-detector/` (hubs + corners). Helpers' private-model download is unchanged.
- Includes the Auto Scout addresses (Open Neptune -> /autoscout/train.php) and everything since 3.2.10.
- Built from the 3.2.10 app runtime; 437 tests pass on the bundled Python; appcast signature verified against
  the pinned key; DMG valid. GitHub release `helper-3.2.11` (helper, feed, DMG, server engine with detectors).

## 2026-10-22 — Claude: hybrid detector tracking result; site package fixed
- Full tracking runs (`local/tracking-compare/`), current detector vs hybrid (owner-labelled wide detector +
  current close-up detector):
  - QM4 (held out): wide detections given a team 601 -> 831 (+38%); close-ups unchanged; median team
    coverage 0.20 -> 0.23.
  - QM3 (the wide detector's training match): 481 -> 846; median coverage 0.18 -> 0.21.
  - Identification, not detection, now limits coverage (~1/5 of the match per team).
- Site package: live `admin/community-learning.php` had Codex's newer helper-download section (sha256
  43b63545...). Rebuilt exactly from the owner's diff into `autoscout/train.php`; package re-uploaded without
  macOS xattrs. Live `training-control.js` (helper-connection-cleanup-20261022) is newer than the repo copy and
  is not part of the package.

## 2026-10-22 — Claude: Auto Scout section (engine 2.5.3-autoscout-section-preview1)
- New `public_html/Neptune/autoscout/`: `index.php` (hub with the six Auto Scout cards), `train.php` (was
  `admin/community-learning.php`), `scoring-areas.php`, `robot-labels.php`.
- `admin/community-learning.php` and `admin/scoring-areas.php` are now 308 redirects that keep the query
  (e.g. the helper's `?connect=1`). `community/` stays: public Watch & tag pages and helper endpoints.
- Site menu (`partials_header.php`, refreshed from live): "Auto Scout" entry for the platform owner, its own
  breadcrumb parent; community pages show it as the active section for that owner.
- Scouting page keeps one "Auto Scout" card; the Command Center "Train & Test" card opens `autoscout/train.php`.
- Helper engine and server links now use `/autoscout/train.php` (Open Neptune button, match-test report link).
- Checked in a local site copy: hub, menu entry, Scouting cards, redirect with `?connect=1`.

## 2026-10-22 — Claude: online Robot labels page (engine 2.5.2-robot-labels-preview1)
- `admin/robot-labels.php`: Auto Scout page in the site layout. Pick a catalog match; it plays from YouTube; box
  every bumper on frames about 4 s apart; Enter saves and moves on; Skip for replays and graphics. Frames come
  from the match's tracking review when one is backed up (and boxes are pre-filled from the detector boxes in
  that review), else every 4 s. Stored per video in `neptune_secure/robot-labels/<org>/<video_id>.json`.
- Card after Scoring areas on Scouting, "Robot labels" tab in `community/layout.php`, hero entry in
  `partials_hero.php`. `youtube-source.js` now reads `[data-youtube]` from any page.
- `api/robot-labels.php` (helper bearer) returns completed frames; `engine/neptune_robot_labels.py` downloads
  them, finds or downloads each video, extracts the exact frames and writes the detector-training manifest.
- Tested in a local site copy with the real QM4 review: 41 frames, pre-fill shown, save/complete/reload works,
  manifest built from the saved frame. Still to check on real use: that a paused YouTube frame matches the
  downloaded file's frame for hand-drawn boxes.

## 2026-10-22 — Claude: bumper detector from the owner's 82 labelled frames
- Labels: 82 frames (41 QM3, 41 QM4), 747 bumpers, all checked by the owner. QM1 had no tracking, so no frames.
- Trained YOLO11n (COCO start, 1280 px, CPU) on QM3; scored on QM4 with `tools/robot-labeler/evaluate.py`
  (IoU >= 0.3 one-to-one; whole-robot boxes count a bumper whose centre they contain).
- QM4, held out (found / right):
  - current bumper detector: wide 46% / 96%, close-ups 85% / 85%
  - RobotTracking (robot26-trial): wide 74% / 61%; over both matches close-ups 43% / 57%
  - new, conf 0.25: wide 80% / 72%, close-ups 55% / 61% (conf 0.15: wide 85% / 56%; conf 0.4: 55% / 86%)
- Conclusion: new detector for the wide panel, current detector for close-ups; label more frames (close-ups,
  other matches, another event) and retrain. Weights: `local/robot-labels/fit-a/runs/bumper/weights/best.pt`
  (not in git). Not wired into tracking yet.

## 2026-10-22 — Claude: perception/game split; robot labeler
- `engine/neptune_perception.py`: the reusable perception layer (robot detector, tracking, identity solver,
  field-layout detector) vs the season game layer. Trained models record both (`perception`, `game_layer`).
  `neptune_yolo.bundle` accepts a `game_independent` detector manifest for any season.
- Finding: tracking reviews hold identity fixes plus boxes that all came from the current detector; none are
  missed robots, so they cannot teach a better detector.
- `tools/robot-labeler/`: local page (127.0.0.1, random URL token) to box every visible bumper on frames from
  the saved tracking reviews, pre-filled with the current detector's boxes (recovered from tracking
  observations). Export writes `local/robot-labels/manifest.json` in the format
  `neptune_detector_training.prepare` accepts. QM1 frames are kept for checking. Tested in a browser: draw,
  delete, complete and export work.
- Candidate whole-robot detector: ai4funhobby-oss/RobotTracking (`robot26-trial.pt` in Codex's trial folder).
  Compare it and the current bumper detector against the same labelled frames before choosing.

## 2026-10-22 — Claude: field detector trained (engine 2.5.0-field-detector-preview1)
- Trained YOLO11n (from the COCO context weights) on 2026txcmp1: 324 frames from QM3/QM4 for training and
  119 from QM1 held out, labelled from the QM4 marks (hubs + the four field-boundary corners). CPU training:
  the Apple GPU (MPS) hung. Early-stopped at epoch 35; best at epoch 20. Held-out QM1: P 0.96, R 0.97,
  mAP50 0.99.
- End to end on QM1 (held out): 4/4 hubs and 4/4 corners found, all 11 regions placed through the field plane,
  median point error 0.003 of frame width, worst 0.099 (right close-up zone behind a sponsor graphic).
  QM1 itself gets no regions in Auto Scout because its video starts mid-teleop and sides can't be read.
- Not yet tested on another event (txcmp2). Same-event results don't show cross-event generalisation.
- Weights: `engine/field-detector/model.pt` (git-ignored; ship in the helper and server engine archive).
  Training files are in `local/field-detector/`.
- Not used in model training yet: training only checks outside scoring rows against marked regions. Location
  as a model input, and using detected regions in training, are not built.

## 2026-10-22 — Claude: event-wide scoring regions; training checks scoring labels; helper 3.2.10 (engine 2.4.9-event-regions-preview1)
- Regions marked on one match now apply to every match at that event (`neptune_field_regions.load` → event
  file). Times come from the reference video, so only the camera view carries over.
- Sides: the reference's red side comes from where its red and blue wide-view regions were drawn; each match's
  red side comes from wide-view bumper positions in the first 5 s of auto. Alliance labels swap when they
  differ, and nothing is applied when a match's sides can't be read (e.g. QM1 starts mid-teleop).
- `api/field-regions.php` answers `{event}` with all of the owner's region sets for that event; the trainer
  downloads them before training (`sync_events`).
- Training: an outside-scouting scoring row whose robot is outside its alliance's marked scoring zone is
  dropped (`external_scoring_away_from_scoring_area`); human labels are kept and counted. Measured on
  QM3/QM4: 96-100% of hand-labelled scoring moments were inside the zone vs 81-89% of all sightings.
  Distance to the hub did not separate them, so it is not used.
- Train on 2026txcmp1, test on 2026txcmp2: these regions only cover txcmp1. txcmp2 needs regions found
  automatically (a learned detector), which is not built yet.
- 423 tests pass on the bundled Python; appcast signature verified.

## 2026-10-22 — Claude: scoring-areas page in the site layout
- `admin/scoring-areas.php` now uses `community_page_start/end` (site header, breadcrumbs, hero, Auto Scout
  tabs, footer) like Watch & tag and Train & test, with a "training aid only" note.
- `community/layout.php` (refreshed from live) has a "Scoring areas" tab after Watch & tag.
- `partials_hero.php` (refreshed from live) has the hero icon and guide steps for "Scoring Areas".
- `field-regions/style.css` is rewritten and scoped to `.field-regions` using site tokens. The old sheet styled
  `body`, `header`, `h1`, buttons etc. page-wide, and its global `canvas` rule caused the dark block that hid
  the page. The scripts read settings from `#field-regions-app` instead of `<body>`.
- Checked with PHP's built-in server and stand-ins for login and the database: the full layout renders, QM4
  plays from YouTube with 11 saved regions, and the footer shows.

## 2026-10-22 — Claude: scoring areas play from YouTube; Scouting card; helper 3.2.9 (engine 2.4.8-field-map-recovery-preview3)
- `scouting.php` (from the live site, downloaded 2026-10-22) is now tracked; it has a "Scoring areas" card after
  "Watch & tag" in the Auto Scout section.
- `admin/scoring-areas.php`: a match picker over `community_matches`, the same catalog Tag Scouting uses. The
  chosen match plays from YouTube (`community/assets/field-regions/youtube-source.js` adapts the YouTube
  player to the `<video>` interface `app.js` uses), and its saved regions load automatically. "Open video
  file" stays as a fallback; the cached-video list is gone.
- YouTube-marked documents have no file size: `api/field-regions.php` and `neptune_field_regions.sync` bind
  them by video name (YouTube ID) when size is absent, plus a new test.
- `app.js` was refreshed from live first (it was newer than the repo).
- Checked in a local browser harness: QM4 loads from YouTube with 11 regions; View, seek, play and pause work.
  YouTube's pause bar ("More videos") covers a strip at the bottom when paused, as in Tag Scouting.
- Helper 3.2.9 (build 30210) built the same way as 3.2.8. 415 tests pass on the bundled Python; the appcast
  signature was verified. GitHub release `helper-3.2.9` has the helper, server engine and site tarball;
  `PUBLISH.md` there refuses to install the site files if live hashes differ from the 2026-10-22 copy.

## 2026-10-22 — Claude: finished Codex's next version; helper 3.2.8 (engine 2.4.8-field-map-recovery-preview2)
- Committed Codex's pending 2.4.7 work as found (e18e8cf).
- Brought work that lived outside the repo into it:
  - `engine/`: `neptune_field_regions.py`, `neptune_homography.py`, `neptune_reacquisition.py`,
    `neptune_housekeeping.py`, `neptune_scouting_rules.py`, `field-regions/` (QM4 regions), and their tests.
  - `server/`: `admin/scoring-areas.php`, `api/field-regions.php`, `community/assets/field-regions/`
    (the deployed v2 pages), plus the live "Mark scoring targets" link in `admin/community-learning.php`.
  - `experiments/roboflow-detector/`: trial code and notes only (no apps or weights).
- Wired it in:
  - `predict` adds field context to tags; it is supporting evidence only.
  - Trajectories, scouting-rule summaries and field observations go into trial results.
  - Tracking runs provisional reacquisition (`reacquisition_proposals`, never used for tags).
  - Identity review holds a cache lease so cleanup can't remove its video mid-review.
  - The trainer cleans up at startup, after every job, and hourly when idle.
- Kept the owner rule (stationary >5 s in teleop = disabled). Codex's `neptune_scouting_rules` would
  only emit `stationary` unless human-confirmed inactivity existed; its stationary/disabled events are
  not added, while its scoring-visit and cycle summaries are.
- OCR cadence is time-based (`read_every=.5` → every 3rd frame at 6 fps), not a fixed 3 frames.
- `neptune_field_regions.sync` no longer crashes without a connection token.
- Tests: 414 pass on the bundled Python (8 system-Python numpy/tkinter errors expected).
- Helper 3.2.8 (build 30209) was assembled from the 3.2.7 app runtime, because the old main repo's
  `.helper-build` is gone. It is staged in `~/Documents/ChatGPT/Neptune/Mac-Helper-3.2.8-ready/public-release`
  with `PUBLISH.md`; the appcast signature was verified against the pinned key. Not published.
- Open: the old main repo working copy no longer exists, so `scripts/sync-to-neptune.sh` has no target;
  `downloads/mac/.htaccess` is not tracked here (live-only).

## 2026-10-22 — Codex: published Linux Training Helper 6.5
- Confirmed the live Linux download was 6.4 while Windows was 6.4.2. Rebuilt Linux 6.5 from the current shared engine, including the compact cross-platform UI, visible Reconnect button, and batched scoreboard OCR progress. No private connection is in the package.
- Verified package contents and SHA-256; the Ubuntu server accepted `apt-get -s install` with dependencies available. Published the 6.5 DEB and updated the two exact download references with hash guards, small code backups, and PHP lint. The public download hash matches the build (`b79935f5e8604aa443db67295c81f30ab670ad3c40158e670fe04e12a856ad71`). Removed transfer staging; server root disk remains about 12 GiB free. A real Linux desktop first-launch test is still needed.

## 2026-10-22 — Codex: fixed Windows setup and published direct Windows/Linux installers
- Fixed the Windows FFmpeg check to treat a missing executable as a normal install case, added its private tools folder to the installer self-check and desktop launch path, and corrected shortcuts to start the owner-paired trainer. Built per-user Windows 6.4.1 NSIS setup EXE; no administrator account, ZIP extraction, CMD launch, or embedded private connection is required. The live EXE passed archive validation and SHA-256 verification. Kept the older 6.3.1 automatic update feed until a real Windows install validates this new entry point.
- Built Linux 6.4 Debian package with a Neptune icon, desktop launcher, per-user first-launch setup, and browser pairing. The package contains no private connection or robot weights. `dpkg-deb --info` and `apt-get -s install` accepted it on the Ubuntu host; the public `.deb` download matched its build hash. A real Linux desktop first launch is still untested.
- Replaced the training-page legacy ZIP instructions with direct Mac app, Windows EXE, and Linux DEB download cards using the Neptune logo; added the `sudo apt-get install ./Neptune-Training-Helper_6.4_all.deb` option. Generalized the connection-page copy and helper name for all three platforms. Live PHP lint and download hashes passed. Production deployment used exact source hashes and small rollback backups; temporary upload servers and staging were removed. Root disk remained about 12 GiB free.
- Four installable-helper tests passed, including the Windows private-FFmpeg path regression; the rebuilt EXE's embedded files passed archive validation. Native Windows and Linux GUI smoke tests remain necessary before advertising an automatic 6.4.1 update feed.

## 2026-10-22 — Codex: published Windows Training Helper 6.3
- Built the Windows 6.3 helper from the prior public 6.2 package with engine 2.4.6, a Neptune icon, Desktop/Start-menu shortcuts, startup and manual update checks, a checksum-verified code-only updater, busy-match deferral, and rollback on failed replacement. Existing connections and saved match work are excluded from updates.
- Five updater tests and all 380 engine tests passed; full/update ZIP manifests and hashes passed. The native Windows installer and in-place updater still need an end-to-end run on a Windows computer. This is an icon-branded Python shortcut, not a standalone EXE.
- Published the full ZIP, code-only update ZIP, feed, exact ZIP allowlist, and corrected download-page text on Neptune. Guarded the prior ZIP hash and saved a 256 KiB rollback copy. PHP lint passed, all live hashes matched, and the public feed and update ZIP returned the expected content and SHA-256. Removed transfer staging and receiver; disk remained 12 GiB free. Windows 6.2 users need one fresh install from Neptune to acquire the updater.

## 2026-10-21 — Codex: removed duplicate server release backups
- At the owner's request, verified the current 3.2.6 ZIP and feed hashes and the separate 3.2.5 rollback installer, then deleted exactly six obsolete /root backup directories after checking for symlinks. Freed 3,791,178,453 bytes; root free space rose from 8.1 to about 12 GiB (59% used). Live release hashes still matched.
- The repeated backup directories had copied entire helper installer archives and/or `community/downloads` while saving small code changes. Added a repository rule to back up only changed files and the prior current DMG on future server updates. No production data, labels, database tables, or current downloads were removed.

## 2026-10-21 — Codex: published signed helper 3.2.6 and audited AWS storage
- Published the signed 3.2.6 ZIP and DMG to Neptune with a guarded backup of the prior feed, installer, allowlist, checksum manifest, and website version text. The appcast changed last; no database change or worker restart. Verified the live ZIP and DMG return HTTP 200 with exact expected sizes and the appcast SHA256 matches the signed local release. Removed the temporary upload receiver and stage.
- AWS disk check found 8.1 GiB free after publication. The apparent 3+ GiB loss is primarily cumulative duplicate release backups under /root: one 1.5 GiB helper backup and five ~424–440 MiB tracking/cloud/release backups; no new MySQL binlog accumulation. These older backups were inventoried, not deleted. The current 3.2.5 installer remains in the explicit release rollback directory.

## 2026-10-21 — Codex: native wide-shot bumper pass and short-gap identity review (engine 2.4.6 preview)
- Added overlapping native-resolution bumper inference on the wide camera once per second, merging only distinct boxes into the existing optical-flow and OCR pipeline. Reports count tile frames, candidates and added detections; the changed continuity revision forces fresh tracking instead of reusing earlier cached tracks.
- Added conservative same-shot, same-alliance track-fragment and short-gap identity suggestions using appearance, position, size, roster and uniqueness. They cannot cross cuts or ambiguous crowd frames; suggested points are explicitly ineligible as training truth until reviewed. Increased the separate reviewed-box detector fitting size to 960 pixels; no new model weights were trained.
- The installed helper's bundled Python passed all 380 engine tests after the final fragment cases. Replaying saved Q3 observations produced 14 new review suggestions, not verified identities. Built signed Mac helper 3.2.6 (build 30207) with engine 2.4.6; its packaged runtime also passed all 380 tests and its ZIP/DMG hashes matched the manifest. Removed the duplicate build copy and kept the signed ZIP/DMG (691 MiB) to limit Mac storage use. It is staged locally, not installed or published. Independent held-out match comparison remains before claiming better coverage.

## 2026-10-21 — Codex: previewable Auto Scout storage cleanup (installed)
- Before changing production code, inventoried server downloads and completed release staging, then removed 10 exact, hash/size-checked obsolete files: 2,249,142,905 bytes (2.095 GiB). Kept helper 3.2.5, rollback 3.2.4, the current DMG, Windows/Linux downloads, and uncertain maintenance uploads. Root free space rose from 6.7 to 8.8 GiB.
- Added an owner-only preview and confirmation panel under Reset Auto Scout. A fixed-path root helper lists exact eligible files and bytes, retains the active and previous signed ZIP, rejects changed previews, and never scans labels, models, reports, or video caches. PHP calls it through one proposed exact sudoers command. No database changes.
- Checks: three deletion/retention tests passed; PHP and JavaScript syntax checks passed; live appcast version 3.2.5 confirmed. Automatic approval review requested specific authorization for the web-facing root cleanup grant; the owner approved it. The first guarded install self-waited on the release lock and rolled back; hashes and absence of new files confirmed the rollback. Corrected the verification order and installed the page, assets, PHP wrapper, root-owned cleanup helper, and exact-command sudoers rule. A live preview executed as `www-data` returned zero eligible files and correctly retained 3.2.5, 3.2.4, and the DMG. No database change or restart.

## 2026-10-21 — Codex: tracking-review picker correction (engine 2.4.5-review-cloud-preview2)
- During the installed 3.2.4 visual check, the saved-match picker stayed at “Reading saved matches” because generated JavaScript joined two statements without a separator. Corrected the template and added a JavaScript syntax regression check.
- Paused the owner-requested in-progress Q3 training run before upgrading; prepared work and labels remain saved. Verified prior Q3 and Q4 tracking corrections were copied to organization-scoped AWS storage (6 and 12 corrections respectively).
- Built and installed signed helper 3.2.5 on the Mac (3.2.4 retained for rollback). The bundled Python passed 373 engine tests, and the PHP review-storage checks passed. Published the guarded 3.2.5 update to AWS with a rollback backup; no database change or service restart. Verified the live engine and release hashes, HTTP access to the ZIP/DMG/update feed, and the Mac picker displaying saved matches plus two cloud reviews. The requested Q3 job remains paused. Removed temporary server release staging after publication, leaving 6.7 GiB free; removed the superseded 3.2.3 Mac rollback app, leaving 2.4 GiB free. Closed review mode and confirmed the 3.2.5 helper reconnected and ready for training.

## 2026-10-21 — Codex: owner-scoped cloud backups for tracking reviews (engine 2.4.4-review-cloud-preview1)
- Restored the approved live scoring contribution and result display changes into `server/`, including `community-contributions.php`, after confirming the exact differences against production.
- Added authenticated `review_list` / `review_get` / `review_put` storage. Full review JSON is compressed; videos stay on the helper. Organization and video fingerprints scope reads and writes, and revision checks reject a stale second helper.
- The Mac review command now receives its saved connection. Corrected local reviews are backed up, and cloud reviews appear in the picker on another helper. Local saves survive a network failure. Approved samples are republished to the local training library when restored.
- Checked PHP storage round trip, organization isolation, idempotency, conflict rejection, and a full size Q3 review (1.59 MiB request, 1.19 MiB stored). The packaged Mac Python passed 65 focused review tests and 372 engine tests before the final cloud picker extension. Final tests and release packaging follow.

## 2026-10-21 — Claude: merged Codex's helper 3.2.2 engine changes (engine 2.4.3-review-learning-preview1)
- Codex's edits were lost from neptune-frc-scouting by an earlier sync, but helper build 30203 (3.2.2,
  engine 2.4.2-presented-video-preview1) still had them. Three-way merged against the import commit; no
  overlap with Claude's changes:
  - `neptune_events.stationary_disabled` + `neptune_training.predict`: owner rule, stationary >5 s in teleop = disabled.
  - `neptune_scoring_model.apply_recorded_contributions`: no recorded scoring = 0; per-alliance contribution to 100%.
  - `neptune_identity_review.py`: viewer draws frame and boxes from the displayed frame's timestamp.
- Added Codex's `test_tracking_rules_update.py` (13 tests pass). Updated one `test_page_worker` assertion to
  the new zero-by-policy rule. Codex's own test edits were not shipped in the build, so they are not recovered.
- Not recovered: Codex's server-side edits (`community-scouting-trials.php`, `admin/community-learning.php`,
  `training-control.js`). Its published copies are on AWS only; pull them from the host to merge.
- Shipped helper 3.2.2 has Codex's rules but NOT the honest held-out checks; it needs a rebuild from here.

## 2026-10-21 — Claude: honest held-out checks (engine 2.4.0-review-learning-preview3)
- Cross-fit folds are keyed by match, not video file, so two uploads of one match can't straddle a fold
  (`fold_key`, method `grouped-cross-fit-by-match-v2`).
- No-video stand-in gate: a stand-in sees only clip time, box position/size, camera and team. A head is
  withheld (`no_signal_beyond_shot_time_or_robot`) unless its held-out AUC beats the stand-in's by 0.05
  (`NUISANCE_MIN_MARGIN`). Examples now carry `box`/`camera` as provenance for this.
- Outside-scouting positives train at weight 0.5 (`EXTERNAL_WEIGHT`, weighted LDA). Held-out AUC is
  reported per source (`auc_by_source.human` / `.outside_scouting`).
- The PU test fixture was itself confounded (all positives earlier than all references); the new gate
  caught it. Fixture times now interleave.
- Tests: `test_training_honesty.py` (6). Engine 351 tests, only the 7 pre-existing environment errors.
- Helper: the server accepts any engine ≥ 2.2.1, so old helpers keep training without these gates. The Mac
  helper needs a rebuild (`trainer-app/scripts`) and the server worker a redeploy after syncing.

## 2026-10-21 — Claude: clock gate in training; team history removed
- `labeled_examples` now rejects outside-scouting rows from a match whose clock check verdict is
  `exclude` (reason `external_clock_match_excluded`). The check runs after each row's own join, so rows
  that fail individually keep their specific reason. `unlabeled_examples` also takes no reference crops
  for those robots/tags from an excluded match. Human video labels are unaffected.
- Exclude rule (neptune_quality): a measured clock with p90 residual > 1.5 s, joined rows out of scouting
  time order, under 50% of rows joining, or no clock at all. Too few readings to measure is `marginal`,
  not excluded.
- Removed `team_priors`, `prior_shares`, `validate_priors`, `observed_shares` from the scoring model and
  from the trained head (`team_priors`, `prior_version`, `validation.team_history`, `teams_with_history`).
- `neptune_quality.py` is now in `neptune_engine.FILES` and `SERVER_FILES.txt` (training imports it).
- Effect: engine fingerprint changes, so `compatible_preparation_engines()` is empty and cached preparation
  is redone on the next run. Not yet synced into neptune-frc-scouting or deployed.
- Tests: engine 345, only the 7 pre-existing environment errors; server PHP unchanged (26/29).

## 2026-10-21 — Claude: match quality reports
- Added `engine/neptune_quality.py` + `engine/test_quality.py` (10 tests) and `docs/match-quality.md`:
  a per-match clock-join check, and a per-match count/points report against reference labels and the video's
  score bug. Read-only; no engine fingerprints change.
- Ran the clock check on the qm1/qm3/qm4 facts: all `usable`. The first version counted the held 2:20/0:00
  reads as failures (33–68% "rejected"); fixed to count only rejects while the clock runs.
- Not done: running it on the ViperScout matches (facts deleted; reprocess first); wiring into training (done in the next entry).

## 2026-10-21 — Claude: repo created
- Moved autonomous scouting out of `neptune-frc-scouting` into this repo. Engine `2.4.0-review-learning-preview2` (I said 2.2.8 earlier; that is the trainer app build). It includes the
  local working-tree edits that were never committed in the main repo (the PU head gates and scoring
  changes), because `helper/` there is untracked and this was the only copy.
- Checked: `scripts/sync-to-neptune.sh … --check` reports no differences against the main repo.
- Open: see "Known problems" in `SYSTEM_MAP.md`; the review is in `reviews/`.
