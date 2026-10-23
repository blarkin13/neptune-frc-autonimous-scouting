<?php
declare(strict_types=1);

/** Robot-detector work for connected helpers: prepare labelling frames, train the detector, share the adopted one.
 *
 * Kept apart from the action-model job tables on purpose. Files live under neptune_secure/robot-detector/<org>/:
 *   requests/<id>.json   queued / claimed / done requests
 *   current/             the adopted wide-shot bumper detector (manifest.json + weights) every helper downloads
 *   prefill/<video>.json detector boxes for Robot labels frames
 */
final class RobotDetectorJobs {
 private string $root;
 public function __construct(string $secure,int $org){$this->root=$secure.'/robot-detector/'.$org;}
 private function dir(string $sub):string{$d=$this->root.'/'.$sub;if(!is_dir($d)&&!mkdir($d,0700,true))throw new RuntimeException('Detector storage unavailable');return $d;}
 private static function write(string $file,array $data):void{
  $tmp=tempnam(dirname($file),'pending-');if($tmp===false||file_put_contents($tmp,json_encode($data,JSON_THROW_ON_ERROR),LOCK_EX)===false)throw new RuntimeException('Could not save');
  chmod($tmp,0600);if(!rename($tmp,$file))throw new RuntimeException('Could not commit save');
 }
 private static function video(string $v):string{if(!preg_match('/^[A-Za-z0-9_-]{11}$/D',$v))throw new InvalidArgumentException('Invalid video');return $v;}

