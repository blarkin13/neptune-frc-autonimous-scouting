<?php
declare(strict_types=1);
// Integration check against an initialized MySQL database; all test writes roll back.
require_once dirname(__DIR__,2).'/neptune_secure/community-training-progress.php';
$dsn=getenv('NEPTUNE_MYSQL_TEST_DSN');
if(!$dsn){fwrite(STDERR,"Set NEPTUNE_MYSQL_TEST_DSN for an initialized MySQL test database.\n");exit(2);}
$db=new PDO($dsn,getenv('NEPTUNE_MYSQL_TEST_USER')?:'root',getenv('NEPTUNE_MYSQL_TEST_PASSWORD')?:'',[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
if($db->getAttribute(PDO::ATTR_DRIVER_NAME)!=='mysql')throw new RuntimeException('MySQL required');
$db->beginTransaction();
try {
 community_training_progress_schema($db);
 if(!$db->inTransaction())throw new RuntimeException('Initialization committed the transaction');
 $id=bin2hex(random_bytes(16));
 community_training_progress_write($db,$id,'Transaction regression check',['matches_done'=>1]);
 if(!$db->inTransaction())throw new RuntimeException('Progress write committed the transaction');
 if(!community_training_progress_read($db,$id))throw new RuntimeException('Missing test progress');
 $db->rollBack();
 if(community_training_progress_read($db,$id)!==null)throw new RuntimeException('Rollback did not undo progress');
 echo "PASS MySQL initialization preserves transaction and progress rolls back\n";
}finally{if($db->inTransaction())$db->rollBack();}
