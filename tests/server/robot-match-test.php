<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/server/neptune_secure/robot-detector-jobs.php';
function check($ok,$why){if(!$ok)throw new RuntimeException($why);echo "PASS $why\n";}
$root=sys_get_temp_dir().'/robot-match-test-'.bin2hex(random_bytes(4));mkdir($root,0700);$j=new RobotDetectorJobs($root,1);$c=['id'=>str_repeat('a',32)];
try{
 $j->poll($c,['version'=>'3.2.81']);$r=$j->queue('test_robot',['video_id'=>'abcdefghijk','match_key'=>'2026test_qm1'],4);
 check($j->claim($c)===null,'old helper cannot turn a match test into training');
 $j->poll($c,['version'=>'3.2.82','capabilities'=>['test_robot_v1','untrusted']]);$claimed=$j->claim($c);check($claimed['id']===$r['id'],'capable helper receives test');
 $base=['request_id'=>$r['id'],'lease'=>$claimed['lease']];$raw=str_repeat('test',400);$chunk=$base+['offset'=>0,'data_b64'=>base64_encode(substr($raw,0,800))];
 check($j->putRobotTestChunk($c,$chunk)['next_offset']===800,'first chunk stored');check($j->putRobotTestChunk($c,$chunk)['next_offset']===800,'retry is idempotent');
 $bad=$base+['offset'=>900,'data_b64'=>base64_encode('wrong')];try{$j->putRobotTestChunk($c,$bad);throw new RuntimeException('accepted out of order');}catch(InvalidArgumentException){}
 $j->putRobotTestChunk($c,$base+['offset'=>800,'data_b64'=>base64_encode(substr($raw,800))]);
 try{$j->putRobotTest($c,$base+['chunked'=>true,'size'=>1600,'sha256'=>str_repeat('0',64)]);throw new RuntimeException('accepted corrupt upload');}catch(InvalidArgumentException){}
 $rec=$j->putRobotTest($c,$base+['chunked'=>true,'size'=>1600,'sha256'=>hash('sha256',$raw),'title'=>'Editable title','description'=>'Editable description']);
 check($rec['test']['title']==='Editable title','metadata saved');check($j->robotTests()[0]['has_video'],'finished test appears in gallery');check(file_get_contents($j->robotTestVideoPath($r['id']))===$raw,'playback serves exact transferred bytes');
}finally{exec('rm -rf '.escapeshellarg($root));}
