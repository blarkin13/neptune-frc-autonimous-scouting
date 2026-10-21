# Outside scouting sources

Train & test has an owner-only Include outside scouting section. ViperScout 2026 scouting CSV and Viper .dat.json event bundles are the first supported formats; this is not a universal importer for arbitrary scouting systems or games.

Choose a CSV or .dat.json bundle, confirm its event code and public attribution link, preview it, then import. A filename such as `2026week0.scouting.csv` suggests `2026week0`; the supplied example `2026ctsou` link is a different event and must not be used to label that file. The page can refresh the event's canonical schedule/video links, show normalized imported records, and include/exclude an import without deleting its history. There is no moderation queue for community contributors.

Two tables preserve source provenance separately: `community_external_imports` (provider, adapter, file hash, event, inclusion state, offset and report) and `community_external_observations` (normalized original robot records and record hashes). Scouter names and created/modified columns are omitted before persistence. Exact repeated imports are idempotent. Identical record contents from multiple files are deduplicated in training; conflicting active versions of a match/robot are excluded with a visible explanation. Public community labels are not inserted, changed or withdrawn by an import.

## Clock and label meaning

The adapter is grounded in Viper's `www/2026/scout.js`: its timer counts upward from a manual start or the first action, with 20 seconds of autonomous, a 3-second gap, and teleop starting at source second 23. It logs counted changes such as `16:auto_fuel_score:10`; an omitted value means one. These are fuel-count activity observations, not ten scoring cycles or ten scoring-start labels. Created/modified wall-clock dates are not used for video alignment.

The export retains the source phase, phase-elapsed time, quantity, adapter/version, record hash, attribution link and optional correction. The helper checks the actual video hash/duration and match/roster, then aligns phase time to nearby validated video-clock readings before locating a matching robot crop. It does not extrapolate across missing clock intervals. Older caches require both phase boundaries to have been observed. This handles small broadcast-clock drift without pretending video elapsed time is identical to match time. Scouter start/click delays remain unknown: these examples are explicitly weak activity supervision. Out-of-phase events and unlinked or mismatched records do not become guessed timestamps. A complete reported teleop climb maps only its final recorded level, when that event fits within the period. Aggregate defense/reliability fields and autonomous outcomes are retained as source information; they are not assigned invented action times or routine intent.

Counted fuel and reported climb levels remain in the source records. This adapter does **not** invent individual point targets from fuel counts, inactive-hub shots or unofficial Week 0 rules. The supplied file has no explicit individual-point field. Existing community score estimates continue to train the scoring head separately. Future source adapters must define explicit game-specific quantity/point semantics before adding score targets.

Outside activity can support the current experimental action candidate, but is never used as calibration/test truth. A given robot/frame/tag is deduplicated so repeated fuel clicks do not multiply an image's training weight. Video/event grouping and independent complete-match release checks still apply. Missing fields are unknown. Neither six rows per match nor an imported file proves complete or accurate scouting.

Training snapshots include these versioned source records. Helper v1.6 (`page-v2`) is required for a batch containing them; older helpers are refused rather than silently skipping the source data. Excluding a source removes it from future snapshots and invalidates any distributed release that depends on its derived labels. Existing run snapshots and imported history remain intact.

## Validation checkpoint

The supplied Week 0 file parses as 90 robot records across 15 matches, 1,259 timeline entries, including 605 counted fuel entries. Two records have period-total warnings. These counts are not useful-example counts: actual video links, clock anchors and robot sightings determine usable training clips.

Tests cover import idempotency, identity removal, mismatched attribution, unavailable videos, roster checks, conflicting revisions, reversible inclusion, unchanged community labels, source-clock conversion, required video anchors, counted quantities, final incremental climb outcomes and exclusion from accuracy references. Source code reference: https://github.com/FRCTeam1073-TheForceTeam/viper/blob/rebuilt/www/2026/scout.js

## Training on an import

