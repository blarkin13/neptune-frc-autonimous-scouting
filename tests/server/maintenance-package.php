<?php
// Load only function declarations from the deployed console, never its bootstrap or actions.
$tokens=token_get_all(file_get_contents($argv[3]));
$code='';
for($i=0;$i<count($tokens);$i++) {
 if(is_array($tokens[$i]) && $tokens[$i][0]===T_FUNCTION) {
  if(!is_array($tokens[$i+2]??null)||!in_array($tokens[$i+2][1],['nm_safe_zip_name','nm_target_for_entry','nm_zip_entries','nm_package_meta','nm_lint_php_source'],true))continue;
  $part='';$depth=0;$started=false;
  for(;$i<count($tokens);$i++) {
   $t=$tokens[$i];$part.=is_array($t)?$t[1]:$t;
   if($t==='{'){$depth++;$started=true;}
   if($t==='}' && --$depth===0 && $started)break;
  }
  $code.=$part."\n";
 }
}
define('NM_ROOT','/var/www/neptune');define('NM_APP_ROOT',NM_ROOT.'/public_html/Neptune');define('NM_PACKAGE_META','neptune-package.json');
eval($code);
$path=$argv[1];$entries=nm_zip_entries($path);$meta=nm_package_meta($path);
$zip=new ZipArchive();$zip->open($path);$count=0;
foreach($entries as $entry){
 if($entry['meta'])continue;
 if(!array_key_exists($entry['name'],$meta['base']) || $meta['base'][$entry['name']]!==null)throw new RuntimeException('Missing new-file guard');
 if(str_ends_with($entry['name'],'.php')){[$ok,$msg]=nm_lint_php_source($zip->getFromIndex($entry['index']),$entry['name']);if(!$ok)throw new RuntimeException($msg);}
 $count++;
}
echo "PASS deployed Maintenance Console: $count file paths, expected-base metadata, PHP syntax\n";
require $argv[2].'/neptune_secure/community-analysis-install.php';
foreach(['1, 2 3'=>[1,2,3],''=>[],'1,1'=>[1]] as $input=>$expected)if(community_analysis_user_ids((string)$input)!==$expected)throw new RuntimeException('ID parsing');
foreach(['-1','0','1 OR 1','1.2'] as $bad){try{community_analysis_user_ids($bad);throw new RuntimeException('Bad ID accepted');}catch(InvalidArgumentException $e){}}
$db=new PDO('sqlite::memory:');$db->exec('CREATE TABLE community_settings(id INT PRIMARY KEY,settings_json TEXT)');
if(community_analysis_settings($db,['community_analysis'=>['enabled'=>false]])!==['enabled'=>false])throw new RuntimeException('Fallback failed');
$db->exec("INSERT INTO community_settings VALUES(1,'{\"enabled\":true}')");
if(community_analysis_settings($db,['community_analysis'=>['enabled'=>false]])!==['enabled'=>true])throw new RuntimeException('DB settings precedence failed');
echo "PASS setup ID validation and stored-settings precedence\n";
