<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/neptune_secure/community-analysis.php';
$dsn=getenv('COMMUNITY_TEST_DSN')?:'sqlite::memory:';
$db=new PDO($dsn,getenv('COMMUNITY_TEST_USER')?:null,getenv('COMMUNITY_TEST_PASSWORD')?:null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
if($db->getAttribute(PDO::ATTR_DRIVER_NAME)==='mysql') {
 $sql=file_get_contents(dirname(__DIR__,2).'/sql/2026-10-17-community-analysis.sql');$db->exec($sql);
} else {
 $db->exec('CREATE TABLE community_matches(id INTEGER PRIMARY KEY AUTOINCREMENT,match_key TEXT UNIQUE,title TEXT,roster_json TEXT,source_url TEXT,source_sha256 TEXT,duration_ms INTEGER,rules_text TEXT,ready INTEGER,created_at INTEGER);
 CREATE TABLE community_attempts(id TEXT PRIMARY KEY,match_id INTEGER,user_id INTEGER,device_id TEXT,request_key TEXT,status TEXT,created_at INTEGER,UNIQUE(user_id,request_key));
 CREATE TABLE community_leases(match_id INTEGER PRIMARY KEY,attempt_id TEXT UNIQUE,user_id INTEGER UNIQUE,device_id TEXT UNIQUE,expires_at INTEGER,stage TEXT);
 CREATE TABLE community_submissions(id TEXT PRIMARY KEY,attempt_id TEXT UNIQUE,match_id INTEGER,user_id INTEGER,payload_json TEXT,payload_hash TEXT,review_state TEXT,reviewer_id INTEGER,review_note TEXT,reviewed_at INTEGER,created_at INTEGER);
 CREATE TABLE community_publications(match_id INTEGER PRIMARY KEY,submission_id TEXT UNIQUE,published_at INTEGER);');
}
$service=new CommunityAnalysis($db,str_repeat('s',32));
$count=0;
function check(bool $condition,string $label):void { global $count;if(!$condition)throw new RuntimeException('FAIL: '.$label);$count++;echo 'PASS '.$label."\n"; }
function fails(callable $f,int $status,string $label):void {try{$f();}catch(CommunityAnalysisError $e){check($e->httpStatus===$status,$label);return;}throw new RuntimeException('Expected failure: '.$label);}
function seed(PDO $db,int $n):int {
 $s=$db->prepare('INSERT INTO community_matches(match_key,title,roster_json,source_url,source_sha256,duration_ms,rules_text,ready,created_at) VALUES(?,?,?,?,?,?,?,1,?)');
 $s->execute(['test-'.$n,'Test match '.$n,'{"red":[1,2,3],"blue":[4,5,6]}','https://example.org/match.mp4',str_repeat('a',64),10000,'Test rules',time()]);return (int)$db->lastInsertId();
}
$m=seed($db,1);$m2=seed($db,2);
$a=$service->claim($m,1,'device-1',str_repeat('a',16));
check($a['pipeline']['paid_api_allowed']===false,'paid inference disabled');
check($service->claim($m,1,'device-1',str_repeat('a',16))['attempt_id']===$a['attempt_id'],'claim retries return same lease');
fails(fn()=>$service->claim($m,2,'device-2',str_repeat('b',16)),409,'second contributor cannot claim occupied match');
fails(fn()=>$service->claim($m2,1,'device-3',str_repeat('c',16)),409,'one active match per user');
fails(fn()=>$service->claim($m2,3,'device-1',str_repeat('d',16)),409,'one active match per device');
fails(fn()=>$service->heartbeat($a['attempt_id'],2,'device-1',$a['lease_token'],'x'),403,'attempt ownership enforced');
fails(fn()=>$service->heartbeat($a['attempt_id'],1,'device-1','wrong','x'),403,'lease token enforced');
$db->prepare('UPDATE community_leases SET expires_at=? WHERE attempt_id=?')->execute([time()-1,$a['attempt_id']]);
fails(fn()=>$service->heartbeat($a['attempt_id'],1,'device-1',$a['lease_token'],'x'),409,'expired heartbeat cannot revive lease');
$b=$service->claim($m,2,'device-2',str_repeat('e',16));
$payload=['schema_version'=>1,'source_sha256'=>str_repeat('a',64),'summary'=>'An explicitly uncertain draft.','model'=>'test-local','runtime'=>'test','prompt_version'=>'1','inference_location'=>'local','observations'=>[['start_ms'=>0,'end_ms'=>1000,'team'=>1,'certainty'=>'uncertain','note'=>'Robot identity partially obscured.']]];
fails(fn()=>$service->submit($a['attempt_id'],1,'device-1',$a['lease_token'],$payload),409,'stale attempt cannot submit after reassignment');
$bad=$payload;$bad['observations'][0]['team']=999;
fails(fn()=>$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$bad),422,'unlisted robot rejected');
$bad=$payload;$bad['observations'][0]['end_ms']=10001;
fails(fn()=>$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$bad),422,'invalid timestamps rejected');
$bad=$payload;$bad['source_sha256']=str_repeat('b',64);
fails(fn()=>$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$bad),422,'wrong source rejected');
$bad=$payload;$bad['inference_location']='cloud';
fails(fn()=>$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$bad),422,'cloud submission rejected');
$bad=$payload;$bad['scoring_contribution']=0;
fails(fn()=>$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$bad),422,'unsupported score including zero rejected');
$r=$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$payload);
check($service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$payload)===$r,'submission retry returns receipt');
$bad=$payload;$bad['summary']='Different';
fails(fn()=>$service->submit($b['attempt_id'],2,'device-2',$b['lease_token'],$bad),409,'immutable payload enforced');
fails(fn()=>$service->published($m),404,'pending submission not public');
fails(fn()=>$service->review($r['submission_id'],2,'published',''),403,'self-publication denied');
$service->review($r['submission_id'],3,'published','Checked footage.');
check($service->published($m)['analysis']['summary']===$payload['summary'],'approved report publicly readable');
fails(fn()=>$service->review($r['submission_id'],4,'rejected','reason'),409,'concurrent stale review rejected');
fails(fn()=>$service->claim($m,5,'device-5',str_repeat('f',16)),409,'published match cannot be claimed again');
$c=$service->claim($m2,2,'device-2',str_repeat('g',16));
$service->release($c['attempt_id'],2,'device-2',$c['lease_token']);
$d=$service->claim($m2,4,'device-4',str_repeat('h',16));
$rejected=$service->submit($d['attempt_id'],4,'device-4',$d['lease_token'],$payload);
$service->review($rejected['submission_id'],3,'rejected','Recheck identity.');
check(!empty($service->claim($m2,5,'device-5',str_repeat('i',16))['attempt_id']),'rejected match becomes available');
// No global limiter: reserve more than 200 distinct jobs/users/devices.
for($i=10;$i<215;$i++)$service->claim(seed($db,$i),$i,'device-'.$i,str_pad((string)$i,16,'x'));
check((int)$db->query('SELECT COUNT(*) FROM community_leases')->fetchColumn()>200,'no hard-coded global cap of 200');
if($db->getAttribute(PDO::ATTR_DRIVER_NAME)==='mysql' && function_exists('pcntl_fork')) {
 $race=seed($db,10000);$children=[];
 for($i=0;$i<16;$i++) {
  $pid=pcntl_fork();
  if($pid===0) {
   try {
    $childDb=new PDO($dsn,getenv('COMMUNITY_TEST_USER')?:null,getenv('COMMUNITY_TEST_PASSWORD')?:null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    (new CommunityAnalysis($childDb,str_repeat('s',32)))->claim($race,1000+$i,'race-device-'.$i,str_pad('race'.$i,16,'x'));
    exit(0);
   } catch(CommunityAnalysisError $e) { exit($e->httpStatus===409?10:20); }
   catch(Throwable $e) { exit(21); }
  }
  $children[]=$pid;
 }
 $wins=0;$conflicts=0;
 foreach($children as $pid){pcntl_waitpid($pid,$status);$code=pcntl_wexitstatus($status);if($code===0)$wins++;if($code===10)$conflicts++;}
 check($wins===1 && $conflicts===15,'sixteen simultaneous claims produce exactly one winner');
 // Forked processes must not reuse an inherited database connection.
 $db=new PDO($dsn,getenv('COMMUNITY_TEST_USER')?:null,getenv('COMMUNITY_TEST_PASSWORD')?:null);
}
echo "Verified $count behavioral checks on ".$db->getAttribute(PDO::ATTR_DRIVER_NAME).".\n";
