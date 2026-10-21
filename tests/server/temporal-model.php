<?php
require __DIR__.'/private-robot-models.php';
$encoder=['name'=>'torchvision-r3d18-kinetics400-v1','feature_version'=>'robot-r3d18-clip-v1','dimension'=>512,'weights_sha256'=>'b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d','frames'=>16,'fps'=>4,'seconds'=>4.0,'backbone_frozen'=>true,'head_training'=>'per-game-Neptune-action-labels'];
$model=['feature_version'=>'robot-r3d18-clip-v1','action_encoder'=>$encoder];
ok(community_action_feature_dimension($model)===512,'server accepts the explicit temporal encoder contract');
$bad=$model;$bad['action_encoder']['weights_sha256']=str_repeat('a',64);ok(community_action_feature_dimension($bad)===0,'server rejects unrecognized temporal weights');
$bad=$model;$bad['action_encoder']['frames']=1;ok(community_action_feature_dimension($bad)===0,'a still image cannot claim the temporal encoder contract');
ok(community_action_feature_dimension(['feature_version'=>'robot-rgb-motion-v1'])===1296,'historical model documents retain their original feature format');

$vm=json_decode('{"feature_version":"robot-videomae-base-clip-v1","action_encoder":{"name":"huggingface-videomae-base-kinetics400-v1","feature_version":"robot-videomae-base-clip-v1","dimension":768,"repository":"MCG-NJU/videomae-base-finetuned-kinetics","revision":"488eb9a0565f257b32866000305c8178965eb9f6","weights_sha256":"065cfde56f97671da4d196e1a3a6d3cf9304dcad92eb671e3632a6c6cdd04f73","frames":16,"fps":4,"seconds":4,"backbone_frozen":true,"head_training":"per-game-Neptune-action-labels","license":"cc-by-nc-4.0"}}',true);
ok(community_action_feature_dimension($vm)===768,'server accepts pinned VideoMAE evaluation contract');
$vm['action_encoder']['revision']='main';ok(community_action_feature_dimension($vm)===0,'unpinned VideoMAE revision is rejected');

$vm['action_encoder']['revision']='488eb9a0565f257b32866000305c8178965eb9f6';
$blocked=false;try{community_require_game_action_model_helper($vm,['action_features'=>'robot-r3d18-clip-v1']);}catch(CommunityAnalysisError $e){$blocked=true;}ok($blocked,'R3D helper cannot receive a VideoMAE model');
community_require_game_action_model_helper($vm,['action_features'=>'robot-videomae-base-clip-v1']);ok(true,'matching VideoMAE helper can receive the model');
