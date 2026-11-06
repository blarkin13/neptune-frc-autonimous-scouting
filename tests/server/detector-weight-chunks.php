<?php
declare(strict_types=1);
// A Medium detector (~40 MB) moves in 1 MiB pieces both ways: whole base64 bodies exceed Neptune's 128 MB PHP memory.
require dirname(__DIR__,2).'/server/neptune_secure/robot-detector-jobs.php';
function check($ok,$why){if(!$ok)throw new RuntimeException($why);echo "PASS $why\n";}
$secure=sys_get_temp_dir().'/weight-chunks-'.bin2hex(random_bytes(4));mkdir($secure,0700);$j=new RobotDetectorJobs($secure,1);$root=$secure.'/robot-detector/1';$c=['id'=>str_repeat('a',32)];
$q=$j->queue('train',[],4);$f=$root.'/requests/'.$q['id'].'.json';$r=json_decode(file_get_contents($f),true);
$r=array_replace($r,['state'=>'claimed','claimed_at'=>time(),'heartbeat_at'=>time(),'computer_id'=>$c['id'],'lease'=>str_repeat('b',32)]);file_put_contents($f,json_encode($r));
$w=random_bytes(2600000);$p=['request_id'=>$r['id'],'lease'=>$r['lease']];
for($o=0;$o<strlen($w);$o+=1048576)$a=$j->putAdoptChunk($c,$p+['offset'=>$o,'data_b64'=>base64_encode(substr($w,$o,1048576))]);
check($a['next_offset']===strlen($w),'trained weights arrive in 1 MiB chunks');
try{$j->adopt($c,$p+['chunked'=>true,'size'=>strlen($w),'sha256'=>str_repeat('0',64)]);check(false,'');}catch(InvalidArgumentException){check(true,'wrong fingerprint refused');}
$out=$j->adopt($c,$p+['chunked'=>true,'size'=>strlen($w),'sha256'=>hash('sha256',$w),'report'=>['x'=>1]]);
check($out['sha256']===hash('sha256',$w),'chunked detector adopted with its fingerprint');
$cur=$j->current(null,true);check(!isset($cur['weights_b64'])&&$cur['weights']['size']===strlen($w),'chunked helpers get size and fingerprint, not the whole file');
$got='';while(strlen($got)<strlen($w))$got.=base64_decode($j->currentChunk(['sha256'=>$out['sha256'],'offset'=>strlen($got)])['data_b64']);
check($got===$w,'helpers download the detector intact in pieces');
check(base64_decode($j->current(null)['weights_b64'])===$w,'older helpers still get weights_b64');
check(!isset($j->current($out['sha256'],true)['weights']),'nothing sent when the helper already has it');
try{$j->currentChunk(['sha256'=>str_repeat('1',64),'offset'=>0]);check(false,'');}catch(InvalidArgumentException){check(true,'stale fingerprint refused');}
