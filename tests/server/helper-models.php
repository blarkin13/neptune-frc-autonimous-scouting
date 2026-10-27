<?php
declare(strict_types=1);
// A helper's model pages: the Train page overview trimmed to status, data counts and the last runs.
require dirname(__DIR__,2).'/server/neptune_secure/autoscout-train-overview.php';
$check=function(bool $ok,string $name):void{if(!$ok)throw new RuntimeException('FAIL: '.$name);echo 'PASS '.$name."\n";};
$run=fn($id,$f1)=>['id'=>$id,'kind'=>'train','state'=>'done','created_at'=>1,'message'=>'m','report'=>['new'=>['f1'=>$f1],'current'=>['f1'=>.8],'adopted'=>false,'frames'=>999],'review'=>['youtube_id'=>'abc','title'=>'t','privacy'=>'unlisted']];
$o=['robot'=>['current'=>['adopted_at'=>5,'report'=>['holdout_match'=>'2026txcmp1_qm4','new'=>['f1'=>.82],'trained_on'=>['x']]],'holdout'=>'2026txcmp1_qm4','matches'=>['a'=>20,'b'=>9,'c'=>3],'min_frames'=>8,'events'=>['2026txcmp1'],
  'runs'=>array_map(fn($i)=>$run('r'.$i,$i/10),range(10,1))],  // newest first, as requests() returns them
 'field'=>['current'=>null,'baseline'=>['kind'=>'bundled'],'game_key'=>'2026-rebuilt','holdout'=>'2026dal_qm6','matches'=>['m1'=>['targets'=>2,'corners'=>true],'m2'=>['targets'=>2,'corners'=>false]],'events'=>['2026dal'],'runs'=>[]],
 'actions'=>['models'=>[['id'=>'a'],['id'=>'b']],'latest'=>['id'=>'b','created_at'=>9],'released'=>'a','counts'=>['matches'=>3,'tags'=>40]]];
$m=autoscout_helper_models($o);
$check($m['robot']['matches']===2&&$m['robot']['frames']===29&&$m['robot']['ready'],'robot data counts only matches with enough frames');
$check(count($m['robot']['runs'])===8&&$m['robot']['runs'][0]['id']==='r10','robot runs: newest eight first');
$check($m['robot']['runs'][0]['new']==['f1'=>1]&&!isset($m['robot']['runs'][0]['report'])&&$m['robot']['runs'][0]['review']===['youtube_id'=>'abc'],'run keeps its scores and review, not the full report');
$check($m['robot']['current']===['adopted_at'=>5,'holdout'=>'2026txcmp1_qm4','new'=>['f1'=>.82]],'model in use with its held-out score');
$check($m['field']['marked']===1&&!$m['field']['ready']&&$m['field']['baseline']&&$m['field']['current']===null,'field: only fully marked matches count');
$check($m['actions']['models']===2&&$m['actions']['released']==='a'&&$m['actions']['counts']['tags']===40,'actions summary');
