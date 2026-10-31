## 2026-10-31 — Climb/defense regions release built: Mac 3.2.83, Windows 6.5.54, Linux 6.6.45, engine 2.7.68 (Claude, not published)

Merged origin/main (afff06f, robot match test 3.2.82). Conflicts in the region-type lists were resolved by keeping `field_reference` and adding `climb_zone` and `defense_zone`. The engine now skips unknown region types, so an event marked with a newer type keeps its other zones.

Built in ~/Documents/ChatGPT/Neptune:
- Mac-Helper-3.2.83-ready: 597 tests OK on the bundled Python, Sparkle signature verified.
- Windows-Helper-6.5.54-ready and Linux-Helper-6.6.45-ready: package sizes within a few KB of 6.5.53/6.6.44.

Also included and not wired in: scoreboard weak labels, the robot-points allocator and the geometry rules (evaluation only).

## 2026-10-30 — Climb/defense region types deployed to the marking page (Claude, owner approved)

The live `autoscout/scoring-areas.php` and `community/assets/field-regions/app.js` differ from this branch: they also have `field_reference`, which is on main. So I didn't replace them whole. Instead I applied targeted edits over AWS SSM that add `climb_zone` and `defense_zone` to the save check and the Region type list. `php -l` passes. The backup is `/root/region-kinds-backup-20261030`.

Caution: released helpers (engine 2.7.41) reject a field-region document with an unknown type. An event marked with a climb or defense area loses all its zone hints on those helpers until a helper release. `validate` on this branch now skips unknown region types instead of failing (test added; suite passes, 531). This branch's `KINDS` also needs `field_reference` from main when it merges.

## 2026-10-30 — Climb and defense region types for marking (Claude, local only, not deployed)

The Scoring Areas page (`autoscout/scoring-areas.php`, with the save check in `community/assets/field-regions/app.js`) and the engine (`neptune_field_regions.KINDS`) now accept two new region types:
- `climb_zone`: the climb area at the end of the match.
- `defense_zone`: where the selected alliance plays defense.

`neptune_geometry_rules.defense` uses a marked `defense_zone` and falls back to the opponent's scoring zone. `climb` reads `climb_zone`. The engine suite passes (530). The site change still needs the owner's approval to deploy.

## 2026-10-30 — Scoreboard-constrained robot points and geometry rules: measured, not wired in (Claude, local only)

Added `neptune_score_labels.allocate`. It splits each held scoreboard increase evenly among that alliance's robots inside a marked scoring zone in the delay-corrected window. With no robot inside, the points stay unassigned. Robot points plus unassigned always equal the displayed increases.

Added `neptune_geometry_rules.py`:
- Defense: sustained (3 s or more) presence in the opponent's marked scoring zone.
- Climb: last tracked position in a region of the game pack's `climb_region_kind`. It returns `unavailable` when nothing is marked.

`engine/evaluation/evaluate_rules.py` compares both with hand labels. Tests are in `engine/test_geometry_rules.py`; the engine suite passes (528).

Results on txcmp1 qm1/3/4/6 with a fixed 5.0 s delay. The pooled delay came partly from qm3/qm4, so it is slightly optimistic.
- Robot-point share against hand score-click share, compared with an even split: qm3 .307 vs .272 (worse), qm4 .302 vs .326, qm6 .102 vs .397. qm1 assigned nothing: its tracking has no robots in a zone.
  Hand clicks cover only some robots (qm6: one alliance), so this truth is itself partial.
- Points assigned: 65–98% per alliance.
- Defense, share of hand defense clicks inside a rule interval: qm3 0/13, qm4 3/28, qm6 16/19. Robot AUC .50 / 1.0 / .56. Defense in this game is mostly not inside the opponent's scoring zone, so the rule is not good enough.
- Climb: no climb regions are marked for any event, so it can't be measured.
- Auto: no facts on this helper for the only auto-labelled match (qm2).

