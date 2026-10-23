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
$_SESSION['robot_labels_csrf']??=bin2hex(random_bytes(32));
$csrf=$_SESSION['robot_labels_csrf'];
// Labels: one file per YouTube video, frames keyed by video time; read by the helper to train the robot detector.
$store=dirname(__DIR__,3).'/neptune_secure/robot-labels/'.(int)$u['organization_id'];
function robot_reply(int $code,array $data):never{http_response_code($code);header('Content-Type: application/json');echo json_encode($data,JSON_THROW_ON_ERROR);exit;}
function robot_video(string $v):string{if(!preg_match('/^[A-Za-z0-9_-]{11}$/D',$v))robot_reply(422,['error'=>'Invalid video.']);return $v;}
function robot_doc(string $store,string $video):array{$f=$store.'/'.$video.'.json';return is_file($f)?json_decode((string)file_get_contents($f),true,32,JSON_THROW_ON_ERROR):['schema_version'=>1,'video_id'=>$video,'frames'=>[]];}
// Boxes the detector found at this moment, from the helper's tracking review backed up for this video.
function robot_prefill(PDO $pdo,int $org,string $video,int $tms):array{
 try{$q=$pdo->prepare('SELECT review_gzip FROM community_identity_reviews WHERE organization_id=? AND video_id=? ORDER BY updated_at DESC LIMIT 1');$q->execute([$org,$video]);$gz=$q->fetchColumn();}
 catch(Throwable $e){return ['boxes'=>[],'times'=>[],'source'=>'none'];}
 if(!$gz)return ['boxes'=>[],'times'=>[],'source'=>'none'];
 $review=json_decode((string)gzdecode((string)$gz),true,64);$points=is_array($review['points']??null)?$review['points']:[];
 $times=[];$out=[];
 foreach($points as $p){
  if(!is_array($p['box']??null)||count($p['box'])!==4||!in_array($p['alliance']??'',['red','blue'],true)||($p['box_source']??'')==='optical_flow')continue;
  $t=(int)round(((float)$p['t'])*1000);$times[$t]=true;
  if(abs($t-$tms)>90)continue;
  [$x,$y,$w,$h]=array_map('floatval',$p['box']);$bw=$w/1.6;$bh=$h/3.4; // undo the tracker's chassis crop around the bumper
  $out[]=['alliance'=>$p['alliance'],'x'=>$x+.3*$bw,'y'=>$y+2*$bh,'w'=>$bw,'h'=>$bh,'source'=>'detector'];
 }
 $times=array_keys($times);sort($times);
 return ['boxes'=>$out,'times'=>$times,'source'=>'tracking_review'];
}
if($_SERVER['REQUEST_METHOD']==='GET'&&isset($_GET['labels'])){$v=robot_video((string)$_GET['labels']);robot_reply(200,robot_doc($store,$v));}
if($_SERVER['REQUEST_METHOD']==='GET'&&isset($_GET['prefill'])){$v=robot_video((string)$_GET['prefill']);robot_reply(200,robot_prefill($pdo,(int)$u['organization_id'],$v,max(0,(int)($_GET['t_ms']??0))));}
if($_SERVER['REQUEST_METHOD']==='POST'){
 if(!hash_equals($csrf,(string)($_SERVER['HTTP_X_ROBOT_LABELS_CSRF']??'')))robot_reply(403,['error'=>'Refresh this page before saving']);
 $raw=file_get_contents('php://input',false,null,0,262145);if(strlen($raw)>262144)robot_reply(413,['error'=>'Too large']);
 try{
  $p=json_decode($raw,true,16,JSON_THROW_ON_ERROR);$v=robot_video((string)($p['video_id']??''));$tms=$p['t_ms']??null;
  if(!is_int($tms)||$tms<0||$tms>36000000)throw new RuntimeException('Invalid video time');
  $match=(string)($p['match_key']??'');if(!preg_match('/^\d{4}[A-Za-z0-9_-]{1,95}$/D',$match))throw new RuntimeException('Invalid match');
  $boxes=[];
  foreach(($p['boxes']??[]) as $b){
   if(!in_array($b['alliance']??'',['red','blue'],true))throw new RuntimeException('Each box needs red or blue');
   $vals=[];foreach(['x','y','w','h'] as $k){if(!is_numeric($b[$k]??null)||!is_finite((float)$b[$k]))throw new RuntimeException('Invalid box');$vals[$k]=(float)$b[$k];}
   if($vals['w']<=0||$vals['h']<=0||$vals['w']>1||$vals['h']>1)continue;
   $boxes[]=['alliance'=>$b['alliance']]+$vals;
  }
  if(count($boxes)>60)throw new RuntimeException('Too many boxes in one frame');
  if(!is_dir($store)&&!mkdir($store,0700,true))throw new RuntimeException('Label storage unavailable');
  $doc=robot_doc($store,$v);$doc['match_key']=$match;
  if(!empty($p['delete']))unset($doc['frames'][(string)$tms]);
  else $doc['frames'][(string)$tms]=['boxes'=>$boxes,'complete'=>!empty($p['complete'])&&empty($p['skipped']),'skipped'=>!empty($p['skipped']),'saved_at'=>time(),'saved_by'=>(int)$u['id']];
  $tmp=tempnam($store,'pending-');if($tmp===false||file_put_contents($tmp,json_encode($doc,JSON_THROW_ON_ERROR),LOCK_EX)===false)throw new RuntimeException('Could not save');
  chmod($tmp,0600);if(!rename($tmp,$store.'/'.$v.'.json'))throw new RuntimeException('Could not commit save');
  robot_reply(200,['ok'=>true,'frames'=>count($doc['frames']),'complete'=>count(array_filter($doc['frames'],fn($f)=>!empty($f['complete'])))]);
 }catch(Throwable $e){robot_reply(422,['error'=>$e->getMessage()]);}
}
$matches=[];$selected=null;$counts=[];
try{
 foreach($pdo->query('SELECT id,match_key,title,source_url FROM community_matches ORDER BY match_key')->fetchAll(PDO::FETCH_ASSOC) as $m){
  $video=CommunityVideoTags::videoId((string)$m['source_url']);if(!$video)continue;
  $m['video_id']=$video;$matches[]=$m;if((int)$m['id']===(int)($_GET['match_id']??0))$selected=$m;
  $f=$store.'/'.$video.'.json';if(is_file($f)){$d=json_decode((string)file_get_contents($f),true);$counts[$video]=count(array_filter($d['frames']??[],fn($x)=>!empty($x['complete'])));}
 }
}catch(Throwable $e){error_log('Robot labels match list: '.$e->getMessage());}
$total=array_sum($counts);
require_once dirname(__DIR__).'/community/layout.php';community_page_start('Robot Labels','Box every robot bumper on match frames so Auto Scout learns to find robots in any broadcast.','robots','PLATFORM OWNER · TRAINING DATA');
?>
<link rel="stylesheet" href="../community/assets/field-regions/style.css?v=4-site-layout">
<link rel="stylesheet" href="../community/assets/robot-labels/robot-labels.css?v=1">
<div class="field-regions robot-labels" id="robot-labels-app" data-csrf="<?=e($csrf)?>"<?php if($selected):?> data-youtube="<?=e($selected['video_id'])?>" data-match-key="<?=e($selected['match_key'])?>"<?php endif?>>
<div class="fr-actions"><p>Training data for the robot detector: box <strong>every</strong> visible bumper, including robots the current detector misses. <?=$total?> frames complete across <?=count(array_filter($counts))?> matches.</p></div>
<div class="workspace"><section class="viewer"><div class="toolbar"><div class="step">01 <b>Choose a match</b></div><div class="sources"><form method="get" class="match-picker"><select name="match_id" aria-label="Match"><option value="">Choose a match…</option><?php foreach($matches as $m):?><option value="<?=(int)$m['id']?>"<?=$selected&&(int)$selected['id']===(int)$m['id']?' selected':''?>><?=e($m['match_key'].($m['title']?' · '.$m['title']:'').(!empty($counts[$m['video_id']])?' · '.$counts[$m['video_id']].' done':''))?></option><?php endforeach?></select><noscript><button>Open</button></noscript></form></div></div>
<div id="frame" class="rl-frame"><div id="zoomer" class="rl-zoomer"><div id="stage" class="stage"><video id="video" playsinline></video><canvas id="canvas" aria-label="Bumper boxes. Drag to draw; click to select."></canvas></div></div><div id="empty"><div class="empty-icon">▣</div><h2>Choose a match to start labeling.</h2><p>It plays from YouTube, like Watch &amp; tag.</p></div><div class="framebadge" id="framebadge">NO MATCH</div></div>
<div class="transport"><button id="prevframe" title="Previous frame to label (←)">◀ Frame</button><button id="play">Play</button><button id="nextframe" title="Next frame to label (→)">Frame ▶</button><span id="clock">00:00.00</span><span id="framecount" class="rl-count"></span></div>
<div class="tips"><span>PAUSE → BOX EVERY BUMPER → ENTER</span><p>Dashed boxes are the detector's guesses (from your tracking review); fix, delete or keep them and draw the ones it missed. Scroll to zoom, Space+drag to pan, 0 to fit.</p></div></section>
<aside><div class="step">02 <b>Box the bumpers</b></div><div class="shape-picker"><button id="red" class="rl-red active" aria-pressed="true">Red (1)</button><button id="blue" class="rl-blue" aria-pressed="false">Blue (2)</button></div>
<p class="hint">Drag on empty space: new box · Click: select · Drag: move · Corner: resize · <b>X</b> flips color · <b>Delete</b> removes.</p>
<div class="rl-stats"><div><span id="boxcount">0</span><small>boxes in this frame</small></div><div><span id="donecount">0</span><small>frames complete in this match</small></div></div>
<button id="complete" class="primary save">All bumpers boxed ↵</button><button id="skip" class="save rl-secondary">Skip frame (replay, graphic, blurry)</button>
<div id="status" role="status" aria-live="polite">Choose a match.</div>
<div class="note"><b>What makes good labels</b><p>Every bumper you can see, red or blue, even partly hidden or far away. Box just the bumper, not the whole robot. Skip frames that aren't live match footage.</p></div></aside></div></div>
<script src="../community/assets/field-regions/youtube-source.js?v=3-generic"></script><script src="../community/assets/robot-labels/robot-labels.js?v=1"></script>
<?php community_page_end(); ?>
