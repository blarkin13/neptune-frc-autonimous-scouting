# Public video tagging — immediate contributions and large-video workspace

The catalog links to `community/tag-video.php?match_id=...`. Watching and saving labels require no account, helper, or paid API. Every saved public label is immediately included in the training-data export. There is no tag-review workflow. This does not retrain the helper automatically or designate human labels as independently verified facts.

## Watching and tagging

The dedicated workspace hides the large public-page hero and gives footage the available screen area. Robot selection and frequent tags remain together below the player. Scoring start, Endgame completed, Defense, Disabled, and Recovered are always available without changing category. Other existing Match Tag Scouting tags remain in More tags. Buttons are repeatable and each click captures the source video's elapsed time. Switching robots changes attribution for subsequent clicks only. Interval mode remains available in Options & help; active intervals must be finished or cancelled before switching robots.

Controls include rewind/forward five seconds, playback speed, 1×/1.5×/2×/3× video-only zoom, directional view presets, drag-to-pan on the enlarged video, reset view, and fullscreen containing the video AND tagging controls. Shortcuts outside editable controls and the YouTube iframe: Space play/pause; R rewind; 1–6 robot; S scoring start; E endgame completed; D defense; X disabled; C recovered; U undo latest saved label. The browser's normal page zoom is not required. Fullscreen availability depends on the browser. Small screens use a responsive wrapped dock; the desktop player fits the actual rendered controls.

Scoring-start clicks identify the start of a scoring sequence, not one game piece, one point, a completed cycle, or a scoring-contribution estimate. Database key remains the existing `scoring` category. Definition version v1 and pre-existing source records are preserved; old generic Scoring labels must not be assumed to have narrower semantics unless the contributor supplies that context. Absence tags record whole-match/phase assessments, not fake point timestamps.

## Stored data and ownership

`community_video_labels` stores immutable source URL/YouTube ID and roster snapshots, robot, existing tag key/label/category/version, elapsed-video timestamps or interval, observed/uncertain certainty, optional public note, anonymous contributor hash, optional signed-in account ID, creation time, and the label state. New labels use `contributed`, never `pending`. The compatibility column is still named review_state to preserve existing data and integrations. Additive migration `community.video.tags.open.v2` releases all old pending labels as contributed without changing certainty or timestamps. Withdrawn labels and legacy rejection decisions remain excluded; no labels are falsely marked verified. The former reviews table remains as a withdrawal/audit history; there are no new approvals or rejections.

A random HTTP-only, secure, same-site browser cookie allows contributors to undo their own labels. Losing the cookie loses undo access. Browser identity is not proof of a distinct person. Public writes require session CSRF protection, roster/tag/time validation, idempotent action IDs, and a short contributor/IP rate limit. Network keys use HMAC hashes, not raw addresses. No private organization scouting is read or changed. Failed saves have Retry buttons; keep the page open until saves finish. Undo soft-withdraws original rows and removes them from future downloads while preserving history.

## Training-data interface

Public `community/training-labels.php?export=1` streams schema-version-2 NDJSON. No account or reviewer permission is required. Every contributed label is available immediately, including uncertain labels with their certainty intact; training workers choose how to use those examples. Withdrawn/rejected labels are excluded. Account IDs, browser identifiers, and network hashes are omitted. Match keys and stable label IDs support dataset splitting by match/event and deduplication. Optional notes are explicitly public in the tagging UI. The old review-tags.php URL redirects here; it has no review actions.

The dataset contains references and timestamps, not downloaded frames or clips. Source SHA256 is explicitly null. Video duration is browser-reported and must be independently checked by the training worker when retrieving the video. The training process still needs source retrieval, evidence verification, clip extraction, separate held-out evaluation, and a model release process. Withdrawing labels removes them from new exports; regenerate exports before training because earlier downloads are snapshots.

## Deployment and verification

Initial feature: `Neptune_Community_Video_Tags_v1.zip`, backup 20261018-001210-1e88. Compact original layout: `Neptune_Community_Video_Tags_Layout_v2.zip`, backup 20261018-001543-844c.

