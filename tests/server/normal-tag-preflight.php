<?php
require dirname(__DIR__,2).'/neptune_secure/community-learning.php';
function check($yes,$message){if(!$yes)throw new RuntimeException($message);echo "PASS $message\n";}
$row=['season'=>2026,'match_key'=>'2026test_qm1','certainty'=>'observed','definition_version'=>'neptune-match-tags-v1','tag_key'=>'scoring','label_scope'=>'moment','polarity'=>'present'];
$pos=json_encode($row)."\n".json_encode($row)."\n";
$r=community_learning_baseline_preflight($pos,2026);check($r['can_run_baseline']&&$r['actions']===2,'ordinary positives unlock preparation without human counterexamples');
$r=community_learning_baseline_preflight($pos.json_encode(array_merge($row,['scoring'=>['mode'=>'alliance_share'],'label_scope'=>'match'])),2026);check($r['scoring_estimates']===1&&$r['actions']===2,'score estimates separate from action examples');
$r=community_learning_baseline_preflight($pos,2025);check($r['actions']===0&&!$r['can_run_baseline'],'seasons isolated');
$r=community_learning_baseline_preflight($pos.json_encode(array_merge($row,['polarity'=>'absent']))."\n".json_encode(array_merge($row,['polarity'=>'absent'])),2026);check($r['can_run_baseline'],'existing suitable baseline data remains supported');
