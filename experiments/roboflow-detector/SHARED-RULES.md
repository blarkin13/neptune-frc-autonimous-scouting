# Shared scouting rules — Mac detector trial

Installed in the separate Neptune Detector Trial app. Restart the app after the
active training job completes to load these changes. No classifier retraining
is required for these deterministic analysis rules.

- More than five observed seconds stationary: stationary observation, not a
  disabled diagnosis. Continuous identity and progressing live clock required.
- Suspected disabled: additionally requires an explicit human-reviewed or
  verified no-purposeful-activity interval; missing classifier tags cannot
  establish inactivity. Overlapping purposeful-action tags suppress this inference.
- Recovery: one second of sustained displacement after suspected disabled,
  with continuous identity and live clock. The disabled interval remains saved.
- Recovery also adds a temporary interruption / suspected mechanical issue;
  the mechanical cause is not confirmed.
- Scoring visits merge candidate scoring events separated by at most three
  seconds. Climb outcomes and failed/attempted scoring do not count as visits.
- Average observed seconds per visit uses deduplicated visible teleop time,
  not a fixed match length. Cycle intervals use consecutive visit onsets only
  when the intervening observation is continuous. No visits means unknown.

Defaults are centralized in neptune_scouting_rules.DEFAULTS and can be overridden
through facts.scouting_rule_settings. Endgame is included within teleop.
Structured results are saved as scouting_rules in the match result; stationary
observations and cycle summaries are not added to the existing server tag
vocabulary. Server-side presentation of these new fields is not yet implemented.
The current pipeline does not populate activity_assessments automatically, so
suspected-disabled/recovery inference abstains until explicit activity evidence
is supplied. Stationary and scoring-visit summaries run automatically.

Validation: 10 focused tests passed. Not yet evaluated on an independent full match.
