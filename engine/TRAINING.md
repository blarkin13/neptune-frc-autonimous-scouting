# Shared game models

Community tags are stored in Neptune’s database. Training, evaluation and release management run on the server at admin/community-learning.php, protected by platform owner access. Contributors do not train local models.

The helper loads seasons and events without a connection. Sign in when starting a match. Use Reload events to retry or change seasons. Shared models shows release status; each match run checks Neptune again, so a retired release or withdrawn training label cannot silently stay active. When there is no evaluated model, supported scoreboard/bumper reading still works.

Each game has its own pack and model. 2026 REBUILT has a reader; 2025 REEFSCAPE rules are configured but its broadcast layout remains unverified. Future games require a server game pack.

The initial robot image/motion classifier is experimental. No released tag model or accuracy equivalent to six scouts has been demonstrated. Sparse tags are useful labels, but cannot measure complete-match recall. Scoring-start tags do not teach point attribution.
