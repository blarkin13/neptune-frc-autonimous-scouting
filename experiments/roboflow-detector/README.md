# Roboflow detector trial — pending weights

Candidate: https://universe.roboflow.com/frc-robot-recognition/frc-robot-detection-6-hjmz0

Selected public model: `frc-robot-detection-6-hjmz0/21`, YOLO11 Nano.
The public deployment dialog exposes API inference, not a weights download.
Roboflow's documented SDK download requires an API key and access to the model.
Use `download_weights.py` in an environment with the Roboflow SDK installed and
`ROBOFLOW_API_KEY` set locally. Never put credentials in this directory.

## Baseline inspected

The adjacent Python modules and requirements are unmodified reference copies
from Windows Helper 6.4.2's update archive, not an installed replacement.
No running helper or release archive has been changed.

The current tracker requires red/blue bumper classes and checks both detector
files against a private bundle manifest. Its context detector identifies people.
The project advertises generic bumper, frc-bumpers, frc-robot, and fuels classes;
actual class names must be checked in the downloaded selected weights.

## Integration requirements

1. Inspect the downloaded artifact format, class names, checksum, and model head.
2. Retain the existing detector and context detector for rollback and comparison.
3. Add an explicit adapter for generic bumper detections. Obtain alliance from
   validated visual bumper color or roster-confirmed OCR; abstain when ambiguous.
   Never map generic bumper classes to an arbitrary alliance.
4. Exclude fuel and whole-robot detections from bumper tracking. Keep whole-robot
   boxes separate if later used for action crops. Resolve overlapping bumper
   aliases before they enter the tracker.
5. Update the trial bundle's checksum manifest and tracking cache revision.
   Do not overwrite baseline cached results.
6. Run both detectors on identical match footage and settings. Start with QM8,
   then QM6 and QM1; include all six matches for the final comparison.
7. Compare manually verified box recall/precision, team identity errors, verified
   track seconds, label localization and temporal rejection counts, accepted
   training positives, runtime, and device. More detections alone is not success.

Neither private baseline weights nor match videos were found in this workspace.
The installed Windows machine or its exported bundle and videos are needed for
the end-to-end comparison. The training JSON alone cannot rerun detections.

Dataset attribution: FRC Robot Detection 6, Frc robot recognition, Roboflow
Universe, CC BY 4.0 as listed on the project page. Verify model-weight terms
separately before distributing a replacement helper.

Download documentation:
https://docs.roboflow.com/models/model-weights/download-roboflow-model-weights
