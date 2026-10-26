<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/server/neptune_secure/robot-label-frames.php';
require dirname(__DIR__,2).'/server/neptune_secure/robot-detector-jobs.php';
$root=sys_get_temp_dir().'/neptune-frames-'.bin2hex(random_bytes(4));mkdir($root,0700);
$check=function(bool $yes,string $s){if(!$yes)throw new RuntimeException($s);echo 'PASS '.$s."\n";};
$jpg=file_get_contents($argv[1]);$video='Q45IuedY5hc';$source=str_repeat('c',64);$store=new RobotLabelFrames($root,1);
$m=$store->put($video,28000,base64_encode($jpg),$source);
$check($store->get($video,28000,$m['sha256'])['bytes']===$jpg,'exact image round trip');
$check(count($store->index($video))===1,'index has frame metadata');
$check((new RobotLabelFrames($root,2))->get($video,28000)===null,'organization isolation');
foreach([['../bad',28000,base64_encode($jpg),$source],[$video,-1,base64_encode($jpg),$source],[$video,0,base64_encode('not jpeg'),$source]] as $args){try{$store->put(...$args);throw new RuntimeException('invalid frame accepted');}catch(InvalidArgumentException){$check(true,'invalid image or path rejected');}}
$jobs=new RobotDetectorJobs($root,1);$pc=['id'=>str_repeat('a',32)];$jobs->queue('prepare',['video_id'=>$video,'match_key'=>'2026tnkn_qm5'],1);$jobs->poll($pc,['version'=>'6.5.15']);$check($jobs->claim($pc)===null,'old helper cannot silently finish a source-still request without images');
$jobs->poll($pc,['version'=>'6.5.16']);$req=$jobs->claim($pc);
$payload=['request_id'=>$req['id'],'lease'=>$req['lease'],'video_id'=>$video,'t_ms'=>48000,'source_sha256'=>$source,'image_b64'=>base64_encode($jpg)];
$check($jobs->putLabelFrame($pc,$payload)['t_ms']===48000,'claimed preparation uploads a frame');
try{$jobs->putLabelFrame(['id'=>str_repeat('b',32)],$payload);throw new RuntimeException('wrong helper accepted');}catch(InvalidArgumentException){$check(true,'wrong helper rejected');}
try{$payload['video_id']='AAAAAAAAAAA';$jobs->putLabelFrame($pc,$payload);throw new RuntimeException('wrong video accepted');}catch(InvalidArgumentException){$check(true,'wrong video rejected');}
$f=fopen($root.'/robot-label-frames/1/'.$video.'/quota.jpg','w');ftruncate($f,192*1024*1024);fclose($f);
try{$store->put($video,92000,base64_encode($jpg),$source);throw new RuntimeException('quota ignored');}catch(InvalidArgumentException){$check(true,'storage quota stops new files without deleting saved frames');}
exec('rm -rf '.escapeshellarg($root));
