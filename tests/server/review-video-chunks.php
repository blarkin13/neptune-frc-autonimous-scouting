<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/server/neptune_secure/robot-detector-jobs.php';
function check($ok,$why){if(!$ok)throw new RuntimeException($why);echo "PASS $why\n";}
$secure=sys_get_temp_dir().'/review-chunks-'.bin2hex(random_bytes(4));mkdir($secure,0700);$j=new RobotDetectorJobs($secure,1);$root=$secure.'/robot-detector/1';$c=['id'=>str_repeat('a',32)];
$q=$j->queue('train',[],4);$f=$root.'/requests/'.$q['id'].'.json';$r=json_decode(file_get_contents($f),true);   // claimed by this helper
$r=array_replace($r,['state'=>'claimed','claimed_at'=>time(),'heartbeat_at'=>time(),'computer_id'=>$c['id'],'lease'=>str_repeat('b',32)]);file_put_contents($f,json_encode($r));
check(is_array($r)&&$r['kind']==='train','helper claims a training run');
$video=random_bytes(2500000);$p=['request_id'=>$r['id'],'lease'=>$r['lease']];
for($o=0;$o<strlen($video);$o+=1048576){$a=$j->putReviewChunk($c,$p+['offset'=>$o,'data_b64'=>base64_encode(substr($video,$o,1048576))]);}
check($a['next_offset']===strlen($video),'review video arrives in 1 MiB chunks');
try{$j->putReview($c,$p+['chunked'=>true,'size'=>strlen($video),'sha256'=>str_repeat('0',64)],null);check(false,'wrong hash refused');}catch(InvalidArgumentException){check(true,'wrong hash refused');}
$out=$j->putReview($c,$p+['chunked'=>true,'size'=>strlen($video),'sha256'=>hash('sha256',$video),'title'=>'t'],null);
check($out['review']['status']==='youtube_not_connected'&&file_get_contents($root.'/review/'.$r['id'].'.mp4')===$video,'chunked review video is saved intact');
try{$j->putRobotTestChunk($c,$p+['offset'=>0,'data_b64'=>base64_encode('x')]);check(false,'');}catch(InvalidArgumentException){check(true,'match-test chunks refused for a training run');}
