# Work log (newest first)

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
