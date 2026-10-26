<?php
declare(strict_types=1);
require_once dirname(__DIR__,3).'/neptune_secure/bootstrap.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-analysis-install.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-training-control.php';
require_once dirname(__DIR__,3).'/neptune_secure/robot-detector-jobs.php';
require_once dirname(__DIR__,3).'/neptune_secure/autoscout-train-overview.php';
require_once dirname(__DIR__,3).'/neptune_secure/external-bumper-training.php';
require_once dirname(__DIR__,3).'/neptune_secure/robot-label-frames.php';
require_once dirname(__DIR__,3).'/neptune_secure/youtube-uploader.php';
require_once dirname(__DIR__,3).'/neptune_secure/score-moments.php';
header('Cache-Control: private, no-store');
// Connected helpers: claim detector requests, report progress, upload pre-fill boxes or an adopted detector,
// and download the current shared detector.
try {
 if($_SERVER['REQUEST_METHOD']!=='POST')throw new CommunityAnalysisError(405,'POST required.');
 $headers=function_exists('getallheaders')?getallheaders():[];$authorization=(string)($_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??$headers['Authorization']??$headers['authorization']??'');
 if(!preg_match('/^Bearer ([a-f0-9]{64})$/D',$authorization,$m))throw new CommunityAnalysisError(401,'Training computer connection required.');
 $computer=(new CommunityTrainers($pdo))->authenticate($m[1],(int)($config['app']['platform_organization_id']??1));
 $raw=file_get_contents('php://input',false,null,0,64*1024*1024+1);if(strlen($raw)>64*1024*1024)throw new CommunityAnalysisError(413,'Request too large.');
 $p=json_decode($raw,true,64,JSON_THROW_ON_ERROR);
 $jobs=new RobotDetectorJobs(dirname(__DIR__,3).'/neptune_secure',(int)$computer['organization_id']);
 $out=match((string)($p['action']??'')){
  'dashboard'=>(function()use($pdo,$computer,$jobs){
   $control=new CommunityTrainingControl($pdo);$owner=(int)$computer['user_id'];
   $computers=autoscout_computers($pdo,$jobs,$control->computers($owner),$jobs->requests());
   $queue=[];foreach($jobs->requests() as $request)if(in_array($request['state']??'', ['queued','claimed'],true))
    $queue[]=['title'=>match($request['kind']??''){'train'=>'Train robot detector','train_field'=>'Train field detector','prepare'=>'Prepare frames',default=>'Training'},'state'=>$request['state']==='claimed'?'running':'waiting','message'=>$request['message']??'','target'=>$request['target']??null,'computer_id'=>$request['computer_id']??null];
   $q=$pdo->prepare("SELECT state,message,control_json FROM community_learning_jobs WHERE season=? AND state IN ('remote_queued','remote_running','queued','running','test_queued','test_running','evaluation_queued','evaluation_running') ORDER BY created_at DESC LIMIT 20");$q->execute([(int)gmdate('Y')]);
   foreach($q as $row){$control=json_decode((string)($row['control_json']??''),true)?:[];$state=(string)$row['state'];$queue[]=['title'=>str_starts_with($state,'test_')?'Test a match':(str_starts_with($state,'evaluation_')?'Independent evaluation':'Train action models & scoring'),'state'=>str_ends_with($state,'queued')?'waiting':'running','message'=>$row['message']??'','target'=>$control['computer_id']??null];}
   foreach($computers as &$row){$row=array_intersect_key($row,array_flip(['id','name','device','online','status','last_seen','platform','stats','counters','log','reported_at','version','job','waiting']));$row['log']=array_slice($row['log']??[],-35);}unset($row);
   return ['game'=>RobotDetectorJobs::defaultGame(),'computers'=>$computers,'queue'=>$queue,'generated_at'=>time()];
  })(),
  'claim'=>['request'=>$jobs->claim($computer)],
  'training_supplement_index'=>['packages'=>(new ExternalBumperTraining(dirname(__DIR__,3).'/neptune_secure',(int)$computer['organization_id']))->index()],
  'training_supplements'=>(function()use($computer,$p){$store=new ExternalBumperTraining(dirname(__DIR__,3).'/neptune_secure',(int)$computer['organization_id']);if(isset($p['id']))return ['datasets'=>[$store->get((string)$p['id'],(string)($p['sha256']??''))]];foreach($store->index() as $item)if($item['id']==='6962-workshop-v1')return ['datasets'=>[$store->get($item['id'],$item['sha256'])]];return ['datasets'=>[]];})(),
  'progress'=>$jobs->progress($computer,$p),
  'finish'=>$jobs->finish($computer,$p),
  'label_frame_put'=>$jobs->putLabelFrame($computer,$p),
  'label_frame_get'=>(function()use($computer,$p){$d=(new RobotLabelFrames(dirname(__DIR__,3).'/neptune_secure',(int)$computer['organization_id']))->get((string)($p['video_id']??''),(int)($p['t_ms']??-1),(string)($p['sha256']??''));if(!$d)throw new InvalidArgumentException('Source frame not found');return ['sha256'=>$d['sha256'],'image_b64'=>base64_encode($d['bytes'])];})(),
  'prefill_put'=>$jobs->putPrefill($computer,$p),
  'current'=>$jobs->current(isset($p['have'])?(string)$p['have']:null),
  'adopt'=>$jobs->adopt($computer,$p),
  'trial_video_put'=>$jobs->putTestVideo($computer,$p,new YouTubeUploader(dirname(__DIR__,3).'/neptune_secure')),
  'computer_poll'=>$jobs->poll($computer,$p),
  'selfcheck_put'=>$jobs->putSelfcheck($computer,$p),
  'score_put'=>(new ScoreMoments(dirname(__DIR__,3).'/neptune_secure',(int)$computer['organization_id']))->put($p),
  'review_put'=>$jobs->putReview($computer,$p,new YouTubeUploader(dirname(__DIR__,3).'/neptune_secure')),
  'current_field'=>$jobs->currentField(isset($p['have'])?(string)$p['have']:null,isset($p['game_key'])?(string)$p['game_key']:null),
  'adopt_field'=>$jobs->adoptField($computer,$p),
  default=>throw new CommunityAnalysisError(422,'Unknown action.'),
 };
 community_training_json_response($out);
}catch(InvalidArgumentException $e){community_training_json_response(['error'=>$e->getMessage()],422);}
catch(CommunityAnalysisError $e){community_training_json_response(['error'=>$e->getMessage()],$e->httpStatus);}
catch(Throwable $e){error_log('Robot detector API: '.$e->getMessage());community_training_json_response(['error'=>'Robot detector service unavailable.'],503);}
