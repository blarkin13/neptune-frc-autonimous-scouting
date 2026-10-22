# Field detector

- `reference.json`: the marked regions the detector carries onto new broadcasts (2026txcmp1 QM4).
- `model.pt`: YOLO weights (scoring_target, field_corner), trained from marked events. Not in git
  (`*.pt` is ignored); shipped in the helper app and the server engine archive.
- Retrain: `neptune_field_detector.build_dataset` on matches from events with marked regions, then `train`.