Immediate dataset + dedicated workspace: `Neptune_Community_Tagging_Studio_v3.zip`, backup 20261018-003324-e327. Screen-fitting follow-up: `Neptune_Community_Tagging_Viewport_v4.zip`. Install through Maintenance Console with exact-base hashes. Migrations run through PHP using the platform migration registry; file rollback does not undo data migration. Preserve the added tables on rollback.

Service tests cover anonymous saves, duplicate retries, invalid roster/tag/time fields, ownership, immediate inclusion without review, preservation of uncertainty, withdrawal exclusion, pending-label migration, and removal of private identifiers from the dataset query. PHP/package and JavaScript syntax checks pass. Live checks verified playback, 2× close-up preset, robot shortcut 3 switching to 11242, fullscreen with all tag controls visible, and data download. The downloaded dataset contained 16 contributed labels including all seven original user labels, with no withdrawn installation tests or private contributor identifiers. Prior live moment/interval/undo checks remain applicable to the unchanged submission format. No model was retrained and no large concurrent-user load test was performed.

## All 19 tags and shortcuts (v5)

`Neptune_Community_All_Tags_v5.zip` installed with backup `20261018-010705-10ed`. All tags now appear once, without category filtering or a More tags menu. Grouping: Scoring & Defense, Autonomous, Endgame, Reliability, Alliance. Controls remain enabled for repeated actions; existing tag keys, provenance, immediate export, and certainty are unchanged.

Shortcuts: Scoring S; Defense D; Fast cycles T; Slow cycles L; No scoring G; No defense H. Autonomous: No attempt Q, Partial W, Completed A, Failed F. Endgame: No attempt V, Partial B, Completed E, Failed N. Reliability: Mechanical issues M, Disabled X, Recovered C. Alliance: Support K, Penalty risk P. Robot 1–6, pause Space, rewind R, undo U remain reserved. Keys are displayed on every button. Absence assessments retain their existing confirmation and whole-match/phase scope.

Live viewport inspection at 1280×720 confirmed 19/19 tag buttons within the screen bounds, with the last tag row ending at 609.5 px; video and controls remain on-screen. Narrow/mobile screens wrap rather than hiding tags; fitting every control without scrolling cannot be guaranteed on phone-sized screens. Source-level keyboard-dispatch tests exercise all 19 tag keys, six robot keys, transport keys, and editable/modifier/repeat/disabled guards without creating public test labels. Service/package/syntax checks pass. No database migration or model change was needed for v5.

## Higher zoom and arrow panning (v6)

`Neptune_Community_Zoom_Pan_v6.zip` adds 4× and 5× alongside the existing zoom levels. While zoomed, arrow keys pan toward the chosen direction; holding an arrow repeats movement, and Shift triples its speed. At 1× arrows are not intercepted. Editable fields, modified shortcuts, and input composition are ignored. Selecting a zoom or view preset focuses the pan surface so arrows work without scrolling the page. Dragging remains supported and pan is bounded to the source area. Existing tag shortcuts and source timestamps are unchanged.

Package/PHP/JS checks and the keyboard/pan regression suite pass. Live checks confirmed scale(4), scale(5), and a change from origin 50%/50% to 50.4808%/52.0993% after Right/Down at 5×. No public test labels were submitted.

## Catalog purpose and instructions (v7)

`Neptune_Community_Catalog_Guide_v7.zip` updates only the catalog index. The public page now explains the purpose of robot-attributed, timestamped examples, immediate contributions without a review queue, and no automatic retraining. The practical guide follows the contributor's workflow: pause/rewind to identify robots and starting positions; replay autonomous for all three robots on one alliance, including visible scoring starts and outcomes; then finish the rest of the match robot by robot before doing the other alliance. It includes scoring-sequence semantics, uncertainty, no-attempt assessments, switching robots, avoiding duplicate tags when replaying, undo, failed-save retry, and a collapsible reference for all 19 tag keys, playback, 1–5× zoom and arrow panning. Starting positions are used to identify/follow robots; no nonexistent starting-position tag or saved coordinate field is claimed.

Live content, guide anchor, Choose a match anchor, expanded controls reference, and season/event selectors were checked after Maintenance Console installation. Screenshot: feature-blueprint/community-catalog-guide-live.png. PHP syntax and the deployed-console package validator passed. No database or helper/model changes were made.
