<?php
declare(strict_types=1);
// Auto Scout pillar blocks, filled by community/assets/pillar.js from train.php?overview.
// A pillar page: pillar_open() · pillar_summary() (what's trained, data, what's next) · its own work area · pillar_close().

function pillar_open(int $season):void { ?>
<link rel="stylesheet" href="/community/assets/train-tabs.css?v=9-console">
<div id="pillar" data-season="<?=$season?>" data-csrf="<?=e(csrf_token())?>" data-endpoint="/autoscout/train.php">
 <div id="pillar-status" class="tt-status" aria-live="polite"><div class="tt-now"><span class="stage-label">RUNNING NOW</span><div data-slot="now">Checking…</div></div><div class="tt-side"><span class="stage-label">HELPERS</span><span data-slot="helpers">Checking…</span><span class="stage-label">WAITING</span><span data-slot="waiting">Nothing</span></div></div>
<?php }

/** How it works, the model in use, the data it learns from, and what is needed next (with Train for the detectors). */
function pillar_summary(string $part,string $how,?string $train=null):void { ?>
 <section class="tt-part" data-part="<?=e($part)?>">
  <p class="tt-how"><?=$how?></p>
  <div class="tt-card tt-sum">
   <div class="tt-sum-tabs" role="tablist" aria-label="<?=e($part)?> summary"><button type="button" role="tab" data-sum="current" aria-selected="true">What’s trained</button><button type="button" role="tab" data-sum="data" aria-selected="false">Your data</button><button type="button" role="tab" data-sum="next" aria-selected="false">What’s needed next<span class="tt-sum-flag" hidden></span></button></div>
   <div data-sum-panel="current"><div data-slot="current">Loading…</div><details class="tt-runs-more"><summary>Past runs</summary><div data-slot="runs"></div></details><?php if($part!=='actions'):?><button type="button" class="button-secondary tt-undo" data-rollback="<?=e($part)?>" hidden>Go back to the previous model</button><?php endif?></div>
   <div data-sum-panel="data" hidden><div data-slot="data">Loading…</div></div>
   <div data-sum-panel="next" hidden><ul class="tt-next" data-slot="next"><li>Loading…</li></ul></div>
   <?php if($train):?><div class="tt-sum-train"><button type="button" data-train="<?=e($part)?>"><?=e($train)?></button><p class="training-note" data-slot="train-note"></p></div><?php endif?>
  </div>
 </section>
<?php }

function pillar_close():void { ?>
</div>
<script src="/community/assets/pillar.js?v=16" defer></script>
<?php }
