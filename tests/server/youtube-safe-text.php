<?php
// YouTube rejects descriptions with angle brackets (HTTP 400 "invalid video description").
require __DIR__.'/../../server/neptune_secure/youtube-uploader.php';
$ok=true;$t=function($c,$m)use(&$ok){echo($c?'PASS ':'FAIL ').$m."\n";$ok=$ok&&$c;};
$s=YouTubeUploader::safeText('Matching uses IoU >= 0.30; a <b> tag; x<=1');
$t(strpbrk($s,'<>')===false,'no angle brackets remain');
$t(str_contains($s,'IoU ≥ 0.30')&&str_contains($s,'x≤1'),'comparisons stay readable');
$t(YouTubeUploader::safeText('plain text')==='plain text','plain text unchanged');
exit($ok?0:1);
