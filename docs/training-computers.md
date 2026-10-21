# Train & test on one Neptune page

Why older candidates produced constant scoring tags and unbalanced points, and how held-out checks now gate them: [auto-scout-quality.md](auto-scout-quality.md).

Open Command Center → Community Scouting → Train & test, or the community header's Train & test link. The owner controls the workflow at `/admin/community-learning.php`.

1. Choose a game. Use a helper computer or Run on Neptune.
2. For a helper, download its personalized Mac/Windows/Linux setup ZIP in the connection modal, extract it and open its setup file. Leave the helper open. It checks prerequisites, connects automatically and waits; no copied token or second Start button is required.
3. Neptune shows the actual connected computer and readiness. Choose the batch size and Run training on the page. The batch freezes the selected first N available matches and all their current source labels.
4. Watch actual stages and prepared-match counts. Closing the modal keeps work running. Stop after this match saves the current match, then pauses; Continue reuses saved preparation on that computer. Another computer must prepare its own missing cache.
5. Done → Close and view results shows the report, usable examples, exclusions and any scoring preview. Reports and model files are returned automatically to Neptune. A preview of training examples is not accuracy.
6. Choose a model, event and match on this same page. Run this match test with a helper or the server. Read the six robot prediction records, unknowns, action tags and source-overlap notice here. Human contributions are kept separate. The original video can be watched inline.
7. Independent evaluation is separate from a trial. Upload a prepared complete reference JSON from the page. The worker retrieves/checks its source footage. Release stays locked until independent checks pass and the owner explicitly releases the model. Nothing is automatically released.

See saved human data shows actual tags/estimates. Include outside scouting imports and displays versioned source observations; see [outside-scouting.md](outside-scouting.md). Outside sources and human annotations are stored in separate tables. There is no student code workspace, contributor review gate or summary generator.

## Computers and resources

Training Helper v1.6 supports Apple Silicon macOS 14+, Windows x64, Ubuntu 24.04/Debian 12. Mac uses Apple Vision; Windows/Linux use RapidOCR. Automatic can select Metal/NVIDIA/CPU. The existing action baseline can fit with Metal/CUDA; the current whole-match scoring regressor runs on CPU. Video reading has its own CPU/backend requirements. These remain setup ZIPs, not native DMG/EXE/DEB installers. Windows/Linux archives are checked; native installation/GPU execution on those systems has not been verified here.

The private managed Neptune worker is installed as `neptune-community-learning.service`, one server task at a time, CPUQuota 10% of one CPU, MemoryHigh 650 MB, MemoryMax 850 MB, swap allowance 1 GB. It uses a private Python environment, FFmpeg, RapidOCR and a pinned Deno runtime. Match preparation is checkpointed; fitting follows completion of the chosen batch. There is no reliable four-hour runtime guarantee.

A live EC2 video access check was blocked by YouTube's bot confirmation. The page reports that source-access failure, keeps Run disabled while unavailable, and offers a fresh background check. This is independent of installed-tool readiness. A connected helper can read the same match from the Mac. No cookies, credentials or anti-bot bypass were installed.

## Storage and recovery

Neptune holds source labels, immutable job snapshots, reports, candidates, trial results and release status. The selected computer holds source videos, OCR/localization evidence and feature caches. Repeated jobs can reuse cache by source hash, game fingerprint, feature version and label content. Finishing a model does not upload all cached videos or crops to Neptune.

Credentials last 30 days, are hashed on Neptune, owner-scoped, revocable and rechecked on API calls. Downloads require the existing owner/Google/CSRF checks. The selected helper alone can claim its page-controlled work. Legacy helpers cannot steal it. Heartbeats and leases protect pause/resume and stale uploads. The server uses internal file transport, not a stored owner token. Candidate files are JSON data.

Game packs remain season-specific. Numeric JSON formatting (0 versus 0.0) does not change rule fingerprints; actual rule/crop/revision changes do. Model transport preserves float types and empty head maps so an unchanged saved model survives the PHP/JSON round trip without weakening content validation.

## Validation

136 helper tests passed after the page, model transport and outside-clock changes. PHP tests verify selected batches, actual readiness, old-client isolation, leases, stop/resume, independent reference gates, source imports and unchanged human tags. The real Mac run used 97 action labels and three score estimates from two matches; it returned a candidate with 23 usable action examples and two usable scoring examples. One scoring target lacked sufficient robot sightings. Stop/resume reused the completed first match. This is functionality evidence, not a human-level accuracy claim. No model was released.

Maintenance backups: main v1.5 `20261019-100800-402a`; modal layout `20261019-102058-9ffb`; model transport/video access fixes `20261019-103339-bff9`.


Outside-source follow-up: calibrated the compact Week 0 overlay on actual Qualification 1 footage, verified its six roster numbers and fitted an unreleased scoring-activity head from two imported robot examples. Nearby observed clock readings are used for phase-time joins; missing intervals are not extrapolated. A separate active 17-match helper job was left running with its original frozen game pack. Updated base trainer ZIPs and the existing private Mac download preserve the same connection. The helper QA loop was stopped after testing. The live EC2 readiness probe correctly disables Run when YouTube blocks access.
