<?php
declare(strict_types=1);
// Shared robot-identity model: status always, the model only after it passed the independent check; every helper fetches it.
require dirname(__DIR__,2).'/server/neptune_secure/tracking-identity.php';
$check=function(bool $ok,string $name):void{if(!$ok)throw new RuntimeException('FAIL: '.$name);echo 'PASS '.$name."\n";};
$tmp=sys_get_temp_dir().'/neptune-tracking-'.bin2hex(random_bytes(4));mkdir($tmp);
$s=new TrackingIdentityShare($tmp,1);$mac=['id'=>str_repeat('a',32)];$pc=['id'=>str_repeat('b',32)];
$model=['weights'=>[.1,-.2,.3,.4,-.5],'bias'=>-1.2];
$check($s->current(null)===['model'=>null],'no shared model at first');
$s->put($mac,['report'=>['version'=>'review-learning-v1','status'=>'candidate','reason'=>'Independent check still required','pairs'=>2311,'matches'=>['2026txcmp1_qm1','bad key!'],'validation'=>['precision'=>0,'tp'=>0]],'model'=>$model]);
$check($s->current(null)===['model'=>null],'a model that has not passed the independent check is not shared');
$db=new PDO('sqlite::memory:');$db->exec('CREATE TABLE community_identity_reviews(organization_id INT,source_sha256 TEXT,match_key TEXT,updated_at INT)');$db->exec("INSERT INTO community_identity_reviews VALUES(1,'x','2026txcmp1_qm6',100)");
$sum=$s->summary($db,1,[str_repeat('a',32)=>'Mac']);
$check($sum['report']['computer']==='Mac'&&$sum['report']['matches']===['2026txcmp1_qm1']&&$sum['shared']===null&&$sum['reviews'][0]['match_key']==='2026txcmp1_qm6','status shows who trained, valid match keys only, and the saved reviews');
$bad=$model;$bad['weights'][0]=INF;
$s->put($mac,['report'=>['version'=>'review-learning-v1','status'=>'active','identity_validation'=>['passed'=>true,'correct'=>200]],'model'=>$bad]);
$check($s->current(null)===['model'=>null],'invalid weights are never shared');
$s->put($mac,['report'=>['version'=>'review-learning-v1','status'=>'active','matches'=>['2026txcmp1_qm1','2026txcmp1_qm3'],'identity_validation'=>['passed'=>true,'correct'=>210,'wrong'=>2]],'model'=>$model]);
$cur=$s->current(null);
$check($cur['model']===['weights'=>[.1,-.2,.3,.4,-.5],'bias'=>-1.2]&&$cur['trained_by']===str_repeat('a',32),'a model that passed is shared');
$check($s->current($cur['sha256'])===['unchanged'=>true,'sha256'=>$cur['sha256']],'a helper that already has it gets no download');
$check($s->summary($db,1,[str_repeat('a',32)=>'Mac'])['shared']['trained_by']==='Mac','Tracking page names the computer that trained the shared model');
try{$s->put($pc,['report'=>['version'=>'../x']]);$refused=false;}catch(InvalidArgumentException){$refused=true;}
$check($refused,'malformed reports are refused');
exec('rm -rf '.escapeshellarg($tmp));