Leave the source Included, choose Use a helper computer, connect v1.6, then increase the batch size until the match list contains the imported event (each row shows its outside activity count). Click Run. The saved report separates imported entries from usable robot examples and shows video-alignment errors. The first Week 0 reader check verified the six overlay roster numbers and mapped 32 imported activities; two robot/frame examples were usable, 22 had no sufficiently close identified robot sighting and six lacked a nearby validated clock reading. These are example counts, not model accuracy. The Week 0 profile was calibrated on Qualification 1; other broadcast variants remain unverified.

Live deployment on 2026-10-19 imported the supplied file under 2026week0 and linked all 15 canonical match videos. A separate local end-to-end run on the actual Qualification 1 video fitted the scoring-activity head using two imported examples plus automatically sampled unlabeled footage. The candidate remains unreleased; no point labels were inferred. Another helper was already running a 17-match job with the previous frozen reader pack, so it was left undisturbed. Maintenance backups: outside import 20261019-105221-19bf; calibrated Week 0 reader/local-clock join 20261019-111413-c3c3; active-run feedback 20261019-112021-9d40; inline training instructions 20261019-112152-81ca.

A second user-created import under 2026nhmer was retained, but its canonical event refresh returns HTTP 404. Those 90 records remain excluded from learning because there are no linked videos. No event aliases were guessed; the supplied source is linked under 2026week0. All 140 helper tests pass after these changes.

## Viper JSON event bundles

The importer accepts a JSON object whose `/data/<event>.scouting.csv` value is the embedded CSV text. It requires exactly one 2026 event, auto-detects that event, rejects a conflicting supplied event and uses the existing CSV adapter. Arbitrary JSON arrays and unrelated JSON schemas are not mapped. No embedded paths are opened, URLs fetched or scripts executed. Pit data and team contact forms are ignored. Scouter names remain omitted by the CSV normalizer.

The import identity uses the embedded scouting CSV hash so uploading the CSV and its containing JSON does not duplicate observations. JSON source reports retain only a bundle hash, input-format marker and optional event name/start/end for provenance. The preview shows event dates and rejected-row notes. No database migration or helper reinstall is needed for this format change.

All three supplied files passed the real parser: 2026kett (90 valid robot rows/15 matches, February 7), 2026ctsou (158/27, October 17), and 2026nhmer (106/18, October 10; one invalid match/robot row omitted). The latter two are offseason data, not evidence available before Week 1. Imported records still need canonical video/roster links and actual clock/robot verification before yielding examples. Live preview testing does not itself save a new import or start training.

Installed through Maintenance Console as Neptune_Viper_JSON_Import.zip, backup 20261019-115612-88ec. Regression tests cover CSV/JSON equivalence, cross-format idempotency, event mismatch/mixed events, unsupported/malformed JSON, metadata and omission of unrelated private bundle contents.

## Required video check and event cleanup

Outside previews refresh the event's match/video catalog and show one result per match. Every source match must have an allowed YouTube match link and a compatible six-robot catalog roster; otherwise the entire file is rejected and no outside import/observation rows are written. The server repeats the check on save, including duplicate uploads, so a stale or bypassed preview cannot authorize an unlinked import. Links are catalog metadata: fetching the footage, source hash, clock and visible robot identity remain trainer checks. A source link alone is not a claim that extraction or download will succeed.

`community-source-videos.json` supplies the 15 individually published FUN Kettering qualification links discovered on 2026-10-19, paired with the schedule from the supplied event bundle. These are marked with source provenance, not robot-action verification. CommunityCatalog merges that event into event listings and normalizes it through the existing match parser; existing attached work still prevents a metadata overwrite.

Remove event archives every outside import under that event with enabled=-1. Archived imports are hidden under Removed events and excluded from future exports. Restore changes them to excluded (enabled=0), never silently to included. Source rows, human tags, candidate reports, frozen snapshots, active worker leases and current jobs are retained. No new tables or columns were added.

Validation: PHP tests cover no-video rejection with zero writes, partial coverage rejection, mismatched roster rejection, stale-preview recheck, CSV/JSON repeat imports, archive/restore and unchanged training jobs. Live Kettering preview passed 15/15 links; a preserved Merrimack source was blocked at 0/18 with no Import button. Archive/restore was tested on the already-excluded Merrimack event and restored its excluded state. The current training run was not stopped, resumed, requeued or modified. Maintenance backups: 20261019-121536-31bd and 20261019-122239-0634.

