<?php
declare(strict_types=1);
// Auto Scout pillar blocks, filled by community/assets/pillar.js from train.php?overview.
// A pillar page: pillar_open() · pillar_summary() · its own work area · pillar_trained() · pillar_close().

function pillar_open(int $season):void { ?>
<link rel="stylesheet" href="/community/assets/train-tabs.css?v=2-pillars">
<div id="pillar" data-season="<?=$season?>" data-csrf="<?=e(csrf_token())?>" data-endpoint="/autoscout/train.php">
 <div id="pillar-status" class="tt-status" aria-live="polite"><div><span class="stage-label">HELPERS</span><span data-slot="helpers">Checking…</span></div><div><span class="stage-label">RUNNING NOW</span><span data-slot="now">Nothing</span></div><div><span class="stage-label">WAITING</span><span data-slot="waiting">Nothing</span></div></div>
<?php }

/** How it works, the model in use, the data it learns from, and what is needed next (with Train for the detectors). */
function pillar_summary(string $part,string $how,?string $train=null):void { ?>
 <section class="tt-part" data-part="<?=e($part)?>">
  <p class="tt-how"><?=$how?></p>
  <div class="tt-grid tt-grid-3">
   <div class="tt-card"><span class="stage-label">MODEL IN USE</span><div data-slot="current">Loading…</div></div>
   <div class="tt-card"><span class="stage-label">YOUR DATA</span><div data-slot="data">Loading…</div></div>
   <div class="tt-card tt-next"><span class="stage-label">WHAT’S NEEDED NEXT</span><ul data-slot="next"><li>Loading…</li></ul><?php if($train):?><button type="button" data-train="<?=e($part)?>"><?=e($train)?></button><p class="training-note" data-slot="train-note"></p><?php endif?></div>
  </div>
 </section>
<?php }

/** Past training runs, and going back to the previous model. */
function pillar_trained(string $part):void { ?>
 <section class="tt-part tt-trained" data-part="<?=e($part)?>">
  <div class="tt-card"><div class="tt-trained-head"><span class="stage-label">WHAT’S TRAINED · PAST RUNS</span><button type="button" class="button-secondary tt-undo" data-rollback="<?=e($part)?>" hidden>Go back to the previous model</button></div><div data-slot="runs"></div></div>
 </section>
<?php }

function pillar_close():void { ?>
</div>
<script src="/community/assets/pillar.js?v=1" defer></script>
<?php }
