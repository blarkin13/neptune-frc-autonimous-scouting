<?php
declare(strict_types=1);
function community_page_start(string $title,string $subtitle,string $active='public',string $eyebrow='AUTO SCOUT'):void {
 global $pdo,$config,$u,$pageTitle,$moduleName,$hideChrome,$isPublicHome,$navigationSection;
 $pageTitle=$title;$moduleName='AUTO SCOUT';$hideChrome=false;
 $viewer=function_exists('current_user')?current_user():null;
 // Auto Scout pages sit under the Auto Scout menu section for the platform owner who has it.
 if(($viewer['role']??'')==='owner'&&(int)($viewer['organization_id']??0)===(int)($config['app']['platform_organization_id']??1))$navigationSection='autoscout';
 include dirname(__DIR__).'/partials_header.php';
 ?>
<link rel="stylesheet" href="/community/assets/community.css?v=9-mission-pages">
<?php
 $communityHeroIcon=neptune_hero_relief_icon($title,'AUTO SCOUT');
 $communityHeroSteps=neptune_hero_guide($title);
 $communityHeroKicker=$eyebrow==='AUTO SCOUT'
     ? 'AUTO SCOUT · '.neptune_hero_category($title,'AUTO SCOUT')
     : $eyebrow;
 ?>
<div class="community-main auto-scout-platform">
  <div class="community-platform-hero neptune-page-hero" data-neptune-hero="server">
    <i class="fa-solid <?=e($communityHeroIcon)?> nd-page-mission-mark" aria-hidden="true"></i>
    <div class="neptune-hero-kicker"><i class="fa-solid fa-tags" aria-hidden="true"></i><span><?=e($communityHeroKicker)?></span></div>
    <h1><?=e($title)?></h1>
    <p><?=e($subtitle)?></p>
    <div class="neptune-hero-pills" aria-label="Page quick guide">
      <?php foreach($communityHeroSteps as $i=>$step): ?>
        <span class="neptune-hero-pill"><i class="fa-solid <?=e($step[0])?>" aria-hidden="true"></i><strong><?=$i+1?></strong> <?=e($step[1])?></span>
      <?php endforeach; ?>
    </div>
  </div>
<nav class="community-nav" aria-label="Auto Scout"><?php foreach(['catalog'=>['Watch & tag','/community/?view=catalog'],'scoring'=>['Scoring areas','/autoscout/scoring-areas.php'],'robots'=>['Robot labels','/autoscout/robot-labels.php'],'results'=>['Saved tags & scores','/community/?view=results'],'learning'=>['Train & test','/autoscout/train.php']] as $key=>$link):?><a href="<?=e($link[1])?>" <?=$active===$key||($key==='catalog'&&$active==='contribute')?'aria-current="page"':''?>><?=e($link[0])?></a><?php endforeach ?><?php if($active!=='hub'):?><a href="/autoscout/index.php">← Auto Scout</a><?php endif?></nav>
<?php }
function community_page_end():void {
 global $pdo,$config,$u,$pageTitle,$moduleName,$hideChrome,$isPublicHome;
 echo '</div>';
 include dirname(__DIR__).'/partials_footer.php';
}
