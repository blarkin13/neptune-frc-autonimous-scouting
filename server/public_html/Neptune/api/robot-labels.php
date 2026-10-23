<?php
declare(strict_types=1);
require_once dirname(__DIR__,3).'/neptune_secure/bootstrap.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-analysis-install.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-training-control.php';
header('Cache-Control: private, no-store');
// The helper's training computer reads the organization's completed robot labels (video time + boxes).
try {
 if($_SERVER['REQUEST_METHOD']!=='POST')throw new CommunityAnalysisError(405,'POST required.');
 $headers=function_exists('getallheaders')?getallheaders():[];$authorization=(string)($_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??$headers['Authorization']??$headers['authorization']??'');
 if(!preg_match('/^Bearer ([a-f0-9]{64})$/D',$authorization,$m))throw new CommunityAnalysisError(401,'Training computer connection required.');
 $computer=(new CommunityTrainers($pdo))->authenticate($m[1],(int)($config['app']['platform_organization_id']??1));
 $store=dirname(__DIR__,3).'/neptune_secure/robot-labels/'.(int)$computer['organization_id'];$docs=[];
 foreach(glob($store.'/*.json')?:[] as $file){
  if(filesize($file)>8388608)continue;$d=json_decode((string)file_get_contents($file),true,32,JSON_THROW_ON_ERROR);
  $frames=array_filter($d['frames']??[],fn($f)=>!empty($f['complete']));
  if($frames)$docs[]=['video_id'=>$d['video_id'],'match_key'=>$d['match_key']??null,'frames'=>$frames];
 }
 community_training_json_response(['documents'=>$docs]);
}catch(CommunityAnalysisError $e){community_training_json_response(['error'=>$e->getMessage()],$e->httpStatus);}catch(Throwable $e){error_log('Robot labels API: '.$e->getMessage());community_training_json_response(['error'=>'Robot labels unavailable.'],503);}
