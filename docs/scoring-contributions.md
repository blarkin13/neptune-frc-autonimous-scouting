# Community scoring contributions

The public video tagger keeps all 19 original shortcuts. S remains a repeatable scoring-start click. O opens the whole-match contribution estimate: robot points and a percentage slider. The full final alliance score, including penalty points, is the denominator. Changing either input updates the other; points are whole numbers and percentage display is rounded. No default one-third allocation is invented.

Totals come from The Blue Alliance's canonical match endpoint, using the existing server-side TBA integration and cache. A played-match time, matching match key and matching six-team roster are required. No total is invented for unplayed/unavailable matches. Without a total the user may record points, but percentage stays unknown. Zero alliance points also leave percentage undefined. Server normalization calculates the share and snapshots total/source/time; client-supplied percentages and alliance totals are ignored. Robot points cannot exceed the known alliance score.

Whole-match estimates have `scoring.mode=alliance_share`, `label_scope=match`, null timestamps, `robot_points`, `alliance_score`, `share_percent`, `score_basis=full_final_alliance_score`, and `penalties_included=true`. Estimated entries retain uncertain evidence. Counted entries are user assertions from complete robot scouting, not independently verified facts. A percentage is a scoring share, never a model confidence or accuracy measure.

Optional sequence evidence remains available inside the editor and through Add amount/Edit amount beside a timestamped Scoring entry. It records component, period, counted successful pieces, estimated range or unknown amount; REBUILT fuel also needs active/inactive/unknown hub status. Unknown amounts/conditions remain null, not zero. REBUILT AUTO tower L1 has an alliance cap, so a visible climb alone is not assigned points. REEFSCAPE and REBUILT values use separate versioned rule profiles. Future games do not inherit numeric values from older games. Whole-match share uses the official total independently of piece-scoring profiles.

Sequence values follow FIRST manuals:
- https://firstfrc.blob.core.windows.net/frc2025/Manual/2025GameManual.pdf (Table 6-2)
- https://firstfrc.blob.core.windows.net/frc2026/Manual/HTML/2026GameManual.htm (Table 6-3, hub status)

`community.video.scoring.v1` adds nullable `scoring_json` and `replaces_id` to `community_video_labels`. Existing labels remain usable. No approval queue is added. Corrections atomically append a replacement and withdraw the original, preserving history and preventing both from entering active exports. Only the originating browser can correct its scoring entry. Save retries are idempotent and keep the original alliance-score snapshot. Whole-match totals shown in the UI prioritize the user's whole-match estimate; timed sequence values are separate evidence and are not summed into that estimate. Different contributors are not blindly aggregated.

Public NDJSON and server snapshots preserve normalized scoring metadata and correction lineage while excluding user/browser/network identifiers. The server ingestion module keeps both kinds distinct. Whole-match estimates do not become timestamped action examples. Trainer v1.4 uses them as separate score-regression targets, retaining their uncertainty; see scoring-model-v1.4.md.

Validation: 95 helper tests pass, including whole-match label ingestion and uncertainty, plus PHP scoring validation, correction/undo/privacy tests and existing core/catalog tests. Browser previews verified both input directions using an actual 426-point final total, without saving fabricated observations. All 97 prior labels remained in the live export. No remote GPU trainer or stronger model was claimed or installed.

Deployment backups:
- Community scoring fields and exports: 20261018-103102-8521
- Updated Community workflow pages: 20261018-103856-170d
- Percentage slider and robot points: 20261018-104643-49cf

Community pages now lead with human contributions; helper analysis, summary publication review, current experimental training and future GPU training are distinguished. Public setup/review information can be read anonymously, while helper downloads/claims and unpublished draft access remain protected. Review POSTs remain reviewer-gated. Neither data labels nor model weights are deleted by these updates.

Final guide backup: `20261018-104937-afd4`. Compact slider layout backup: `20261018-105130-23a4`. Final live browser check showed all editor fields together, including the 426-point source total. Test inputs were cancelled; no fabricated training observations were saved.
