<?php
declare(strict_types=1);
function community_page_start(string $title,string $subtitle,string $active='public',string $eyebrow='AUTO SCOUT'):void {
 global $pdo,$config,$u,$pageTitle,$moduleName,$hideChrome,$isPublicHome;
 $pageTitle=$title;$moduleName='AUTO SCOUT';$hideChrome=false;
 include dirname(__DIR__).'/partials_header.php';
 ?>
<link rel="stylesheet" href="/community/assets/community.css?v=8-theme-layout">
<div class="community-main auto-scout-platform"><div class="community-platform-hero"><span class="stage-label">PLATFORM OWNER · AUTO SCOUT</span><h1><?=e($title)?></h1><p><?=e($subtitle)?></p></div>
<nav class="community-nav" aria-label="Auto Scout"><?php foreach(['catalog'=>['Watch & tag','/community/?view=catalog'],'results'=>['Saved tags & scores','/community/?view=results'],'learning'=>['Train & test','/admin/community-learning.php']] as $key=>$link):?><a href="<?=e($link[1])?>" <?=$active===$key||($key==='catalog'&&$active==='contribute')?'aria-current="page"':''?>><?=e($link[0])?></a><?php endforeach ?><a href="/scouting.php">← Scouting</a></nav>
<?php }
function community_page_end():void {
 global $pdo,$config,$u,$pageTitle,$moduleName,$hideChrome,$isPublicHome;
 echo '</div>';
 include dirname(__DIR__).'/partials_footer.php';
}
