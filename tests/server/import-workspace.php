<?php
require __DIR__.'/external-scouting.php';
require dirname(__DIR__,2).'/neptune_secure/community-source-mapping.php';
require dirname(__DIR__,2).'/neptune_secure/community-reset.php';
$mapping=['match'=>'match','team'=>'robot','action'=>'action','phase'=>'phase','time'=>'seconds','clock'=>'phase_elapsed'];
$csv="match,robot,action,phase,seconds,private_email\nqm1,1,scoring,auto,10,PRIVATE@example.invalid\nqm1,2,attempted_defense,teleop,30,PRIVATE@example.invalid\n";
$mapped=community_source_mapped($csv,'2026week0',$mapping);ok($mapped['report']['timeline_entries']===2,'mapped CSV keeps explicit actions');ok(!str_contains(json_encode($mapped),'PRIVATE@'),'unmapped private fields never persist');
$json=json_encode(['records'=>[['match'=>'qm1','robot'=>'1','action'=>'scoring','phase'=>'auto','seconds'=>'0:10','private_email'=>'PRIVATE']]]);ok(count(community_source_mapped($json,'2026week0',$mapping)['records'])===1,'flat JSON records map without vendor assumptions');
rejects(fn()=>community_source_mapped(str_replace('scoring,auto','unknown_tag,auto',$csv),'2026week0',$mapping),'unknown action blocks import');
rejects(fn()=>community_source_mapped(str_replace('auto,10','auto,99',$csv),'2026week0',$mapping),'invalid phase timestamp rejected');
$remaining=community_source_mapped($csv,'2026week0',array_replace($mapping,['clock'=>'phase_remaining']));ok($remaining['records'][1]['payload']['timeline'][0]['time_ms']===110000,'remaining clock is explicitly converted');
ok($remaining['file_sha256']!==$mapped['file_sha256'],'changed mapping invalidates preview identity');
$multi=community_source_mapped($csv."qm1,1,scoring,teleop,10,PRIVATE@example.invalid\n",'2026week0',$mapping);ok(count($multi['records'])===2&&count($multi['records'][0]['payload']['timeline'])===2,'multiple actions are grouped per robot instead of conflicting');
$save=$svc->save($mapped,7,'https://example.org/team-export');$rows=$svc->training(2026);$mappedRows=array_values(array_filter($rows,fn($r)=>$r['definition_version']==='mapped-actions-v1'));ok(count($mappedRows)===2&&$mappedRows[1]['external']['weak_supervision']===true,'generic imported actions reach the actual training snapshot as outside examples');
rejects(fn()=>$svc->save($mapped,7,'javascript:alert(1)'),'source attribution rejects script URL');
file_put_contents('/tmp/neptune-mapped-test.ndjson',implode("\n",array_map(fn($r)=>json_encode($r),$mappedRows))."\n");
// The reset uses the production service, but a fully isolated SQLite database.
foreach(['community_match_catalog','community_publications','community_submissions','community_leases','community_attempt_media','community_attempts','community_pair_requests','community_pair_limits'] as $t)$db->exec("CREATE TABLE IF NOT EXISTS `$t`(id TEXT)");
$db->exec('CREATE TABLE IF NOT EXISTS community_devices(id TEXT,revoked INT DEFAULT 0)');
$before=$db->query('SELECT * FROM community_video_labels ORDER BY id')->fetchAll(PDO::FETCH_ASSOC);$history=$db->query('SELECT * FROM community_video_label_reviews ORDER BY id')->fetchAll(PDO::FETCH_ASSOC);
rejects(fn()=>community_reset_machine_data($db,'yes'),'reset requires exact typed confirmation');
$db->exec("UPDATE community_learning_jobs SET state='running'");rejects(fn()=>community_reset_machine_data($db,'RESET MACHINE DATA'),'reset cannot race active training');ok((int)$db->query('SELECT COUNT(*) FROM community_external_imports')->fetchColumn()>0,'blocked reset keeps imported data');
$db->exec("UPDATE community_learning_jobs SET state='failed'");community_reset_machine_data($db,'RESET MACHINE DATA');ok($before===$db->query('SELECT * FROM community_video_labels ORDER BY id')->fetchAll(PDO::FETCH_ASSOC)&&$history===$db->query('SELECT * FROM community_video_label_reviews ORDER BY id')->fetchAll(PDO::FETCH_ASSOC),'reset preserves every human tag and its history');ok((int)$db->query('SELECT COUNT(*) FROM community_learning_jobs')->fetchColumn()===0&&(int)$db->query('SELECT COUNT(*) FROM community_external_imports')->fetchColumn()===0,'reset clears machine work and outside imports');ok((int)$db->query('SELECT COUNT(*) FROM community_training_computers WHERE revoked=0')->fetchColumn()===0,'reset revokes old workers so stale results cannot upload');
// Complete source counts become estimates, never official per-robot scores.
$points=CommunityExternalScouting::reportedPoints(['fields'=>['auto_fuel_score'=>'5','tele_fuel_score'=>'20','auto_climb_level'=>'1','tele_climb_level'=>'3'],'warnings'=>[]]);
ok($points['robot_points']===70,'2026 source points use fuel 1, auto climb 15, teleop level 3 30');
ok(CommunityExternalScouting::reportedPoints(['fields'=>['auto_fuel_score'=>'5','tele_fuel_score'=>'20','auto_climb_level'=>'2','tele_climb_level'=>'3'],'warnings'=>[]])===null,'invalid auto climb stays unknown');
ok(CommunityExternalScouting::reportedPoints(['fields'=>['auto_fuel_score'=>'5','tele_fuel_score'=>'20'],'warnings'=>[]])===null,'missing climb fields are not silently zero');
$source="match,team,auto_fuel_score,tele_fuel_score,auto_climb_level,tele_climb_level,timeline\nqm1,1,5,20,1,3,18:auto_fuel_score:5\n";
$parsed=CommunityExternalScouting::parse($source,'2026week0');$svc->save($parsed,7,'https://public.viperscout.com/export.html#event=2026week0');$scoreRows=array_values(array_filter($svc->training(2026),fn($r)=>$r['definition_version']==='viper-2026-points-v1'));
ok(count($scoreRows)===1&&$scoreRows[0]['scoring']['robot_points']===70&&$scoreRows[0]['certainty']==='uncertain','source scoring enters snapshot as an attributed estimate');
ok($scoreRows[0]['scoring']['alliance_score']===null&&$scoreRows[0]['scoring']['source']==='external_scouting_estimate','unknown alliance total is never fabricated');
ok(community_import_score_target($scoreRows[0]),'server validates complete imported point provenance');
file_put_contents('/tmp/neptune-imported-score-test.ndjson',json_encode($scoreRows[0])."\n");
