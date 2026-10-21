<?php
declare(strict_types=1);
require_once __DIR__.'/bootstrap.php';
require_once __DIR__.'/google-auth.php';
require_once __DIR__.'/platform-security.php';
$communityOwner=require_role(['owner']);
if((int)$communityOwner['organization_id']!==(int)($config['app']['platform_organization_id']??1))access_denied('Platform owner access required while Auto Scout is being developed.');
neptune_require_platform_owner_google($communityOwner);
header('Cache-Control: private, no-store');
