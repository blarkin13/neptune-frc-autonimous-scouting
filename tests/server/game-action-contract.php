<?php
require_once dirname(__DIR__,2).'/neptune_secure/community-learning.php';
$snapshot=stream_get_contents(STDIN);$definitions=community_game_action_definitions($snapshot,'2026-rebuilt');
$valid=true;foreach($definitions as $tag=>$definition){if(!community_game_action_definition_matches($definition,$definition))$valid=false;$bad=$definition;$bad['variants'][0]['definition_version']='neptune-game-v1-'.str_repeat('b',32);if(community_game_action_definition_matches($bad,$definition))$valid=false;}
if(!$valid)throw new RuntimeException('Model provenance boundary failed.');
echo json_encode(['definitions'=>$definitions,'preflight'=>community_learning_baseline_preflight($snapshot."\n".$snapshot,2026)],JSON_THROW_ON_ERROR);
