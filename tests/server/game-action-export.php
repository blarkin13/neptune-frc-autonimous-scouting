<?php
/** End-to-end in-memory fixture: existing PHP export -> preflight -> model upload. */
require __DIR__.'/training-computers.php';
$db->exec('UPDATE community_training_computers SET revoked=0');
$revision='neptune-game-rev-42-'.str_repeat('a',32);
$q=$db->prepare("UPDATE community_video_labels SET tag_key=?,tag_label=?,tag_category=?,definition_version=?,label_scope='moment',start_ms=93000,end_ms=93000,certainty='observed',polarity='present',scoring_json=NULL WHERE id=?");
foreach([1,2] as $i)$q->execute(['gb:score_10_fuel','Score 10 fuel','Scoring & Defense',$revision,str_pad((string)$i,32,'0',STR_PAD_LEFT)]);
$export=community_learning_export($db);$rows=array_map(fn($line)=>json_decode($line,true),array_filter(explode("\n",$export)));$gb=array_values(array_filter($rows,fn($r)=>str_starts_with($r['tag_key'],'gb:')));
ok(count($gb)===2&&community_game_action_row($gb[0],2026),'actual PHP export preserves schema-v2 Game Builder moments and revision');
ok($gb[0]['start_ms']===93000&&$gb[0]['end_ms']===93000&&$gb[0]['scoring']===null,'actual export keeps elapsed-video milliseconds and no extra scoring entry');
ok(community_learning_baseline_preflight($export,2026)['can_run_baseline'],'preflight counts two new action observations');
rejects(fn()=>community_require_game_action_helper($export,[]),'old helper cannot silently drop game action labels');
community_require_game_action_helper($export,['label_contracts'=>['game-builder-moments-v1']]);
$jobId=$service->queue(2026,7);$job=$service->claim($computer,['training_protocol'=>'checkpoint-v1','label_contracts'=>['game-builder-moments-v1']])['job'];
$definitions=community_game_action_definitions($export,'2026-rebuilt');
$candidate=['job_id'=>$jobId,'lease'=>$job['lease'],'result'=>['report'=>['examples'=>2],'model'=>['game_key'=>'2026-rebuilt','feature_version'=>'robot-rgb-motion-v1','model_id'=>str_repeat('f',64),'heads'=>['gb:score_10_fuel'=>$head],'action_definitions'=>$definitions,'used_label_ids'=>array_column($gb,'id'),'release_ready'=>false],'benchmark'=>null]];
$invalid=$candidate;$invalid['result']['model']['action_definitions']['gb:score_10_fuel']['variants'][0]['definition_version']='neptune-game-v1-'.str_repeat('b',32);
rejects(fn()=>$service->finish($computer,$invalid),'model upload rejects invented game-definition provenance');
ok($service->finish($computer,$candidate)['state']==='candidate','model upload accepts a distinct Game Builder action head with snapshot provenance');
$stored=json_decode($db->query("SELECT model_json FROM community_learning_jobs WHERE id='".$jobId."'")->fetchColumn(),true);
ok(isset($stored['heads']['gb:score_10_fuel'])&&$stored['action_definitions']===$definitions,'stored model preserves action code and exact source revision');
rejects(fn()=>community_require_game_action_model_helper($stored,[]),'prediction jobs cannot use a helper without Game Builder support');
community_require_game_action_model_helper($stored,['label_contracts'=>['game-builder-moments-v1']]);
// A separately reserved trial saves model-owned action metadata, never caller-supplied names.
require_once dirname(__DIR__,2).'/neptune_secure/community-scouting-trials.php';
$trialId=str_repeat('9',32);$trialLease=str_repeat('8',64);$request=['match_id'=>1,'match_key'=>'2026test_qm7','title'=>'Test Q7','roster'=>$roster,'source_url'=>'https://www.youtube.com/watch?v=_2hGzZRvw0A','model_id'=>$stored['model_id'],'alliance_scores'=>[]];
$q=$db->prepare("INSERT INTO community_learning_jobs(id,season,state,created_by,created_at,snapshot_ndjson,model_json) VALUES(?,2026,'test_running',7,?,?,?)");$q->execute([$trialId,time(),json_encode($request),community_model_document($stored)]);
$q=$db->prepare('INSERT INTO community_training_leases(job_id,computer_id,lease_hash,expires_at,game_json) VALUES(?,?,?,?,?)');$q->execute([$trialId,$computer['id'],hash('sha256',$trialLease),time()+600,'{}']);
$scores=[];foreach(array_merge($roster['red'],$roster['blue']) as $team)$scores[]=['team'=>$team,'status'=>'unknown','points'=>null,'share_percent'=>null,'reason'=>'No verified video scoring evidence'];
$data=['model_id'=>$stored['model_id'],'source_sha256'=>str_repeat('1',64),'duration_s'=>180.0,'scores'=>$scores,'tags'=>[['team'=>6369,'tag_key'=>'gb:score_10_fuel','start_ms'=>93000,'tag_label'=>'tampered name']]];
(new CommunityScoutingTrials($db))->finish($computer,['job_id'=>$trialId,'lease'=>$trialLease,'result'=>$data]);
$r=json_decode($db->query("SELECT report_json FROM community_learning_jobs WHERE id='".$trialId."'")->fetchColumn(),true);
ok($r['tags'][0]['tag_label']==='Score 10 fuel'&&$r['tags'][0]['definition_version']===$revision&&$r['tags'][0]['start_ms']===$r['tags'][0]['end_ms'],'saved predictions preserve authoritative action label, revision and moment scope');
