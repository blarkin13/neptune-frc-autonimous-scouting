<?php
declare(strict_types=1);
require_once dirname(__DIR__,3).'/neptune_secure/bootstrap.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-analysis-install.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-training-control.php';
require_once dirname(__DIR__,3).'/neptune_secure/robot-detector-jobs.php';
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
  'claim'=>['request'=>$jobs->claim($computer)],
  'progress'=>$jobs->progress($computer,$p),
  'finish'=>$jobs->finish($computer,$p),
  'prefill_put'=>$jobs->putPrefill($computer,$p),
  'current'=>$jobs->current(isset($p['have'])?(string)$p['have']:null),
  'adopt'=>$jobs->adopt($computer,$p),
  'trial_video_put'=>$jobs->putTestVideo($computer,$p,new YouTubeUploader(dirname(__DIR__,3).'/neptune_secure')),
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
