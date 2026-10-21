# Work log (newest first)

## 2026-10-21 — Claude: clock gate in training; team history removed
- `labeled_examples` now rejects outside-scouting rows from a match whose clock check verdict is
  `exclude` (reason `external_clock_match_excluded`). The check runs after each row's own join, so rows
  that fail individually keep their specific reason. `unlabeled_examples` also takes no reference crops
  for those robots/tags from an excluded match. Human video labels are unaffected.
- Exclude rule (neptune_quality): a measured clock with p90 residual > 1.5 s, joined rows out of scouting
  time order, under 50% of rows joining, or no clock at all. Too few readings to measure is `marginal`,
  not excluded.
- Removed `team_priors`, `prior_shares`, `validate_priors`, `observed_shares` from the scoring model and
  from the trained head (`team_priors`, `prior_version`, `validation.team_history`, `teams_with_history`).
- `neptune_quality.py` is now in `neptune_engine.FILES` and `SERVER_FILES.txt` (training imports it).
- Effect: engine fingerprint changes, so `compatible_preparation_engines()` is empty and cached preparation
  is redone on the next run. Not yet synced into neptune-frc-scouting or deployed.
- Tests: engine 345, only the 7 pre-existing environment errors; server PHP unchanged (26/29).

## 2026-10-21 — Claude: match quality reports
- Added `engine/neptune_quality.py` + `engine/test_quality.py` (10 tests) and `docs/match-quality.md`:
  a per-match clock-join check, and a per-match count/points report against reference labels and the video's
  score bug. Read-only; no engine fingerprints change.
- Ran the clock check on the qm1/qm3/qm4 facts: all `usable`. The first version counted the held 2:20/0:00
  reads as failures (33–68% "rejected"); fixed to count only rejects while the clock runs.
- Not done: running it on the ViperScout matches (facts deleted; reprocess first); wiring into training (done in the next entry).

## 2026-10-21 — Claude: repo created
- Moved autonomous scouting out of `neptune-frc-scouting` into this repo. Engine `2.4.0-review-learning-preview2` (I said 2.2.8 earlier; that is the trainer app build). It includes the
  local working-tree edits that were never committed in the main repo (the PU head gates and scoring
  changes), because `helper/` there is untracked and this was the only copy.
- Checked: `scripts/sync-to-neptune.sh … --check` reports no differences against the main repo.
- Open: see "Known problems" in `SYSTEM_MAP.md`; the review is in `reviews/`.