During testing the original local JSON upload files were no longer present in Downloads. Preview checks used sanitized records retrieved through Neptune's existing View imported records screen, not fabricated observations. Disposable agent QA video/OCR caches were removed to free approximately 850 MiB; trainer work, labels and reports were retained.

## Owner Auto Scout workspace — October 19, 2026

The Scouting page now has a platform-owner Auto Scout section linking Watch & tag,
Import scouting, Train & test and Saved scouting. Community HTML pages and the human
label export require the platform-owner Neptune/Google session during development.
Existing credentialed worker APIs retain their separate authentication.

The import workspace has an accessible custom file button and a one-file drag/drop
zone (8 MB). Preview and Import are distinct actions; preview never saves an import.
Source cards link ViperScout, ScoutingPASS and The Blue Alliance, with their distinct
roles explained. These links do not promise compatible action timelines from every
provider or convert alliance results into robot scoring labels.

ViperScout's existing 2026 CSV/event-JSON adapter remains unchanged. The new mapped
adapter accepts flat CSV action rows or JSON arrays / records / data arrays. The owner
maps match, robot, action, phase and time, explicitly selecting elapsed/remaining
phase seconds. Only existing Neptune tag keys/labels are accepted. Nested exports,
aggregate-only data, unknown actions, invalid robots and out-of-phase timestamps
are rejected. Full event video/roster checks are still required. Personal unmapped
columns are discarded. Multiple actions are grouped per robot to avoid false source
conflicts. Outside labels remain weak supervision, never evaluation truth or robot
point targets. Current timing is explicitly limited to 2026.

Mapped imports require a helper advertising `mapped-actions-v1`; the queue rejects
older helpers with an update instruction. All three trainer downloads and the server
reader have been rebuilt with that adapter. Installer archives were checked; native
Windows/Linux GPU operation was not exercised on this Mac.

Remove import now archives only that import; Restore returns it excluded until the
owner chooses Include. Existing running snapshots are kept.

Reset machine data is a CSRF-protected owner action. It requires the exact phrase
`RESET MACHINE DATA`, refuses an active run, clears machine jobs/models/results and
outside imports across games, revokes workers, and verifies complete row hashes for
human labels, label history, matches and catalog before committing. It does not
remove caches on remote computers or touch ordinary scouting/accounts. No reset was
performed as part of deployment.

Validation: 140 helper regression tests passed; PHP import-workspace tests cover
mapping/privacy/clocks, multiple actions, source URL validation, active-run reset
rejection, human-data preservation and stale-worker revocation. Real Kettering preview
passed on the installed page without importing data. Signed-out catalog and human
export requests redirect to login. Maintenance backups: 20261019-133720-83a7
(main update), 20261019-134015-d30f (spacing/card polish).

## Imported scoring targets and platform styling — October 19, 2026

ViperScout records with explicit, valid auto/teleop scored-fuel and climb fields now
supply estimated individual robot task points. Missing fields and flagged records
remain excluded. Imported estimates carry their source components and lower training
weight; they are not official per-robot scores or independent evaluation references.
The new point-target head can train without a final alliance denominator; percentages
remain unknown until a final alliance total is available. Human contribution targets
remain supported and take priority over a duplicate imported target.

The 2026 AGE blue-left overlay has its own profile. Its previous reversed alliance
interpretation failed roster verification. The trainer can reparse compatible saved
raw OCR and reuse confirmed bumper sightings under the corrected profile without
changing the original readings. Other layouts and source hashes remain checked.

The new export recognized 88 imported robot point estimates plus 3 human estimates.
An isolated scoring-only run against the actual saved videos produced 18 usable
examples across 8 matches (16 imported and 2 human), compared with 2 usable examples
in the old production report. Exclusions stayed explicit: 10 incomplete match identity,
27 insufficient robot sightings and 36 incomplete match video. No model was uploaded
or released by this QA run. These numbers demonstrate import/fit wiring, not accuracy.
The example appearance-based scoring baseline still needs independent evaluation.

