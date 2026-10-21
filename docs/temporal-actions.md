# Temporal video action encoder — 2.2.0 preview 1

Neptune automatically prepares four-second, sixteen-frame clips from full match videos. Users keep watching and tagging full matches. No one needs to trim, export or upload short clips.

## Model and learning

The shared engine now supports Torchvision R3D-18 (`KINETICS400_V1`), loaded from the fixed official URL `https://download.pytorch.org/models/r3d_18-b3b3357e.pth`. Full SHA256: `b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d`. First setup downloads about 128 MB once into a shared cache and verifies that fingerprint. No model URL from a training job or import is executed. Inference never substitutes randomly initialized weights.

The pretrained 400 human-action classifier is removed. Its frozen video backbone supplies a 512-dimensional temporal embedding. Neptune fits its existing per-tag action heads on those embeddings using each season's human tags and aligned imported activity. This is transfer learning with retrained season-specific heads, not end-to-end fine-tuning of all R3D layers. The human Kinetics class names are never interpreted as FRC actions.

Game key, rule/tag-definition fingerprint, encoder version and encoder fingerprint are recorded and validated. A 2026 head is not reused for a different year's game or a changed game pack. General bumper tracking and video representation can be reused where compatible; the game-specific heads must be retrained on that season's examples. A game-pack description records the definition but does not magically teach the model its meaning without matching examples.

Positive/unlabeled learning, source-group separation, independent evaluation, phase restrictions and owner release gates remain in place. Missing tags do not become verified negative labels. Scoring contribution heads keep their existing descriptor and input dimensions; the temporal action embedding is not misinterpreted as robot points.

## Automatic clip path

1. Imported actions use the existing verified broadcast-clock alignment; human tags already use video time.
2. The labeled robot must have an OCR-anchored YOLO/BoT-SORT track at that moment.
3. Every clip frame must have a nearby trusted localization for the same robot, track and camera scene. Clips spanning camera cuts, identity gaps or phase boundaries are rejected with exact reasons. Future number reads do not retrospectively label earlier footage.
4. Each crop follows the robot and includes nearby context while staying inside the same camera panel. Scoreboards and other panels are excluded.
5. FFmpeg streams the frames into memory. No permanent clip MP4 or pile of frame images is created. A single clip uses sixteen small crops.
6. The official encoder produces the embedding; fitted season-specific heads provide action-candidate scores. Existing episode decoding and uncertainty/release checks still apply.

Clip plans (video times, crop boxes, track/scene, robot and encoder fingerprint) are kept with positive-example provenance and cached feature records. Decoder or identity failures are counted per example; one unusable positive clip does not discard every other label in the match. Unknown reference clips are skipped without turning them into negatives.

The new feature contract is `robot-r3d18-clip-v1` (512 values). Historical `robot-rgb-motion-v1` models retain their 1296-value contract and remain readable. Server candidate validation accepts only the explicit known format and encoder fingerprint. Cached action features/prepared examples are versioned separately from scoring features. Predictions choose the backend recorded in the saved model.

## Server and Training Helper

Both ship identical engine source including `neptune_temporal.py`. Torch and Torchvision were already introduced by the YOLO preview; their pinned versions stay `2.9.1` / `0.24.1`. First-time setup adds the official video weights. The helper reports `action_features=robot-r3d18-clip-v1`; older helpers cannot claim new temporal jobs but already-running jobs may finish. Server setup downloads the encoder into its existing private tools area, then the managed worker must be restarted after current work ends.

The 128 MB weights are not stuffed into the Maintenance ZIP. They are fetched once from PyTorch during setup. Private Prosper tracking weights retain the authenticated-download handling from the previous preview; no GitHub credentials, connection tokens or private models are added to public base ZIPs.

This preview covers the owner Training Helper, server training, match trials and evaluation execution paths. Updating the separate public analysis-helper distribution for released temporal models is not part of this preview; do not release a new-format model to those older clients. Existing model release checks still require independent complete-match evidence.

## Actual checks

A four-second clip was automatically extracted along an identified robot track in real Q7 footage, then encoded into 512 finite values on both CPU and Apple Metal. It took about 5.0 seconds on CPU and 5.8 seconds on Metal including initial model loading. These are startup/inference checks, not throughput or recognition-accuracy results. No Q7 labels or video were used to fit the action heads. No real FRC temporal action model has been retrained in this development session, and no accuracy improvement is claimed.

Automated tests cover phase boundaries, camera cuts, track/scene swaps, another robot's identity, missing/changed weights, frame counts, feature-format separation, training on 512-value inputs, game isolation, and per-label rejection. PHP tests cover server acceptance of the encoder contract and rejection of incompatible weights or still-image claims. JavaScript tests check useful no-model result messages.

Windows/Linux/CUDA execution still needs target-machine verification. The frozen-backbone approach keeps fitting affordable, but CPU clip encoding is additional work and may slow the low-usage server. Unclear robot tracks still cannot provide valid training clips.

## Current five-match failure is not solved by adding an encoder

The saved run `ea5d8b19b9d9cafc439debcb70f7a345` produced six positive action examples from two source matches and two usable scoring examples. Recorded exclusions include 85 robot-localization misses, 24 unresolved clock joins and two broadcast-layout failures (`2026kett_qm1`, `2026ctwat_qm35`). The temporal encoder does not fix those broadcast parsers. Repeating the same batch alone will not repair those failures. Better input recovery/layout handling is still needed.

Defense remains an observed interaction to learn, not a rule that awards a tag whenever two opposing robots are close. This preview does not implement causal defensive-blocking detection, ball counting, successful-shot attribution or guaranteed climb recognition. End-to-end detector fine-tuning and temporal-backbone fine-tuning are also not implemented here.

Sources: Torchvision 0.24.1 video ResNet implementation and its R3D-18 pretrained weight metadata; Neptune's existing game packs, labels, clock alignment and training execution paths.
