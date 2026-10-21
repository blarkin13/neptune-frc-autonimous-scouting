<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/neptune_secure/community-analysis.php';
require dirname(__DIR__,2).'/neptune_secure/community-training-control.php';
$db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$db->exec('CREATE TABLE community_learning_jobs(id TEXT PRIMARY KEY,season INTEGER,state TEXT,created_by INTEGER,created_at INTEGER,started_at INTEGER,finished_at INTEGER,heartbeat_at INTEGER,message TEXT,snapshot_sha256 TEXT,snapshot_ndjson TEXT,report_json TEXT,model_json TEXT,benchmark_json TEXT,control_json TEXT);
CREATE TABLE community_training_leases(job_id TEXT PRIMARY KEY,computer_id TEXT,lease_hash TEXT,expires_at INTEGER,result_hash TEXT,game_json TEXT);
CREATE TABLE community_training_computers(id TEXT PRIMARY KEY,user_id INTEGER,last_seen INTEGER,revoked INTEGER DEFAULT 0);');
$n=0;function storage_check(bool $ok,string $why):void{global $n;if(!$ok)throw new RuntimeException($why);echo 'PASS '.$why."\n";$n++;}
$id=str_repeat('a',32);$computer=['id'=>str_repeat('b',32),'user_id'=>7];$token=str_repeat('c',64);$snapshot=str_repeat('saved-human-label-and-import-data;',85000);
$controlData=['kind'=>'training','executor'=>'helper','computer_id'=>$computer['id'],'matches_done'=>0,'matches_total'=>40,'stop_requested'=>false];
$db->prepare('INSERT INTO community_learning_jobs(id,season,state,created_by,created_at,heartbeat_at,message,snapshot_ndjson,control_json) VALUES(?,2026,\'remote_running\',7,?,?,?,?,?)')->execute([$id,time(),time()-900,'Initial job message',$snapshot,json_encode($controlData)]);
$db->prepare('INSERT INTO community_training_leases VALUES(?,?,?,?,?,?)')->execute([$id,$computer['id'],hash('sha256',$token),time()+600,null,'{}']);
$db->prepare('INSERT INTO community_training_computers(id,user_id) VALUES(?,7)')->execute([$computer['id']]);
$control=new CommunityTrainingControl($db);$legacy=new CommunityTrainers($db);$trials=new CommunityScoutingTrials($db);
$db->exec("CREATE TRIGGER forbid_large_job_write BEFORE UPDATE OF heartbeat_at,message,control_json,snapshot_ndjson ON community_learning_jobs BEGIN SELECT RAISE(ABORT,'Heartbeat touched large job row'); END;");
$p=['job_id'=>$id,'lease'=>$token,'message'=>'Reading robot tracks','checkpoint'=>['matches_done'=>9,'matches_total'=>40,'current_match'=>'2026test_qm9','phase'=>'tracking','unexpected'=>str_repeat('x',100000)]];
for($i=0;$i<30;$i++)$control->heartbeat($computer,$p);
storage_check($db->query('SELECT snapshot_ndjson FROM community_learning_jobs')->fetchColumn()===$snapshot,'30 page heartbeats leave the large snapshot row untouched');
$progress=community_training_progress_read($db,$id);
storage_check(strlen($progress['checkpoint_json'])<1024&&!str_contains($progress['checkpoint_json'],'unexpected'),'progress stores only bounded approved fields');
$row=$db->query('SELECT * FROM community_learning_jobs')->fetch(PDO::FETCH_ASSOC);$view=community_training_progress_overlay($db,$row);
storage_check(json_decode($view['control_json'],true)['matches_done']===9&&$view['message']==='Reading robot tracks','status overlays live progress and messages');
storage_check((int)$view['heartbeat_at']>=(int)$row['heartbeat_at']+600,'status displays the live heartbeat rather than the stale snapshot timestamp');
$sql=community_training_progress_heartbeat_sql();$q=$db->prepare('SELECT COUNT(*) FROM community_learning_jobs WHERE '.$sql.'<?');$q->execute([time()-600]);
storage_check((int)$q->fetchColumn()===0,'recent runtime heartbeat prevents a stale-job claim');
$legacy->heartbeat($computer,['job_id'=>$id,'lease'=>$token,'message'=>'Legacy helper']);
storage_check(community_training_progress_read($db,$id)['message']==='Legacy helper','legacy training heartbeats also avoid the large row');
storage_check(json_decode(community_training_progress_read($db,$id)['checkpoint_json'],true)['matches_done']===9,'heartbeat without a checkpoint preserves saved progress');
$before=$db->query('SELECT * FROM community_learning_progress')->fetchAll(PDO::FETCH_ASSOC);
try{$control->heartbeat(['id'=>str_repeat('d',32)],$p);throw new RuntimeException('Wrong device accepted');}catch(CommunityAnalysisError $e){storage_check($e->httpStatus===409,'wrong device remains rejected');}
try{$control->heartbeat($computer,array_replace($p,['lease'=>'invalid']));throw new RuntimeException('Wrong lease accepted');}catch(CommunityAnalysisError $e){storage_check($e->httpStatus===409,'wrong lease remains rejected');}
storage_check($before===$db->query('SELECT * FROM community_learning_progress')->fetchAll(PDO::FETCH_ASSOC),'unauthorized requests cannot change progress');
$db->exec("UPDATE community_learning_jobs SET state='test_running'");$trials->heartbeat($computer,['job_id'=>$id,'lease'=>$token,'message'=>'Testing a match']);
storage_check(community_training_progress_read($db,$id)['message']==='Testing a match','legacy match-test heartbeat avoids the model row');
$db->exec('DROP TRIGGER forbid_large_job_write');$db->exec("UPDATE community_learning_jobs SET state='remote_running'");
$control->stop($id,7);
$db->exec("CREATE TRIGGER forbid_large_job_write BEFORE UPDATE OF heartbeat_at,message,control_json,snapshot_ndjson ON community_learning_jobs BEGIN SELECT RAISE(ABORT,'Heartbeat touched large job row'); END;");
storage_check($control->heartbeat($computer,$p)['stop_requested'],'owner stop requests still reach a running helper');
$db->exec('DROP TRIGGER forbid_large_job_write');$db->exec("UPDATE community_learning_jobs SET state='candidate',message='Final model saved'");
$final=community_training_progress_overlay($db,$db->query('SELECT * FROM community_learning_jobs')->fetch(PDO::FETCH_ASSOC));
storage_check($final['message']==='Final model saved'&&json_decode($final['control_json'],true)['matches_done']===9,'terminal results keep final messages and last progress');
$db->exec('UPDATE community_learning_jobs SET heartbeat_at='.(time()+100));
$db->exec("UPDATE community_learning_jobs SET state='remote_running',message='New lease message'");
$renewed=community_training_progress_overlay($db,$db->query('SELECT * FROM community_learning_jobs')->fetch(PDO::FETCH_ASSOC));
storage_check($renewed['message']==='New lease message','older runtime heartbeat cannot overwrite a newer job transition');
echo $n." storage regression checks passed\n";
