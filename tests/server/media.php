<?php
declare(strict_types=1);
require __DIR__.'/run.php';
$db->exec('CREATE TABLE community_attempt_media(attempt_id TEXT PRIMARY KEY,source_sha256 TEXT,duration_ms INTEGER)');
$id=seed($db,999);$db->prepare("UPDATE community_matches SET source_sha256='',duration_ms=0,source_url=? WHERE id=?")->execute(['https://www.youtube.com/watch?v=_2hGzZRvw0A',$id]);
$c=$service->claim($id,9999,'catalog-device',str_repeat('z',16));$a=$c['attempt_id'];$t=$c['lease_token'];
$payload['source_sha256']=str_repeat('c',64);$payload['observations'][0]['team']=1;$payload['observations'][0]['start_ms']=0;$payload['observations'][0]['end_ms']=1000;
fails(fn()=>$service->submit($a,9999,'catalog-device',$t,$payload),422,'YouTube submission requires downloaded-video evidence');
fails(fn()=>$service->recordMedia($a,9998,'catalog-device',$t,str_repeat('c',64),10000),403,'media evidence requires reservation ownership');
fails(fn()=>$service->recordMedia($a,9999,'catalog-device',$t,str_repeat('c',64),600001),422,'full-event video evidence rejected');
$r=$service->recordMedia($a,9999,'catalog-device',$t,str_repeat('c',64),10000);check($r['duration_ms']===10000,'downloaded video fingerprint and duration recorded');
fails(fn()=>$service->recordMedia($a,9999,'catalog-device',$t,str_repeat('d',64),10000),409,'attempt video evidence is immutable');
$service->submit($a,9999,'catalog-device',$t,$payload);check(true,'YouTube draft validated against attempt-specific evidence');
