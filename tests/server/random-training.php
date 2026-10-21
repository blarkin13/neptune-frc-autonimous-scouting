<?php
require __DIR__.'/helper-capabilities.php';
$dataset=[];for($i=1;$i<=50;$i++)$dataset[]=['id'=>$i,'key'=>'2026event_qm'.$i];$dataset[]=['id'=>999,'key'=>'2026txcmp1_qm7'];
$a=community_training_order($dataset,str_repeat('a',32));$b=community_training_order($dataset,str_repeat('b',32));
ok($a===community_training_order(array_reverse($dataset),str_repeat('a',32)),'same seed and match set give identical order, independent of catalog order');
ok($a!==$b,'fresh training seed changes the match selection');
ok(count($a)===50&&count(array_unique(array_column($a,'id')))===50,'randomization neither duplicates nor loses eligible matches');
ok(!in_array('2026txcmp1_qm7',array_column($a,'key'),true),'independent Q7 remains reserved');
rejects(fn()=>community_training_order($dataset,'not-a-seed'),'invalid selection seed rejected');
$scoreOnly="match,team,scouter,auto_fuel_score,tele_fuel_score,auto_climb_level,tele_climb_level\nqm1,1,PRIVATE NAME,4,20,0,1\n";
$p=CommunityExternalScouting::parse(json_encode(['/data/2026ne-dcmp-burns-195.scouting.csv'=>$scoreOnly]),'');
ok($p['event_key']==='2026necmp1'&&$p['report']['source_event_key']==='2026ne-dcmp-burns-195','source alias is retained while Burns uses its catalog event code');
ok(!$p['report']['timeline_available']&&$p['report']['timeline_entries']===0&&$p['report']['point_targets']===1,'score-only export supplies a point estimate without invented action timestamps');
ok(!str_contains(json_encode($p),'PRIVATE NAME'),'batch parser discards private scouter columns');