 /** Queue a request from the website. Re-queuing the same open request returns the existing one. */
 public function queue(string $kind,array $p,int $user):array{
  if(!in_array($kind,['prepare','train'],true))throw new InvalidArgumentException('Unknown request');
  $body=['kind'=>$kind];
  if($kind==='prepare'){$body['video_id']=self::video((string)($p['video_id']??''));$body['match_key']=(string)($p['match_key']??'');if(!preg_match('/^\d{4}[A-Za-z0-9_-]{1,95}$/D',$body['match_key']))throw new InvalidArgumentException('Invalid match');}
  foreach($this->requests() as $r)if(in_array($r['state'],['queued','claimed'],true)&&$r['kind']===$kind&&($r['video_id']??null)===($body['video_id']??null))return $r;
  $r=$body+['id'=>bin2hex(random_bytes(12)),'state'=>'queued','created_at'=>time(),'created_by'=>$user,'message'=>'Waiting for a connected helper'];
  self::write($this->dir('requests').'/'.$r['id'].'.json',$r);return $r;
 }
 public function requests():array{
  $out=[];foreach(glob($this->root.'/requests/*.json')?:[] as $f){$r=json_decode((string)file_get_contents($f),true);if(is_array($r))$out[]=$r;}
  usort($out,fn($a,$b)=>$b['created_at']<=>$a['created_at']);return array_slice($out,0,50);
 }
 /** A helper takes the oldest queued request; a claim older than 4 hours without progress is reclaimable. */
 public function claim(array $computer):?array{
  $all=array_reverse($this->requests());
  foreach($all as $r){
   $stale=$r['state']==='claimed'&&time()-(int)($r['heartbeat_at']??$r['claimed_at']??0)>4*3600;
   if($r['state']!=='queued'&&!$stale)continue;
   $r=array_replace($r,['state'=>'claimed','claimed_at'=>time(),'heartbeat_at'=>time(),'computer_id'=>$computer['id'],'lease'=>bin2hex(random_bytes(16)),'message'=>'Started on a helper']);
   self::write($this->dir('requests').'/'.$r['id'].'.json',$r);return $r;
  }
  return null;
 }
 private function owned(array $computer,array $p):array{
  $id=(string)($p['request_id']??'');if(!preg_match('/^[a-f0-9]{24}$/D',$id))throw new InvalidArgumentException('Invalid request');
  $f=$this->root.'/requests/'.$id.'.json';$r=is_file($f)?json_decode((string)file_get_contents($f),true):null;
  if(!$r||($r['computer_id']??null)!==$computer['id']||!hash_equals((string)($r['lease']??''),(string)($p['lease']??'')))throw new InvalidArgumentException('This request belongs to another helper');
  return $r;
 }
 public function progress(array $computer,array $p):array{
  $r=$this->owned($computer,$p);$r['heartbeat_at']=time();$r['message']=mb_substr((string)($p['message']??''),0,300);
  self::write($this->root.'/requests/'.$r['id'].'.json',$r);return ['ok'=>true];
 }
 public function finish(array $computer,array $p):array{
  $r=$this->owned($computer,$p);$ok=!empty($p['ok']);
  $r=array_replace($r,['state'=>$ok?'done':'failed','finished_at'=>time(),'message'=>mb_substr((string)($p['message']??''),0,500),'report'=>is_array($p['report']??null)?$p['report']:null]);
  unset($r['lease']);self::write($this->root.'/requests/'.$r['id'].'.json',$r);return ['ok'=>true];
 }
 /** Detector guesses for Robot labels frames: {t_ms: [{alliance,x,y,w,h}]} plus the frame times. */
 public function putPrefill(array $computer,array $p):array{
  $this->owned($computer,$p);$v=self::video((string)($p['video_id']??''));$frames=[];
  foreach(($p['frames']??[]) as $t=>$boxes){
   if(!ctype_digit((string)$t)||!is_array($boxes)||count($boxes)>80)throw new InvalidArgumentException('Invalid frame');
   $frames[(string)$t]=array_values(array_filter(array_map(fn($b)=>is_array($b)&&in_array($b['alliance']??'',['red','blue'],true)?['alliance'=>$b['alliance'],'x'=>(float)$b['x'],'y'=>(float)$b['y'],'w'=>(float)$b['w'],'h'=>(float)$b['h']]:null,$boxes)));
  }
  if(count($frames)>2000)throw new InvalidArgumentException('Too many frames');
  self::write($this->dir('prefill').'/'.$v.'.json',['video_id'=>$v,'frames'=>$frames,'detector'=>(string)($p['detector']??''),'created_at'=>time()]);
  return ['ok'=>true,'frames'=>count($frames)];
 }
 public function prefill(string $video):?array{$f=$this->root.'/prefill/'.self::video($video).'.json';return is_file($f)?json_decode((string)file_get_contents($f),true):null;}
 /** The adopted detector: manifest always; weights only when the helper's copy differs. */
 public function current(?string $have=null):array{
  $m=$this->root.'/current/manifest.json';if(!is_file($m))return ['detector'=>null];
  $manifest=json_decode((string)file_get_contents($m),true);$out=['detector'=>$manifest];
  if($have!==($manifest['by_camera']['wide']['sha256']??null)){$w=$this->root.'/current/'.($manifest['by_camera']['wide']['file']??'');if(is_file($w))$out['weights_b64']=base64_encode((string)file_get_contents($w));}
  return $out;
 }
 /** Adopt a detector the helper trained and showed better on a held-out match. Previous one is kept. */
 public function adopt(array $computer,array $p):array{
  $r=$this->owned($computer,$p);if($r['kind']!=='train')throw new InvalidArgumentException('Only a training request can adopt a detector');
  $raw=base64_decode((string)($p['weights_b64']??''),true);if($raw===false||strlen($raw)<1000||strlen($raw)>60*1024*1024)throw new InvalidArgumentException('Invalid detector weights');
  $sha=hash('sha256',$raw);$report=is_array($p['report']??null)?$p['report']:[];
  $cur=$this->dir('current');$old=$cur.'/manifest.json';
  if(is_file($old)){$hist=$this->dir('history/'.date('Ymd-His'));foreach(glob($cur.'/*')?:[] as $f)copy($f,$hist.'/'.basename($f));}
  $file='bumper_wide_'.substr($sha,0,12).'.pt';file_put_contents($cur.'/'.$file,$raw,LOCK_EX);chmod($cur.'/'.$file,0600);
  foreach(glob($cur.'/bumper_wide_*.pt')?:[] as $f)if(basename($f)!==$file)unlink($f);
  self::write($old,['schema_version'=>1,'by_camera'=>['wide'=>['file'=>$file,'sha256'=>$sha]],'adopted_at'=>time(),'request_id'=>$r['id'],'report'=>$report]);
  return ['ok'=>true,'sha256'=>$sha];
 }
}
