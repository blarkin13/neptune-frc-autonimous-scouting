<?php
declare(strict_types=1);
// Remote helper updates: owner requests and auto-update, latest versions from the feeds, and requests clearing on check-in.
require dirname(__DIR__,2).'/server/neptune_secure/autoscout-train-overview.php';
$check=function(bool $ok,string $name):void{if(!$ok)throw new RuntimeException('FAIL: '.$name);echo 'PASS '.$name."\n";};
$tmp=sys_get_temp_dir().'/neptune-updates-'.bin2hex(random_bytes(4));mkdir($tmp.'/downloads/mac',0700,true);mkdir($tmp.'/downloads/windows');mkdir($tmp.'/secure');
file_put_contents($tmp.'/downloads/mac/appcast.xml','<rss><channel><item><sparkle:version>1</sparkle:version><sparkle:shortVersionString>3.2.63</sparkle:shortVersionString></item></channel></rss>');
file_put_contents($tmp.'/downloads/windows/latest.json',json_encode(['version'=>'6.5.34']));
$GLOBALS['neptune_downloads_dir']=$tmp.'/downloads';
$check(helper_latest_version('Mac · Apple M2')==='3.2.63'&&helper_latest_version('Windows · NVIDIA RTX 4070')==='6.5.34','latest versions come from the Mac appcast and Windows feed');
$check(helper_latest_version('Linux · CPU')===null&&helper_latest_version('')===null,'no feed or unknown platform: no latest version');

$jobs=new RobotDetectorJobs($tmp.'/secure',1);$c=['id'=>'0123456789abcdef0123456789abcdef'];
$s=$jobs->settings('0123456789abcdef0123456789abcdef');
$check($s['keep_awake']==='jobs'&&$s['auto_update']===false&&$s['update_requested']===null,'defaults: no update requested, auto-update off');
$jobs->setSettings('0123456789abcdef0123456789abcdef',['update'=>'request','auto_update'=>true]);$s=$jobs->settings('0123456789abcdef0123456789abcdef');
$check($s['update_requested']>0&&$s['auto_update']===true&&$s['keep_awake']==='jobs','request and auto-update save without touching keep-awake');
try{$jobs->setSettings('0123456789abcdef0123456789abcdef',['update'=>'now']);$bad=false;}catch(InvalidArgumentException){$bad=true;}
$check($bad,'only request or cancel are accepted');

$r=$jobs->poll($c,['version'=>'6.5.33','platform'=>'Windows · CPU','remote_update'=>true,'update'=>'Downloading 6.5.34…']);
$check($r['settings']['update_requested']>0&&$r['settings']['latest']==='6.5.34','an older helper keeps its request and learns the latest version');
$u=autoscout_update_state($jobs->status('0123456789abcdef0123456789abcdef'),$jobs->settings('0123456789abcdef0123456789abcdef'));
$check($u['behind']&&$u['remote']&&$u['message']==='Downloading 6.5.34…','status shows behind, remote-capable and the helper\'s update message');
$r=$jobs->poll($c,['version'=>'6.5.34','platform'=>'Windows · CPU','remote_update'=>true]);
$check($r['settings']['update_requested']===null&&$r['settings']['auto_update']===true,'reporting the latest version clears the request, auto-update stays');
$u=autoscout_update_state($jobs->status('0123456789abcdef0123456789abcdef'),$jobs->settings('0123456789abcdef0123456789abcdef'));
$check(!$u['behind']&&$u['message']===null,'up to date: not behind');
$jobs->setSettings('0123456789abcdef0123456789abcdef',['update'=>'request']);
$f=$tmp.'/secure/robot-detector/1/computers/0123456789abcdef0123456789abcdef.json';$d=json_decode(file_get_contents($f),true);$d['update_requested']=time()-90000;file_put_contents($f,json_encode($d));
$r=$jobs->poll($c,['version'=>'6.5.20','platform'=>'Windows · CPU']);
$check($r['settings']['update_requested']===null,'a request older than a day lapses');
exec('rm -rf '.escapeshellarg($tmp));
