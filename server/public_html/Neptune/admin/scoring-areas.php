<?php
declare(strict_types=1);
require_once dirname(__DIR__,3).'/neptune_secure/bootstrap.php';
require_once dirname(__DIR__,3).'/neptune_secure/google-auth.php';
require_once dirname(__DIR__,3).'/neptune_secure/platform-security.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-analysis-install.php';
require_once dirname(__DIR__,3).'/neptune_secure/community-video-tags.php';
$u=require_role(['owner']);
if((int)$u['organization_id']!==(int)($config['app']['platform_organization_id']??1))access_denied('Platform owner access required.');
neptune_require_platform_owner_google($u);
header('Cache-Control: private, no-store');
$_SESSION['field_regions_csrf']??=bin2hex(random_bytes(32));
$fieldCsrf=$_SESSION['field_regions_csrf'];
$store=dirname(__DIR__,3).'/neptune_secure/field-regions/'.(int)$u['id'];
function field_reply(int $code,array $data):never{http_response_code($code);header('Content-Type: application/json');echo json_encode($data,JSON_THROW_ON_ERROR);exit;}
if(isset($_GET['list'])){
 $files=array_merge(glob(dirname(__DIR__,3).'/neptune_secure/field-regions/seed-documents/*.json')?:[],glob($store.'/*.json')?:[]);$out=[];
 foreach($files as $file){if(filesize($file)>2097152)continue;$d=json_decode((string)file_get_contents($file),true);if(!is_array($d))continue;$out[]=['id'=>hash('sha256',$d['source']['id']),'name'=>$d['source']['name'],'source'=>$d['source'],'document'=>$d,'cloud_document'=>true];}
 field_reply(200,$out);
}
if(isset($_GET['load'])){
 $key=(string)$_GET['load'];if(!preg_match('/^[a-f0-9]{64}$/D',$key))field_reply(400,['error'=>'Invalid source key']);
 $file=$store.'/'.$key.'.json';if(!is_file($file))field_reply(404,['error'=>'No saved annotations for this source']);
 field_reply(200,json_decode((string)file_get_contents($file),true,64,JSON_THROW_ON_ERROR));
}
if($_SERVER['REQUEST_METHOD']==='POST'){
 if(!hash_equals($fieldCsrf,(string)($_SERVER['HTTP_X_FIELD_CSRF']??'')))field_reply(403,['error'=>'Refresh this page before saving']);
 $raw=file_get_contents('php://input',false,null,0,2097153);if(strlen($raw)>2097152)field_reply(413,['error'=>'Annotation file exceeds 2 MB']);
 try{
  $d=json_decode($raw,true,64,JSON_THROW_ON_ERROR);
  if(($d['contract']??'')!=='neptune-field-regions-v1'||($d['schema_version']??0)!==1||($d['coordinate_system']??'')!=='normalized_full_video_frame'||($d['time_basis']??'')!=='video_elapsed_ms'||!is_string($d['source']['id']??null)||!is_array($d['regions']??null)||count($d['regions'])>500)throw new RuntimeException('Invalid field-region document');
  foreach($d['regions'] as $r){
   if(!in_array($r['kind']??'', ['scoring_target','scoring_zone','collection_zone','feeding_zone','field_boundary','field_calibration'],true)||!in_array($r['camera_view']??'', ['wide','closeup-left','closeup-right','other'],true)||!in_array($r['alliance']??'', ['red','blue','neutral'],true)||($r['reviewed']??false)!==true)throw new RuntimeException('Invalid region metadata');
   $ps=$r['points']??[];if(!is_array($ps)||count($ps)<3||count($ps)>100)throw new RuntimeException('Invalid polygon');
   foreach($ps as $p){if(!is_array($p)||count($p)!==2)throw new RuntimeException('Invalid point');foreach($p as $x)if(!is_numeric($x)||!is_finite((float)$x)||$x<0||$x>1)throw new RuntimeException('Invalid normalized point');}
   foreach(['start_ms','reference_ms','end_ms'] as $k)if(!isset($r[$k])||!is_numeric($r[$k])||!is_finite((float)$r[$k]))throw new RuntimeException('Invalid time');
   if($r['start_ms']<0||$r['reference_ms']<$r['start_ms']||$r['end_ms']<$r['reference_ms'])throw new RuntimeException('Invalid time interval');
  }
  if(!is_dir($store)&&!mkdir($store,0700,true))throw new RuntimeException('Annotation storage unavailable');
  $key=hash('sha256',$d['source']['id']);$tmp=tempnam($store,'pending-');
  if($tmp===false||file_put_contents($tmp,json_encode($d,JSON_THROW_ON_ERROR),LOCK_EX)===false)throw new RuntimeException('Could not save');
  chmod($tmp,0600);if(!rename($tmp,$store.'/'.$key.'.json'))throw new RuntimeException('Could not commit save');
  field_reply(200,['ok'=>true,'regions'=>count($d['regions']),'key'=>$key]);
 }catch(Throwable $e){field_reply(422,['error'=>$e->getMessage()]);}
}
// Matches come from the same catalog as Community Tag Scouting and play from YouTube.
$matches=[];$selected=null;
try{
 foreach($pdo->query('SELECT id,match_key,title,source_url FROM community_matches ORDER BY match_key')->fetchAll(PDO::FETCH_ASSOC) as $m){
  $video=CommunityVideoTags::videoId((string)$m['source_url']);if(!$video)continue;
  $m['video_id']=$video;$matches[]=$m;if((int)$m['id']===(int)($_GET['match_id']??0))$selected=$m;
 }
}catch(Throwable $e){error_log('Scoring areas match list: '.$e->getMessage());}
?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Neptune · Scoring areas</title><link rel="stylesheet" href="../community/assets/field-regions/style.css?v=3-fieldmap"></head><body data-cloud-endpoint="scoring-areas.php" data-cloud-csrf="<?=htmlspecialchars($fieldCsrf,ENT_QUOTES)?>"<?php if($selected):?> data-youtube="<?=htmlspecialchars($selected['video_id'],ENT_QUOTES)?>" data-match-key="<?=htmlspecialchars($selected['match_key'],ENT_QUOTES)?>"<?php endif?>>
<header><div class="brand"><span class="logo">N</span><span>NEPTUNE <small>SCOUTING LAB</small></span></div><span class="badge"><?=$selected?'YOUTUBE · ':''?>PRIVATE WORKSPACE</span></header>
<main><div class="intro"><div><div class="eyebrow">FIELD UNDERSTANDING / 01</div><h1>Give the field some context.</h1><p>Mark the scoring target. Trace the surrounding zones. Keep each annotation tied to the camera view you actually watched.</p></div><div><button id="cloudsave" class="primary">Save to Neptune</button> <button id="export">Export annotations ↗</button></div></div>
<div class="workspace"><section class="viewer"><div class="toolbar"><div class="step">01 <b>Choose your footage</b></div><div class="sources"><form method="get" class="match-picker"><select name="match_id" aria-label="Match"><option value="">Choose a match…</option><?php foreach($matches as $m):?><option value="<?=(int)$m['id']?>"<?=$selected&&(int)$selected['id']===(int)$m['id']?' selected':''?>><?=htmlspecialchars($m['match_key'].($m['title']?' · '.$m['title']:''),ENT_QUOTES)?></option><?php endforeach?></select><noscript><button>Open</button></noscript></form><select id="library" aria-label="Saved regions"><option value="">Saved regions…</option></select><label class="button">Open video file<input id="file" type="file" accept="video/*" hidden></label></div></div>
<div id="stage" class="stage"><video id="video" playsinline preload="metadata"></video><canvas id="canvas" aria-label="Annotation canvas. Drag a box or click polygon vertices."></canvas><div id="empty"><div class="empty-icon">▱</div><h2>Your next training example starts here.</h2><p>Choose a match above. It plays from YouTube, like Community Tag Scouting.<br>No download needed. Open video file is still available for other footage.</p></div><div class="framebadge" id="framebadge">NO VIDEO LOADED</div></div>
<div class="transport"><button id="back" aria-label="Back one second">−1s</button><button id="play">Play</button><button id="next" aria-label="Forward one second">+1s</button><span id="clock">00:00.00 / 00:00.00</span><select id="speed" aria-label="Playback speed"><option value="0.25">¼×</option><option value="0.5">½×</option><option selected value="1">1×</option></select></div><input id="timeline" type="range" min="0" max="1" step=".01" value="0" aria-label="Video timeline">
<div class="tips"><span>PAUSE → DRAW → SET RANGE → SAVE</span><p>Targets and zones are supporting evidence. Being inside a zone does not prove that a robot scored.</p></div>
<div class="saved-head"><h2>Saved regions <span id="count">0</span></h2><div><button id="undo">Undo last save</button><label class="button">Import JSON<input id="import" type="file" accept="application/json,.json" hidden></label></div></div><div id="regions"><p class="muted">No regions yet. Start with a scoring target.</p></div></section>
<aside><div class="step">02 <b>Define a region</b></div><label for="game">Game / season</label><input id="game" value="2026-rebuilt"><label for="view">Camera view</label><select id="view"><option value="wide">Wide field</option><option value="closeup-left">Closeup · left</option><option value="closeup-right">Closeup · right</option><option value="other">Other view</option></select><label for="shot">Shot / camera position</label><input id="shot" value="shot-1"><small>Use a new shot after a pan, zoom, or camera cut.</small>
<label for="kind">Region type</label><select id="kind"><option value="scoring_target">Scoring target</option><option value="scoring_zone">Typical scoring position</option><option value="collection_zone">Collection zone</option><option value="feeding_zone">Feeding zone</option><option value="field_boundary">Field boundary</option><option value="field_calibration">Top-down map · four field corners</option></select><label for="alliance">Alliance</label><select id="alliance"><option value="neutral">Neutral / shared</option><option value="red">Red</option><option value="blue">Blue</option></select><label for="label">Region name</label><input id="label" placeholder="e.g. Red hub opening" maxlength="100">
<div class="shape-picker"><button id="box" class="active" aria-pressed="true">▭ Box</button><button id="polygon" aria-pressed="false">⬡ Polygon</button></div><p class="hint" id="hint">Pause and drag around the target.</p><div class="inline"><button id="finish">Finish polygon</button><button id="clear">Clear drawing</button></div>
<div class="step range-step">03 <b>Set the visible interval</b></div><div class="range"><div><label for="start">From second</label><input id="start" type="number" min="0" step=".01" value="0"><button id="setstart">Use current</button></div><div><label for="end">Through second</label><input id="end" type="number" min="0" step=".01" value="0"><button id="setend">Use current</button></div></div><small>Only include time where the region stays in this position. A single instant is valid for a reference frame.</small><button id="save" class="primary save">Save region</button><div id="status" role="status" aria-live="polite">Ready when you are.</div><div class="note"><b>Top-down trajectory</b><p>For a field map, mark exactly four corners in order: top-left, top-right, bottom-right, bottom-left. Use a separate calibration after each camera movement.</p><label class="button">Open trajectory result<input id="trajectoryfile" type="file" accept="application/json,.json" hidden></label><canvas id="fieldmap" width="560" height="300" aria-label="Top-down robot trajectories"></canvas><small id="mapstatus">Waiting for a calibrated match result.</small></div><div class="note"><b>Boxes or polygons?</b><p>Boxes work well for openings and goals. Polygons follow angled field zones more closely. Coordinates are saved relative to the full video frame.</p></div></aside></div></main><script src="../community/assets/field-regions/youtube-source.js?v=1"></script><script src="../community/assets/field-regions/app.js?v=2-youtube"></script></body></html>
