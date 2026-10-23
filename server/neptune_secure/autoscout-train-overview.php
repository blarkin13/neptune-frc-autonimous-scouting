<?php
declare(strict_types=1);
require_once __DIR__.'/robot-detector-jobs.php';

/** One status read for the Train page: helpers, what is running and waiting, and each trainable part's model and data. */
function autoscout_train_overview(PDO $pdo,array $panel,int $org,int $user,string $game):array {
 $secure=__DIR__;$jobs=new RobotDetectorJobs($secure,$org);
 $requests=array_map(fn($r)=>array_intersect_key($r,array_flip(['id','kind','state','computer_id','created_at','claimed_at','heartbeat_at','finished_at','message','report','video_id','match_key'])),$jobs->requests());
 // Robot labels: complete frames per match (site saves take precedence over the local seed frames).
 $videos=[];
 foreach(array_merge(glob($secure.'/robot-labels/seed/*.json')?:[],glob($secure.'/robot-labels/'.$org.'/*.json')?:[]) as $f){
  $d=json_decode((string)file_get_contents($f),true);if(!is_array($d)||empty($d['video_id']))continue;$v=$d['video_id'];
  $videos[$v]['frames']=($d['frames']??[])+($videos[$v]['frames']??[]);$videos[$v]['match_key']=$d['match_key']??($videos[$v]['match_key']??null);
 }
 $robotMatches=[];foreach($videos as $v){$n=count(array_filter($v['frames'],fn($fr)=>!empty($fr['complete'])));if($n&&$v['match_key'])$robotMatches[$v['match_key']]=($robotMatches[$v['match_key']]??0)+$n;}
 // Scoring areas: this game's matches with scoring targets and the four field corners marked.
 $fieldMatches=[];
 foreach(array_merge(glob($secure.'/field-regions/seed-documents/*.json')?:[],glob($secure.'/field-regions/'.$user.'/*.json')?:[]) as $f){
  if(filesize($f)>2097152)continue;$d=json_decode((string)file_get_contents($f),true);if(!is_array($d))continue;$kinds=array_column(array_filter($d['regions']??[],fn($r)=>($r['game_key']??'')===$game),'kind');if(!$kinds)continue;
  // Documents name their video (YouTube id or a cached file named after it); find its match.
  $src=$d['source']??[];$vid=(string)($src['video_id']??preg_replace('/\.[a-z0-9]+$/i','',(string)($src['name']??'')));$key=(string)($src['match_key']??'');
  if($key===''&&preg_match('/^[A-Za-z0-9_-]{11}$/D',$vid)){$q=$pdo->prepare('SELECT match_key FROM community_matches WHERE source_url LIKE ? LIMIT 1');$q->execute(['%'.$vid.'%']);$key=(string)($q->fetchColumn()?:'');}
  if($key==='')$key=$vid?:basename($f,'.json');
  $fieldMatches[$key]=['targets'=>count(array_keys($kinds,'scoring_target')),'corners'=>in_array('field_calibration',$kinds,true)];
 }
 $event=fn($k)=>preg_match('/^(\d{4}[a-z0-9]+)_/',(string)$k,$m)?$m[1]:'';
 $robot=$jobs->current('skip-weights')['detector'];$field=$jobs->currentField('skip-weights',$game)['detector'];
 $latest=null;foreach($panel['jobs'] as $j)if($j['state']==='candidate'){$latest=$j;break;}
 $active=['remote_queued','remote_running','queued','running','test_queued','test_running','evaluation_queued','evaluation_running'];
 $queue=[];
 foreach(array_reverse($requests) as $r)if(in_array($r['state'],['queued','claimed'],true))$queue[]=['part'=>$r['kind']==='train_field'?'field':($r['kind']==='train'?'robot':'prepare'),'state'=>$r['state']==='claimed'?'running':'waiting','title'=>['train'=>'Train robot detector','train_field'=>'Train field detector · '.($r['game_key']??''),'prepare'=>'Prepare frames · '.($r['match_key']??'')][$r['kind']]??$r['kind'],'message'=>$r['message']??'','since'=>$r['created_at']];
 foreach(array_reverse($panel['jobs']) as $j)if(in_array($j['state'],$active,true))$queue[]=['part'=>str_starts_with($j['state'],'test_')||str_starts_with($j['state'],'evaluation_')?'test':'actions','state'=>str_ends_with($j['state'],'_queued')||$j['state']==='queued'?'waiting':'running','title'=>str_starts_with($j['state'],'test_')?'Test a match':(str_starts_with($j['state'],'evaluation_')?'Independent evaluation':'Train action models & scoring'),'message'=>$j['message']??'','since'=>$j['created_at']];
 // Say which pillar each job belongs to and what it is learning from (the same matches the helper picks).
 $usable=array_keys(array_filter($robotMatches,fn($n)=>$n>=8));sort($usable);
 $marked=array_keys(array_filter($fieldMatches,fn($v)=>$v['targets']&&$v['corners']));sort($marked);
 $about=['robot'=>['1 · Robots — robot detector',sprintf('Learning from %d labelled frames in %d matches%s',array_sum(array_intersect_key($robotMatches,array_flip($usable))),count($usable),$usable?' · checking on '.end($usable).' (held out)':'')],
  'field'=>['2 · Field — field detector',sprintf('Learning from %d marked matches%s',count($marked),$marked?' · checking on '.end($marked).' (held out)':'')],
  'actions'=>['3 · Actions — action & scoring models',sprintf('Learning from %d tagged matches (%d tags, %d imported actions)',$panel['counts']['matches']??0,$panel['counts']['tags']??0,$panel['counts']['external']??0)],
  'test'=>['Test & release','']];
 foreach($queue as &$q){[$q['label'],$q['about']]=$about[$q['part']]??['1 · Robots — '.$q['title'],''];}unset($q);
 usort($queue,fn($a,$b)=>[$a['state']!=='running',$a['since']]<=>[$b['state']!=='running',$b['since']]);
 return [
  // A helper on a detector job reports to that queue, not the action-training one, so its last_seen goes stale.
  'helpers'=>array_map(function($c)use($requests){
   $job=null;foreach($requests as $r)if($r['state']==='claimed'&&($r['computer_id']??null)===$c['id']&&time()-(int)($r['heartbeat_at']??0)<900)$job=$r;
   return $job?['name'=>$c['name'],'status'=>'working','online'=>true,'ready'=>false,'working'=>true]:['name'=>$c['name'],'status'=>$c['status'],'online'=>$c['online'],'ready'=>$c['ready']];
  },array_values(array_filter($panel['computers'],fn($c)=>!$c['revoked']))),
  'queue'=>$queue,
  'robot'=>['current'=>$robot,'history'=>count($jobs->history('robot')),'matches'=>$robotMatches,'events'=>array_values(array_unique(array_filter(array_map($event,array_keys($robotMatches))))),'min_frames'=>8,'runs'=>array_values(array_filter($requests,fn($r)=>$r['kind']==='train'))],
  'field'=>['game_key'=>$game,'current'=>$field,'history'=>count($jobs->history('field',$game)),'matches'=>$fieldMatches,'events'=>array_values(array_unique(array_filter(array_map($event,array_keys($fieldMatches))))),'runs'=>array_values(array_filter($requests,fn($r)=>$r['kind']==='train_field'&&($r['game_key']??RobotDetectorJobs::defaultGame())===$game))],
  'actions'=>['latest'=>$latest?['id'=>$latest['id'],'created_at'=>$latest['created_at']]:null,'released'=>$panel['released'],'counts'=>$panel['counts']],
 ];
}
