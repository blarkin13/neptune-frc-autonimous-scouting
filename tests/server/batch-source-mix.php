<?php
require __DIR__.'/page-control.php';
$seed=str_repeat('d',32);
$mix=[['id'=>1,'key'=>'2026test_qm1','tags'=>4,'human_scores'=>0,'external'=>0],['id'=>2,'key'=>'2026test_qm2','tags'=>0,'human_scores'=>1,'external'=>8],['id'=>3,'key'=>'2026test_qm3','tags'=>0,'human_scores'=>0,'external'=>5],['id'=>4,'key'=>'2026test_qm4','tags'=>0,'human_scores'=>0,'external'=>0,'imported_scores'=>6],['id'=>5,'key'=>'2026test_qm5','tags'=>0,'human_scores'=>0,'external'=>8],['id'=>999,'key'=>'2026txcmp1_qm7','tags'=>5]];
$a=community_training_select($mix,$seed,4,2,2,['2026test_qm2']);
ok(count($a)===4&&count(array_filter($a,'community_training_is_human'))===2,'source quotas include exactly two human and two imported-only matches');
ok(count(array_unique(array_column($a,'id')))===4,'mixed-source match is counted once');
ok(in_array('2026test_qm2',array_column($a,'key'),true),'explicit human match is always included');
ok($a===community_training_select(array_reverse($mix),$seed,4,2,2,['2026test_qm2']),'source quotas and order are deterministic for a saved seed');
ok(!in_array('2026txcmp1_qm7',array_column($a,'key'),true),'source quotas cannot include reserved independent footage');
rejects(fn()=>community_training_select($mix,$seed,4,2,1),'sum mismatch rejected');
rejects(fn()=>community_training_select($mix,$seed,4,3,1),'insufficient human quota rejected');
rejects(fn()=>community_training_select($mix,$seed,2,1,1,['2026test_qm1','2026test_qm2']),'pins cannot exceed human quota');
rejects(fn()=>community_training_select($mix,$seed,2,1,1,['2026test_qm3']),'imported match cannot be pinned as human');
rejects(fn()=>community_training_select($mix,$seed,2,1,1,['2026test_qm2','2026test_qm2']),'duplicate pins rejected');
rejects(fn()=>community_training_select($mix,$seed,2,1,1,['2026txcmp1_qm7']),'reserved match cannot be pinned');
foreach(['1.5','-1','2x',[],null] as $bad)rejects(fn()=>community_training_count($bad),'invalid count rejected');
ok(community_training_count('0')===0&&community_training_count('12')===12,'zero and whole counts accepted');
rejects(fn()=>community_training_pins('{"key":"match"}'),'pins must be an explicit list');
$db->exec("UPDATE community_learning_jobs SET state='cancelled' WHERE state IN ('remote_queued','remote_running','remote_paused','queued','running','server_paused')");
$batch=$control->queue(2026,7,'server',null,2,$seed,2,0,['2026test_qm8']);
$stored=json_decode($db->query("SELECT control_json FROM community_learning_jobs WHERE id='".$batch['id']."'")->fetchColumn(),true);
ok($stored['source_counts']===['human_tagged'=>2,'imported_scouting'=>0]&&$stored['pinned_human_matches']===['2026test_qm8'],'queued job freezes actual source counts and pinned human choices');

ok(!community_training_engine_ready(['engine_version'=>'2.2.0-temporal-preview1'])&&community_training_engine_ready(['engine_version'=>'2.2.1-clock-camera-preview1']),'old temporal helper cannot claim corrected-engine work');
