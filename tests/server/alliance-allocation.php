<?php
require dirname(__DIR__,2).'/neptune_secure/community-score-model.php';
function check($v,$label){if(!$v)throw new RuntimeException($label);echo 'PASS '.$label."\n";}
function robot($team,$alliance,$points,$total){return ['team'=>$team,'alliance'=>$alliance,'robot_points'=>$points,'share_percent'=>$points===null?null:100*$points/$total,'alliance_score'=>$total,'status'=>$points===null?'unknown':'predicted','reason'=>$points===null?'insufficient_robot_sightings':null];}
$scores=[robot(7506,'red',46,272),robot(7503,'red',18,272),robot(3005,'red',16,272),robot(1477,'blue',48,199),robot(5261,'blue',26,199),robot(11200,'blue',null,199)];$original=$scores;$out=community_score_allocation($scores);
check(array_column($out['red']['rows'],'allocated_points')===[157,61,54],'Qual 35 red estimates are allocated to red final score');
check(abs(array_sum(array_column($out['red']['rows'],'allocated_share_percent'))-100)<.000001,'red robot shares total exactly 100 percent');
check($out['blue']['rows'][2]['allocated_points']===null&&$out['blue']['rows'][2]['allocated_share_percent']===null,'unknown blue robot stays unknown');
check($out['blue']['unassigned_points']===125&&$out['blue']['unassigned_share_percent']===62.814,'unseen contribution is explicitly unassigned');
check(abs(array_sum(array_column($out['blue']['rows'],'allocated_share_percent'))+$out['blue']['unassigned_share_percent']-100)<.000001,'blue total including unassigned is 100 percent independently');
check($scores===$original&&$out['red']['raw_model_points_total']===80,'raw predictions are unchanged for accuracy evaluation');
$other=$scores;$other[3]['robot_points']=100;$other[4]['robot_points']=20;$b=community_score_allocation($other);check($b['red']===$out['red'],'blue predictions cannot change red allocation');
$zero=array_map(fn($r)=>array_replace($r,['robot_points'=>0,'status'=>'predicted','alliance_score'=>0]),$scores);$z=community_score_allocation($zero);check($z['red']['allocation_percent']===null&&$z['red']['rows'][0]['allocated_share_percent']===null,'zero final score has no fabricated percentage');
$noSignal=array_map(fn($r)=>array_replace($r,['robot_points'=>0,'status'=>'predicted']),$scores);$z=community_score_allocation($noSignal);check($z['red']['unassigned_points']===272&&$z['red']['unassigned_share_percent']==100,'zero model weights do not invent equal robot contributions');
foreach([1,7,199,272,100000] as $total){$v=community_score_apportion([1,1,1],$total);check(array_sum($v)===$total,'rounding preserves total '.$total);}
