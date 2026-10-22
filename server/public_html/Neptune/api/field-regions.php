<?php
declare(strict_types=1);
require_once dirname(__DIR__,3).'/neptune_secure/bootstrap.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-analysis-install.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-training-control.php';
header('Cache-Control: private, no-store');
try {
 if($_SERVER['REQUEST_METHOD']!=='POST')throw new CommunityAnalysisError(405,'POST required.');
 $headers=function_exists('getallheaders')?getallheaders():[];$authorization=(string)($_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??$headers['Authorization']??$headers['authorization']??'');
 if(!preg_match('/^Bearer ([a-f0-9]{64})$/D',$authorization,$m))throw new CommunityAnalysisError(401,'Training computer connection required.');
 $service=new CommunityTrainers($pdo);$computer=$service->authenticate($m[1],(int)($config['app']['platform_organization_id']??1));
 $raw=file_get_contents('php://input',false,null,0,4097);if(strlen($raw)>4096)throw new CommunityAnalysisError(413,'Request too large.');
 $p=json_decode($raw,true,16,JSON_THROW_ON_ERROR);
 $name=(string)($p['video_name']??'');$sha=(string)($p['source_sha256']??'');$size=$p['video_size']??0;
 if(!preg_match('/^[A-Za-z0-9_-]{11}\.mp4$/D',$name)||!preg_match('/^[a-f0-9]{64}$/D',$sha)||!is_int($size)||$size<=0)throw new CommunityAnalysisError(422,'Verified video details required.');
 $base=dirname(__DIR__,3).'/neptune_secure/field-regions';$files=array_merge(glob($base.'/seed-documents/*.json')?:[],glob($base.'/'.(int)$computer['user_id'].'/*.json')?:[]);$match=null;
 foreach($files as $file){if(filesize($file)>2097152)continue;$d=json_decode((string)file_get_contents($file),true,64,JSON_THROW_ON_ERROR);if(($d['source']['name']??'')!==$name||(int)($d['source']['size']??0)!==$size)continue;if(isset($d['source_sha256'])&&$d['source_sha256']!==$sha)continue;$match=$d;}
 community_training_json_response(['document'=>$match,'binding'=> $match?'verify_source_locally':'no_matching_annotations']);
}catch(CommunityAnalysisError $e){community_training_json_response(['error'=>$e->getMessage()],$e->httpStatus);}catch(Throwable $e){error_log('Field regions API: '.$e->getMessage());community_training_json_response(['error'=>'Field regions unavailable.'],503);}
