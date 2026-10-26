# Neptune Auto Scout video journal

All generated project demos, diagnostics and model reviews are journaled on **@NeptuneModelTraining**, channel `UCE6AdQni69dVftWxBxEjApA`, as **Unlisted**. See AGENTS.md for the owner’s standing instruction.

| Entry | Experiment | Current native-HD version |
|---|---|---|
| 001 | Q4 detection, identity continuity and action-readiness baseline | [1080p60 video](https://www.youtube.com/watch?v=8ZcIyoHJQMg) |
| 002 | Persistent identity records and reappearance test on the same Q4 detections | [1080p60 video](https://www.youtube.com/watch?v=arnKuPCP3-g) |

The first low-resolution drafts were superseded after owner review. The revised videos preserve source geometry/frame rate at 1920×1080/60 fps, use a high-bitrate encode, larger labels and a compact inset HUD, and include five-second experiment introductions and eight-second result cards. Tracking remains sampled at 3 fps. The journal video timestamp is source time +5 seconds. YouTube processing and actual stream dimensions/frame rate were verified; 1080p60 was also present in the player’s quality menu.

Entry 002 did **not** improve overall Q4 identity availability: baseline 380/966 samples; persistent OCR-supported layer 308/966; including unverified visual proposals 325/966. Its purpose is to document that outcome honestly. The YOLO weights were not retrained. The local implementation has not been deployed as a helper release.

`entries.json` records actual video IDs, channel, privacy, source hashes, processing state, descriptions and render geometry. Draft IDs are retained for audit history, not presented as the current versions. No original unannotated match sources or disposable test fixtures were uploaded as separate entries.

## Publishing future entries

1. Annotate the actual observations, proposals and unknowns; keep legends readable at native resolution. Include the question, method, measured outcome, limitations and next experiment.
2. Finalize descriptive titles/descriptions/chapters before uploading. The current server OAuth connection supports upload and readback; it does not grant video-metadata update permission.
3. Reuse `neptune_secure/youtube-uploader.php` and its existing connection. For large videos, create a standard resumable upload session on Neptune, capture that narrow session privately through SSM, and stream the video directly from the Mac to Google. Do not expose new production upload endpoints or transfer OAuth refresh/access tokens to the Mac. Temporary resumable-session URLs must never enter git or logs.
4. Verify the returned channel ID, actual Unlisted visibility, YouTube processing, HD dimensions/frame rate and player quality options. Save a receipt and update this index.
5. Keep original media and large videos under ignored `local/`, preserve project labels/corrections, and remove task transfer staging. No recurring automation was installed.

Private production receipt copy: `/var/www/neptune/neptune_secure/youtube/journal-20261025.json`. Local source/renders: `local/q4-pipeline-audit-20261025/`, `local/q4-persistent-identity-20261025/`, and `local/video-journal-20261025/`.
