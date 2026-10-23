# Robot detector (engine-shipped)

`bumper_wide.pt` is Neptune's own bumper detector for the wide camera, trained on owner-labelled frames
(Robot labels). Tracking uses it for the wide view and keeps the private downloaded detector for close-ups
(`neptune_yolo.with_bundled_cameras`). Weights are not in git (`*.pt` ignored); ship them in the helper app and
the server engine archive. Retrain from `local/robot-labels` (or site labels via `neptune_robot_labels`).
