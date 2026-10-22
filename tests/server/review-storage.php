<?php
declare(strict_types=1);
class CommunityAnalysisError extends RuntimeException {public function __construct(public int $httpStatus,string $message){parent::__construct($message);}}
require dirname(__DIR__,2).'/server/neptune_secure/community-review-storage.php';
$db=new PDO('sqlite::memory:');$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$store=new CommunityReviewStorage($db);$store->schema();
$owner=['organization_id'=>1,'user_id'=>7];$other=['organization_id'=>2,'user_id'=>8];
$source=str_repeat('a',64);
$review=['schema_version'=>1,'source_sha256'=>$source,'match_key'=>'2026test_qm1','video_id'=>'abcdefghijk','roster'=>['red'=>[1,2,3],'blue'=>[4,5,6]],'points'=>[],'corrections'=>[['review_track'=>'x','start'=>1,'end'=>2,'team'=>1]]];
$encode=function(array $r) use($source):array{$raw=json_encode($r,JSON_THROW_ON_ERROR);return ['source_sha256'=>$source,'expected_revision'=>null,'review_gzip_b64'=>base64_encode(gzencode($raw))];};
$check=function(bool $ok,string $name):void{if(!$ok)throw new RuntimeException($name);};
$first=$store->put($owner,$encode($review));$check($first['ok']&&!$first['unchanged'],'first backup');
$loaded=$store->get($owner,['source_sha256'=>$source]);$check($loaded['found']&&$loaded['revision']===$first['revision'],'owner read');
$check(json_decode(gzdecode(base64_decode($loaded['review_gzip_b64'])),true)['corrections']===$review['corrections'],'review round trip');
$check(!$store->get($other,['source_sha256'=>$source])['found'],'organization isolation');
$check(count($store->listing($owner)['reviews'])===1&&$store->listing($other)['reviews']===[],'owner-only review list');
$check($store->put($owner,$encode($review))['unchanged'],'idempotent retry');
$review['corrections'][]=['review_track'=>'y','start'=>3,'end'=>4,'team'=>2];$next=$encode($review);
try{$store->put($owner,$next);throw new RuntimeException('stale helper overwrote review');}catch(CommunityAnalysisError $error){$check($error->httpStatus===409,'stale edit rejected');}
$next['expected_revision']=$first['revision'];$second=$store->put($owner,$next);$check($second['revision']!==$first['revision'],'revision update');
$check($db->query('SELECT COUNT(*) FROM community_identity_reviews')->fetchColumn()==1,'single retained review');
echo "review storage checks passed\n";
