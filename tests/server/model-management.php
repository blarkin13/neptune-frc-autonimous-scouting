<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/neptune_secure/community-analysis.php';
require dirname(__DIR__,2).'/neptune_secure/community-model-management.php';
require dirname(__DIR__,2).'/neptune_secure/community-training-control.php';
$db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$db->exec('CREATE TABLE community_learning_jobs(id TEXT PRIMARY KEY,season INTEGER,state TEXT,created_at INTEGER,model_json TEXT,report_json TEXT,benchmark_json TEXT,snapshot_ndjson TEXT,control_json TEXT);
CREATE TABLE community_learning_releases(season INTEGER PRIMARY KEY,job_id TEXT,released_by INTEGER,released_at INTEGER);
CREATE TABLE human_labels(id INTEGER PRIMARY KEY,label TEXT);INSERT INTO human_labels VALUES(1,\'human observation\');
CREATE TABLE outside_imports(id INTEGER PRIMARY KEY,data TEXT);INSERT INTO outside_imports VALUES(1,\'imported scouting\');');
$count=0;function model_check(bool $ok,string $label):void{global $count;if(!$ok)throw new RuntimeException($label);$count++;echo 'PASS '.$label."\n";}
function model_reject(callable $fn,int $status,string $label):void{try{$fn();}catch(CommunityAnalysisError $e){model_check($e->httpStatus===$status,$label);return;}throw new RuntimeException('Request accepted: '.$label);}
function saved_model(PDO $db,string $id,int $season=2026):void{$db->prepare('INSERT INTO community_learning_jobs VALUES(?,?,?,?,?,?,?,?,?)')->execute([$id,$season,'candidate',time(),json_encode(['model_id'=>str_repeat('c',64),'heads'=>['gb:score_10_fuel'=>['weights'=>[1,2,3]]]]),'saved report','saved evaluation','saved training labels',json_encode(['kind'=>'training'])]);}
$a=str_repeat('a',32);$b=str_repeat('b',32);saved_model($db,$a);saved_model($db,$b,2025);$svc=new CommunityModelManagement($db);
$list=$svc->saved(2026);model_check(count($list)===1&&$list[0]['id']===$a&&$list[0]['bytes']>0,'saved models are scoped to the selected game and include stored size');
$before=$db->query('SELECT * FROM community_learning_jobs ORDER BY id')->fetchAll(PDO::FETCH_ASSOC);
model_reject(fn()=>$svc->delete(2026,$a,'delete'),422,'deletion requires exact typed confirmation');
model_reject(fn()=>$svc->delete(2025,$a,'DELETE MODEL'),404,'another game cannot delete the selected model');
model_reject(fn()=>$svc->delete(2026,'../../unsafe','DELETE MODEL'),422,'model deletion accepts IDs, not filesystem paths');
model_check($before===$db->query('SELECT * FROM community_learning_jobs ORDER BY id')->fetchAll(PDO::FETCH_ASSOC),'rejected requests leave stored models untouched');
$test=str_repeat('d',32);$db->prepare('INSERT INTO community_learning_jobs(id,season,state,snapshot_ndjson,report_json,model_json) VALUES(?,2026,?,?,?,?)')->execute([$test,'test_queued',json_encode(['model_job'=>$a]),'prediction report','copied test model']);
foreach(['test_queued','test_running','evaluation_queued','evaluation_running'] as $state){$db->prepare('UPDATE community_learning_jobs SET state=? WHERE id=?')->execute([$state,$test]);model_reject(fn()=>$svc->delete(2026,$a,'DELETE MODEL'),409,'model used by '.$state.' cannot be deleted');}
model_check($svc->saved(2026)[0]['in_use'],'model list identifies a model in use');
$db->prepare("UPDATE community_learning_jobs SET state='test_complete' WHERE id=?")->execute([$test]);
$db->prepare('INSERT INTO community_learning_releases VALUES(?,?,7,?)')->execute([2026,$a,time()]);$db->prepare('INSERT INTO community_learning_releases VALUES(?,?,7,?)')->execute([2025,$b,time()]);
model_check($svc->saved(2026)[0]['released'],'model list identifies the released model');
model_reject(fn()=>$svc->delete(2026,$a,'DELETE MODEL'),409,'released model requires explicit withdrawal consent');
model_check($db->query('SELECT COUNT(*) FROM community_learning_releases')->fetchColumn()==2,'failed withdrawal consent leaves releases untouched');
$old=$db->query("SELECT * FROM community_learning_jobs WHERE id='$a'")->fetch(PDO::FETCH_ASSOC);$result=$svc->delete(2026,$a,'DELETE MODEL',true);
$new=$db->query("SELECT * FROM community_learning_jobs WHERE id='$a'")->fetch(PDO::FETCH_ASSOC);
model_check($result['withdrawn']&&$new['model_json']===null&&$new['state']==='model_deleted','confirmed deletion clears the model and marks the retained run');
model_check($db->query('SELECT job_id FROM community_learning_releases')->fetchColumn()===$b,'withdrawal affects only the selected game and model');
foreach(['report_json','benchmark_json','snapshot_ndjson','control_json'] as $key)model_check($new[$key]===$old[$key],'model deletion preserves '.$key);
model_check($db->query("SELECT report_json FROM community_learning_jobs WHERE id='$test'")->fetchColumn()==='prediction report','past prediction results remain saved');
model_check($db->query('SELECT label FROM human_labels')->fetchColumn()==='human observation'&&$db->query('SELECT data FROM outside_imports')->fetchColumn()==='imported scouting','human labels and imports remain untouched');
model_check($svc->saved(2026)===[],'deleted model is removed from the saved-model list');
model_check($svc->delete(2026,$a,'DELETE MODEL')['already_deleted'],'retrying a successful deletion is safe');
model_reject(fn()=>$svc->release(2026,$a,7),422,'deleted model cannot be released afterward');
$control=new CommunityTrainingControl($db);
model_reject(fn()=>$control->model(2026,$a),422,'deleted model cannot be selected for a fresh prediction');
$queue=new ReflectionMethod(CommunityTrainingControl::class,'queueModelWork');
model_reject(fn()=>$queue->invoke($control,2026,7,['executor'=>'server'],'trial',['model_job'=>$a],['model_id'=>str_repeat('c',64)]),409,'a queued prediction rechecks model existence inside its transaction');
echo $count." model-management checks passed\n";
