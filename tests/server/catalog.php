<?php
declare(strict_types=1);
require __DIR__.'/../../neptune_secure/community-catalog.php';
function ok($v,$name){if(!$v)throw new RuntimeException($name);echo 'PASS '.$name."\n";}
$m=['key'=>'2026test_qm7','comp_level'=>'qm','match_number'=>7,'set_number'=>1,'alliances'=>['red'=>['team_keys'=>['frc1','frc2','frc3']],'blue'=>['team_keys'=>['frc4','frc5','frc6']]],'videos'=>[['type'=>'youtube','key'=>'_2hGzZRvw0A']]];
$r=CommunityCatalog::normalize($m,'2026test','Test event');ok($r['ready']===1&&$r['roster']['blue']===[4,5,6]&&$r['video_id']==='_2hGzZRvw0A','public roster and video mapping');
$m['videos']=[];$r=CommunityCatalog::normalize($m,'2026test','Test');ok($r['ready']===0&&$r['video_id']==='','missing video remains visible but unavailable');
$m['videos']=[['type'=>'youtube','key'=>'https://malicious.invalid']];ok(CommunityCatalog::normalize($m,'2026test','Test')['video_id']==='','invalid video ID rejected');
$m['alliances']['blue']['team_keys']=['frc1','frc5','frc6'];ok(CommunityCatalog::normalize($m,'2026test','Test')['missing_roster'],'duplicate team cannot become ready');
$m['key']='2025other_qm7';ok(CommunityCatalog::normalize($m,'2026test','Test')===null,'cross-event matches rejected');
CommunityCatalog::season(2025);ok(true,'REEFSCAPE season available');
foreach([2024,(int)gmdate('Y')+2] as $year){try{CommunityCatalog::season($year);throw new RuntimeException('Invalid season accepted');}catch(CommunityAnalysisError $e){ok($e->httpStatus===422,'season boundary '.$year);}}
$db=new PDO('sqlite::memory:');$calls=[];$fetch=function($path,$ttl)use(&$calls){$calls[]=$path;return [['key'=>'2026b','name'=>'B','start_date'=>'2026-04-01'],['key'=>'2026a','name'=>'A','start_date'=>'2026-03-01'],['key'=>'2025x','name'=>'Wrong year']];};$catalog=new CommunityCatalog($db,$fetch);$events=$catalog->events(2026);ok(array_column($events,'key')===['2026a','2026b'],'all season events filtered and sorted');