New batches use the updated export and game revision. Existing frozen runs and old
reports are unchanged and clearly marked as predating the fix. Download the updated
training helper and start a new batch; do not resume an old frozen batch to add newly
supported targets. Existing imports do not need to be uploaded again. Compatible saved
videos, OCR and features can be reused.

Auto Scout HTML pages now use the shared authenticated Neptune header, breadcrumb,
footer and organization theme. Cards, forms, navigation and action colors follow the
platform. Owner-only development access remains in place.

Validation: 146 Python tests and the PHP import-workspace suite passed. All three
trainer ZIP archives were rebuilt and checked; native Windows/Linux GPU execution
was not tested on this Mac. Live Maintenance Console installs: backup
20261019-152331-466f (18 files) and 20261019-152847-6c1b (4 styling/copy files).
The server training worker was reloaded only after confirming no active jobs.
No reset or data migration was performed.

Live visual follow-up: tagging keeps a compact heading under the shared header;
all 19 tag buttons fit in the checked 1280×720 viewport. The catalog, tagging screen,
saved-match list, per-robot results, and training/import page were checked live.
Additional styling backups: 20261019-153129-e842 and 20261019-153236-dfb8.

### Helper capability handshake repair

The server's hardware allowlist was stripping `outside_adapters` from the updated
helper's polling messages. This made both mapped-import and imported-point support
appear absent. A shared sanitizer now preserves only the three supported adapter
names as a bounded array, while still dropping tokens and unrelated telemetry.
It is used by setup status, page claims and legacy claims. Actual job claims also
check the imported adapter, so an older client cannot claim unsupported work.

A regression test exercises the actual update heartbeat → browser readiness →
queue → claim path with an imported point target, plus rejection of an older client.
The installed Mac helper's live heartbeat was verified reporting all three adapters;
no new client download or credential was needed. Maintenance backup:
20261019-155159-0c7f. Existing jobs, videos, labels and model releases were untouched.

### Video-test diagnosis and source correction

Mercury Qualification 29's provider lists two YouTube links. The catalog previously
picked FsOmBnfY334 first; actual decoded frames show a field-side camera without a
readable broadcast overlay. Alternative x0zEgJYH6EI was downloaded and checked in an
isolated folder. Apple Vision accepted 193 overlay/marker frames and confirmed the
qualification number, all six roster numbers, and the results-screen title. The
event-name check remains unavailable because no metadata title was supplied to that
isolated analysis; it was not silently promoted to verified.

The broadcast starts at Auto 0:15: five autonomous seconds are missing (inferred
auto start video -5 s). It clears the layout failure, but all six whole-match score
descriptors still abstain under the existing full-match gate. A source-specific
warning now appears before the owner runs the match test. Visible action prediction
is still a test, not a promise of accurate or complete scouting.

A secure broadcast preference applies only when the exact match key, six-robot
alliance roster and provider video candidate agree. The Q29 database source was
changed only after checking for zero human labels and zero contributor attempts;
the previous metadata is saved root-only at
/var/backups/neptune-q29-video-20261019.json. Existing job snapshots and reports
remain unchanged. No human timestamps were moved to a different video.

Failed-test screens now explain the supported-scoreboard requirement, keep raw
technical details collapsible, link the exact tested video and manual tagging, and
show zero processed rather than a full progress bar for an early failure. Scoring
exclusion counters explicitly count robot estimates, not matches. The old
incomplete_match_video label is rendered as unverified period boundaries; it does
not claim that source footage is physically missing.

The existing 36 boundary exclusions cover Week 0 Q2, Q3, Q11, Q12, Q13 and Q15
(six score targets each). Q1 and Q10 have partial roster verification (five targets
each). The 27 remaining targets lack sufficiently distributed confirmed bumper
sightings. No threshold was weakened and no old model/report was rewritten.

Validation: PHP helper-capability/import/page-control regression chain passed;
new broadcast-selection tests cover roster mismatch, unavailable video, exact
match scope and source-specific coverage notes. JavaScript syntax and diagnostic
copy checks passed. Maintenance backups: 20261019-163427-e329 and
20261019-163724-04bc. Updated production report was checked live: 71 usable action
examples and 18 usable score examples across 8 matches; those are training counts,
not accuracy measurements.
