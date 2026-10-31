<?php
declare(strict_types=1);
require_once __DIR__.'/../../neptune_secure/community-training-pairing.php';
$db=new PDO('sqlite::memory:');$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$db->exec("CREATE TABLE organizations(id INTEGER PRIMARY KEY,platform_status TEXT);INSERT INTO organizations VALUES(1,'active');
CREATE TABLE users(id INTEGER PRIMARY KEY,organization_id INT,role TEXT,password_hash TEXT,active INT,must_change_password INT,display_name TEXT,username TEXT);
INSERT INTO users VALUES(1,1,'owner','password-one',1,0,'Scout One','one');INSERT INTO users VALUES(2,1,'scouter','password-two',1,0,'Scout Two','two');
CREATE TABLE community_training_pair_requests(id TEXT PRIMARY KEY,challenge TEXT,state TEXT,port INT,user_code TEXT,status TEXT DEFAULT 'pending',user_id INT,credential_revision TEXT,code_hash TEXT,created_at INT,expires_at INT);
CREATE TABLE community_training_pair_limits(ip_hash TEXT PRIMARY KEY,window_start INT,starts INT);
CREATE TABLE community_training_computers(id TEXT PRIMARY KEY,user_id INT,token_hash TEXT,credential_revision TEXT,expires_at INT,created_at INT,revoked INT DEFAULT 0,name TEXT);");
$p=new CommunityTrainingPairing($db,['secret'=>str_repeat('s',64),'platform_organization_id'=>1]);
$verifier=str_repeat('a',64);$challenge=rtrim(strtr(base64_encode(hash('sha256',$verifier,true)),'+/','-_'),'=');$state=str_repeat('b',64);
$n=0;
function check(bool $ok,string $message):void{global $n;if(!$ok)throw new RuntimeException($message);$n++;echo 'PASS '.$message."\n";}
function rejected(callable $fn,int $status,string $message):void{try{$fn();}catch(CommunityAnalysisError $e){check($e->httpStatus===$status,$message);return;}throw new RuntimeException('Not rejected: '.$message);}
$new=fn()=> $p->start(['challenge'=>$challenge,'state'=>$state,'port'=>49123],'203.0.113.1');
$r=$new();check(!isset($r['access_token']),'starting connection grants no access');
rejected(fn()=> $p->exchange(['request_id'=>$r['request_id'],'code'=>str_repeat('c',64),'verifier'=>$verifier]),401,'pending approval cannot issue credentials');
rejected(fn()=> $p->authorize($r['request_id'],2,hash('sha256','password-two'),true),403,'browser approval requires platform owner access');
$url=$p->authorize($r['request_id'],1,hash('sha256','password-one'),true);$parts=parse_url($url);parse_str($parts['query'],$params);
check($parts['scheme']==='http'&&$parts['host']==='127.0.0.1'&&$parts['port']===49123&&$params['state']===$state,'callback restricted to requested loopback port and state');
rejected(fn()=> $p->exchange(['request_id'=>$r['request_id'],'code'=>$params['code'],'verifier'=>str_repeat('z',64)]),401,'intercepted authorization code needs PKCE verifier');
$grant=$p->exchange(['request_id'=>$r['request_id'],'code'=>$params['code'],'verifier'=>$verifier]);check(strlen($grant['access_token'])===64,'approved helper receives internal credential');
check($db->query('SELECT token_hash FROM community_training_computers')->fetchColumn()===hash('sha256',$grant['access_token']),'database stores credential hash only');
rejected(fn()=> $p->exchange(['request_id'=>$r['request_id'],'code'=>$params['code'],'verifier'=>$verifier]),401,'authorization code is single use');
$r=$new();$p->authorize($r['request_id'],1,hash('sha256','password-one'),false);
rejected(fn()=> $p->exchange(['request_id'=>$r['request_id'],'code'=>str_repeat('a',64),'verifier'=>$verifier]),401,'denied approval cannot issue credentials');
$r=$new();$db->exec("UPDATE community_training_pair_requests SET expires_at=0 WHERE id='".$r['request_id']."'");
rejected(fn()=> $p->inspect($r['request_id']),410,'expired browser approval is rejected');
$r=$new();$url=$p->authorize($r['request_id'],1,hash('sha256','password-one'),true);parse_str(parse_url($url,PHP_URL_QUERY),$params);$db->exec("UPDATE users SET password_hash='changed' WHERE id=1");
rejected(fn()=> $p->exchange(['request_id'=>$r['request_id'],'code'=>$params['code'],'verifier'=>$verifier]),401,'account credential change invalidates pending approval');
$db->exec("UPDATE users SET password_hash='password-one' WHERE id=1");
$r=$new();$url=$p->authorize($r['request_id'],1,hash('sha256','password-one'),true);parse_str(parse_url($url,PHP_URL_QUERY),$params);$db->exec("UPDATE organizations SET platform_status='suspended' WHERE id=1");
rejected(fn()=> $p->exchange(['request_id'=>$r['request_id'],'code'=>$params['code'],'verifier'=>$verifier]),403,'organization suspension invalidates pending approval');
$db->exec("UPDATE organizations SET platform_status='active' WHERE id=1");
for($i=0;$i<20;$i++)$p->start(['challenge'=>$challenge,'state'=>$state,'port'=>49123],'198.51.100.2');
rejected(fn()=> $p->start(['challenge'=>$challenge,'state'=>$state,'port'=>49123],'198.51.100.2'),429,'connection starts throttled per IP without a global helper cap');
rejected(fn()=> $p->start(['challenge'=>$challenge,'state'=>$state,'port'=>80],'203.0.113.2'),422,'invalid callback port rejected');
echo "Verified $n browser-connection checks.\n";
// Reconnect keeps the computer: same id and name with a fresh connection; another user's id is never taken over; new ones use their own name.
$db->exec("UPDATE users SET password_hash='password-one' WHERE id=1");
$pair=function(array $extra)use($p,$new,$verifier):array{$r=$new();$url=$p->authorize($r['request_id'],1,hash('sha256','password-one'),true);parse_str(parse_url($url,PHP_URL_QUERY),$q);return $p->exchange(['request_id'=>$r['request_id'],'code'=>$q['code'],'verifier'=>$verifier]+$extra);};
$first=$pair(['name'=>'Lab PC']);check($db->query("SELECT name FROM community_training_computers WHERE id='".$first['computer_id']."'")->fetchColumn()==='Lab PC','a new computer is named after itself');
$db->exec("UPDATE community_training_computers SET name='Renamed rig',expires_at=1 WHERE id='".$first['computer_id']."'");$before=(int)$db->query('SELECT COUNT(*) FROM community_training_computers')->fetchColumn();
$again=$pair(['computer_id'=>$first['computer_id'],'name'=>'Lab PC']);
check($again['computer_id']===$first['computer_id']&&(int)$db->query('SELECT COUNT(*) FROM community_training_computers')->fetchColumn()===$before,'reconnecting reuses the same computer instead of adding one');
check($db->query("SELECT name FROM community_training_computers WHERE id='".$first['computer_id']."'")->fetchColumn()==='Renamed rig'&&$db->query("SELECT token_hash FROM community_training_computers WHERE id='".$first['computer_id']."'")->fetchColumn()===hash('sha256',$again['access_token'])&&(int)$db->query("SELECT expires_at FROM community_training_computers WHERE id='".$first['computer_id']."'")->fetchColumn()>time(),'it keeps its name and gets a fresh connection');
$db->exec("INSERT INTO community_training_computers(id,user_id,token_hash,credential_revision,expires_at,created_at,name) VALUES('".str_repeat('e',32)."',2,'x','y',1,1,'Someone else')");
$other=$pair(['computer_id'=>str_repeat('e',32)]);check($other['computer_id']!==str_repeat('e',32)&&$db->query("SELECT token_hash FROM community_training_computers WHERE id='".str_repeat('e',32)."'")->fetchColumn()==='x','another user\'s computer is never taken over');
