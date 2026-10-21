# Match quality reports (`engine/neptune_quality.py`)

Read-only checks. They never change labels, imports or models, and the file is deliberately not in
`neptune_engine.FILES`, so adding it invalidates no cached preparation.

## 1. Clock-join check: can this match's outside scouting be trusted?

```sh
python3 engine/neptune_quality.py clock --facts <facts.json> --labels <labels.ndjson>
```

For each phase it measures the observed game clock against one steadily running clock:
- residual (median and p90, in seconds);
- longest frozen stretch;
- coverage;
- reads rejected *while the clock should be running* (the held 2:20 and 0:00 values are not counted).

It then joins every outside-scouting row with the same `neptune_clock.align` training uses, and reports:
- how each row turned out (aligned, ambiguous, unavailable, and why);
- whether the scouting's time order survived the join.

Verdict: `usable`, `marginal` (with the reasons) or `exclude`. The thresholds are at the top of the file.

## 2. Count and points report: does the output add up?

```sh
python3 engine/neptune_quality.py counts --facts <facts.json> --predicted <events.ndjson> \
  --labels <reference labels.ndjson> --points engine/points-2026-rebuilt.json [--official official.json]
```

For each (team, action) it reports:
- predicted vs reference counts, matched one-to-one within ±3 s;
- missed and extra;
- overall recall and precision.

For each alliance it reports:
- predicted points and reference points;
- the final score the video's own score bug shows;
- optionally the official total, **for checking only**.

Penalties and untagged actions make a gap with those totals expected. The report shows the gap and never
forces it closed. Tags without a points value are listed as unpriced, not guessed.

`points-2026-rebuilt.json` is a starting table: one point per fuel, climb levels 10/20/30. Check
`gb:score_2_fuel` and the climb codes against the published Game Builder definition before relying on
point totals.

## First results (2026-10-21)

qm1, qm3 and qm4 facts on this Mac: clock residual 0 s, no rejects while running → `usable`. qm1's video
starts partway into teleop and has no auto phase, so any auto outside rows for it cannot join; the report
shows them as `phase_not_in_video`. No outside rows exist locally for these matches. The ViperScout
matches' facts were removed by media cleanup, so the join check needs to be rerun when they are reprocessed.
