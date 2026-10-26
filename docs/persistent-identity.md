# Persistent robot identity prototype

`engine/neptune_persistent_identity.py` adds source-bound identity records to the current tracker. Fresh tracking returns them under `persistent_identity`; the cached-tracking path computes the new layer from saved observations without rerunning detection. The original localizations, action training eligibility and release gates remain unchanged. This source change has not been built into or deployed as a helper release.

## Behavior

Each of the verified roster's six teams has a stable ID derived from the source-video fingerprint and team number. Observed tracklets are split at missing intervals, recycled tracker IDs, camera/scene boundaries and implausible jumps. OCR-supported tracklets reconnect to that record across long gaps. Conflicting reads and simultaneous duplicate identities block propagation. Appearance proposals compare camera-local median color descriptors against OCR-supported exemplars, require separation from competing teammates and reject competing targets. They never seed further exemplars or become training labels.

`state_at` reports visible or not-observed states. It keeps last-seen time but does not invent a box, position, action or scoring evidence during a gap. Camera-specific returns and returns after gaps in supported assignments across all views are recorded separately. An assignment gap is not proof of physical absence from the video.

The appearance feature is the existing 24-value color descriptor. This is not a newly trained robot-specific ReID network, whole-robot detector, or Ollama integration. Offline processing can use later anchors; it is not a claim of online performance.

## Q4 development test — October 25, 2026

The test reuses the exact 5,336 raw observations from the fresh Q4 baseline, so detector variation does not explain the comparison. Saved human corrections are withheld from matching. Q7 is excluded.

| Result | Value |
|---|---:|
| Persistent roster records | 6 |
| Tracklets | 1,059 |
| OCR-supported return events after gaps across all assigned views | 28 |
| OCR-supported returns to individual cameras | 26 |
| Camera-return appearance proposals | 17 |
| Baseline identity availability | 380 / 966 samples (39%) |
| Persistent OCR-supported availability | 308 / 966 samples (32%) |
| Including unverified visual proposals | 325 / 966 samples (34%) |

**It did not improve overall Q4 identity availability.** The record/reconnection machinery works, but these results do not establish improved identity accuracy or continuous whole-match tracking. The baseline includes existing roster/motion inferences; the new layer is more conservative. It does not replace the baseline localizations.

Of 224 existing human-corrected points, 32 could be matched to assigned crops and all 32 agreed; 192 remained unassigned. This is a nonrandom development check, not an independent full-match accuracy benchmark. The 28 return events have OCR support, not independent verification of correctness.

111 tests pass across persistent identities, existing identity/review tests, tracking, review-learning, temporal clips and training integrity. Tests cover long gaps, duplicate identities, recycled IDs, ambiguous same-looking teammates, competing visual targets, conflicting reads and camera separation.

Artifacts and reproduction scripts: `local/q4-persistent-identity-20261025/`. The source-native quality revision is 1920×1080 at 60 fps, with a five-second intro and eight-second result card. Tracking remains sampled at 3 fps. Video source times therefore map to journal playback time +5 seconds.

Next experiment: preserve the baseline's useful assignments while adding independently checked appearance-based reconnection. Compare a trained robot-specific visual representation and selected Ollama bumper reads on unresolved tracklets; do not promote unverified proposals into training or claim off-screen actions.
