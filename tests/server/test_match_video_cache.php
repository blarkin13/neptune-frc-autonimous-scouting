<?php
declare(strict_types=1);
require_once __DIR__.'/../../server/neptune_secure/match-video-cache.php';
function check(bool $v):void{if(!$v)throw new RuntimeException('Assertion failed');}
function rejects(callable $f):void{try{$f();}catch(InvalidArgumentException $e){return;}throw new RuntimeException('Expected rejection');}
$root=sys_get_temp_dir().'/neptune-cache-test-'.bin2hex(random_bytes(6));mkdir($root,0700);
try{
 $cache=new MatchVideoCache($root,1);$other=new MatchVideoCache($root,2);$v='AAAAAAAAAAA';$raw="\0\0\0\x18ftypisom".str_repeat('x',40);$sha=hash('sha256',$raw);
 check(!$cache->info($v)['available']);rejects(fn()=>$cache->info('../anything'));rejects(fn()=>$cache->begin($v,$sha,MatchVideoCache::MAX+1,'owner'));
 $a=$cache->begin($v,$sha,strlen($raw),'owner');check($cache->begin($v,$sha,strlen($raw),'owner')['upload_id']===$a['upload_id']);
 check(!$cache->info($v)['available']);rejects(fn()=>$other->begin($v,$sha,strlen($raw),'else'));rejects(fn()=>$other->put($a['upload_id'],0,base64_encode($raw),'owner'));
 rejects(fn()=>$cache->put($a['upload_id'],3,base64_encode($raw),'owner'));
 check($cache->put($a['upload_id'],0,base64_encode($raw),'owner')['available']);check(!$other->info($v)['available']);
 $got=$cache->chunk($v,$sha,0);check(base64_decode($got['data_b64'],true)===$raw);check($got['sha256']===$sha);
 rejects(fn()=>$cache->begin($v,str_repeat('b',64),strlen($raw),'owner'));check($cache->info($v)['video']['sha256']===$sha);
 $a=$cache->begin('BBBBBBBBBBB',str_repeat('c',64),strlen($raw),'owner');rejects(fn()=>$cache->put($a['upload_id'],0,base64_encode($raw),'owner'));check(!$cache->info('BBBBBBBBBBB')['available']);
 $f=fopen($root.'/match-video-cache/1/full.mp4','w');ftruncate($f,MatchVideoCache::CAP);fclose($f);rejects(fn()=>$cache->begin('CCCCCCCCCCC',$sha,strlen($raw),'owner'));
 echo "Private cache checks passed: resume, visibility, owner isolation, offsets, checksums, source preservation, capacity.\n";
}finally{
 $it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $f){if($f->isDir())rmdir($f->getPathname());else unlink($f->getPathname());}rmdir($root);
}
