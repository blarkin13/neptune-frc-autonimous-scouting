<?php
require __DIR__.'/helper-capabilities.php';
require dirname(__DIR__,2).'/neptune_secure/community-robot-models.php';
$root=sys_get_temp_dir().'/neptune-model-test-'.bin2hex(random_bytes(8));mkdir($root,0700);
try{
 file_put_contents($root.'/bumper.pt','fixture');
 $row=['file'=>'bumper.pt','sha256'=>hash('sha256','fixture')];
 file_put_contents($root.'/manifest.json',json_encode(['schema_version'=>1,'bumper'=>$row,'context'=>$row]));
 $zip=new ZipArchive();$zip->open($root.'/test.zip',ZipArchive::CREATE);
 community_robot_models_add($zip,'Neptune Trainer/',$root);$zip->close();
 $zip=new ZipArchive();$zip->open($root.'/test.zip');
 ok($zip->getFromName('Neptune Trainer/robot-models/bumper.pt')==='fixture','private weights added to authenticated personalized download');$zip->close();
 file_put_contents($root.'/bumper.pt','changed');$zip=new ZipArchive();$zip->open($root.'/bad.zip',ZipArchive::CREATE);
 $blocked=false;try{community_robot_models_add($zip,'Neptune Trainer/',$root);}catch(RuntimeException $e){$blocked=true;}$zip->close();
 ok($blocked,'changed model bytes block personalized package generation');
}finally{foreach(glob($root.'/*') as $file)unlink($file);rmdir($root);}
