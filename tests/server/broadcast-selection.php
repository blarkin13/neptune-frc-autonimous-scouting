<?php
require dirname(__DIR__,2).'/neptune_secure/community-catalog.php';
function check($v,$name){if(!$v)throw new RuntimeException($name);echo 'PASS '.$name."\n";}
$m=['key'=>'2026txcmp1_qm29','comp_level'=>'qm','match_number'=>29,'alliances'=>['red'=>['team_keys'=>['frc7503','frc2468','frc11277']],'blue'=>['team_keys'=>['frc324','frc6672','frc2587']]],'videos'=>[['type'=>'youtube','key'=>'FsOmBnfY334'],['type'=>'youtube','key'=>'x0zEgJYH6EI']]];
check(CommunityCatalog::normalize($m,'2026txcmp1','Mercury')['video_id']==='x0zEgJYH6EI','verified broadcast wins over the first field-side video');
$other=$m;$other['alliances']['red']['team_keys'][0]='frc1';check(CommunityCatalog::normalize($other,'2026txcmp1','Mercury')['video_id']==='FsOmBnfY334','changed roster cannot reuse the preference');
$other=$m;array_pop($other['videos']);check(CommunityCatalog::normalize($other,'2026txcmp1','Mercury')['video_id']==='FsOmBnfY334','preference cannot invent a provider video');
$other=$m;$other['key']='2026txcmp1_qm30';check(CommunityCatalog::normalize($other,'2026txcmp1','Mercury')['video_id']==='FsOmBnfY334','preference applies only to its verified match');
check(str_contains(CommunityCatalog::videoNote('2026txcmp1_qm29','https://www.youtube.com/watch?v=x0zEgJYH6EI'),'five seconds'),'known truncated broadcast is explained before testing');
check(CommunityCatalog::videoNote('2026txcmp1_qm29','https://www.youtube.com/watch?v=FsOmBnfY334')==='','coverage warning is tied to the exact source');
