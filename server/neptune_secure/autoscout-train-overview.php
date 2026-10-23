<?php
declare(strict_types=1);
require_once __DIR__.'/robot-detector-jobs.php';

/** One status read for the Train page: helpers, what is running and waiting, and each trainable part's model and data. */
function autoscout_train_overview(PDO $pdo,array $panel,int $org,int $user):array {
 $secure=__DIR__;$jobs=new RobotDetectorJobs($secure,$org);
 $requests=array_map(fn($r)=>array_intersect_key($r,array_flip(['id','kind','state','created_at','claimed_at','heartbeat_at','finished_at','message','report','video_id','match_key'])),$jobs->requests());
 // Robot labels: complete frames per match (site saves take precedence over the local seed frames).
 $videos=[];
 foreach(array_merge(glob($secure.'/robot-labels/seed/*.json')?:[],glob($secure.'/robot-labels/'.$org.'/*.json')?:[]) as $f){
  $d=json_decode((string)file_get_contents($f),true);if(!is_array($d)||empty($d['video_id']))continue;$v=$d['video_id'];
  $videos[$v]['frames']=($d['frames']??[])+($videos[$v]['frames']??[]);$videos[$v]['match_key']=$d['match_key']??($videos[$v]['match_key']??null);
 }
 $robotMatches=[];foreach($videos as $v){$n=count(array_filter($v['frames'],fn($fr)=>!empty($fr['complete'])));if($n&&$v['match_key'])$robotMatches[$v['match_key']]=($robotMatches[$v['match_key']]??0)+$n;}
 // Scoring areas: matches with hubs and the four field corners marked.
 $fieldMatches=[];
 foreach(array_merge(glob($secure.'/field-regions/seed-documents/*.json')?:[],glob($secure.'/field-regions/'.$user.'/*.json')?:[]) as $f){
  if(filesize($f)>2097152)continue;$d=json_decode((string)file_get_contents($f),true);if(!is_array($d))continue;$kinds=array_column($d['regions']??[],'kind');
  // Documents name their video (YouTube id or a cached file named after it); find its match.
  $src=$d['source']??[];$vid=(string)($src['video_id']??preg_replace('/\.[a-z0-9]+$/i','',(string)($src['name']??'')));$key=(string)($src['match_key']??'');
  if($key===''&&preg_match('/^[A-Za-z0-9_-]{11}$/D',$vid)){$q=$pdo->prepare('SELECT match_key FROM community_matches WHERE source_url LIKE ? LIMIT 1');$q->execute(['%'.$vid.'%']);$key=(string)($q->fetchColumn()?:'');}
  if($key==='')$key=$vid?:basename($f,'.json');
  $fieldMatches[$key]=['targets'=>count(array_keys($kinds,'scoring_target')),'corners'=>in_array('field_calibration',$kinds,true)];
 }
 $event=fn($k)=>preg_match('/^(\d{4}[a-z0-9]+)_/',(string)$k,$m)?$m[1]:'';
 $robot=$jobs->current('skip-weights')['detector'];$field=$jobs->currentField('skip-weights')['detector'];
 $latest=null;foreach($panel['jobs'] as $j)if($j['state']==='candidate'){$latest=$j;break;}
 $active=['remote_queued','remote_running','queued','running','test_queued','test_running','evaluation_queued','evaluation_running'];
 $queue=[];
 foreach(array_reverse($requests) as $r)if(in_array($r['state'],['queued','claimed'],true))$queue[]=['part'=>$r['kind']==='train_field'?'field':($r['kind']==='train'?'robot':'prepare'),'state'=>$r['state']==='claimed'?'running':'waiting','title'=>['train'=>'Train robot detector','train_field'=>'Train field detector','prepare'=>'Prepare frames · '.($r['match_key']??'')][$r['kind']]??$r['kind'],'message'=>$r['message']??'','since'=>$r['created_at']];
 foreach(array_reverse($panel['jobs']) as $j)if(in_array($j['state'],$active,true))$queue[]=['part'=>str_starts_with($j['state'],'test_')||str_starts_with($j['state'],'evaluation_')?'test':'actions','state'=>str_ends_with($j['state'],'_queued')||$j['state']==='queued'?'waiting':'running','title'=>str_starts_with($j['state'],'test_')?'Test a match':(str_starts_with($j['state'],'evaluation_')?'Independent evaluation':'Train action models & scoring'),'message'=>$j['message']??'','since'=>$j['created_at']];
 usort($queue,fn($a,$b)=>[$a['state']!=='running',$a['since']]<=>[$b['state']!=='running',$b['since']]);
 return [
  'helpers'=>array_map(fn($c)=>['name'=>$c['name'],'status'=>$c['status'],'online'=>$c['online'],'ready'=>$c['ready']],array_values(array_filter($panel['computers'],fn($c)=>!$c['revoked']))),
  'queue'=>$queue,
  'robot'=>['current'=>$robot,'history'=>count($jobs->history('robot')),'matches'=>$robotMatches,'events'=>array_values(array_unique(array_filter(array_map($event,array_keys($robotMatches))))),'min_frames'=>8,'runs'=>array_values(array_filter($requests,fn($r)=>$r['kind']==='train'))],
  'field'=>['current'=>$field,'history'=>count($jobs->history('field')),'matches'=>$fieldMatches,'events'=>array_values(array_unique(array_filter(array_map($event,array_keys($fieldMatches))))),'runs'=>array_values(array_filter($requests,fn($r)=>$r['kind']==='train_field'))],
  'actions'=>['latest'=>$latest?['id'=>$latest['id'],'created_at'=>$latest['created_at']]:null,'released'=>$panel['released'],'counts'=>$panel['counts']],
 ];
}
