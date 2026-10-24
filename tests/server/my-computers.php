<?php
declare(strict_types=1);
// My computers: detector runs sent to one computer, per-computer keep-awake settings and helper check-ins.
require dirname(__DIR__,2).'/server/neptune_secure/robot-detector-jobs.php';
$check=function(bool $ok,string $name):void{if(!$ok)throw new RuntimeException('FAIL: '.$name);echo 'PASS '.$name."\n";};
$root=sys_get_temp_dir().'/neptune-computers-'.bin2hex(random_bytes(4));mkdir($root,0700);
$jobs=new RobotDetectorJobs($root,1);$mac=['id'=>str_repeat('a',32)];$pc=['id'=>str_repeat('b',32)];
$r=$jobs->queue('train',['computer'=>$pc['id']],7);
$check(($r['target']??null)===$pc['id']&&$r['message']==='Waiting for the chosen computer','targeted request');
$check($jobs->claim($mac)===null,'another computer cannot claim it');
$claimed=$jobs->claim($pc);$check(($claimed['id']??null)===$r['id'],'the chosen computer claims it');
$jobs->finish($pc,['request_id'=>$r['id'],'lease'=>$claimed['lease'],'ok'=>true]);
$any=$jobs->queue('train',[],7);$check(!isset($any['target'])&&($jobs->claim($mac)['id']??null)===$any['id'],'untargeted run goes to any helper');
$check($jobs->settings($mac['id'])===['keep_awake'=>'jobs'],'keep awake defaults to during jobs');
$jobs->setSettings($mac['id'],['keep_awake'=>'always']);$check($jobs->poll($mac,['busy'=>true,'awake'=>true,'message'=>'Training','version'=>'3.2.35'])['settings']['keep_awake']==='always','helper receives its setting');
$st=$jobs->status($mac['id']);$check($st['awake']&&$st['busy']&&$st['version']==='3.2.35'&&$st['at']>=time()-5,'helper status saved');
try{$jobs->setSettings($mac['id'],['keep_awake'=>'forever']);$check(false,'bad mode accepted');}catch(InvalidArgumentException){$check(true,'unknown keep-awake mode refused');}
try{$jobs->settings('../x');$check(false,'bad id accepted');}catch(InvalidArgumentException){$check(true,'computer id validated');}
exec('rm -rf '.escapeshellarg($root));
