# Community tag scouting workflow — October 18, 2026

The user withdrew the student development workspace and requested robot tags with scoring estimates instead of match summaries. The existing video tagging page, its JavaScript, and its CSS were preserved byte for byte.

## User flow

Community → Watch & tag: choose a season, event and match; choose a robot; tag observed actions; optionally enter whole-match points or an alliance-share percentage. The other score field updates automatically. One robot or a few clear observations are useful. Tags save immediately without review.

Saved tags & scores lists matches with current-source contributions and displays each robot's timestamped tags, uncertainty and score estimates. Categories distinguish autonomous from endgame outcomes. Different contributors' entries remain separate; overlapping tags and estimates are never summed. A missing entry remains unknown.

Train & test has three short steps: download/open the trainer, choose Run 1 match or Continue, then request training on Neptune. The latest result explains preparation, model fitting and testing separately. The current evaluation control accepts a prepared reference benchmark; a simple select-a-match test screen is not implemented. The experimental learner predicts actions, not scoring amounts.

## Removed

Maintenance Console rollbacks removed Neptune_Workspace_Navigation_v1_1, Neptune_Workspace_Layout_v1_1 and Neptune_Student_Workspace_v1. The student page, private service, source ZIP, editor CSS/JS, navigation and access UI are gone. The student URL now returns 404.

Migration community.student.workspace.removed.v1 checks all three workspace tables before dropping any. It refuses if any saved record exists. Live verification returned `student_workspace_tables_remaining: []`; the tables were empty. Community tags, scoring evidence and learning jobs were retained. Migration audit records remain in the existing tracker.

Summary download/setup/review pages now lead to tagging. Summary API operations return 410; shared event/match browsing remains available. The Command Center helper-summary card and summary settings controls were removed. Historical summary records were retained, without publication links or active submission workflow.

## Verification and recovery

- All patch PHP passed the deployed Maintenance Console validator.
- Cleanup test verifies exact table scope, empty-only removal, checks before any DROP, repeat safety, and preservation of tags/jobs.
- Live: selected Mercury event, saw prior contributions (27 and 73 entries), opened robot results, confirmed saved points/percentages, selected robot 2881 and opened/cancelled the existing scoring editor. No test labels or score estimates were saved.
- Live trainer dashboard shows actual saved counts (including uncertain human score estimates), separately from training eligibility.
- Initial simplification package: Neptune_Tag_Scouting_Simple_v1.zip, backup 20261018-185129-480a.
- Display correction package: Neptune_Tag_Scouting_Clarity_v1_1.zip, backup 20261018-185559-c6ed.
- File rollback does not restore dropped empty workspace tables; this is an intentional feature withdrawal.
