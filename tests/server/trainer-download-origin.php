<?php
$source=file_get_contents(dirname(__DIR__,2).'/public_html/Neptune/community/download-trainer.php');
$start=strpos($source,'function neptune_trainer_site(): string {');
$end=strpos($source,'$names=',$start);
eval(substr($source,$start,$end-$start));
function base_url($path=''){global $config;return $config['app']['base_url'];}
function neptune_google_settings(){global $callbackValue;return ['redirect_uri'=>$callbackValue];}
$cases=[['/','',null,'https://neptunefrc.com'],['/Neptune','',null,'https://neptunefrc.com/Neptune'],['/','https://other.example/auth/google-callback.php',null,'https://other.example'],['https://site.example/Neptune','',null,'https://site.example/Neptune'],['/','', 'https://custom.example','https://custom.example']];
foreach($cases as [$base,$callbackValue,$origin,$expected]){$config=['app'=>['base_url'=>$base]];if($origin)$config['app']['public_origin']=$origin;if(neptune_trainer_site()!==$expected)throw new Exception('Resolver mismatch');}
$config=['app'=>['base_url'=>'http://unsafe.example']];try{neptune_trainer_site();throw new Exception('Accepted HTTP');}catch(RuntimeException $expected){}
echo "PASS 6 trainer origin regression cases\n";
