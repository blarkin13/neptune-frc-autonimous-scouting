<?php
// Exercise the actual page's POST redirects under strict PHP argument checking.
declare(strict_types=1);
$source=file_get_contents(__DIR__.'/../../public_html/Neptune/community/connect.php');
$source=str_replace('declare(strict_types=1);','',$source);
$source=preg_replace('/^require_once .*;$/m','',$source);
$stub= <<<'STUB'
<?php
declare(strict_types=1);
$_SERVER['REQUEST_METHOD']='POST'; $_POST=['request'=>str_repeat('a',32),'decision'=>'approve'];
$pdo=null;$config=[];
function community_analysis_settings($p,$c){return ['enabled'=>true];}
function community_pairing_schema($p){}
function current_user(){return ['id'=>1];}
function require_login(){return ['id'=>1,'credential_revision'=>str_repeat('b',64)];}
function verify_csrf(){}
class CommunityAnalysisError extends RuntimeException {public function __construct(public int $httpStatus,string $message){parent::__construct($message);}}
class CommunityPairing {
function __construct($p,$s){}
function inspect($id){return ['port'=>12345,'state'=>str_repeat('c',64),'status'=>'pending'];}
function authorize($id,$uid,$revision,$approve){if(getenv('CONNECT_TEST_DENY'))throw new CommunityAnalysisError(403,'Denied');return 'http://127.0.0.1:12345/neptune-connect?code=test';}
}
function e($s){return htmlspecialchars((string)$s);}
register_shutdown_function(function(){if(http_response_code()===303){echo "PASS redirect\n";}else{fwrite(STDERR,'Unexpected response status: '.http_response_code()."\n");exit(1);}});
?>
STUB;
$tmp=tempnam(sys_get_temp_dir(),'connect-redirect-');
try {
 file_put_contents($tmp,$stub.$source);
 foreach(['','CONNECT_TEST_DENY=1 '] as $env){
  $output=[];$code=0;exec($env.escapeshellarg(PHP_BINARY).' '.escapeshellarg($tmp).' 2>&1',$output,$code);
  if($code!==0||implode("\n",$output)!=='PASS redirect')throw new RuntimeException(implode("\n",$output));
 }
 echo "PASS approval and access-denial page redirects use HTTP 303\n";
} finally {unlink($tmp);}