Next: mark a climb region and a defense region (the opponent's half, as a field-wide polygon) for txcmp1, then re-run.

## 2026-10-30 — Weak scoreboard labels on unlabelled matches: no measurable gain (Claude, local only)

The owner marked scoring zones for 2026kett (qm7), 2026week0 (qm8) and 2026txfor (qm10). I copied the marks read-only from the server (AWS SSM, with the owner's approval) into `~/.neptune-trainer/field-regions/events/`. 2026ctwat has no marks; its earlier local file was an empty list.

Added `engine/evaluation/build_weak_matches.py` (facts + tracking, then weak and unlabelled R3D-18 clips per match) and `evaluate_score_labels.unlabelled_match_effect`. Outputs are in `~/.neptune-trainer/weak-labels/`. Run it with NEPTUNE_GAMES_HOME at a job folder: the engine's built-in pack lacks the AGE and Week 0 layouts.

- **Kettering is dropped.** The mid-build broadcast shows clock and teams but no alliance scores.
- **Facts built:** Week 0 qm3/6/8/11/14, txcmp1 qm8 (tracking unavailable: "OCR stream ended"), ctwat qm4/56/62. ctwat qm32 failed: an AGE variant with only 39 of 167 overlay frames showing the marker.
- **Delay:** 5.0 s, pooled over the hand clicks on txcmp1 qm1/3/4/6. No Week 0 data was used.
- **Week 0 yield:** 113 score changes, 26 credited to one robot, 14 usable clips. The Week 0 marks cover only the wide camera, so most changes are "no marked zone" or "no alliance robot seen".

**Held-out AUC on hand positives.** Folds are the hand-labelled txcmp1 matches; Week 0 rows are in every fold's training set and never scored.

| Action | Folds | Week 0 unlabelled clips only | With 14 weak positives |
|---|---|---|---|
| score_1_fuel | 3 | 0.674 | 0.673 |
| score_2_fuel | 3 | 0.624 | 0.641 |
| scoring | 2 | 0.468 | 0.467 |

No measurable gain. 14 labels is too few, and the differences are noise-level.

**Alliance-total check on unlabelled matches** (points model trained on all 249 score examples): only Week 0 qm14 red could be checked, at +118 (predicted 217 vs displayed 99). Every other alliance has a robot with too few sightings for the points model, or the video is incomplete, so robot points can't yet be checked on matches like these.

**What would change this:** marks on the close-up cameras as well as the wide view, more complete tracking per robot, and events whose broadcast shows scores. Nothing is wired into training. Not pushed or released.

## 2026-10-26 — Scoring labels from scoreboard changes; alliance-total check (Claude, local only)

The owner asked for weak scoring labels built from scoreboard score changes, plus a check of robot points against the alliance total. Kept local: not pushed, released or deployed.

Added `engine/neptune_score_labels.py`:
- `score_events`: an alliance score increase counts only if the new value is read at least twice in a row. Drops and one-read jumps are ignored.
- `measure_delay`: the broadcast delay between a robot's action and the scoreboard change, measured from hand clicks (most common lag, -2 to 10 s). It is measured, not assumed.
- `attribute`: an event goes to a robot only when exactly one of the alliance's tracked robots was inside a marked scoring zone in the 3 s before the delay-corrected change. Otherwise it is kept, unattributed, with a reason.
- Labels carry source `scoreboard_change`, weight 0.25 and `weak_supervision`, and are never merged into hand labels.
- `alliance_check`: the summed robot points per alliance against the final displayed score. Alliance-level parts (results_screen_components other than auto/teleop) are removed when the results screen was read. Duplicate estimates of one robot are averaged; an alliance missing a robot is marked incomplete.
- Nothing game-specific: zones come from marked field regions, and alliance-level parts from the game pack.

Added `engine/evaluation/evaluate_score_labels.py`. The delay applied to each match is measured on the other matches only. Q7 is refused. Truth is the hand clicks on the four txcmp1 matches that still have facts on this Mac.

**Delay:** 3.1 s (Q1), 5.0 s (Q3), 6.9 s (Q4) and 5.6 s (Q6) measured per match. It is not constant, which limits timing precision.

**Attribution against hand clicks.** Precision = attributed events with a click from that robot within the window. "Other robot" = the same events credited to another alliance robot that was seen (chance).

| Match | Window (s) | Events attributed | Precision | Other robot | Recall |
|---|---|---|---|---|---|
| Q3 | 2 | 18/34 | 0.72 | 0.12 | 0.38 |
| Q3 | 3 | 22/34 | 0.73 | 0.17 | 0.54 |
| Q3 | 5 | 24/34 | 0.79 | 0.28 | 0.67 |
| Q4 | 2 | 19/34 | 0.47 | 0.00 | 0.42 |
| Q4 | 3 | 20/34 | 0.45 | 0.04 | 0.51 |
| Q4 | 5 | 21/34 | 0.52 | 0.03 | 0.64 |
| Q1, Q6 | any | 0 | — | — | — |

Q1 and Q6 have no marked scoring zones on this Mac, so nothing is attributed there, by design.

**Weak labels added to training.** Match-held-out folds and gates unchanged. AUC is measured on hand positives only.

| Action | Weak positives | AUC hand only → with weak | Recall | Gate |
|---|---|---|---|---|
| score_1_fuel | 14 | 0.678 → 0.679 | 0.49 → 0.49 | passes both |
| score_2_fuel | 17 | 0.652 → 0.672 | 0.54 → 0.61 | passes both |
| scoring | 31 | 0.649 → 0.660 | — | no signal both |

These are small gains from 14–31 rows on two matches that already have dense hand labels: not evidence of improvement. The labels should matter on matches with marked zones and no hand labels, and none of those have facts on this Mac.

**Robot points.** The weak labels don't feed the points regressor, so leave-one-match-out MAE is unchanged (48.3). Alliance-total check with leave-one-match-out predictions: Q3 red +52 (blue incomplete), Q4 red −18, Q4 blue +41, Q6 red +74 (blue incomplete). Mean |gap| is 46 points per alliance. No results screen was read on these matches, so the totals still include fouls. Hand estimates match the totals by construction, so only the model's gap is informative.

Checked: `test_score_labels.py` (11 tests); 524 engine tests OK on the bundled Python. Not wired into training, `neptune_engine.FILES` or the server.

Next, if the owner wants it: mark scoring zones for more events, run facts on unlabelled matches, and measure the weak labels' effect on matches without hand labels.
## 2026-10-30 — Codex: robot match test completion and compatibility

Found the live test failed before producing a video: a 3.2.81 helper accepted unknown test_robot work and fell through to detector training. Test jobs now require an explicit helper capability; new helpers reject unknown kinds. The Robots page shows failures and the first finished result, loads newly available media, releases the session while streaming/uploading, and includes a download link plus editable YouTube upload fields. Native source frames/rate render to H.264 fast-start MP4; verified chunk transfer supports larger full-match videos and preserves the local output until server acknowledgement. Local PHP integration checks cover old-helper refusal, compatible claim, chunk retries/order/hash integrity and saved playback; Python robot job suite (17) and a 15fps H.264 smoke render pass. Release/deployment validation is pending.

## 2026-10-30 — Codex: TXCMP1 Q4 bumper extent redo

Reviewed the 75 current Q4 source-frame box sets, tightened chassis/mechanism extents to visible bumper foam, retained visible partial foam, removed unsupported labels, and reconciled 11 later edits. Saved per frame with exact previous-row guards; final readback of all 75 rows matches correction records and all normalized boxes are in bounds. 585 boxes remain. Training was not started. Receipts and source review artifacts: local/qm4-label-audit-20261026/current-corrections (artifact workspace).

## 2026-10-30 — Codex: March4 Q5 full visible bumper perimeter correction

- User found systematic front-face-only boxes after initial batch. Re-audited all125 exact native frames and wide/inset panels using expanded context, enclosing all visible foam faces per robot appearance. Expanded angled bounds, merged split faces, removed unsupported rail/glare/mechanism labels. Existing user edits used as baseline and guarded against concurrent change.
- Saved25 corrected rows each for2026bcvi,2026mndu,2026mnwi,2026mndu2,2026okok Q5. Currenttotal 1039 bumperboxes. Eachrow read back; independent server pass verifies all125 reviewed-row hashes and immutable source images. No training started.
- Evidence and receipts: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/march4-qm5-review/correction-final-verification.json`, per-match correction-reviewed.json and correction-save-result.json. Supersedes earlier narrow-box audit. User next authorized March5,2026 Q5,25frames each, about10 usefulclose-up-pane frames/match, save eachframe as completed.

## 2026-10-30 — Robot detection match test + helper selector on 1 · Robots page (Gemini)

- Added a **Test a match** section to `server/public_html/Neptune/autoscout/robot-labels.php` using the shared Year / Event / Match selector (`server/public_html/Neptune/community/assets/match-picker/match-picker.js`, updated to support multiple pickers and `data-select-only="1"` mode without page navigation), a **Helper** dropdown (`#robot-test-computer` populated from `community_training_computers` with live online/busy status), and a **Test** button.
- Queues `test_robot` jobs via `RobotDetectorJobs` (`server/neptune_secure/robot-detector-jobs.php`, `server/public_html/Neptune/api/robot-detector.php`, `server/neptune_secure/autoscout-train-overview.php`), targeting either the chosen helper computer or the first available helper. The helper runs `test_robot()` (`engine/neptune_robot_jobs.py`, `engine/neptune_steps.py`) using the current robot detector, BoT-SORT tracker, bumper OCR, `reconcile`, and `with_constant_identity`, then renders `robot_test_video()` (`engine/neptune_review_video.py`):
  - **Original broadcast view**: colored bounding boxes and bumper OCR tags matching the Review tracking palette (`#69deb4` green = OCR verified, `#48d9ed` cyan = constant / inferred identity, `#ffc773` amber = unresolved).
  - **Top-down homography view**: live 2D field projection with 3-second motion trails (using saved four-corner / boundary / `field_reference` marks from `neptune_homography.py`, or a wide-band perspective fallback when unmarked), plus a 6-robot constant identity status panel and full-match timeline strip.
- Saves the rendered MP4 and pre-filled metadata on Neptune (`robot_test_put`) so it can be watched directly in an inline `<video>` player (`robot-labels.php?robot_test_video=<id>`) with editable **Title** and **Description** fields and an **Upload to YouTube** button (`upload_robot_test_youtube`).
- Checked: PHP syntax (`php -l`), JS syntax (`node --check`), PHP `RobotDetectorJobs` end-to-end test, and Python unit tests in `engine/test_robot_jobs.py`. Committed and pushed to `main`; `site-autoscout` package built.

## 2026-10-30 — Codex: March 4, 2026 Q5 bumper batch live

- User requested Q5 at every event starting March4,2026,25frames each, and authorized parallel reviewers. Catalog: Canadian Pacific52981, Lake Superior53248, Minnesota Bluff Country73059, Northern Lights62776, Oklahoma62962. Registered125 native1920×1080 exact private source stills, manually reviewed main/inset foam appearances, corrected proposal misses/chassis extents and removed fieldhardware/fuel/banner falseboxes. Parent reviewed per-box evidence and enlarged ambiguous crops, completed checks after reviewer usage limits.
- Saved25 complete rows per match,1,052 bumper appearance boxes. Locked new-timestamp writes preserved existing labels, checked immutable source/image hashes and exact readback after each save. Independent final server check verifies125 complete frames and125 source image hashes;116 rows unchanged, nine Canadian Pacific rows were subsequently edited by signed-in user4 and preserved. Final readback has1,056 boxes. No training started; reserved Q7 untouched.
- Metadata, native stills, reviewed JSON, save receipts, current-state snapshots and final-verification.json: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/march4-qm5-review/`. Final batch payloads reflect our reviewed saves; current snapshots preserve subsequent user edits. Earlier generation scripts retain intermediate decisions and must not overwrite final saved labels.

## 2026-10-30 — Codex: TXCMP1 Q3 full existing-frame bumper audit completed

- Manually reviewed all 92 already-labeled timestamps of match 208, `2026txcmp1_qm3`, against immutable native 1920×1080 source stills, including main and inset panels. All 92 extracted JPEG hashes match server frame metadata. Corrected missed/loose bumper labels and removed false labels on field hardware, advertisements and chassis; visible occluded/clipped bumper foam retained, fully hidden bumpers omitted.
- Saved all 92 reviewed rows with exact prior-row guards, per-batch server document backups and atomic replacement. Independent final server fetch confirms all 92 complete, 770 bumper appearance boxes, exact reviewed boxes and frame hashes. The original 92 timestamp keys remain unchanged. No model training started; broader Reefscape batch remains stopped.
- This full audit supersedes the earlier frame 1/frame 2 entries: each now has nine boxes after two tiny fixed-field false positives were removed.
- Evidence, source hash verification, reviewed JSON and save/readback receipts: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/txcmp1-qm3-full-audit/`; final receipt `final-verification.json`. Source video SHA-256: `8dc8db13fc738645cb1a2c1053ff808250b0ee2fe43d65f5c85a886ae259b5b0`. Server backup directories use `/root/q3-label-audit-backup-<timestamp>`.

## 2026-10-30 — Codex: TXCMP1 Q3 frame 2 correction

- Corrected match 208 second prepared frame (4,000 ms): inspected native 1920×1080 still and enlarged main/inset crops, saved 11 bumper appearances. Verified immutable frame SHA-256, guarded against concurrent edits, backed up prior document, and read back exact corrected row. Preserved the other 91 frames, including frame 1.
- Before/after labels, source still, overlay and server receipt: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/txcmp1-qm3-frame2-audit/`. No training started.

## 2026-10-30 — Codex: TXCMP1 Q3 frame 1 bumper correction

- Corrected match 208, `2026txcmp1_qm3`, first prepared frame at 0 ms. Inspected immutable 1920×1080 source still and enlarged main/inset crops. Saved 11 bumper appearances replacing five prior boxes, including inset misses and partially occluded bumpers. Preserved the other frames using a guarded row comparison and backup; verified exact saved JSON and source SHA-256.
- Receipt, before/after data and overlay: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/txcmp1-qm3-frame1-audit/`. No model training started. Earlier two-match audit remains unfinished.

## 2026-10-30 — Field-references release: Mac 3.2.81, Windows 6.5.52, Linux 6.6.43, engine 2.7.66 (Claude, deployed)

Owner asked to merge and build. Live helpers were on engine 2.7.65 with code main lacked, so main first merged `claude/exciting-kilby-bb0e78` (YOLO11 Small robot detector) and `release-2.7.43` (robot-identity check); only WORK.md conflicted. Merged main checked against the live Linux 6.6.42 package: every live line is present or superseded. Then committed Codex's polygon/corner work and the field references.

Built in ~/Documents/ChatGPT/Neptune: Mac-Helper-3.2.81-ready (signed, Sparkle signature verified, 578 tests on the bundled Python; GitHub release step stubbed, not run), Windows-Helper-6.5.52-ready (update zip, full zip, Setup.exe; same file list as 6.5.51), Linux-Helper-6.6.43-ready (deb, update zip, apt repo; same file list as 6.6.42). Engine suite 578 OK, packaging tests 12 OK.

Server changes against live: engine `neptune_homography.py`, `neptune_field_regions.py`, `season_rules.json`, `neptune_engine.py`; site `autoscout/scoring-areas.php`, `community/assets/field-regions/app.js`. Live app.js fetched publicly equals HEAD minus the field-reference edits.

Owner approved publish and deploy. GitHub main had the tracking (2.7.64) and keep-awake (2.7.65) release commits under other hashes plus Windows/robot-labels changes, so main merged origin/main first (9057881) and all three helpers were rebuilt from it; 578 tests on the bundled Mac Python. GitHub releases helper-3.2.81, helper-windows-6.5.52, helper-linux-6.6.43.

Deployed through AWS SSM f3851229: 16 files fetched and verified, 21 changed. Backup: `/root/field-references-release-backup-20261030`. Pruned 3 old copies (316 MB). The first attempt stopped at the live-hash check: the server engine's `neptune_homography.py` and `neptune_field_regions.py` were still the 2.7.65 versions (Codex's polygon patch hadn't reached them); this release installs them. A second attempt stopped on the leftover empty backup folder; it was removed.

Checked from outside: Windows `latest.json` 6.5.52 and Linux 6.6.43 on engine 2.7.66 (update zip SHA-256 matches local), appcast 3.2.81 (zip size matches), apt lists 6.6.43, live Field page `app.js` matches the commit.

## 2026-10-30 — Codex: local artifact cleanup

- User requested purging unnecessary repository artifacts. Removed 13.9 GiB of downloaded original match videos, duplicate completed helper build trees, release/transfer archives and bytecode caches from the Documents workspace. Preserved source, datasets, model weights, labels, native audit stills, source metadata, decisions and save receipts.
- Kept Codex checkpoint history intact while Codex is running. No Neptune server data changed and the labeling batch remains stopped. Verified all 2,046 Reefscape candidate stills remain. Removed-file manifest and receipt: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/cleanup-20261030/`.

## 2026-10-30 — Top-down map from field references when the near corners are cut off (Claude, local, not released)

Built the floor-reference map the 2026-10-29 geometry test pointed to. Nothing committed, pushed or deployed.

- Game pack: `engine/season_rules.json` 2026 revision 4 adds `field_references` (sizes and positions from manual TU22 5.2–5.8): far corners, far guardrail, both alliance walls, centre line, both hub bases, and the tower upright pair (a direction parallel to the guardrails, since the towers are mirrored). The server copy matches. No game values in code.
- Engine: `neptune_homography.reference_map()` solves the picture→field map from any mix of marked points, lines and directions; it returns nothing unless the marks pin the plane down, agree within 4% of the frame, and put the field in front of the camera. `trajectories()` uses it per wide shot only when no four-corner calibration exists. `field_reference` is a new region kind (1 point or 2), validated in `neptune_field_regions` and never treated as a zone.
- Field page: new region type "Top-down map · field reference point or line" with a reference picker filled from the game pack; one click for a point, two for a line; server POST and JSON import accept it (1–2 points, reference name). `app.js?v=5-field-references`. Checked in a local harness with real clicks: marks save, draw, export, re-import, and pass both the engine and the server validation; bad marks are rejected.
- Accuracy (engine code on the five full-view events, near edge hidden, 200 simulated markings each, error at visible floor points): hubs + far corners only: median 4–7 in at 0.3% marking noise, 8–14 in at 0.6%. All references: median 3–5 in (p90 6–10 in) at 0.3%, 6–9 in at 0.6%. Rejection at 4% tolerance: 0% at 0.3% noise, 0–13% at 0.6%; swapped hubs are always rejected, but a hub marked 4% of the frame too high is not.
- Tests: `engine/test_field_references.py` (9). Full engine suite on the bundled helper Python: 571 OK.
- Follow-ups: Train page and Field page text still say "four field corners"; the Train overview's calibration flag ignores references; per-mark residuals on the Field page would let markers fix a bad click.

## 2026-10-29 — Codex: March 4–8, 2025 robot-labeling batch in progress

- User requested two matches per event starting March 4–8, 2025, 25 manually reviewed bumper frames per match. Verified 31 events: 62 matches / 1,550 frames.
- Prepared all 62 playable source videos and unreviewed detector proposals locally. Proposals are not completed training labels.
- Saved and read back 25 reviewed frames each for İstanbul Q6 (`2025tuis_qm6`, match 66181; 188 boxes) and Bosphorus Q6 (`2025tuis2_qm6`, match 66094; 194 boxes). Imported immutable native source stills through Neptune; verified frame/source SHA-256 before guarded label merges. Preserved existing labels; ran release pruning after each save.
- Remaining: 60 matches / 1,500 reviewed frames. No training or model adoption started. Local event/match index, decisions, source frames and receipts: `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/reefscape-march4-8-batch/STATUS.md`.

## 2026-10-29 — Field corners hidden by the picture: geometry test (Claude, local, not released)

Owner asked whether clipped corners can be estimated with math. On the 60 marked documents, extending all four boundary edges gives a quad for 52, but in 47 the bottom edge is a flat crop (score overlay or split-screen top), so the near corners come out too high (checked on Kettering, Houston and txcmp1 frames). Only Dallas, capoh, cahal, orsal and okok show a real near edge.

Using only the real edges (far guardrail, both alliance walls) with the manual's field size (651.2 x 317.7 in) and a level pinhole camera centred on the picture: near corners within 3–5% of frame width for Dallas and orsal, 30–50% off for capoh, cahal and okok. Adding both hub top openings (158.6 in from each alliance wall, centred, one fitted height): within 1–5% for Dallas, capoh and orsal; 15–42% off for cahal and okok. The fitted hub height sits at its 40 in lower bound in four of five matches, so an assumption is off: the manual text does not say whether 158.6 in is to the hub's centre or face, the hub height is not in the text, and split-screen panes move the picture centre. Not reliable enough to use; nothing added to the game pack or engine.

Refit with the manual's exact hub numbers (TU22 pp. 21–23: the 158.6 in alliance zone ends at the hub's face, so the centre is 182.1 in from the wall; the opening's front edge is 72 in up): Dallas 1–3%, okok 4–8%, orsal 6%, capoh 23–28%, cahal 13–29%. Every variant (182.1/158.6 in, 72/60 in) fits the marked lines and hubs almost exactly, yet moves the hidden corners by 20–40% of frame width. The solve is ill-conditioned when the near corners are far off-screen, which is the case it was meant for. Verdict: estimated corners are dependable only where the near corners sit just outside the picture; elsewhere keep marked zones and the outer-target fallback. A physical floor line visible below the hubs (e.g. the CENTER LINE or ROBOT STARTING LINES, if marked) would add the missing constraint.

Floor reference points fix it (simulated on the five matches with all four corners known, marking noise 0.3% / 0.6% of the frame, error for floor points inside the picture). Far corners + both hub bases (front-bottom edge centre, 158.6 in from each alliance wall, centred): median 4–7 in / 7–14 in. The owner's construction (far corners + field centre, found where the line between matching tower-upright bases crosses the CENTER LINE, + the vanishing point of both alliance walls and the CENTER LINE): 4–7 in / 7–14 in. Both together: 3–5 in / 6–10 in. The centre construction assumes the field is rotationally symmetric (matching uprights pair through the 180° turn); the drawings should confirm. Scripts: `hub_base_test.py`, `centre_point_test.py`. Scripts: `local/field-detector-eval-20261029/near_edge_solve.py`, `near_edge_hubs.py`, `recovered_corners.jpg`.

## 2026-10-29 — Codex: completed 20 REEFSCAPE review frames

The owner clarified 20 frames total in the same 2025 Northern Lights Q6 match, rather than 20 matches. Manually reviewed and saved 16 additional source instants: 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 128, 136, 144 and 152 seconds. Retained visually checked detector proposals, added missing visible bumper fragments and rejected duplicate, spectator/reflection and unverifiable occluded proposals. Inspected source wide/closeup crops with coordinate grids and final box overlays; no boxes were copied across timestamps.

Save/read-back succeeded: 16 added completed frames with 136 boxes; 20 completed frames total including the original 30/60/90/120-second reviews (172 bumper appearances, not unique robots). Existing four reviewed frame records were preserved; remaining 30 prepared frames remain guesses. Server validated immutable JPEG fingerprints, shared video source fingerprint and normalized box bounds, refused timestamp conflicts, backed up only the existing label document, atomically saved and verified the document, and ran release pruning. No detector training or adoption was triggered. Task evidence: local/reefscape-20-frame-review/meta.json, reviewed.py, manual-labels.json, reviewed/ and save-result.json in the task workspace. Only review stills were produced. Neptune: https://neptunefrc.com/autoscout/robot-labels.php?match_id=60266.

## 2026-10-29 — Field detector: measured on held-out venues; retraining does not fix it; keep marked zones (Claude, local, not released)

The owner asked to improve the field detector. Measured first, on frames every 2 s from 8 owner-marked matches, scoring each hub and each in-view corner (found within 10% of frame width, per-frame hit rate, match-level as the adoption check). Candidates were trained like `train_field` (warm start from the bundled weights, 1280, batch 4, every fifth training frame as validation, 15 passes on the owner's Linux helper, CPU). Dallas qm6 and Q7 never trained anything.

| Held-out match (camera) | Bundled (in use) | C0: data today's runs use (txcmp1 qm4 + cmptx sf2m1) | C1: all 7 marked matches | C2: C1 + scale .9 / perspective .001 |
|---|---|---|---|---|
| 2026dal_qm6 (side angle) | 3/6: hubs 2/2, corners 1/4 (per-frame 81%) | 3/6: hubs 2/2, corners 1/4 (89%) | 3/6: hubs 2/2, corners 1/4 (32%) | 3/6: hubs 2/2, corners 1/4 (35%) |
| 2026kett_qm7 (bottom off frame) | 1/4: hubs 0/2 | 0/4: hubs 0/2 | trained on | trained on |
| 2026cmptx_sf2m1 (Houston) | 0/4: hubs 0/2, corners 0/2 | trained on | trained on | trained on |
| 2026txsan_qm8 | 4/8: hubs 2/2, corners 2/4 | 6/8 (both close-up hubs) | trained on | trained on |
| 2026txcmp1_qm8, txfor_qm10, week0_qm8 | all hubs, txcmp1 corners 3/3 | same | trained on | trained on |

C0 reproduces the site's Oct 29 11:52 run (3/6 vs 3/6), so the shown field runs could not beat the detector in use. The bundled detector's failures are hubs that appear large near the top of the picture (Kettering, Houston) and the three Dallas corners nobody's training data shows (Dallas is the only side-angle venue with corners). More marks from end-on venues and stronger scale augmentation did not move Dallas; they halved its per-frame corner hit rate. Target-only/boundary-only matches put visible but unlabelled corners in training frames, which teaches "not a corner"; worth watching now that 37 such matches were added.

Upper bound with hand-marked landmarks (no detector), zone IoU against the owner's own zones at another venue: hubs only (similarity) 0.35–0.68; four-corner homography 0.56–0.81; two marked matches at the same event 0.77. A field-coordinate homography from any visible corners + hub feet failed (0.00–0.04 with two corners): hub feet land at inconsistent field positions across calibrated matches, so the marked corners are not the same physical points across venues.

Found and fixed locally that `visible_corners`/`document_at`/`train_field` dropped every match whose boundary was not exactly four points (Kettering) or had no corners (Fort Worth, Week 0), so field runs trained on two matches. Codex's polygon work (entries below, deployed) supersedes that change with explicit `corner_indices`; it kept my edge-boundary test. The Train page and its guidance still mention four corners in `train-tabs.js`.

Recommendation: keep marked zones as the default (one marked match per event; now 52 events). The detector is a rough fallback for unmarked events. Hubs are its usable part; corners need confirmed physical corners at several side-camera venues before retraining can help Dallas-like views. Next measurable step: retrain on the 52-event hub labels and score hubs leave-venue-out, with Dallas as the corner check.

Checked: 560 engine tests OK on the bundled Python 3.13, including Codex's current field changes. The bundled detector scores identically on the Mac (MPS) and Linux (CPU). Evidence, scripts and per-landmark JSON: `local/field-detector-eval-20261029/` (not in git). Nothing pushed, released or deployed.

## 2026-10-29 — Codex: manually corrected four REEFSCAPE robot-label frames

At the owner's request to improve the detector guesses, visually reviewed the exact 30/60/90/120-second source instants for 2025 Northern Lights Qualification 6. Corrected missed blue bumpers, split adjacent red/blue bumper boxes, tightened visible-fragment bounds and removed the 120-second spectator false positive. Saved 36 bumper-appearance boxes across four completed frames in Neptune. The other 46 prepared frames remain guesses; no model was retrained or adopted.

Verified the local source-video SHA-256 against all four immutable Neptune frame records. Re-decoded timestamps with FFmpeg, inspected full-resolution frames, enlarged occlusion crops and box overlays. Server save checked immutable JPEG hashes, valid normalized boxes and absence of concurrently saved labels at those timestamps, then read back the persisted document: four complete frames. Existing labels/guesses elsewhere were preserved; only the replaced label document was eligible for backup, and release pruning ran. Counts represent appearances across broadcast panels, not unique robots; no numerical accuracy claim was made. Reviewer metadata identifies Codex. Receipts and reviewed stills: task workspace local/reefscape-robot-detection-20261029/manual-save-result.json, manual-labels.json and manual-*.jpg. No generated diagnostic video.

## 2026-10-29 — Codex: REEFSCAPE robot-detector trial

At the owner's request, ran Neptune's current robot bumper detector on Northern Lights Regional 2025 Qualification 6 (`2025mndu2_qm6`, catalog match 60266, source `yHG0zVaXvH8`). Queued a normal prepare request, `0268706c3bee17b0690b7e54`; the connected helper completed it and persisted 50 source frames with 195 bumper-appearance guesses. These remain detector prefill, not completed human labels or 195 unique robots. Current weights fingerprint: `b77206cbc1159ae4849c63d3bcd00d7ac7acd29ee422c1f5e80a300a60a7c080`.

Independently decoded and inspected 30/60/90/120-second frames locally using the same weights. The detector finds REEFSCAPE bumpers but misses visible blue bumpers, can merge adjacent opposing bumpers (90-second wide view), and produced an extreme-right spectator false positive at 120 seconds. No exhaustive ground truth or accuracy percentage was invented. CPU and helper per-frame counts differ slightly; neither is treated as truth. No training/adoption, scoring changes or completed-label writes were performed. Only review stills were generated, no new diagnostic video. Evidence and receipts: task workspace local/reefscape-robot-detection-20261029. View in Neptune: https://neptunefrc.com/autoscout/robot-labels.php?match_id=60266.

## 2026-10-29 — Codex: expanded field labels to 52 events

At the owner's request, visually reviewed all 22 saved user-4 field documents and added 37 new matches, one per additional event. All 37 new examples mark two wide-camera scoring targets and a visible boundary polygon at the decoded 60-second reference frame, with explicit empty confirmed/inferred-corner lists for clipped outlines. Downloaded and fingerprinted the exact individual source videos; Southern Cross Q6 was unavailable, so used Q3 after checking its video. No reserved Mercury Q7 source was included.

Existing label IDs were preserved. Filled missing target/boundary pairs in Waterbury Q6, Fort Worth Q10 and Week 0 Q8. Re-reviewed Kettering Q7 geometry. Corrected Einstein SF2M1's outro/title-card reference to visible match footage at 60 seconds and retained its clipped map region as an outline rather than false calibration. Existing annotation timing was narrowed to the reviewed instant for those repaired legacy examples; no static coordinates were extended across unverified camera cuts. Other labels, imports, scoring rules and running jobs were preserved. No invented physical corners or reference scores were added.

Uploaded with canonical-document concurrent-edit guards, backups limited to replaced documents, full schema/geometry validation, existing-ID checks, and saved-document read-back. Neptune now has 59 user-saved documents across 52 events (285 regions), plus the existing seed document. New examples and the 22 saved documents all satisfy target + boundary eligibility. Field training was not started. Final evidence, source provenance, review stills, receipts and direct match links: task workspace local/field-expansion-20261029/EVENTS-AND-MATCHES.md and verification.json. Only source stills were produced, no generated project videos. Server release pruning completed after the upload.

## 2026-10-29 — Codex: deployed polygon support and repaired 16 match documents

Deployed the targeted website/server-engine polygon patch via SSM after AWS reauthentication, preserving live YOLO11 Small and tracking changes. Backups covered only replaced files; Python compilation and PHP lint passed and release pruning ran. Updated all 16 earlier annotated user-4 match documents in place with explicit outline-only corner metadata; preserved all existing region IDs, coordinates, targets, timing and source fingerprints. No unverifiable physical corners were invented. Neptune's live Your data panel now shows 23 marked matches and 20 with targets + boundary. The 16 repaired documents all validate and satisfy target + boundary eligibility; they remain 60-second reference labels, not continuous-video calibration.

Validation: 39 focused tests passed against the merged production engine, Windows package and bundled Mac runtime. Saved UI proof and deployment scripts/receipts in the task workspace local/polygon-rollout. Windows 6.5.51, Linux 6.6.42 and signed Mac 3.2.80 updates prepared from the current published packages, preserving tracking; published and verified via public feeds (Windows/Linux archive hashes, signed Mac feed, server-side Mac archive hash and public archive size). Field jobs now require these compatible helper versions; existing active jobs were not interrupted. Active training jobs were not interrupted. The separate four-physical-corner homography requirement and confirmed-corner held-out evaluation gate remain intact.

## 2026-10-29 — Codex: polygon boundary eligibility and explicit corners

Field training accepts scoring targets with a visible boundary polygon (including hexagons), separately from four-physical-corner map calibration. Polygon vertices are no longer automatically corner labels; optional confirmed and inferred vertex lists are validated in the editor, API and engine. Inferred corners do not become corner-training truth. Legacy four-point calibration semantics remain compatible. Overview, helper summary, and button eligibility use targets + boundary; held-out evaluation still requires confirmed corners and preserves an explicitly requested evaluation match. No user annotation documents, reserved benchmarks, releases, or running training jobs were changed.

Validation: 39 focused Python tests (field detector, regions, source-timed training, polygon regression), PHP summary classification and syntax checks, JS metadata behavior and syntax checks. Prepared against existing uncommitted engine changes with hash guards; originals backed up in the task workspace. Local source update only; hosted server and packaged helpers require coordinated rollout before this behavior is live.
## 2026-10-30 — Keep-awake release: Mac 3.2.80, Windows 6.5.51, Linux 6.6.42, engine 2.7.65 (Claude)

The owner's Windows PC slept with Keep awake set to Always. Fixed in `neptune_awake.py` (34bb387) and released, approved by the owner:
- SetThreadExecutionState now has DWORD argtypes, and a failed call no longer ends the 30 s holder thread.
- The last mode Neptune sent is saved in `~/.neptune-trainer/keep-awake.txt`, so Always holds from launch and while the helper is offline or signed out. A check-in reply without the setting keeps the current mode.
- `awake` on My computers reports whether Windows accepted the request, not just the wanted mode.
- On Modern Standby PCs (`powercfg /a` lists S0 Low Power Idle) the screen turning off can still start standby; the owner was told to set the screen timeout to Never while plugged in if it still sleeps.
- Built in a separate worktree from origin/main. All three packages carry the fix and import the helper modules.

## 2026-10-29 — Tracking release: Mac 3.2.79, Windows 6.5.50, Linux 6.6.41, engine 2.7.64 (Claude)

The owner approved merging the tracking session's identity-model work (`release-2.7.43`: 00ea88d, e23ffdc, 16326b5) and releasing it with the Tracking pillar, the shared identity model and the pillar order (Robots, Tracking, Field, Actions). It is built on f420182 (the Small-detector release).
- The merge and builds ran in a separate worktree, because the main checkout holds the field session's and Codex's uncommitted edits.
- Detector weights were copied in from the main checkout.
- 560 engine tests and the helper server tests pass on the merged code.
- The Windows and Linux packages import the Tracking and shared-model code from their own files. The installed 6.5.49 / 6.6.40 updaters accept these updates.
- The identity model passes its new held-out check on the owner's four reviews (350 right, 0 wrong). The reviewing helper reports and shares it after the next saved review on this version.

Deployed through AWS SSM. A permission check blocked Claude from sending it, so the owner sent the prepared command (e68cecc3) after renewing the AWS sign-in. 60 files hash-checked, 65 changed, including the new `tracking-identity.php`, and `api/robot-detector.php` matched f420182 live. Backup: `/root/tracking-release-backup-20261029`.

Checked from outside:
- The appcast offers 3.2.79 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.50 and 6.6.41 on engine 2.7.64, and both update zips match their local SHA-256. apt lists 6.6.41.

## 2026-10-29 — Robot-identity model: fit fixed, match-held-out identity check (Claude, not released)
- Why the head linked nothing: the 5 pair features differ in scale by ~100x and the fit took 150 fixed gradient steps, so it stopped badly under-fitted. Every same-robot pair scored at most .87, below the .9 link threshold. The features themselves separate well (same robot vs other: centre distance .02 vs .43, appearance .05 vs .23).
- `fit` is now a class-balanced logistic regression fitted by Newton steps on standardized features, folded back to the same 5 raw weights plus bias, so stored models keep their format.
- Leave-one-match-out pair check on the owner's library (QM1/3/4/6, 2311 pairs): before tp 0, fp 0, fn 1219, tn 1081. After tp 1079, fp 0, fn 140, tn 1081 (precision 1.0, recall .885). The candidate is now eligible.
- New `identity_check`: a match-held-out identity check on the full saved reviews (`identity-reviews/*/identity-review.json`), with no hand-built audit file. Each match is scored by a head trained without that match or its video. Reconcile sees only detections, tracker IDs and bumper reads; the human corrections are the answer key. Reserved matches (Q7) are skipped. Same bar as `evaluate_association`: 2 or more matches, precision .98 or better, 150 or more correct, and no fewer correct or more wrong than without the model. It runs after training (about 9 s) and activates only on a pass.
- Result on the owner's 4 reviews (1688 checked boxes): without the model 443 correct, 42 wrong, 1203 unnamed; with it 454 correct, 42 wrong, 1192 unnamed. Precision .915, so not activated and not shared.
- What blocks the .98 bar is the solver, not the model. All 124 bumper-read names are right. All 42 wrong are solver guesses the review page marks for review: 30 motion-plus-roster guesses (QM1 close-up track 169 at 99-101 s; QM6 wide track -3 at 1-2 s) and 12 short-gap visual bridges (0 of 12 right). The model adds 11 correct names and no wrong ones.
- Not used: the 2 extra reviews on Neptune (txsan qm2, capoh qm9). Fetching them needs the helper's saved connection credential.
- Prototype and diagnostics: local/identity-model-20261029/. Tests added in test_review_learning.py; full suite OK.
- Solver guesses (owner chose "Fix solver guesses"). The 42 wrong names came from three moments. They were sorted by evidence (local/identity-model-20261029/guesses.py):
  - Follower serials (negative tracker IDs, boxes the tracker never confirmed) in the wide view: 36 right, 17 wrong. All 12 short-gap bridge suggestions also landed on them, 0 right.
  - Lone close-up boxes: 61 right, 11 wrong. The 11 are QM1 track 169: 6672 was carried 5 s backward across four tracker IDs from a read at 103 s, but the robot was 5261.
  - Rules added in `solve_window`, applied only to guesses with no bumper read: no name on a follower serial (`unconfirmed_track_needs_review`). In a close-up frame with one box, no carried name unless its own track has a bumper read (`lone_closeup_box_needs_review`). Short-gap and fragment bridges never target follower serials.
  - `identity_check` no longer scores boxes the reviewer drew (`manual_proposal`); the tracker never produced them.
- Identity check after the rules (1596 boxes): without the model 341 right, 0 wrong; with it 350 right, 0 wrong. Precision 1.0, so it passes and the model activates (tested on a copy of the library; the owner's files were not changed).
- Caveats:
  - The rules were found on these same 4 matches, so this pass is not independent evidence.
  - Coverage drops. Solver right names 454 to 350. Constant-identity layer right names: QM1 223 to 186, QM6 187 to 118, QM4 65 unchanged. Lost seconds per robot: QM1 80.2 to 86.0, QM6 76.2 to 85.1, QM4 93.5 to 104.2.
  - Wrong names in the tracking scores stay 0, and the hidden-OCR check is unchanged (the same 22 earlier QM6 seed misses).
- Owner chose to keep the rules (2026-10-29). Not released or pushed; release waits for owner approval.

## 2026-10-29 — Tracking pillar and a shared robot-identity model (Claude, local, not released)

The owner reviews tracking on the Mac, trains robot detection on the Windows PC and field detection on the Linux server. They asked for OCR and tracking to have a home, with the identity model shared by every helper.

- **Shared identity model:**
  - The helper where tracking is reviewed trains the association model after each saved review, as before. It now reports to Neptune (`tracking_put`): status always, and the model only once it has passed the independent identity check there.
  - `server/neptune_secure/tracking-identity.php` keeps `status.json` and `shared.json` per organization.
  - Every helper fetches the shared model after a check-in, at most every 10 minutes (`tracking_current`, `neptune_review_learning.sync_shared`). `active_association()` uses this computer's own passed model first, otherwise the shared one.
  - The gate is unchanged.
- **Tracking pillar:** a new Tracking page in both helpers, data from `models.tracking`. It shows:
  - whether a shared identity model is in use and who trained it;
  - reviewed matches saved on Neptune and which ones trained it;
  - the latest held-out check;
  - what it needs next;
  - Review tracking….
- **OCR** has nothing Neptune trains (Apple Vision or RapidOCR checked against the roster), so it has no pillar of its own.
- **Finding:** the Mac's current candidate links no robots confidently on held-out matches (tp 0 of 1,219 same-robot pairs at 0.9), so nothing is shared yet. The model itself needs work, which is separate from this plumbing.

Checked:
- `tests/server/tracking-identity.php` (8 PASS) and `engine/test_shared_identity.py` (4).
- Engine suite 554 OK. The first run caught the new fetch loop using `closing.wait`, which broke a connection test; it now runs off check-in replies.
- Tk and Mac Tracking previews.

## 2026-10-28 — Style automatic updates as switches on Helpers (Codex, deployed)

The Helpers page's per-computer Update automatically checkbox is now rendered as an accessible switch, using the existing Neptune theme variables. It keeps the same `data-auto-update` save handler and checked state. The new stylesheet includes a keyboard focus ring and reduced-motion behavior; the CSS and JavaScript asset URLs are versioned so browsers reload them. Local JavaScript syntax, PHP lint and diff checks pass. Read-only AWS preflight confirmed all four live files matched the prior Git revision.

Owner approved publication. Git commit `1e506e6` pushed. AWS SSM deployment `2e975c12-22b0-4731-9163-eacb4f592e15` succeeded with exact live-hash checks and backup `/root/helper-auto-update-toggle-backup-20261028`. Public versioned JavaScript and CSS URLs return the expected SHA-256 values. The owner-only rendered page was not visually checked without an authenticated browser session.
## 2026-10-29 — Small-detector release: Mac 3.2.78, Windows 6.5.49, Linux 6.6.40, engine 2.7.63 (Claude)

The owner approved the release of the YOLO11 Small detector and the other-seasons fix (entry below). Robot runs now need these versions (`supportsRobotValidation`).

Deployed through AWS SSM 0f1e7784 (owner ran it): 14 files fetched and verified, 19 changed. Backup: `/root/small-detector-release-backup-20261029`. Pruned 3 old copies (316 MB).

Checked from outside: Windows `latest.json` 6.5.49 on engine 2.7.63 (update zip SHA-256 matches local), Linux 6.6.40, appcast 3.2.78.

## 2026-10-29 — Robot detector: YOLO11 Small (Claude)
- The adopted bumper detector is YOLO11 Nano (2.6 M parameters). Held-out QM4 F1 has stayed at 0.83–0.86 across runs.
- `neptune_robot_jobs.training_base` now returns (weights, recipe). If the detector in use isn't Small, a run starts fresh from COCO `yolo11s.pt` (recipe `coco-yolo11s-first-small-v1`, 120 passes); once a Small detector is adopted, runs warm-start from it as before (80 passes). The holdout guard still applies to warm starts; COCO saw no match.
- `small_base()` downloads yolo11s.pt once to `~/.neptune-trainer/base-models/` and refuses it unless its sha256 matches the pinned 85a76fe8…d502d5. Report adds `model_size`.
- Adoption gate unchanged: new F1 must beat the current one by 0.02 on the held-out match.
- Tests: Nano→Small switch, fingerprint refusal, warm-start/holdout guard with Small. Engine suite 551 passing (bundled helper Python).
- Other seasons: `neptune_detector_training.prepare` accepted only `2026…` match keys, so a labelled 2023 match failed the 2:44 PM run ("Every frame needs its match and source-video fingerprint"). Any match key starting with a year now trains; Q7 and the held-out match stay refused. Tests added; suite 553 passing.
## 2026-10-28 — Run-details release: Mac 3.2.77, Windows 6.5.48, Linux 6.6.39, engine 2.7.62 (Claude)

The owner approved the release of run details on the Computers page and the latest-pass line (entry below). It is built on Codex's validation-split and switch work (Mac 3.2.76, Windows 6.5.47, Linux 6.6.38). The Windows and Linux packages import the helper modules from their own files, and the installed 6.5.47 / 6.6.38 updaters accept these updates.

Deployed through AWS SSM: 58 files hash-checked, 63 changed (engine and downloads only). Backup: `/root/run-details-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.77 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.48 and 6.6.39 on engine 2.7.62, and both update zips match their local SHA-256. apt lists 6.6.39.

## 2026-10-28 — Run details on the helper's Computers page; latest pass scores (Claude, local, not released)

The owner asked for the website's run detail on a working computer's card, especially the latest score line.
- A computer running a job now shows the full console inside its card on the Computers page (Tk `console_into`, Mac `console(..., into:)`): step, readings, stage and overall bars, next steps, recent log and Cancel. It updates in place.
- Every console, on the Overview too, adds a green "latest pass →" line taken from the newest end-of-pass log entry, e.g. `pass 47/80 · box 1.384 · cls 0.919 · dfl 1.322 · mAP50 0.729 · P 0.785 · R 0.703`.

Checked: the engine suite; Tk and Mac Computers previews with a running detector job.

## 2026-10-28 — Remove two Auto Scout entry points; RC double-click file opening (Codex, deployed)

Removed the owner-only Auto Scout card from `scouting.php` and the full Shared robot evidence / Community Scouting section and its two cards from `admin/index.php`. The Auto Scout feature itself and other navigation are unchanged. In the separate local RC source (`Documents/ChatGPT/rc.neptunefrc.com/release-center/web/app.js`), delayed the single-click details modal so a double click on a file or folder in either list or grid view opens it. Symbolic links still show details and are not followed. PHP lint, JavaScript syntax, and a focused single/double-click event test pass.

Owner approved publication. Git commit `17f2893` pushed. AWS SSM deployment `e70b8866-8e30-48e7-90f4-ac7206e70c03` succeeded with exact live-hash checks and staged PHP lint; backup `/root/autoscout-hubs-rc-doubleclick-backup-20261028`. RC was patched only in the click-handler block to preserve unrelated live code. Resulting live SHA-256: scouting `408fbfe4b08e`, admin `5d1d6daa53f3`, RC app.js `6213672ee7fd` (matches the syntax-checked local source). An initial attempt stopped before changing files because Node.js is not installed on the server; server-side JS syntax check was made conditional and the local Node check passed. Direct unauthenticated HTTP checks redirect to login, so rendered owner-only pages were not visually checked after deployment.

## 2026-10-28 — Separate YOLO training and validation frames (Codex, released)

The detector job previously copied every fifth training image and label into YOLO validation while leaving the originals in training. It now moves those pairs, so the exact same frame cannot appear in both folders. The independent held-out match remains outside YOLO's model selection and is still used only for the final adoption comparison. Updated the robot-job test to require disjoint training and validation image names and matching counts. This is a frame-level separation, so near-adjacent frames from the same match may still share visual content.

Released Mac 3.2.76, Windows 6.5.47, Linux 6.6.38, engine 2.7.61. The Mac signature and DMG verified; Windows/Linux update archives contain the new code. 549 bundled-Python engine tests pass. Git commit `a435765`; release-deployer path fix `bcf6f72`. AWS SSM command `4e7cf4a5-7223-40c4-aeb8-82f174649861` succeeded: 12 files hash-checked, 17 files/feed entries changed, rollback `/root/validation-split-release-backup-20261028b`, pruning completed. The first SSM attempt stopped before changing files because its preflight mapped engine files to the wrong directory; that checker is fixed in `bcf6f72`. Public Mac, Windows and Linux update feeds show the new versions. The Windows 5060 helper reported 6.5.47 after a remote update request.

Queued detector run `6058ab3c45bef719a080368f` specifically on the 5060; it entered step 1 (download robot labels). At queue time the Robots page reported 435 complete frames across 24 matches, up from 249/19 in the earlier 0.82 run. This run is a useful next result but cannot isolate the effect of the split fix from the newly added data. Held-out F1 pending.

## 2026-10-28 — No-flash release: Mac 3.2.75, Windows 6.5.46, Linux 6.6.37, engine 2.7.60 (Claude)

The owner approved the release of in-place refreshes (entry below). The Windows and Linux packages import the helper modules from their own files. The installed 6.5.45 / 6.6.36 updaters accept these updates.

Deployed through AWS SSM: 58 files hash-checked, 63 changed (engine and downloads only). Backup: `/root/no-flash-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.75 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.46 and 6.6.37 on engine 2.7.60, and both update zips match their local SHA-256. apt lists 6.6.37.

## 2026-10-28 — Windows/Linux: refreshes update in place instead of rebuilding (Claude, local, not released)

The owner saw Windows redraw every 10 s and Linux more often, while the Mac stayed smooth. Every dashboard refresh (10 s) and every live-reading update rebuilt all cards. Even swapped in at once, Windows paints each new card as it is created, and Linux got extra rebuilds from the `busy` messages.

- `render()` now rebuilds only when `(page, ui.structure_key(dash, models, busy))` changes. The key covers computers, queue and models, without readings, counters, logs or job messages.
- Otherwise `ui.refresh_live(dash)` runs the updaters the page registered in `ui.LIVE`:
  - Computers: four meters and the job line per computer.
  - Overview console (now `console_values` + `console`): helper, step, readings, stage and overall bars (`Meter`), next steps and log lines, found again by request, job id or label.

Checked:
- A script check confirmed: readings-only refreshes keep the same widgets and change the numbers; going offline changes the key; console progress and log update in place.
- The real window ran through two refresh cycles without errors, and the engine suite passes.
- Not seen on Windows or Linux hardware.

## 2026-10-28 — Startup fix release: Mac 3.2.74, Windows 6.5.45, Linux 6.6.36, engine 2.7.59 (Claude)

The owner approved the release: the missing-module fix and the remove ✕ (entry below), plus the server `remove_computer` action. Before publishing, the Windows full package and the Linux .deb were unpacked, and `neptune_trainer`, `_pairing`, `_entry`, `neptune_ui`, `neptune_telemetry`, `neptune_facts` and `neptune_layouts` were imported from only their files, with an isolated Python. Both passed. Helpers on 6.5.42–6.5.44 / 6.6.33–6.6.35 can't start, so they need a manual install of this version.

Deployed through AWS SSM: 59 files hash-checked, 64 changed, including `api/robot-detector.php`, whose live copy matched e540c0c. Backup: `/root/startup-fix-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.74 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.45 and 6.6.36 on engine 2.7.59; both update zips and Setup.exe match their local SHA-256. apt lists 6.6.36.

## 2026-10-28 — Windows/Linux helpers failed to start (missing neptune_layouts); remove offline computers (Claude, local, not released)

The owner found Connect/Reconnect closing the Linux and Windows helpers, with `ModuleNotFoundError: No module named 'neptune_layouts'`.

- **Cause:** learned layouts (d4dee8d, released as 3.2.71 / 6.5.42 / 6.6.33) added `engine/neptune_layouts.py`, imported through `neptune_facts`, but not to `neptune_engine.FILES`. The Windows/Linux builders ship only FILES, so 6.5.42–6.5.44 and 6.6.33–6.6.35 can't start, while the Mac (which copies every engine `.py`) was fine.
- **Also:** `neptune_helper`, `neptune_learning`, `neptune_setup` and `neptune_shared_models` shipped only as stale copies from the original base packages, so later repo changes to them never reached Windows/Linux.
- **Fix:** all five are added to FILES. The new `engine/test_package_files.py` fails if any engine module reachable from `neptune_trainer`, `neptune_ui` or `neptune_telemetry` isn't in FILES or a builder's launcher list. It was checked against the old list, where it fails.
- **Remove offline computers:** new helper API action `remove_computer`, with the website's rules: owner's own computer, not connected, holding no run, not the calling helper. The Tk and Mac Computers pages show ✕ on offline entries, with a confirmation.

Checked: the engine suite (incl. the new test); helper server tests; the Tk Computers preview (✕ only on the offline entry); the Mac app compiles.

## 2026-10-28 — Reconnect release: Mac 3.2.73, Windows 6.5.44, Linux 6.6.35, engine 2.7.58 (Claude)

The owner approved the release: the reconnect fixes (entry below) plus the server pairing change. It is built on 9636a78 (the robot session's captions-off, already deployed). The installed 6.5.43 / 6.6.34 updaters accept these updates.

Deployed through AWS SSM: 59 files hash-checked, 64 changed, including `community-training-pairing.php`, whose live copy matched 9636a78. Backup: `/root/reconnect-release-backup-20261028`.
- The server's prune command now prints a JSON summary, so someone replaced `/usr/local/sbin/neptune-prune-releases` since it was installed. It removed 3 old releases.
- The deploy script, previously kept only in a scratch folder, is now `trainer-app/scripts/deploy-release-server.py`.

Checked from outside:
- The appcast offers 3.2.73 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.44 and 6.6.35 on engine 2.7.58, and both update zips match their local SHA-256. apt lists 6.6.35.
- `connect_exchange` answers 422 to a malformed request.

## 2026-10-28 — Reconnect keeps the computer; Windows/Linux Reconnect opens at once (Claude, local, not released)

The owner found every helper signed out at once, the Windows Reconnect not working, and each reconnect adding a new computer named "Neptune Training Helper".

- **Why they all signed out:** `CommunityTrainers::authenticate` refuses a helper whose `credential_revision` (a hash of the owner's password hash) no longer matches, or after its 30-day expiry. All at once points to the owner's password record changing. Not confirmed: the production read was refused.
- **Pairing** (`CommunityTrainingPairing::exchange`):
  - A helper may send its previous `computer_id`. If that computer belongs to the approving user, it gets a fresh token, revision and 30 days, and keeps its record, name and settings. Another user's computer is never taken over.
  - New computers use the helper-sent `name` (its host name) instead of "Neptune Training Helper".
- **Helpers:**
  - Tk (`neptune_trainer_entry`/`_pairing`) sends the saved `computer_id` and `platform.node()`.
  - Mac sends the Keychain connection's `computer_id` and the Mac's name. The Mac pairing module `native_connect.py` is now in the repo, because builds used to carry it over from the previous app, and `release-mac-helper.sh` copies it.
- **Windows/Linux Reconnect:** it waited for the worker loop to end before opening approval, and a loop retrying a refused connection may not end. Now, when no job runs, it starts the approval window at once and closes. The single-instance lock lets the new window take over.

Checked: the engine suite; `training-pairing.php` (18 checks: reuse, name kept, fresh token, other users' computers safe, host-name naming); other helper server tests; `test_installable_trainer`; the Mac app compiles. Not run against a real reconnect.

## 2026-10-28 — Logo release: Mac 3.2.72, Windows 6.5.43, Linux 6.6.34, engine 2.7.57 (Claude)

The owner approved releasing the sidebar logo. It is built on the OCR session's learned-layouts release (7f50566: 3.2.71 / 6.5.42 / 6.6.33, engine 2.7.56). That release was found already live, deployed by hand. Neither release changes server code. The installed 6.5.42 / 6.6.33 updaters accept these updates.

Deployed through AWS SSM: 58 files hash-checked, 63 changed (engine and downloads only). Backup: `/root/logo-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.72 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.43 and 6.6.34 on engine 2.7.57, and both update zips match their local SHA-256. apt lists 6.6.34.

## 2026-10-28 — Hippocampus logo in the sidebar (Claude, local, not released)

The owner's wide "Hippocampus / Neptune Training Helper" logo replaces the Neptune wordmark and the two text lines at the top of the sidebar, on both Tk and Mac.
- File: `engine/hippocampus-logo.png`, trimmed and 600 px wide, 166 KB, listed in `neptune_engine.FILES`.
- Tk scales it to the 186-px sidebar with Pillow, and falls back to text if the image can't load. The Mac shows it 63 pt tall.

Checked: the engine suite; the real Tk window and the Mac preview match the owner's mockup.

## 2026-10-28 — Learned scoreboard layouts; Mac 3.2.71, Windows 6.5.42, Linux 6.6.33, engine 2.7.56 (Claude)

Owner request: learn each new scoreboard instead of hand-adding profiles. When no profile matches, the generic reader (round 2) settles sides by its roster/RED-BLUE vote. New `engine/neptune_layouts.py` remembers such an overlay in `~/.neptune-helper/learned-layouts/<season>.json` (outside the game pack, so the game fingerprint and trained models are unchanged): a 24x4 colour thumbnail of the band averaged over 8 clock frames, the median clock box, the sides and camera_top.

- **Learning:** only when the sides came from the video's own passing vote, teleop was anchored and the overlay roster check is `match` station by station. Official results are not used.
- **Use:** `settle_generic` — a passing vote always wins (a disagreeing learned entry is noted in `facts.layout.learned_layout`). Only when the vote fails does a **confirmed** entry (2+ different matches, no conflicts) with the same look (thumbnail distance ≤ 18) and clock position (±0.04) decide sides; the 20-clock gate still applies and more frames voting against it still refuses. A later disagreeing vote marks the entry as conflicted and it stops deciding.
- **Replay** (`tools/ocr-benchmark/learned_layouts.py`, 14 saved matches with rosters, Q7 excluded): learning formed 4 entries (txcmp1+txsan, ctwat, two week0 framings); every learn vote matched the reference. With team numbers and RED/BLUE words removed (a broadcast that never shows them), sides with no store: 0 of 14; with the learned store **13 right, 0 wrong, 1 unread** (week0 qm3's own provisional entry). Thumbnail distance between opposite-side overlays ≥ 50.9, between same-side matches ≤ 31.3; threshold 18 errs toward a new provisional entry.
- These saved matches all match built-in profiles, so in normal runs learning only happens on broadcasts that fail today. PIPELINE_VERSION unchanged.

## 2026-10-28 — Single-window and menu-name release: Mac 3.2.70, Windows 6.5.41, Linux 6.6.32, engine 2.7.55 (Claude)

The owner approved the release. It ships one helper window per computer (Windows/Linux) and Hippocampus as the Mac app name. The installed 6.5.40 / 6.6.31 updaters accept these updates.

Deployed through AWS SSM: 58 files hash-checked, 63 changed (engine and downloads only). Backup: `/root/single-window-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.70 at the local zip's size; the bundle's CFBundleName is Hippocampus with the bundle id unchanged.
- Windows and Linux `latest.json` show 6.5.41 and 6.6.32 on engine 2.7.55, and both update zips match their local SHA-256. apt lists 6.6.32.

## 2026-10-28 — One helper window per computer; Hippocampus in the Mac menu bar (Claude, local, not released)

The owner could open several copies of the Linux helper, and the Mac menu bar still said Neptune Training Helper.

- **Windows/Linux:** `neptune_trainer.single_instance()` holds a lock on `~/.neptune-trainer/helper.lock` for the helper's lifetime (`fcntl`, or `msvcrt` on Windows).
  - A second copy waits up to 5 s, which covers reconnect and update hand-offs, then says Hippocampus is already open and quits.
  - Checked with two processes: refused while held, taken once released.
- **Mac:** `CFBundleName` / `CFBundleDisplayName` are now "Hippocampus", set by `release-mac-helper.sh` on each build and in `build-native-mac.py`. That covers the menu bar, Quit Hippocampus and Sparkle's windows.
  - Unchanged: the bundle id (updates), the Keychain service (saved connection), the `.app` file name (Sparkle replaces it in place) and the log and support folders.
- **Icons:** the 3.2.69 bundle already carries the new icon; the Dock and Finder show a cached one until refreshed.

## 2026-10-28 — Hippocampus release: Mac 3.2.69, Windows 6.5.40, Linux 6.6.31, engine 2.7.54 (Claude)

The owner approved shipping the Hippocampus name and app icon (entry below).
- Windows update 1.06 MB, carrying the new `Neptune.ico`; Linux update 0.85 MB.
- The installed 6.5.39 / 6.6.30 updaters accept them.

Deployed through AWS SSM: 58 files hash-checked, 63 changed (engine and downloads; no server code changed). Backup: `/root/hippocampus-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.69 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.40 and 6.6.31 on engine 2.7.54, and both update zips match their local SHA-256. apt lists 6.6.31.
- The Mac bundle's `Neptune.icns` matches the repo's.

## 2026-10-28 — Hippocampus branding (Claude, local, not released)

The owner named the helper Hippocampus, as display text only:
- Under the Neptune logo in the sidebar it reads "HIPPOCAMPUS / Model Training Helper", on both Tk and Mac.
- The window title is "Hippocampus - Neptune Training Helper": Tk main window, the Linux setup window, and the Mac `window.title` (hidden by the Mac's full-size content, but shown in the Window menu and Mission Control).
- Package names, bundle ids, download names and feeds are unchanged.

App icon: the owner's Hippocampus artwork, with the 1024-px master in `trainer-app/icons/hippocampus-1024.png`.
- Mac: `Resources/Neptune.icns`, 16–1024 px. `release-mac-helper.sh` now copies it into each build, since builds copy the previous app and would otherwise keep the old icon.
- Windows: `trainer-app/windows/Neptune.ico`, seven sizes from 16 to 256 px, for the installer, shortcuts and window.
- Linux: `trainer-app/linux/Neptune.png`, 256 px, for the hicolor icon and now also the Tk window via `iconphoto`. Before this, only Windows set a window icon.

## 2026-10-28 — Cancel, carets and switches release: Mac 3.2.68, Windows 6.5.39, Linux 6.6.30, engine 2.7.53 (Claude)

The owner approved the release. It ships cancel and stop from the helper, collapsible sections, themed switches, and the server's `cancel_run` action and run ids.
- Windows update 0.94 MB, Linux update 0.80 MB.
- The installed 6.5.38 / 6.6.29 updaters accept them.

Deploy:
- The first attempt stopped before changing anything. The live-file check found the server's `community-training-control.php` is an Oct 20 copy that predates the repo's version (the repo file was never deployed), so replacing it would have shipped unrelated changes.
- The helper cancel moved to a new `community-training-cancel.php` (`community_training_cancel()`). That class and the website's cancel on `train.php` are back to their deployed versions.
- Redeployed (09d8084): 60 files hash-checked, 65 changed. Backup: `/root/cancel-collapse-release-backup-20261028b`; the failed attempt's backup is empty.

Checked from outside:
- The appcast offers 3.2.68 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.39 and 6.6.30 on engine 2.7.53, and both update zips match their local SHA-256. apt lists 6.6.30.
- `cancel_run` answers 401 without a token.

Not yet tried with a real run.

Follow-up: the repo's `community-training-control.php` differs from what the server runs. Reconcile it before anything else depends on the newer version.

## 2026-10-28 — Themed switches instead of checkboxes (Claude, local, not released)

The owner disliked the old web-style checkboxes. "Update automatically" is now a switch in the app's colours, accent when on and slate when off: `ui.Switch` (antialiased with Pillow) on Windows/Linux, `ThemedSwitch` on the Mac. It was the only checkbox in either app. The native NSSwitch was tried first and dropped, because it looks blue even when off against the dark cards.

Checked: the engine suite; the Tk and Mac Computers previews show both states.

## 2026-10-28 — Cancel runs from the helper; collapsible sections (Claude, local, not released)

The owner asked to cancel runs directly in the helper, and for every section to collapse with a caret. They briefly asked for other computers on the Overview, then withdrew it (the Computers page covers it); it was removed before commit.

Server:
- The dashboard queue now carries each run's id: `request` for detector runs, `job` for Actions runs.
- New helper action `cancel_run`:
  - `request` cancels a detector run (`RobotDetectorJobs::cancel`);
  - `job` + `mode=stop` stops an Actions run after its current match (`CommunityTrainingControl::stop`, owner-checked);
  - `job` + `mode=cancel` cancels it now.
- The website's cancel SQL moved into `CommunityTrainingControl::cancel($id, $owner)`, with no owner limit when called from the website and limited to the starting user when called from a helper. Leases are released either way.

Helpers (Tk and Mac), each with a confirmation:
- Cancel buttons appear on the running-job console and on waiting queue rows: Cancel for detector runs; Stop after this match and Cancel now for Actions runs.
- Waiting or running rows under Recent runs get Cancel too.
- Every titled section has a ▾/▸ caret: the console, queue, Recent runs, each computer, Improve this model, and this computer's own card. The choice is remembered (Tk `~/.neptune-trainer/ui-state.json`, Mac UserDefaults).

Checked:
- 545 engine tests OK; `page-control.php` covers the new cancel (owner only, waiting runs, lease released) and the other helper server tests pass.
- Tk and Mac previews show the carets, a collapsed card and the Cancel buttons; the real Tk window opened without errors.
- Cancelling has not been run against the live server.

## 2026-10-28 — One-artwork release: Mac 3.2.67, Windows 6.5.38, Linux 6.6.29, engine 2.7.52 (Claude)

The owner approved the release.
- The Windows and Mac builds start from the previous package, so files that are no longer shipped were carried over: the three retired `neptune-art-*.jpg`. Both builders now drop them: `RETIRED` in `build-windows-training-helper.py`, and an `rm` in `release-mac-helper.sh`.
- Helpers that update in place keep any old copies; they are unused, about 1 MB.
- Windows update 0.94 MB, Linux update 0.80 MB. The installed 6.5.37 / 6.6.28 updaters accept them.

Deployed through AWS SSM: 58 files hash-checked, 63 changed (engine and downloads; no server code changed). Backup: `/root/one-artwork-release-backup-20261028`.

Checked from outside:
- The appcast offers 3.2.67 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.38 and 6.6.29 on engine 2.7.52, and both update zips match their local SHA-256. apt lists 6.6.29.

## 2026-10-28 — One background artwork for every page (Claude, local, not released)

The owner chose a single image, the sea-horse in deep water, for every page in every app. It is `engine/neptune-art.jpg` (300 KB) and replaces the three per-page `neptune-art-*.jpg` files, which are removed from the repo and from `neptune_engine.FILES`. Tk (`Shell.select`) and Mac (`ArtView`, set once in `buildMain`) both load it.

Checked: the engine suite on the bundled Python; the real Tk window and the Mac preview both show it.

## 2026-10-28 — Helper redesign release: Mac 3.2.66, Windows 6.5.37, Linux 6.6.28, engine 2.7.51 (Claude)

The owner approved releasing the redesign (entry below) as 3.2.65 / 6.5.36 / 6.6.27. Those numbers had just gone to the tracking session's constant-identity v4 release (GitHub only, not deployed), so this one is 3.2.66 / 6.5.37 / 6.6.28, built on top of 36e5984. It ships both changes, and that session was asked not to deploy its own.

Builds:
- Windows: update 1.67 MB, Setup.exe 11.3 MB.
- Linux: update 1.54 MB, .deb 11.5 MB, apt repo signed and packed from inside `apt/`.
- The updaters already installed on 6.5.35 and 6.6.26 accept these updates (checked with their own code from f97324f). This is the first release those computers can get from Neptune's Update button.

Deployed through AWS SSM over the tracking session's deploy of 36e5984, which the owner had already run: 61 files hash-checked, 66 changed. Backup: `/root/helper-redesign-2-release-backup-20261028`. The prune removed Mac 3.2.64, Windows 6.5.35 and the OCR-release backup.

Checked from outside:
- The appcast offers 3.2.66 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.37 and 6.6.28 on engine 2.7.51, and both update zips match their local SHA-256.
- apt lists 6.6.28, and the API answers 401 without a token.

Not yet seen on a real helper.

## 2026-10-28 — Helper redesign pass: no flashing, modern buttons, icons, artwork, console-first Overview (Claude, local, not released)

The owner's notes:
- Linux helper blinks.
- Scrollbar always shows.
- Buttons look dated.
- No icons like the Mac.

Also asked for:
- the artwork behind the main content only, with a solid sidebar and near-opaque cards;
- Running now as the centerpiece with epoch, loss, GPU memory, elapsed, ETA and log;
- model cards only while that model trains;
- a compact Ready-to-train idle state;
- an icon for each computer's kind.

Tk (Windows/Linux, `neptune_ui.py`, `neptune_trainer.py`):
- Blinking: every refresh destroyed and rebuilt every card. New cards are now built hidden and swapped in at once (`BubblePage.show_only` → `finish`); a refresh of the same page keeps its scroll position.
- The scrollbar is a thin arrowless bar that only shows when cards overflow.
- `ui.Button` is a rounded flat button (antialiased with Pillow) with icons, replacing the ttk buttons.
- Meters are thin rounded bars (`ui.Meter`), and the dropdown is flat.
- Icons come from Lucide (ISC, `neptune-icons-LICENSE.txt`), pre-rendered into `neptune-icons.png`, on the sidebar, tools and buttons.
- The sidebar is solid navy. Page artwork (`neptune-art-*.jpg`, the owner's images) is cover-scaled and dimmed behind the cards.

Both apps:
- Overview: console first, a model tile only while that model trains, and the queue only when it has runs.
- When idle: "Nothing running. Start a run" with Robot detector / Field detector / Actions on Neptune buttons, and the computer card says "Ready to train".
- The console shows `epoch n/N · batch · loss · it/s`: `telemetry.batch_counter` now records the running loss.
- Computers pages and the this-computer card show a laptop/desktop/server icon. `telemetry.form_factor()` works this out from a battery, or the Linux chassis type. Helpers report `form`; the server stores it and the dashboard returns it.
- Mac (`App.swift`): `ArtView` artwork behind the main area, opaque sidebar, cards at 0.95 alpha, SF Symbols for computer kinds.

New engine files (flat names, so existing updaters accept them): `neptune-icons.png`, `neptune-icons-LICENSE.txt`, and three `neptune-art-*.jpg`, about 1 MB in all.

Checked:
- 543 engine tests OK on the bundled Python 3.13. Server tests helper-updates 10, my-computers 15 and helper-models 6 PASS. Updater tests 8 OK.
- Tk pages previewed with sample data (running and idle Overview, Computers). The real `neptune_trainer.main()` opened from a temp copy with a dummy connection and rendered without errors.
- Mac preview: Overview and Computers.
- Not run on Linux or Windows hardware, so the end of the blinking is unconfirmed there.

## 2026-10-28 — Remote updates release: Mac 3.2.64, Windows 6.5.35, Linux 6.6.26, engine 2.7.49 (Claude)

The owner approved the release. Builds:
- Mac: 542 engine tests OK on the bundled Python, Sparkle signature verified, DMG verified.
- Windows: update 605 KB, Setup.exe 10.2 MB.
- Linux: .deb 10.4 MB with the new launcher and updater, apt repo signed. The Linux update zip is 469 KB and verified by the updater itself, with 74 files and no .pt.
- The deploy adds `downloads/linux/latest.json`, the Linux update zip, and a linux `.htaccess` that allows only that zip.

Deployed through AWS SSM: 63 files downloaded and hash-checked, 68 changed. Backup: `/root/remote-updates-release-backup-20261028b`.
- The first attempt stopped before publishing anything and rolled back: apt-repo.tar.gz had been packed one folder too deep (`apt/dists`). It was repacked at the root, replaced on the GitHub release, and redeployed.
- The prune then removed 3.2.62 and 6.5.33 and the two OCR-release backups. It kept `…20261028b` and the unused backup from the failed attempt.

Checked from outside:
- The appcast offers 3.2.64 at the local zip's size.
- Windows and Linux `latest.json` show 6.5.35 and 6.6.26 on engine 2.7.49. Both update zips download with matching SHA-256.
- apt Packages lists 6.6.26 and InRelease serves.
- pillar.js v23 is live and the helper API answers 401 without a token.

Not yet seen on a real helper.

## 2026-10-28 — Remote helper updates from Neptune (Claude)

The owner asked for helper updates to install by themselves and reopen, and to be started remotely from Neptune, on Mac, Windows and Linux.

Server:
- Each computer's settings (`RobotDetectorJobs::settings`) now hold `update_requested` (a time) and `auto_update`.
- The website (`computer_settings`) and the helpers (new `update_computer` action, for one computer or `all`) set them; only the owner's own computers can be changed.
- `poll()` returns them with the newest published version. `helper_latest_version()` reads it from the Mac appcast or the Windows/Linux `latest.json`.
- A request clears once the helper reports that version, and lapses after a day.
- Check-ins also store `remote_update` (this helper can act on requests) and `update` (its last update message).
- `autoscout_computers` adds `update` (latest, behind, remote, requested, auto, message) for the Computers pages.

Windows and Linux (`neptune_trainer.main`):
- An open request, or auto-update (hourly), runs the existing check → verified download → install-after-the-match path. A requested download can start during a job.
- `neptune_update_apply.py` now reopens the helper after installing, or after rolling back.
- `neptune_windows_update.py` serves both platforms, each with its own feed (`downloads/linux/latest.json`).
- The Linux .deb launcher (`bootstrap.py`) now replaces the per-user copy only with a newer packaged version, and sets `NEPTUNE_LINUX_UPDATES` so the helper knows it may update itself.
- `build-linux-deb.py` writes a Linux update zip and feed in the Windows format, without `.pt` files or the connection.

Mac:
- `native_worker.py` forwards each check-in reply.
- `App.swift` turns on Sparkle's silent downloads when a request is open or auto-update is on, checks in the background, and in `willInstallUpdateOnQuit` installs and relaunches now, or after the match.
- The app reports its own version (`NEPTUNE_HELPER_VERSION`) instead of the engine's.

Computers pages:
- Mac, Tk and the website (pillar.js v23) show each computer's version against the newest release.
- Each card has Update / Cancel update and an "Update automatically" checkbox, plus Update all.
- Helpers that can't act on requests yet say they need one update by hand.
- `prune-release-server.sh` also prunes Linux update zips.

First release needs, per platform:
- Mac 3.2.64 and Windows 6.5.35 must be installed once through today's update button. That one install does not reopen by itself, because the old installer runs it.
- Linux needs 6.6.26 through apt once, for the new launcher.
- The deploy must publish `linux/latest.json` and its update zip, and allow them in the linux folder's `.htaccess`.

Checked:
- Server tests: `tests/server/helper-updates.php` (10 PASS), `my-computers.php` and `helper-models.php` updated and passing. catalog, maintenance-package, robot-label-frames, temporal-model and training-progress-mysql fail the same way without this change.
- `test_windows_update.py`: 8 OK. New tests cover the Linux feed and launcher, and a Linux update zip built, verified, installed and reopened.
- Engine suite: 542 OK on the bundled Python 3.13. Mac app compiles.
- Mac and Tk Computers pages previewed with sample data covering every state.
- Not done: no real install on Windows, Linux or Mac hardware, and the website card was not viewed in a browser.

## 2026-10-27 — OCR round 2 release: Mac 3.2.63, Windows 6.5.34, Linux 6.6.25, engine 2.7.48 (Claude)

Ships OCR round 2 (entry below): saved game packs gain new layouts, generic scoreboard fallback, settled tracks skip the colour retry, score-box re-read.

## 2026-10-27 — Constant identity v3: look fallback in the wide view; QM6 review checked; Mac 3.2.62, Windows 6.5.33, Linux 6.6.24, engine 2.7.47 (Claude)

Owner request: use what each robot looks like when its number cannot be read. `neptune_constant_identity` (v3) adds a last pass: an unnamed wide-view tracklet takes the team whose already-named tracklets in the same match and camera have the clearly closest look profile (the tracker's 24-value colour profile; all three alliance teams must be in the gallery; best within 2x the link limit; margin .1; never in close-ups; the gallery is fixed first so one guess never seeds another; reads and same-time conflicts still veto). Margin chosen on the hidden-OCR check (half of OCR seeds hidden, labels checked against them): .06 named 9 of 36 QM4 boxes wrong, .08 was the first clean margin, .1 keeps a step in hand. At .1: hidden-OCR look labels QM4 9/9, QM1 35/35 right; reviewed boxes unchanged (QM1 175 correct, QM4 46, both 0 wrong), QM4 lost time 94.2 -> 93.7 s per robot. Small gain, kept because nothing it adds has been wrong.

QM6 (first 0-10.7 s plus one long close-up track, 441 corrected / 235 not-robot, retracked with the current engine): 105 correct, 95 "wrong", 0 switches, lost 78.8 s per robot. All 95 are one close-up-right track (track 11, 8.2-24.5 s) the review saved as 324; the frame at 8.3 s clearly shows 8088 on its bumper, which is what the tracker said. Owner asked to correct it. Deployed via SSM 36d71146 (owner ran it): 60 files verified, 64 changed, backup /root/look-fallback-release-backup-20261027, pruned (disk 36%); public feeds show Windows 6.5.33, Mac 3.2.62, apt 6.6.24.
## 2026-10-27 — OCR round 2: saved packs gain new layouts, generic scoreboard fallback, held-out bumper test, faster tracking, score re-read (Claude, not released)

- **Saved game packs:** the Mac helper never refreshes `~/.neptune-helper/games/<season>.json` (only the old GUI called `neptune_shared_models.refresh`), so a copy from 2026-10-18 lacked the AGE and Week 0 layouts the server now serves. `neptune_games.profiles` fills layouts a saved pack lacks from the built-in rules when both are the same game (`game_key`); the saved pack wins on conflicts. A different game key is untouched.
- **Generic scoreboard fallback:** when no layout profile matches, `analyze_video` reads the clock and scores by position (`parse_overlay_generic`) with sides settled once for the video (`generic_layout`: 20+ clock frames, 90%+ of side-showing frames agreeing; sides from the roster or RED/BLUE words). Identity checks unchanged. On 16 saved matches (txcmp1, capoh, ctwat, txsan, week0) it never disagreed with the matching profile on clock or score and always got the sides; it reads many scores the profile skips. PIPELINE_VERSION unchanged (only videos that failed before are affected).
- **Held-out bumpers:** `tools/ocr-benchmark/truth-heldout.json`, 156 boxes on 2026capoh_qm9 (another event, never tuned on). Readable bumpers right: Apple Vision 22 → **84 of 99, 0 wrong**; RapidOCR 76 (2 wrong) → **98 of 99, 0 wrong**. Mostly team 5025.
- **Identities on reviewed matches** (Q4, Q6 held out; old = before the OCR change, mid = OCR change, new = + speed fix): Q4 38 right / 0 wrong for all three. Q6 old 58 right / 0 wrong; mid and new 101 right / 95 "wrong". All 95 are one close-up track the human review labels 324 whose bumper reads 8088 on the frames (checked at 8.2 s and 24.5 s; the review itself labels the same robot 8088 at 0 s): **the Q6 review is mislabelled there**, the OCR is right. Q6 review `174236e2…` closeup-right track 11 needs correcting by the owner; other identity measurements use it.
- **Speed:** a track with 3 agreeing exact reads skips the coloured OCR retry (white pass still runs). Same identities; Q4 2656 s → 2365 s, Q6 2787 s → 2378 s (two matches tracked in parallel on this Mac). CONTINUITY_REVISION v9.
- **Score re-read:** frames with a clock and both labels but a missing score re-read the enlarged score box (3x; a lone O is zero). Apple Vision scores 168/0/8 → **172/0/4** (right/wrong/unread); RapidOCR 176/176. A wider crop read clock digits (20 for 0) and was rejected.
- **Not fixed:** RapidOCR's one false read on a no-number box is a lit driver-station sign over a false detection; a saturation filter dropped a real read and kept it, so it was removed.

Checked: engine suite on the bundled Python, all OK (541 tests). Benchmarks and tracking outputs in `local/ocr-benchmark/` (not in git).

## 2026-10-27 — Tracking review keyboard shortcuts; Mac 3.2.61, Windows 6.5.32, Linux 6.6.23, engine 2.7.46 (Claude)

Owner request. On the review page: 1–3 pick the selected box's alliance teams, Enter saves, Delete/Backspace hides the selected box as "not a robot" only when it is Unknown (named boxes need the menu, so a slip cannot erase a real robot), Z undoes the last save. Keys are ignored while typing in a field. Script syntax checked with node; review tests OK. Deployed via SSM d6de4f06 (owner ran it): 60 files verified, 64 changed, backup /root/review-keys-release-backup-20261027, pruned (disk 35%); public feeds show Windows 6.5.32, Mac 3.2.61, apt 6.6.23.

## 2026-10-27 — Tracking review: a box can be named with the other alliance's team; Mac 3.2.60, Windows 6.5.31, Linux 6.6.22, engine 2.7.45 (Claude)

Owner hit a 6800 bumper inside a box the detector called red; the review list offered only red's three teams, so the only choices were Unknown or a wrong label. The Robot number list now also offers the other alliance's teams ("6800 (blue: the colour is wrong)"). `apply_corrections` accepts any team on the match roster and moves the corrected interval's boxes to that team's alliance (`alliance_corrected`); the rest of the track and the saved original review are unchanged. Teams not in the match are still refused. Engine 2.7.45. Deployed via SSM 9bdf0167 (owner ran it): 60 files verified, 64 changed, backup /root/cross-alliance-release-backup-20261027, pruned (disk 36%); public feeds show Windows 6.5.31, Mac 3.2.60, apt 6.6.22. Checked: engine suite OK on the bundled Python (new `test_other_alliance_team_fixes_the_box_colour`).

## 2026-10-27 — Robot check uses tracking's duplicate-box cleanup; Mac 3.2.59, Windows 6.5.30, Linux 6.6.21, engine 2.7.44 (Claude)

Run 57512e23 (1,010 training frames) kept the current detector: QM4 F1 0.830 vs 0.814 (+0.016 < 0.02). Wide improved on both counts (F1 0.799→0.853, false positives 87→71); close-ups lost precision (false positives 22→61). Misses are mostly large (57) not small (10); alliance mix-ups 4. The owner's review-video screenshots show many yellow "extra" boxes nested on a bumper already found, plus a few QM4 answer boxes that cover the robot top as well as the bumper.

Cause: tracking already removes nested same-colour boxes (`neptune_yolo.unique_bumpers`, overlap 0.85), but `neptune_robot_jobs.detect()` (QM4 check, review video, labelling guesses) did not, so the check counted duplicates tracking never sees. `detect()` now applies `unique_bumpers` unchanged: no new threshold, nothing tuned on QM4. Gates unchanged.

Measured, current detector only, on the local Oct 26 QM4 audit copy (75 frames, 601 boxes; legacy labels and re-extracted images, so absolute numbers are lower than the server's 554-box check): F1 0.672→0.728, false positives 229→126 (close-up 117→80, wide 112→46), recall 0.699→0.692. The new candidate's weights stayed on the Windows PC, so the two detectors were not compared here; the next run compares both with the cleanup. Deployed via SSM 34f9615e (owner ran it): 61 files verified, 65 changed, backup /root/nested-box-release-backup-20261027, pruned; public feeds show Windows 6.5.30, Mac 3.2.59, apt 6.6.21. Robot runs now need these helpers (engine 2.7.44 / Mac 3.2.59 / Windows 6.5.30 / Linux 6.6.21), so the candidate and the detector in use are always scored the same way. 520 engine tests OK.

## 2026-10-27 — Release: constant robot identity; Mac 3.2.58, Windows 6.5.29, Linux 6.6.20, engine 2.7.43 (Claude)

Ships constant-identity-v2 (PR #1). Built from this worktree with `bumper_wide.pt` and field `model.pt` copied from the main checkout and hash-checked. Deployed 2026-10-27 through AWS SSM command 00581769 (owner ran it): 60 files fetched and verified, 64 changed, backup /root/constant-identity-release-backup-20261027, then pruned (disk 36%). Public appcast 3.2.58 and apt 6.6.20 confirmed.

## 2026-10-27 — Look-based re-ID and 12 fps tracking tested (Claude)

Look-matching (handcrafted bumper shade and chassis features, our detector's backbone, DINOv2 ViT-S/14) cannot name same-alliance robots with zero wrong labels. DINOv2 is best, at 62% in the wide view and chance in the close-ups, so nothing was added to tracking. QM1 at 12 fps: 0 wrong, lost time 82.2 → 76.5 s per robot, and twice the detections; the default stays at 6 fps. The metric fix in 1f90dd5 covers QM1's earlier "wrong" labels. Tables are in `docs/persistent-identity.md`; scripts are in `local/appearance-reid-20261027/`. The owner approved the DINOv2 download (88 MB, PyTorch cache, not in git).

## 2026-10-26 — Constant identity v2: 1.5 s link gap after the QM1 review (Claude)

The owner reviewed QM1: 951 corrected boxes and 1,589 marked "not a robot". The 2 s motion and colour link carried 6672's read back onto 5261 across a 1.83 s gap. That was 11 wrong close-up boxes. `LINK_GAP` is now 1.5 s (`constant-identity-v2`). On QM1, correctly labeled boxes go from 151 to 175, and the layer adds no wrong ones. On QM4, 46 boxes are labeled with 0 wrong, and lost time per robot falls from 97.5 s to 94.2 s. The hidden-OCR check is 309 of 309 on three matches. Added a regression test. The engine suite passes on the bundled Python. The table is in `docs/persistent-identity.md`.

The 11 "wrong" QM1 labels left after this, from OCR and the roster solver, were metric errors. A reviewed robot with no label was matched to an overlapping labeled neighbour. `evaluate` now also matches against every tracker detection. QM1 then has 0 wrong and 0 switches, before and after the layer.

## 2026-10-26 — Constant identity: no links past an unnamed rival; crowded-frame solver rejected (Claude)

A stricter hidden-OCR check reruns the roster solver without the hidden reads. It found the first version 18 wrong of 381 carried labels on QM4: a close-up scrum carried 9492 onto 10340. Now any near-equal rival tracklet blocks a link, whether named, unnamed or in contact. The check then gives 153 of 153 correct. Reviewed QM4 is 46 of 224 correct (was 70, originally 21), still 0 wrong and 0 switches. The earlier "430 of 430" was the weaker check. Tried and reverted: letting the roster solver keep three boxes in crowded frames (5 wrong reviewed boxes).

Checked: 504 engine tests OK on the bundled Python. Not released or pushed.

## 2026-10-26 — Constant robot identity layer; close-up roster guesses need a read (Claude)

Measured first, on the two human-reviewed matches (QM4, QM3; Q7 never used). Identity was almost never wrong but mostly missing. QM4: 21 of 224 reviewed robot boxes labeled, 0 wrong, 0 switches, 99 of 164 s lost per robot. QM3: 60 boxes the reviewer marked "not a robot" (a still close-up box) carried a team via roster elimination, so they would have fed scoring.

New `engine/neptune_constant_identity.py` carries trusted OCR and roster labels along tracker tracklets. Tracklets end at gaps, jumps, cuts and contact. Linking across short gaps in one shot needs the motion gate, colour, number reads and no rival. A contact stretch is kept when the same track leaves with the same number. The third robot is named by elimination in the wide view. Its labels go to scoring attribution (`constant_identity`; events, scouting rules, field regions, homography), never to training. `with_roster_inferred` now needs a number read on the track before a close-up roster guess is used. New `engine/neptune_identity_metrics.py` does the measuring. Details and the table are in `docs/persistent-identity.md`.

Result: QM4 21 → 70 reviewed boxes correctly labeled (70 of the 97 that have a detection), 0 wrong, 0 switches. QM3 non-robot labels 60 → 0. Lost seconds per robot: QM4 99.2 → 94.4, QM3 113.2 → 112.7. The rest is detection and OCR coverage. Hidden-OCR check: 430 of 430 carried labels match hidden OCR.

Checked: 502 engine tests OK on the bundled Python (13 new). Not released, pushed or deployed; no fresh video run.
## 2026-10-27 — Robots page: black-and-white picture toggle (Claude)

Owner request: red boxes on red bumpers are hard to see. `autoscout/robot-labels.php` gets a "Black & white" button next to the clock (and the **G** key) that greys only the frame picture (video or source still); the boxes stay coloured because they are drawn on the canvas above it. The choice is remembered per browser (localStorage, wrapped in try/catch). Checked in a local copy of the frame stage on a QM1 still: grayscale on the picture only, toggles back with G. One-file server deploy, no helper release.

## 2026-10-27 — Helper Recent runs showed the oldest runs (Claude)

The owner saw Oct 23–24 runs under Recent runs on the helper's Robots and Field pages. `autoscout_helper_models()` reversed `RobotDetectorJobs::requests()`, which is already newest first, before taking eight, so it showed the eight oldest of the last 50. It now takes the first eight. The test fixture made the same oldest-first assumption, so it passed; it now lists runs newest first, as `requests()` does. The fix is server-side only, so no helper release is needed.

Checked: `tests/server/helper-models.php` 6 PASS.
## 2026-10-27 — Hard-frame picker: tracking reviews choose frames to box on the Robots page; Mac 3.2.57, Windows 6.5.28, Linux 6.6.19, engine 2.7.42 (Claude)

Audit first: saved tracking reviews cannot train the bumper detector. Their boxes are `crop_box`-widened chassis crops; "corrected" fixes the team number, not the box, so every box is one the detector already found; a missed robot leaves no trace, so only 1 QM1 wide frame (0 in QM3) is provably complete. Of the 1,589 QM1 "not a robot" boxes, 1,563 are in the close-up insets and 685 are one track.

So instead `engine/neptune_hard_frames.py` picks timestamps from a review: first/middle/last of each "not a robot" track, and the middle of any gap of 1 s or more in a reviewed robot's track within one camera view. Picks are a second apart, capped at 40, and refused for Q7 (reserved) and the held-out match. A prepare request may carry `times_ms` (at most 60). The helper adds them to the 4 s grid (`frame_times`), so the owner boxes every visible bumper there under the normal rules. The server holds such requests for helpers at engine 2.7.42 / Mac 3.2.57 / Windows 6.5.28 / Linux 6.6.19 or later, which must be the release that ships this. A queued prepare for the same video is still reused as before, so its picks are not added.

Released 2026-10-27: Mac 3.2.57, Windows 6.5.28, Linux 6.6.19, engine 2.7.42, all on GitHub. The first Windows/Linux/Mac builds from this worktree had no `bumper_wide.pt` or field `model.pt` (both git-ignored, only in the main checkout). They were caught before publishing; the weights were copied, their hashes checked against the manifests, and everything rebuilt. Build releases from a checkout that has the weights. Deployed through AWS SSM command 74eedfab (owner ran it) with the previous release's manifest-driven deploy script: 60 files fetched and verified, 64 changed, backup /root/hard-frames-release-backup-20261027, then pruned. The public Windows latest.json, Mac appcast and apt Packages show 6.5.28 / 3.2.57 / 6.6.19. Queuing QM1 (T1K71dqCJA4) and QM3 (ZlnweItn8ww) with their picks: `local/deploy-hard-frames/queue-ssm.json` (owner runs it).

Current picks: QM1 38 frames (37 false positive, 1 lost robot), QM3 4; QM4 refused. List: side-session notes `hard-frames-qm1-qm3.jsonl`. Checked: 519 engine tests and tests/server/my-computers.php OK on the bundled Python. Not released or queued.


## 2026-10-27 — Storage cleanup on AWS and this Mac; deploys now prune (Claude)

The owner reported the Mac using a lot of storage and AWS at 93%. The server disk was at 94%: 27 of 29 GB used, 2 GB free. Each release left a ~313 MB Mac zip in `community/downloads/mac` and a ~480 MB backup in `/root`.

AWS, as the owner asked:
- Removed Mac zips 3.2.33–3.2.54; 3.2.55 and 3.2.56 are kept. The appcast points only at 3.2.56, and every version is still on GitHub Releases.
- Trimmed the journal to 100 MB (freed 231 MB).
- Removed every `/root/*backup-2026*` folder except `fort-worth-layout-release-backup-20261026`. That pattern also matched about 60 older code-deploy backups from Sept 17–Oct 25 (autoscout-section, neptune-*, rc-*, windows-*), not just the 13 release backups listed to the owner. They were copies of replaced files, and the live site does not use them.
- Kept the SQL dump `/root/scouting_before_utc_20261016-124944.sql` and the backup folders without a date in their name.
- Result: 62% used, 11 GB free. Mac appcast, 3.2.56 zip, DMG and Windows latest.json all return 200.

Mac:
- Removed the pip, Sublime Text, Homebrew, Movavi and Raspberry Pi caches.
- Removed Windows 6.5.11–6.5.26 and Linux 6.6.4–6.6.17 build folders. Kept Windows 6.5.27 and 6.4.2, Linux 6.6.18, and the Linux 6.5 base.
- Free space went from 27 to 38 GB.

Deploys now prune: `trainer-app/scripts/prune-release-server.sh`, installed on the server as `/usr/local/sbin/neptune-prune-releases`, with the AGENTS.md rule 10 addition.
- Keeps the two newest Mac zips and Windows update zips, plus anything a feed points at, and the two newest dated `/root` backups.
- Vacuums the journal and never touches `.sql` dumps.
- The dry run listed only Windows update zips 6.3–6.5.25 to remove (2 MB each); the real run is not done yet, pending the owner's OK.

## 2026-10-26 — Fort Worth layout release: Mac 3.2.56, Windows 6.5.27, Linux 6.6.18, engine 2.7.41 (Claude)

Ships the full-height FIRST AGE overlay (`frc-2026-age-large-v1`, entry below) so match tests on FIT District Fort Worth videos can read the clock and roster. The game pack is unchanged, so trained action models stay valid. The owner approved the release.

Deployed through AWS SSM (62 files: engine, downloads, update feeds, apt; backup /root/fort-worth-layout-release-backup-20261026). Public Windows latest.json, Mac appcast, apt Packages show the new versions; downloaded update archives match local SHA-256.

Checked: Mac build ran 513 engine tests OK on its bundled Python, Sparkle signature verified, DMG verified; package sizes match 3.2.55/6.5.26/6.6.17.

Build note: the worktree had no `engine/robot-detector/bumper_wide.pt` or `engine/field-detector/model.pt` (kept out of git). The first Windows/Linux builds came out 0.5 MB against the usual 10 MB, so I discarded them, copied both files from the main checkout (hashes match the manifest and the installed 3.2.55), and rebuilt. Build releases from a worktree only after copying those files.

## 2026-10-26 — Fort Worth broadcast layout (engine-side, game pack unchanged) (Claude)

The owner's match test on FIT District Fort Worth qm10 (https://www.youtube.com/watch?v=JfrWE1N9Dmw) stopped with "Unsupported broadcast layout". The overlay is FIRST AGE with blue on the left, but drawn at full height: the clock and scores sit in the lower half of the band, where `frc-2026-age-blue-left-v1` doesn't look. OCR also reads its "AGE" logo as "AGLO".

- Added `frc-2026-age-large-v1` in `neptune_facts.EXTRA_LAYOUTS`. It is tried after the game pack's profiles. It isn't in the pack, so the game fingerprint and every model trained on it (including the Oct 26 one) stay valid. The marker is the REBUILT logo on the right.
- `team_token`: a roster number with one or two logo symbols read in front of it ("* 3676") now counts as that team. Nothing else is accepted.

Checked: the full facts pipeline on qm10 on this Mac gives layout `frc-2026-age-large-v1` on 252/252 overlay frames, auto 12.95–32.95 s and teleop 37–177 s, and match number, all six roster stations and event all `match`. Final displayed scores: blue 219, red 57. The results screen wasn't found (status unknown). New `test_age_large_layout.py` (4 tests); the engine suite is OK on the bundled Python. Not released: helpers need the new engine before the Train page match test can use it.

## 2026-10-26 — Action model measured; no new model (Claude)

Measured on this Mac's prepared cache (`prepared/97384b0b…`, R3D-18 512-d clips: 73k robot clips, 50 matches, 249 robot score targets; Q7 absent), with the training's own match-held-out checks. Gates unchanged.

| Action | Positives (matches) | Held-out AUC | Stand-in AUC | Recall at ≤35% flag rate | Result |
|---|---|---|---|---|---|
| gb:score_1_fuel | 1603 (3) | 0.678 | 0.625 | 0.49 | passes by 0.003 |
| gb:score_2_fuel | 402 (3) | 0.652 | 0.287 | 0.54 | passes |
| scoring | 304 (18) | 0.569 | — | — | no signal |
| climb, defense, feed, auto_* | 2–18 (1–2) | — | — | — | too few matches |

Robot points (leave one match out): mean absolute error (MAE) 48.3 points with video vs 61.1 when every robot gets the training mean. The newest local model (20261024T025723) has no action heads (score_1 fell to its stand-in, score_2 had AUC 0.47), and its robot-point MAE was 65.4 vs 74.8 on 12 robots. Precision can't be measured: none of these actions has confirmed negatives (only end_* do), and there is no complete six-robot benchmark, so `evaluate_benchmark` can't run.

Error sources:
- Data coverage. The fuel labels all come from three txcmp1 matches, and the other actions from one or two matches each.
- Label noise. ViperScout `scoring` positives rank below chance on unseen matches (AUC 0.448); hand labels reach 0.649. The hand labels cover only 2 matches, so a hand-only head can't be validated (needs 3). Weighting the imports at 0.25 or 0 moved hand-label AUC by at most 0.015.
- Duplicate rows per click. One click becomes up to 12 rows from neighbouring sightings and tracks.
- Robot and camera confound. The no-video stand-in nearly matches score_1_fuel.

Tried, not shipped, because none was a consistent win:

| Change | score_1 AUC / stand-in | score_2 AUC / stand-in | scoring AUC |
|---|---|---|---|
| none (current) | .678 / .625 | .652 / .287 | .569 |
| one weight per click | .679 / .632 (fails) | .614 | .551 |
| references matched to positives' camera | .668 / .732 (fails) | .723, recall .79 | .583 |
| references matched to positives' robot | .680 / .428 | .640 / .586 | .570 |
| shrunk variance in the linear head | .668 / .615 | .654 | .574 |

With three matches these are noise-level differences, and picking among them on the same folds would be tuning against the evaluation. Robot-point kernel width and ridge settings also changed MAE by less than 1 point (47.4–48.4).

Added `engine/evaluation/evaluate_actions.py` (reproduces these numbers from any prepared cache and refuses the reserved Q7) and `engine/test_evaluate_actions.py` (3 tests). No engine module, gate or label changed. Checked: 492 engine tests OK on the bundled Python 3.13.

Next: hand-label score_1, score_2, climb and defense in at least 3 more matches from other events. The robot-matched references look worth re-testing once there are about 8 matches.
## 2026-10-26 — Helper: larger logo, no bubbles, Running now as the website's console (Codex, finished by Claude): Mac 3.2.55, Windows 6.5.26, Linux 6.6.17, engine 2.7.40

Owner asked for a larger logo, no moving bubbles, and Running now showing what the website's console shows. Codex removed both platforms' bubble animation, enlarged the sidebar mark, and labelled this Mac "Tracking review"/"Image review" on Computers (live readings pause while a local review is open; Codex closed the review on the installed 3.2.54 and the Mac reconnected with readings). Claude replaced the logo with the wide NEPTUNE wordmark across the sidebar (Mac and Tk) and rebuilt Running now as a console on both platforms: part label and helper with GPU, step and match key, GPU/VRAM/°C/CPU/RAM line, stage bar (passes/batches, match counters, or the log's [i/n]), overall bar with elapsed and time left, next steps, last six log lines colour-coded. Fixed from Codex's draft: action jobs name their helper in `target`, not `computer_id`, so their readings were missing. Server: the dashboard queue now carries each job's `label` and `started` time.

Checked: Mac and Tk previews with an Actions job fixture matching the owner's example; 506 engine tests OK; server tests OK; no whitespace errors.

## 2026-10-26 — Helper redesign: sidebar pages, model pages with Train; Mac 3.2.54, Windows 6.5.25, Linux 6.6.16, engine 2.7.39 (Claude)

Owner asked for a modern, less redundant helper that shows and works on the models. Mac (`App.swift`) and Windows/Linux (`neptune_ui.Shell`, `neptune_trainer.main`) now share one layout: a sidebar (Overview, Robots, Field, Actions, Computers, Activity; Tools: Review tracking, Label image folder; connection/version/updates/Reconnect at the foot) beside a header and a page of cards over the bubbles. Overview: this computer's card with readings and device, this computer's job only while busy, Running now elsewhere with progress and last log line, three clickable model tiles, queue. Robot/Field pages: model in use with held-out score, holdout match, data counts, last eight runs (result, new vs in use, review video, message) and a Train button with a computer picker (confirms first). Actions page: release state, tagged matches/tags, guidance; training opens Neptune. Removed: duplicate logos and this-Mac cards, the button bar, the empty Running now card.

Server: `api/robot-detector.php` adds `models` (owner's Train overview trimmed by `autoscout_helper_models()`) and `queue_training` (robot/field run, optional target among the owner's own computers, holdout chosen as on the Train page). Ships with the OCR work (2.7.38) not yet deployed until now.

Checked: Mac and Tk previews of every page with fixture data (fixed an NSNull "Training" state and an over-wide picker); 506 engine tests OK; `tests/server/helper-models.php` 6 PASS, `my-computers.php` OK. Not exercised against live data before deploy; Tk previewed on macOS only.

## 2026-10-26 — OCR release: Mac 3.2.53, Windows 6.5.24, Linux 6.6.15, engine 2.7.38 (Claude)

Ships the roster-constrained bumper reads and the scoreboard side check (entry below) to every helper. Saved match facts re-parse and saved tracking reruns on first use.

## 2026-10-26 — Scouting uses marked zones only; Mac 3.2.52, Windows 6.5.23, Linux 6.6.14, engine 2.7.37 (Claude; ships with the robot validation fix below)

Owner decision: the field detector is deprioritized. Each event uses one fixed camera and one marked match already covers every match at that event, so the detector only mattered for unmarked events, where its guesses (both hubs, rarely corners on a new venue) could mislead scoring. `neptune_field_regions.load()` no longer falls back to detected regions by default, and match runs no longer call `detect_if_unmarked`; unmarked events run without scoring-zone hints. Train page guidance (pillar.js v22): mark one match per scouted event; field detector training is optional. Marks and the Train field detector button are kept. Robot detection, OCR, constant tracking and the action model are now separate sessions.

Checked: 489 engine tests OK.
## 2026-10-26 — Robot detector: held-out match out of YOLO validation; failure breakdown in the check (Claude, not released)

Measured: the adopted bumper detector (report on this Mac, engine robot-detector-jobs-v2) scores held-out 2026txcmp1_qm4 F1 0.814 (recall 0.821, precision 0.807; 75 frames, 554 bumpers) vs 0.784 for the detector it replaced. Wide band is weakest: F1 0.799, 87 of the 109 false positives, 53 of the 99 misses. Close-ups: F1 0.838, recall 0.793. That run's frames were cleaned up, so the misses could not be re-sorted by cause (far, occluded, people or carts).

Recipe audit: training and the check both run at 1280 (no picture-size bug). Bug: `labels.build(..., holdout={holdout})` put QM4 in YOLO's validation folder, so QM4 chose best.pt and drove early stopping (patience 20). So the 0.814 is optimistic. Fix: `yolo_validation_from_training()` swaps the validation folder for every fifth labelled training frame (taken before workshop images are added) and removes the held-out images from the dataset; recipe is now `adopted-bumper-warm-start-v2-train-validation`. The held-out match is still only the adoption check; gates are unchanged (F1 +0.02, warm start refuses weights that saw the holdout, Q7 reserved).

Diagnostics: the check boxes now carry alliance, and `evaluate()` reports `failures` (alliance_mixed, missed_small under 2.5% of frame height, missed_large, false_positive_wide/closeup). F1 is unchanged; `score()` still ignores alliance, so red/blue mix-ups were counted as found before and are now shown separately.

Checked: 492 engine tests OK on the bundled Mac 3.2.51 Python (new tests: validation never contains the holdout, failure notes leave the score unchanged, one picture size). No retraining run yet; no F1 gain claimed. The next robot run measures it, and robot runs only get this fix after a helper release.
## 2026-10-26 — OCR: measured benchmark, bumper crops read against the roster, scoreboard side check (Claude)

Built `tools/ocr-benchmark/`: 160 bumper boxes (2026txcmp1 Q3/Q4 robot-label frames; 73 fully legible, 39 partly, 48 no number) and the clock and scores on 88 overlay frames from 4 events, all read by eye; images stay in `local/`, checked by SHA-256. No Q7, no official results. Settings were tuned on this set, so it is a development benchmark, not a held-out test.

Bumpers (`neptune_ocr.bumper_window/white_rows/read_team`, used by `neptune_yolo` sampled reads and `neptune_tracking.track_reads`): tight window around the strip enlarged to ~160 px tall; the reader sees a white-digit map first and the colour crop only when there is no exact read; digit fragments joined; answers limited to the match roster (corrections only within the bumper's alliance, 4+ digits). Fully legible boxes read correctly: Apple Vision 36 → 57 of 73 (wrong 1 → 0), RapidOCR 57 → 67 (wrong 2 → 0); false reads on no-number boxes RapidOCR 4 → 1, Apple Vision 0 → 0. Identity gates unchanged (two exact moments, conflicts still drop a track). `CONTINUITY_REVISION` → `bumper-window-roster-reads-v8`.

Scoreboard: Week 0 (red left) and AGE (blue left) profiles share one geometry; a ctwat frame matched the wrong one and swapped red and blue. `detect_layout` now takes the roster and skips a profile whose roster regions show the other alliance's teams more than their own; joined roster rows ("5025 10147 2584") are split. Apple Vision scores 162 right / 2 wrong / 12 unread → 168 / 0 / 8 (rest: single-digit scores Apple Vision does not detect); RapidOCR 176/176 before and after; clocks 88/88. `PIPELINE_VERSION` → `facts-4.2-roster-sides` (saved facts are reparsed from raw OCR on next use). `parse_overlay_generic` (roster-anchored, layout-free) is added and tested but not wired into production.

Found, not changed: this Mac's `~/.neptune-helper/games/2026.json` (Oct 18, from the server's game pack) replaces the built-in layouts and lacks the AGE and Week 0 profiles, so capoh/ctwat-style overlays fail here until the server pack is updated.

Checked: 503 engine tests OK on the bundled Python (new `test_ocr_reads.py`, side-check and split tests). Q4 tracker (YOLO, Apple Vision, CPU), HEAD engine vs this change: exact bumper anchors 1028 → 1243, identified points 1265 → 1330, coverage 4734 0.27 → 0.36, 9444 0.31 → 0.32, 6377 0.06 → 0.07, 10340 0.31 → 0.32, 9492 0.80 and 5417 0.04 unchanged; time 329 → 480 s (second colour pass). Q4 has no per-track truth, so identity errors are not measured there. Not released, pushed or deployed.

## 2026-10-26 — Field retraining at the checked picture size; held-out match out of training; Mac 3.2.51, Windows 6.5.22, Linux 6.6.13, engine 2.7.36 (Claude)

First run scored per corner (11:27) still kept the current detector on 2026dal_qm6: new 2/6 within 0.8% (both hubs, no corners) vs current 3/6 within 4.0%. Two training bugs found in `train_field`: (1) fine-tuning ran at imgsz 960 while the shipped detector was trained, and every placement check runs, at 1280 (`fd.FRAME_WIDTH`), so small far corners were learned at 3/4 scale; now 1280, batch 4 (as robot training). (2) The held-out match's frames were YOLO's validation set, which chose best.pt; the check match now never enters the dataset and every fifth training frame is the validation set. Field runs now require engine 2.7.36 / Mac 3.2.51 / Windows 6.5.22 / Linux 6.6.13.

Checked: 489 engine tests OK. No end-to-end training test; the next field run is the first measurement. Labels unchanged.

## 2026-10-26 — Field detector: frame-edge corners and per-corner credit; Mac 3.2.50, Windows 6.5.21, Linux 6.6.12, engine 2.7.35 (Claude)

Every field run since Oct 25 kept the current detector on held-out 2026dal_qm6 (new 1/6 vs current 2/6). Cause is mainly data: two championship-camera training matches cannot teach Dallas's far side camera. Two code issues made it worse and are fixed. (1) Championship marks put the two bottom field corners on the frame edge (the field runs out of view); those points were trained as `field_corner`. `neptune_field_detector.visible_corners()` now drops marked corners within 1% of the frame edge from labels and from scoring; saved marks are unchanged. (2) The held-out check credited corners only when exactly four were found; each visible marked corner now matches one-to-one to the nearest found corner within 10%. The adoption rule itself is unchanged (more found, then closer by the margin).

Server: field runs now require helpers with these fixes (engine 2.7.35 / Mac 3.2.50 / Windows 6.5.21 / Linux 6.6.12; Linux jumps past Codex's 6.6.11 bar). Train page guidance asks for corners where the field ends, at least 4 events including side-camera venues, and another marked match from the held-out match's event (pillar.js v21). Past runs were scored the old way.

Checked: 489 engine tests OK on the bundled Python, including new edge-corner and three-of-four-corner tests. No detector trained or improvement claimed; the next field run measures it.

## 2026-10-26 — One-window helper dashboard: Mac 3.2.49, Windows 6.5.20, Linux 6.6.6, engine 2.7.34 (Claude)

Picked up Codex's native Mac dashboard (Codex's WebKit attempt was dropped: Google sign-in refuses embedded web views). All three helpers now show one resizable window over drifting bubbles in the lighter navy: this computer's card, job and device controls, then Neptune's Running now, other helpers and queue (read from a new read-only `dashboard` action on `api/robot-detector.php`, owner's computers only), then activity and version. Mac full screen via the green button / ⌃⌘F. Gray Neptune logos ship as `engine/neptune-logo-{square,wide}.png` (listed in `neptune_engine.FILES`); no game name is hard-coded.

Fixed on the way: AppKit cards and rows were constrained to their parent before being added (threw, leaving an empty window); `release-mac-helper.sh` now copies every file in `neptune_engine.FILES`, not only Python. Windows/Linux share `neptune_ui.BubblePage` (each card is a canvas window so bubbles show between cards).

Checked: Mac 3.2.49 built from installed 3.2.48, 487 engine tests OK on the bundled Python, Sparkle signature verified, DMG verified. Windows/Linux packages contain the new UI and logos; Tk page rendered at 1000×760 and 660×500 with the Tk 9 Python. Not run as a real helper on Windows or Linux hardware before publishing.

## 2026-10-26 — Field reference-frame correction after failed 9:06 AM run

The newly published 2.7.32 field recipe ran on the Windows 6.5.18 helper and failed held-out 2026dal_qm6: new detector 1/6, current shipped detector 2/6. Review video Xo5QUw7w9IQ shows the candidate boxed the blue target sometimes, missed red, and produced a spectator-area false positive; no new field model was adopted. This is not an accuracy fix yet.

Identified one definite training-data bug in the helper: `ft.samples()` forced the saved exact reference timestamp into training after the normal broadcast-view filter. The championship source 2026cmptx_sf2m1 at 214.2s is a full-screen FIRST title card, yet field-target and corner boxes were attached. The source video SHA matches the run report; the user's marks on normal frames 15/70/130s align with the actual targets. Added the same visual-view check to forced reference frames. An actual video replay now retains 44 valid championship frames and rejects the slate; the Dallas holdout retains all 89 valid frames including its 184.77s reference. 29 engine tests passed.

Published signed Mac 3.2.48 / Windows 6.5.19, engine 2.7.33. Verified public Mac feed/size/signature and server archive hash; verified public Windows SHA and actual updater prepare/apply. Server now holds field training requests for 2.7.33-compatible helpers, while older helpers can finish robot training. Installed Mac 3.2.48 locally; deep signature valid, user's 650 checked image review state SHA preserved, app reopened. Windows PC still reported 6.5.18 while busy with a robot detector job. Queued one new field validation request `c99531d97b6d23a9467e566d` on that 5060, held out on 2026dal_qm6; the server will not let it start until that helper installs 6.5.19. The run remains necessary to measure model improvement. Server rollback files: `/root/field-reference-update-backup-20261026`. Local evidence: `local/field-training-fix/reference-fix/`.

## 2026-10-26 — Published field-training fix and checked-image import

Published signed Mac 3.2.47 (engine 2.7.32) and Windows 6.5.18 through AWS SSM; public update feeds verified, Windows public archive checksum and actual updater prepare/apply verified with connection preserved. Mac archive reconstructed byte-identically from 3.2.43 plus changed files and signature verified before publication. Installed Mac remains 3.2.46 until its update is applied; Windows installation not remotely verified.

Field training now warm-starts from the same-game baseline, respects saved camera/shot label intervals, preserves the three-frame stability and adoption gates, and records parent training provenance to protect holdouts. Corrected website baseline/readiness wording and deployed paged private supplemental-image API. Imported 650 checked folder photographs (45 checked empty negatives); excluded 36 unchecked. Existing 20 workshop originals plus 40 derivatives retained: 710 total train-only images / 1300 boxes (618 red, 682 blue). No new detector trained or accuracy improvement claimed. No labels changed.

Validation: 28 engine tests passed; complete 710-image importer verified earlier; PHP/JS syntax and package isolation/checksum tests passed. Release evidence and small changed-file server backup: local/field-training-fix/deploy and /root/field-import-update-backup-20261026. User review session and clean-image/YOLO-label exports preserved. No extra boxed-image copies generated.

## 2026-10-26 — Codex: publish and enable the 20 workshop training images

Owner renewed AWS SSO. Published the private organization1 workshop package (20 images/28 boxes:19 blue/9 red), authenticated training_supplements API action, and helper-compatibility claim filter. Older helpers cannot claim robot-training jobs while this package exists; minimum Windows6.5.17 / Mac3.2.44 or native engine2.7.29 / future Linux6.6.9. Field jobs unaffected. Minimal live string patches preserved other production changes; backed up only API/jobs/download feed/allowlist/checksum manifest to /root/workshop-training-backup-20261026. Private package mode0600 and directories0700, owned by www-data. Verified every image hash and server readability; removed61-chunk temporary transfer stage. Windows6.5.17 published and public HTTPS archive SHA verified4365084955c076de2864d04d0b2c4783c25363c929c3e294569cae22a53d93cb.

Installed Mac3.2.44/engine2.7.29-workshop-training in place from reviewed3.2.43 baseline, changing only jobs/new importer/engine identity/Info.plist and resource signature. Native UI executable unchanged; old changed files retained under local/workshop-training-integration/mac-installed-rollback. Closed idle helper, installed and deep-signature verified, reopened through native app control, verified saved connection46EF reconnected and Show activity default remains closed. Screenshot mac-connected-3.2.44.png. No long CPU training started, no Windows installation claimed, no model adoption, no Q4/Q7 label changes. Next robot training on updated Mac or Windows6.5.17 includes these20 train-only workshop images, separately reported from match provenance. Linux updater not released and Mac public appcast remains3.2.43; this Mac is locally updated. Receipts under Documents/ChatGPT/autonomous_scouting/local/workshop-training-integration. No new video generated.

## 2026-10-26 — Codex: implement workshop-image inclusion; deployment blocked on AWS login

Owner requested including the 20 corrected workshop images. Added explicit authenticated training_supplements API response using private per-organization external-bumper-training/6962-workshop-v1.json, and a separate neptune_external_bumpers.py importer called after ordinary reviewed-match preparation. No fake 2026 match rows: workshop source date remains unknown; images enter train only, their provenance is reported separately, held-out image duplicates/checksum failures/invalid classes or boxes reject the entire payload before writing. Existing match-manifest gate, Q4/Q7 and .02 adoption gate unchanged. Robot-job report totals include external frames/boxes and external_training records. Packaged 20 corrected images/28 boxes into private JSON under Documents/ChatGPT/autonomous_scouting/local/workshop-training-integration.

Four importer checks pass (real20 payload and unchanged val; invalid late box no partial writes; validation-image duplicate rejection; checksum/source/split fail closed), existing14 job/label tests pass, PHP lint passes. Built narrowly scoped Windows6.5.17/engine2.7.29-workshop-training from hash-verified6.5.16, replacing only jobs/new importer/engine version/build identity. Real updater prepare/apply verified connection preservation and rollback. SHA2564365084955c076de2864d04d0b2c4783c25363c929c3e294569cae22a53d93cb. Artifacts and verification.json local/workshop-training-integration. NOT PUBLISHED OR INSTALLED; NO TRAINING STARTED. AWS escalation confirmed expired SSO, requested aws sso login --profile neptune. Mac/Linux release integration and live deployment still outstanding; do not claim helpers include these images yet.

Owner supplied field-detector screenshot during this work. Verified code has bundled 2026-rebuilt field weights trained on Q3/Q4 fallback (neptune_field_detector.model_path) while website empty state only checks server-adopted currentField manifest. Thus no server-adopted detector can coexist with an in-use bundled baseline. Screenshot reports none found for recent candidates versus2/6 baseline. Root cause of failed field candidates not established; code repeats each match's fixed region labels on sampled frames, which needs visual alignment/camera validation before blaming training. No field detector or UI change made.

## 2026-10-26 — Codex: correct all 20 workshop bumper images; inventory requested full dataset

Visually reviewed all 20 640x640 workshop images and saved separate corrected YOLO labels with explicit class remapping (source blue0/red1 to Neptune-compatible red0/blue1). Reviewed/tightened extents and added two previously unboxed visible blue fragments in frames4/15, yielding 28 boxes (19 blue/9 red). U-shaped bumper bounding rectangles necessarily enclose chassis/background; did not trim visible rear/side bumper pixels just to reduce box area. Original files untouched. Saved original/corrected coordinates, image hashes, reproducible build scripts, ZIP and verified overlays under Documents/ChatGPT/autonomous_scouting/local/train-bumpers-corrected. Inspected all corrected overlays; verified all image hashes, class IDs, normalized bounds and ZIP CRC. Source year/license unknown, whole workshop group train-only; no fabricated 2026 match manifest, helper import or training.

Owner expanded correction scope to the other advertised 6,035 Roboflow images. Inventoried every row in the downloaded v11 archive: 14,251 exported transformed images, 3,758 distinct base filenames; this does not establish that all advertised project originals are present or unique. Saved full-export-review-inventory.json, all rows explicitly not_corrected, under local/roboflow-v11-audit. Requested original-image export without augmentation and with boxes included, while preserving current archive. Full dataset correction is outstanding; do not claim 6,035 corrected. Q4/Q7 untouched; no video generated.

## 2026-10-26 — Codex: inspect expanded train folder

Owner completed adding yolo/train files. Read metadata and checked actual image dimensions for all detection annotations: 676 JPEGs comprise 20 bumper-detection images (26 boxes: 17 blue/9 red), 230 whole-robot detection images (411 FRCrobot boxes/5 object boxes), and 426 image-classification examples (207 blue/219 red, no bounding boxes). All referenced images exist. One whole-robot annotation extends beyond its 4032x3024 image and is flagged, not silently clipped. Visually sampled six images from each component. Bumper examples show team6962 in a workshop; some include chassis and need tightening. Classification/whole-robot examples are distinct tasks and cannot simply be treated as bumper boxes. Source dates/matches/license missing from this combined folder; no invented provenance. Audit script, JSON, sample index and image saved under Documents/ChatGPT/autonomous_scouting/local/train-folder-audit. No import, training, model adoption, label writes, Q4/Q7 changes or video generated.

## 2026-10-26 — Codex: curate a first external bumper supplement

Owner authorized cleanup of the speedy dataset. Inventoried all 400 rows and grouped four filename sequences. Visual review identified video2 as repeated Hopper Q48 match footage, so discarded supplied train/valid/test assignments and kept all selected external examples training-only. Spaced review selection covered 48 images; accepted 23, excluded ambiguous/oversized/occluded examples and the redundant video2 sequence. Remaining 377 images are excluded from this first selection, NOT claimed individually reviewed or corrected. Assigned alliance by visible bumper color (31 blue boxes, two red), manually tightened 12 extents, preserved original geometry and source filename/hash in provenance, converted 33 boxes to normalized Ultralytics YOLO labels. Original downloads untouched. Imbalance and older-season provenance explicit; not a replacement for the existing dataset. Did not fabricate reviewed-2026 manifest fields, bypass trainer gates, train, publish or adopt a model. Q4/Q7 excluded.

Saved reproducible selection/build scripts, original/changed box records, all-400 selection decisions, attribution, 23 annotated overlays, preview HTML and curated-bumper-supplement.zip under Documents/ChatGPT/autonomous_scouting/local/roboflow-speedy-curated. Verified every image SHA, all normalized label bounds/class IDs/counts, and ZIP CRC; inspected corrected full-image overlays. Standard package requires external-data integration before the existing helper can consume it. No new video generated.

## 2026-10-26 — Codex: inspect speedy 400 bumper dataset

Owner added extracted yolo/FRC Bumper Detection speedy (v1 speedy 400, CC BY 4.0). Read all annotations: 400 images, 704 boxes, two empty-label images; train 299/510 boxes, valid 67/125, test 34/69. Single generic frc-bumpers class and YOLOv4 PyTorch pixel-coordinate format. Compared to first archive: 397 same-split annotation rows unchanged, three not present in the same split. Visually inspected 16 deterministic positive samples: mostly tight bumper examples but some include chassis/large occluded regions; repeated older 2023 match footage spans splits. More useful curation starting point than the full heavily augmented archive, but not independent new coverage or evidence of improved detector accuracy. Saved statistics, image comparison and sample sheet/index under Documents/ChatGPT/autonomous_scouting/local/roboflow-speedy-audit. No import, training, gate changes, live labels or Q7 changes; no video generated.

## 2026-10-26 — Codex: inspect owner-downloaded Roboflow bumper archive

Read yolo/FRC Bumper Detection.v11-correct-labels-14k-imgs.yolov4pytorch.zip without extracting the full archive (SHA256 21a352246c621e666148e6a789454f315108743c5598f6ce53ef340f94497948). Contains 14,251 JPEGs and YOLOv4 PyTorch split-level annotations: 7,118 geometrically valid boxes, one frc-bumpers class, 9,910 zero-label images. Reviewed a deterministic 16-image sample: mixed tight-bumper/whole-robot extents, heavy rotations, unrelated activity footage, and some unannotated visible robots. 591 base filenames occur across splits; source grouping requires investigation. No named Q4/Q7 filename hits, which does not certify absence of leakage. Dataset carries CC BY 4.0 attribution. Saved audit JSON, reproducible inspection script, sample sheet/index and import recommendations under Documents/ChatGPT/autonomous_scouting/local/roboflow-v11-audit. No data imported, training queued, gates changed or video generated. Current training requires reviewed 2026 red/blue boxes and source fingerprints; do not fabricate those fields for this older mixed dataset.

## 2026-10-26 — Codex: finish Q4 saved-label audit

Reviewed all 75 completed Q4 source frames and all 601 saved-box context crops from an immutable authenticated-site snapshot. Final findings: 57 non-robot boxes, one duplicate on the same visible bumper in the same camera view, 73 additional existing boxes requiring review, and three visible missing blue 4734 bumper locations. Findings affect 60 frames. One initially suspected field-hardware box at 55.952 seconds was demoted to review because occlusion prevents a confident removal decision. Repeated robot views in separate camera panes are not duplicates. Legacy labels have no saved-image hashes: errors can originate in annotation or frame alignment. 58 source JPEGs exactly match earlier evaluation hashes; remaining 17 use the same cached source and production extraction recipe. Current labels differ from the older journal-video snapshot, so the video findings must not be treated as current box indices.

Created view-only interactive report, CSV, source images, full-frame overlays, context sheets, and 57 proposed removals with per-frame fingerprints under Documents/ChatGPT/autonomous_scouting/local/qm4-label-audit-20261026. Browser verified Google-logo example at 63.952 seconds, saved audit-report-verified.png, and checked source-image coverage and proposal counts. No live labels, training, thresholds, weights, website code or Q7 data changed; no new video generated. External Roboflow dataset investigation deferred at owner's request to finish Q4.

## 2026-10-26 — Codex: inspect non-robot missed boxes in published detector review

Owner asked about https://www.youtube.com/watch?v=qo-j2CtASfc (Robot detector run, Q4, new F1 .73 versus current .74). Viewed paused samples through YouTube, including review 00:50 / frame 31 of 75. A red missed-reference rectangle appears over the small FIRST logo in the sponsor graphic near the bottom center, with no visible robot bumper at that location. Checked engine/neptune_review_video.py robot_video/match: red rectangles are unmatched saved reference boxes; yellow rectangles are unmatched model predictions, and blue is the detector in use. Thus the non-robot red box indicates invalid reference geometry or frame alignment, not a model-generated false detection. It can incorrectly penalize recall; misplaced references can also make real detections count as unmatched predictions. Video inspection alone does not distinguish an incorrect original label from a label/image timestamp mismatch or quantify corrected F1. Q4 remains held out: these errors affect evaluation, not training examples. No labels, thresholds, weights, training requests or live website code changed. Saved screenshot evidence under Documents/ChatGPT/autonomous_scouting/local/review-audit-qo-j2CtASfc/frame31-at-50s.png. No new project video generated.

## 2026-10-25 — Codex: audit annotation changes versus detector scores

Owner corrected oversized boxes and missed robots and asked whether earlier numbers were inflated. Read recent label metadata and compared Q4 geometry to the previously frozen detector-comparison reference. Q4 was changing during the audit: one intermediate read had 58 complete frames/489 boxes; the later immutable snapshot contains 74 frames/587 boxes. Do not describe that intermediate count as the final corrected set. Reused the exact cached current-detector predictions on only the original 58 images for a controlled annotation diagnostic: old and corrected shared-frame annotations both produce TP346, 144 missed, FP116, precision .748918, recall .706122, F1 .726891. Some box geometry changed, including one removed and one added box, but matching outcomes did not. Sixteen newly added Q4 timestamps are explicitly excluded from this controlled comparison, so .727 is not a measured score on the new full set. Both upward and downward annotation bias remain possible; this audit does not certify every label or prove general real-world accuracy. No training, fresh inference, label writes or model adoption performed. Reference snapshot/hash, changed-frame list and diagnostic saved under Documents/ChatGPT/autonomous_scouting/local/windows-updated-run-audit/{q4-corrected-label-snapshot.json,q4-corrected-label-rescore.json}. Temporary private server transfer file removed.

## 2026-10-25 — Codex: caption-free source stills and image-bound robot labels

Owner screenshot confirmed actual YouTube subtitles obscuring bumpers; corrected earlier mistaken attribution to broadcast graphics. Implemented private, content-addressed JPEG storage under robot-label-frames/<org>/<video>, authenticated image/index routes, lease-bound helper uploads, and checksum-bound saved labels. New helper preparation extracts the same full-resolution ffmpeg -q:v 2 images used for training, uploads stills including existing labeled timestamps, and runs bumper guesses on those images. Training fetches and verifies saved-image bytes instead of re-seeking the video for reviewed stills; legacy labels remain unchanged. Source caches have 192 MiB/video and 2 GiB/org limits and never remove saved images automatically. New source-still requests wait for a compatible helper release so older helpers cannot silently complete them with boxes only. Q7, model adoption gates and existing labels preserved.

Initial deployment supplied only six images and mishandled missing-image state: it left the YouTube player visible with boxes from another timestamp and passed clicks through. Owner reported the regression; immediately restored the original PHP/JS/CSS from small rollback backup without altering labels. Repaired and tested on a separate authenticated preview before release: missing/loading stills now hide the iframe and intercept pointer input, boxes draw only on a verified still, and context playback disables editing. Browser test-only mode made no saved label changes: creation increased 5 to 6 boxes; moving/deleting returned to 5 without playback; Play/Pause returned to the same 76.000-second source still. Imported all 54 full-resolution Q5 sample images; normal page now selects the tested still editor when source images exist, retaining original editor for unprepared matches. Live screenshot under local/windows-updated-run-audit/caption-free-labeler-verified.png. Existing boxes are preserved at their original normalized coordinates; this does not certify previously saved labels' alignment.

Installed Mac 3.2.43 / engine 2.7.28-source-stills, retained the dashboard and existing Keychain storage, verified code signature and actual connected UI after owner approved Keychain. Built/published Windows 6.5.16 and Linux 6.6.8 plus signed Mac Sparkle archive/feed. Initial helper publication was rejected by automatic approval review because the first reconstructed Mac archive failed Apple signing checks and the labeler had regressed. Repaired archive by preserving original nested framework signatures, removing an unshipped generated pyc from the seal, and signing the parent bundle. Only retried publication after generate_appcast Apple checks, Ed25519 verification, apt signature, actual Windows updater prepare/apply (connection retained), 14 Python label/job checks, 11 PHP source-frame/auth/quota checks, 10 existing computer checks, and isolated browser tests passed. Server verifies package hashes before publication; exact allowlist entries, small metadata rollback /root/source-still-helper-backup-20261025, and transfer-stage removal verified. Sources/artifacts/receipts under local/source-still-helper-release; full DMG and Windows setup remain previous installers with update feeds. No native Windows/Linux UI test performed. No new project video generated by still-image UI testing.

Queued only clear-frame preparation for a second catalog match, Smoky Mountains Q1 (112y3F7NuWU), request b222ce0da874dec55b51e31d, targeted to updated Mac 46EF. This is source-frame preparation, not detector training or adoption. End-to-end check passed: Mac claimed at 1792981881, completed at 1792981965 (84 seconds of preparation), uploaded 54 source stills and 258 bumper guesses. Reloaded the normal labeler for match_id=40443 and verified SOURCE STILL at 00:28.00 with no YouTube subtitles/player overlays; saved qm1-caption-free-verified.png. Public Windows/Linux archive hashes and Mac feed/archive accessibility checked after publication. Owner may have independently queued training while labeling.

## 2026-10-25 — Codex: confirmed invalid positive training frame

Downloaded Q45IuedY5hc with the production helper downloader and extracted all six newly added 2026tnkn_qm5 timestamps using the production ffmpeg method. Rendered all 55 saved boxes. At 0 ms the source is the opening FIRST AGE/REBUILT title card, but 11 positive bumper boxes cover that graphic. This is a confirmed frame/label alignment error, not merely an association between dataset size and F1. Remaining five timestamps show match footage; their complete annotation quality is not independently certified. Preserved source labels and model state; no training queued. Evidence and findings at Documents/ChatGPT/autonomous_scouting/local/windows-updated-run-audit/{six-frame-label-audit.jpg,0-labels.jpg,audit-findings.json}. Correction requires aligning the actual intended frame/boxes before reusing that training example; do not blame the owner or silently delete labels. The single bad frame does not establish the entire regression's cause.

## 2026-10-25 — Codex: live helper dashboards; updated Windows detector audit

Replaced the oversized status layout with the owner's website-style computer card and Running now panel. Native Mac 3.2.42 / engine 2.7.27 shows hostname, logo, availability, CPU/GPU/RAM/GPU-memory and real job progress. Windows 6.5.15 and Linux 6.6.7 use the shared equivalent. Activity starts closed and toggling preserves hardware-card height. Existing telemetry samples feed local displays before network send; isolated subscriber failures cannot interrupt reporting. Retained connection/device/stop/review controls. Installed and signature-verified Mac app; actual connected screenshot shows live readings. Published signed Mac/Windows/Linux update packages through SSM, verified server hashes, Sparkle/apt signatures and public Mac/Windows feeds. Exact archive allowlist entries only; small replaced-file rollback and transfer stage removal verified. Full DMG/Windows setup remain previous base installers with update feeds. Windows/Linux visual behavior was not tested natively on this Mac. Offscreen native UI test verifies stage progress and stable card sizing; three telemetry and nine robot-job checks pass. Artifacts: Documents/ChatGPT/autonomous_scouting/local/compact-helper-release.

Owner confirmed two 17:31/17:48 Windows runs used updated helper. Live reports confirm robot-detector-jobs-v2-warm-start/adopted-bumper-warm-start-v1, same parent SHA and frozen 58-frame Q4 evaluation fingerprint. Both candidates: TP356/FP173/missed134, F1 .699; current TP346/FP116/missed144, F1 .727. Earlier updated run: TP349/FP110/F1 .736, below unchanged .02 adoption margin. Latest dataset adds six frames (55 bumper boxes) from 2026tnkn_qm5: association with regression requires visual inspection, not proof of incorrect labels. No adoption, gate relaxation or repeat training. Both review uploads rejected by YouTube upload limit; confirmed both 17,617,845-byte MP4s retained on server. Saved label document and retention receipt under local/windows-updated-run-audit. Mac experiment 89860aa0c2ae021c3d8f2f5b was cancelled at owner's request after slow CPU progress; helper cleanup had already removed its temporary checkpoint, so no partial checkpoint retained.

## 2026-10-25 — Codex: RobotTracking checkpoint comparison

Tested the exact requested RobotTracking robot_detector3/weights/best.pt (SHA e43d481d67f19b1737e7d28074f6609feba4e587a7eac921e8372b375ae40dae), class names mapped blue/red correctly, against the frozen 58 Q4 frames/490 bumper labels. Existing one-to-one IoU .3/conf .25 evaluation: Neptune1280 F1 .7269; candidate640 .6333; candidate1280 .5660. Wide/closeup combination .7233, union .6867 and agreement .6733 do not improve overall F1. No weights adopted, repository code incorporated, or arbitrary repository scripts executed. Q4 is development evaluation, not independent proof; tracking/OCR not benchmarked. Reports under local/robottracking-candidate. Inspected Bear Metal Roboflow project: published own-validation mAP cannot be compared directly with Neptune F1; weights have not been tested. Q7 untouched; labels preserved. No new video generated by these still-image tests.

## 2026-10-25 — Codex: Mac-only detector experiment started

Owner cannot access Windows and directed updated execution to the Mac. Confirmed Mac helper UI 3.2.38 / engine 2.7.25 and live telemetry. Queued detector experiment 89860aa0c2ae021c3d8f2f5b specifically for Mac 46efacbc6b5e485fad19f3105addf5e7. Corrected the maintenance-created request file ownership to the normal www-data owner (mode remains 0600), allowing the helper to read and claim it. Verified active preparation in the Mac activity window and local dataset: 216 frames, 158 training / 58 Q4 evaluation across 17 actual matches. Dataset audit and UI screenshot retained under Documents/ChatGPT/autonomous_scouting/local/mac-detector-fix-3.2.38. Windows received no queued experiment. Current detector remains in use until the unchanged adoption gate passes; accuracy outcome pending.

## 2026-10-25 — Codex: diagnose detector regression, fix warm start, update Mac

Read live failed-run reports: latest candidate recall .724 / precision .553 / F1 .627 versus current .706 / .749 / .727 on 58 Q4 frames (490 bumpers). Earlier evaluation used 41 frames (355 bumpers), explaining movement of the unchanged model's score. New candidate found about nine extra true bumpers but approximately 171 extra false positives. Verified released Windows 6.5.12 and Mac 3.2.37 training code started each run from the COCO context detector. Changed detector jobs to fine-tune the adopted bumper weights, reject inherited holdout contamination, and record actual dataset matches/counts, parent-weight hash, evaluation fingerprint, matched/missed/false-positive counts. Adoption margin unchanged; Q7 excluded. Fixed reporting that omitted small training matches from the provenance list even though their frames were used.

17 targeted regression checks pass (9 job, 3 labels, 5 dataset); full training-job integration checks verify warm-start selection and rejection of a worse candidate. Loaded the actual adopted model and verified red/blue classes and safe Q4 provenance. Built a Windows 6.5.13 code update from the checksum-verified 6.5.12 public archive, replacing only detector-job code, engine/app identity and file hashes. Exercised the real updater prepare/apply path, preserving a test connection and rollback. Published through encrypted SSM; verified public HTTPS archive hash after adding its exact filename to the existing release allowlist. Small release metadata backup at /root/windows-6.5.13-backup-20261025; no temporary stage retained.

Owner directed execution to the Mac because Windows is inaccessible. Installed local Mac 3.2.38 / engine 2.7.25-bumper-warm-start using the same minimal patch, retaining the existing ad-hoc signing method and verifying the signature. Changed-file rollback under Documents/ChatGPT/autonomous_scouting/local/mac-detector-fix-3.2.38/rollback. Confirmed updated engine and CPU device in live server telemetry for Mac 46efacbc6b5e485fad19f3105addf5e7. Requested one Mac-targeted training experiment; receipt/status in the same local folder. No accuracy improvement claimed before evaluation. Existing labels were not modified.

## 2026-10-25 — Codex: verified owner-completed bumper frame queue

Owner reported all frames checked. Read the authenticated live saved-label API for all four videos: all 18 exact requested timestamps are complete and not skipped. Six cross-event training candidates contain 41 boxes; twelve Q4 evaluation frames contain 93 boxes. Updated the local queue JSON/CSV and completion verification receipt. Completeness is verified; correctness remains owner-reviewed. No training queued and no labels modified. Q4 remains current detector holdout; Q7 excluded.

## 2026-10-25 — Codex: align Q4 correction queue with live labeler

Fixed the local 18-frame review queue: twelve Q4 entries now use the live labeler’s 7.952s + 4s sequence, regenerated full-size previews, match_id=209 links, and MM:SS.ss labeling-clock text. Original arbitrary diagnostic timestamps remain identified as nearby investigation times, not exact frames offered by the labeler. Read authenticated catalog and prefill API to verify video jrpeWpe_iqU, match 209 and available timestamps; checked all twelve entries belong to the sequence and previews exist. Also observed YouTube initially displaying a stale results poster despite the requested clock; clicking Play/Pause initialized footage, but paused seeking was approximate (~0.17s). Did not change production code or any saved labels. Q4 remains separate as current detector holdout.

## 2026-10-25 — Codex: frame correction shortlist

Created an 18-frame local review queue at `/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/frame-correction-queue-20261025/index.html` with full-size JPEG previews, CSV/JSON, video timestamps and labeling/source links. Six existing detector-proposal frames span CAPOH Q9, CTWAT Q32 and TXSAN Q2; twelve Q4 diagnostic frames target recorded identity gaps and the 74.286s assignment-change interval. Review candidates are explicitly not confirmed detector errors; Q4 diagnostics remain separate from the proposed training batch, and Q7 is excluded. No website labels, training data, model weights or release state changed. Checked all 18 images exist and are nonempty, queue count and Q7 exclusion; visually inspected three cross-event source frames. Label links do not claim to select timestamps automatically.

# Work log (newest first)

## 2026-10-25 — Codex: full-match Q4 pipeline diagnostic and annotated video
- Reran the current detector/tracker on saved Q4 video across all three camera views using the installed helper runtime and CPU defaults (3 fps effective); 1,476 camera frames, 327.34 s. Verified the source SHA; reused source-bound clock/roster/OCR facts. Preserved original facts, labels, corrections and model files; Q7 untouched.
- Audited automatic and existing-human-correction variants separately with the real temporal clip planner. Automatic identities available at 380/966 whole-second team-time samples; continuous 4-second clips available near 261/966 (27%). Team 6377 had zero clip-ready samples. Counts describe availability, not accuracy or independent actions. Saved corrections yielded 252/966 clip-ready samples, so they do not currently solve continuity.
- Newest saved local action model (`20261024T025723-b5192ca6-971d5`) validates against the current game/detector but has zero usable learned action heads. Called the actual prediction entry point: zero learned actions, 12 separate stationary-rule events. No learned features were inferred with empty heads. No AWS model-state query, training, activation, deployment or new correction was performed.
- Created a 174-second annotated full-match MP4 (1660x720, 12 fps), a report with per-team identity/clip availability, gap timestamps, one assignment-change flag (not a proven swap), model rejection reasons and raw JSON evidence. Video spot check also shows non-robot detections in the wide view.
- Artifacts and reproduction scripts: `local/q4-pipeline-audit-20261025/`; loopback report at port 49532. Verified source/fact integrity, metric totals, video duration, visual overlays, HTTP byte ranges and native-player timestamp links. Report table and annotations inspected in the in-app browser.

## 2026-10-24 — Codex: local Ollama bumper-reading review trial
- Started installed Ollama 0.40.6 on loopback `127.0.0.1:11434` using existing `qwen2.5vl:3b` (Q4_K_M); no model download, AWS deployment, or automatic tracking change. Server is session-managed, not configured for login startup.
- Added `tools/bumper-reader/read.py` and documentation: serial crop inference with structured output, bounded context, input/model hashes, unknown results for partial readings, and a visual report. All suggestions remain unverified, training-ineligible and excluded from identity anchors. Q7 is excluded from manifest trials.
- Ran six boxes from one Q4 frame. Visual spot check: four clear number suggestions match (5417, 9492, 4734, 9444), one obscured crop yielded a questionable complete 103, one abstained. This is a smoke test, not an accuracy benchmark. Warm median 14.6 s/crop; first request 36.8 s including load. Apple Vision baseline took 0.74 s for all six and missed/partially read several numbers. No corrections or labels were saved.
- Three validation tests pass; `git diff --check` passes. Private artifacts: `local/ollama-bumpers-first-run/` (`suggestions.json`, baseline, evaluation notes, crops, `report.html`). Review report served on loopback port 49531.

## 2026-10-24 — Codex: approved EC2 release-storage cleanup
- Removed 27 obsolete Mac/Windows release rollback directories and unused October 21 release staging from `/tmp`, recovering 7.57 GiB. Root usage fell from 88% to 61%, with about 12 GiB available.
- Kept `/root/helper-3.2.37-backup-20261025T035143Z` and `/root/windows-6.5.12-backup-20261025T035219Z`. SHA-256 inventories verified all retained rollback files and published helper downloads unchanged. Database, SQL backup and swap were preserved.
- Remote audit inventory: `/root/neptune-storage-cleanup-20261025T043740Z.json`. Existing release retention rule in AGENTS.md still applies; no automatic pruning job was installed.

## 2026-10-24 — Codex: helper status placement (deployed to AWS)
- Running now, Connected helpers and Queue appear only in Helpers & settings.
- Each pillar shows only whether its own training is running.
- Verified the patch was already applied locally; PHP/JavaScript syntax and pillar rendering checks passed.
- Deployed the three website files to AWS via SSM on 2026-10-24 (America/Chicago), after matching all live hashes to the pre-patch versions. Verified installed SHA-256 hashes and server PHP lint. Rollback: `/root/helpers-status-backup-20261025T043029Z`. Only these three files were backed up; temporary deployment staging was removed. Browser preview was not performed.

## 2026-10-24 — Claude: live console, tabbed summaries, Test & release stepper
- Running now is a live console: GPU/CPU/RAM meters (nvidia-smi, macOS ioreg, psutil), pass/batch/it-s and
  overall bars, last helper lines. Helpers report every 5 s (15 s idle) from `neptune_telemetry.Reporter`.
- Pillar summaries are one tabbed card (opens on "What's needed next" when something needs doing).
- 3 · Actions laid out like the other pillars; cancel covers stale runs.
- Test & release: Model → Preview → Score → Release stepper; live release checklist and the list of
  tagged matches usable as an answer key (`?answer_key_candidates=<model job>`). Gates unchanged.
- Engine 2.7.23, Windows 6.5.11, Linux 6.6.4 (Mac 3.2.36 pending release).

## 2026-10-24 — Claude: GPU number reading, connect fixes, My computers
- Windows/Linux number reading on the NVIDIA GPU (`onnxruntime-gpu` CUDA 13, installed once when the device is
  NVIDIA GPU; CPU fallback). Actions progress counts reading (30%) and tracking (40%) per match.
- Windows 6.5.8–6.5.9: connect page opens via `os.startfile`, link shown; connect window tall enough for its button.
- Linux 6.6.2: video runtime download accepts GitHub's release-asset redirect (checksum unchanged).
- My computers (Helpers & settings): every connected computer, live job, start robot/field runs on that computer
  (`target` on detector requests), Actions via the existing picker, stop, rename, keep awake (jobs/always/off,
  stored in `robot-detector/<org>/computers/`). Helpers check in with `computer_poll`; `neptune_awake.py` uses
  caffeinate / SetThreadExecutionState / systemd-inhibit. Engine 2.7.22, Windows 6.5.10, Linux 6.6.3.

## 2026-10-23 — Claude: pillars, per-game field detector, 2025 layouts, helper 3.2.15–3.2.20
- Auto Scout is three pillar pages (Robots → Field → Actions) plus Test & release and Helpers; each pillar
  holds its examples, Train, model in use and past runs (commit b9d6539, previewed locally, not packaged yet).
- Field detector per `game_key` (server `field-current/<game>/`, helper `field-detector/<game>/`), with the
  reference marks it was trained on; old single detector migrates to 2026 automatically. Game-neutral wording.
- 2025 REEFSCAPE layout profiles (standard FIRST, FIM); checked on 3 broadcasts: layout, periods, scores.
- Fixes: label video download (`source_sha256`), frames list/dict, helper shown as working during detector jobs.
- Storage: release script keeps two build folders; helper deletes detector work folders after 6 h.
- Helper shows "step N of M / Now / Next". Handoff for Codex: `docs/HANDOFF.md`.

## 2026-10-23 — Claude: field-detector training job (engine 2.7.1-field-detector-training)
- Scoring areas has "Train field detector". An idle helper downloads every saved region document (new
  `api/field-regions.php {all:true}`), samples broadcast frames from each marked match, trains YOLO on hubs +
  field-boundary corners, holds out the most recent match, and adopts on Neptune only if it finds more
  hubs/corners there, or the same number 0.2% of frame width closer. Helpers download the adopted one
  (`~/.neptune-trainer/field-detector`, preferred by `neptune_field_detector.model_path`).
- Smoke test (QM3 + QM4 marks, 1 epoch): current detector 8/8 within 0.12% on held-out QM4; the 1-epoch model
  found none and was not adopted.

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

## 2026-10-28 — Scorer: hidden duplicates are not non-robots
- `neptune_identity_metrics.evaluate`: a hidden (excluded) box named with the team the reviewer gave another box in the same camera frame now counts as `hidden_duplicates_named`, not `labeled_non_robots`. Test added.
- QM6 rescore: 490 reviewed, 177 correct, 0 wrong, 0 switches, 6 named non-robots (was 62; 56 were hidden duplicates on wide 8088 at 6–12 s), 78.8 lost s/robot. QM1/QM3/QM4 unchanged.

## 2026-10-28 — Unnamed robots: causes and contact carry (constant-identity-v4); Mac 3.2.65, Windows 6.5.36, Linux 6.6.27, engine 2.7.50 (Claude)
- Sorted the unnamed reviewed robot boxes (QM1/3/4/6, 1290). Biggest groups: wide tracklets chained only to other unnamed tracklets, with no bumper read anywhere on the chain (469); optical-flow boxes (267, nearly all inside unnamed tracks); no tracker box at all (205, detector); wrong alliance colour (50, QM6 close-up).
- Fix: a contact stretch keeps the number of the same tracker track from one named side; the two sides naming different teams still leaves it unnamed. Hidden-OCR check: contact carries 28 → 210, all correct; the 22 seeded misses in QM6 were there before.
- Tried and dropped: naming optical-flow boxes from their track. Few gains on its own; with the contact change it raised QM6 not-a-robot names from 6 to 18.
- Scores (correct / lost s per robot), before → after; wrong 0 and switches 0 everywhere, not-a-robot unchanged: QM1 175 / 82.2 → 223 / 80.2; QM4 46 / 93.7 → 65 / 93.5; QM6 177 / 78.8 → 187 / 76.2; QM3 0 → 0.
- Diagnostics: local/identity-constancy-20261026/unnamed.py, unnamed2.py.
- Deployed via SSM 938f4c30 (owner ran it): 62 files fetched and verified, 67 changed, backup /root/contact-carry-release-backup-20261028, pruned (disk 36%). Live feeds: Windows 6.5.36, Linux 6.6.27 (latest.json and apt), Mac 3.2.65.
