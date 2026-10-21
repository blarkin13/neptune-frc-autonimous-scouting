<?php
declare(strict_types=1);
require __DIR__.'/../../neptune_secure/community-video-tags.php';
function ok(bool $yes,string $message):void{if(!$yes)throw new RuntimeException($message);echo 'PASS '.$message."\n";}
function rejects(callable $fn,string $message):void{try{$fn();throw new RuntimeException('Accepted invalid data: '.$message);}catch(CommunityAnalysisError $ex){ok(true,$message);}}
$db=new PDO('sqlite::memory:');$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$db->exec('CREATE TABLE community_matches(id INTEGER PRIMARY KEY,match_key TEXT,title TEXT,source_url TEXT,roster_json TEXT)');
$db->exec('CREATE TABLE community_video_labels(id TEXT PRIMARY KEY,match_id INTEGER,contributor_key TEXT,user_id INTEGER,ip_key TEXT,source_url TEXT,video_id TEXT,roster_json TEXT,team_number INTEGER,tag_key TEXT,tag_label TEXT,tag_category TEXT,definition_version TEXT,label_scope TEXT,start_ms INTEGER,end_ms INTEGER,video_duration_ms INTEGER,certainty TEXT,note TEXT,review_state TEXT,created_at INTEGER,updated_at INTEGER,polarity TEXT DEFAULT \'present\',scoring_json TEXT,replaces_id TEXT)');
$db->exec('CREATE TABLE community_video_label_reviews(id TEXT PRIMARY KEY,label_id TEXT,reviewer_user_id INTEGER,action TEXT,note TEXT,created_at INTEGER)');
$roster=['red'=>[6369,2689,127],'blue'=>[9128,11178,5414]];
$q=$db->prepare('INSERT INTO community_matches VALUES(1,?,?,?,?)');$q->execute(['2026test_qm7','Test Q7','https://www.youtube.com/watch?v=_2hGzZRvw0A',json_encode($roster)]);
$s=new CommunityVideoTags($db);$m=$s->match(1);$actor=str_repeat('a',64);$other=str_repeat('b',64);
$label=['id'=>str_repeat('c',32),'team'=>6369,'tag_key'=>'scoring','scope'=>'moment','start_ms'=>12000,'end_ms'=>12000,'duration_ms'=>180000,'certainty'=>'observed','note'=>'Visible action'];
ok(count(community_video_tag_catalog())===19,'existing impact.php category subset, no invented tags');
ok(CommunityVideoTags::videoId('https://evil.test/watch?v=_2hGzZRvw0A')===null,'untrusted video host rejected');
foreach([['team'=>999],['tag_key'=>'invented'],['start_ms'=>-1],['end_ms'=>180001],['certainty'=>'certain'],['note'=>str_repeat('x',1001)],['scope'=>'interval'],['tag_key'=>'no_scoring'],['duration_ms'=>700000]] as $change)rejects(fn()=>CommunityVideoTags::validate(array_replace($label,$change),$m),'reject '.json_encode($change));
$s->save($label,1,$actor,null,'ip');$s->save($label,1,$actor,null,'ip');ok(count($s->mine(1,$actor))===1,'anonymous save and retry are idempotent');
rejects(fn()=>$s->save($label,1,$other,null,'ip'),'another browser cannot reuse label ID');
rejects(fn()=>$s->save(array_replace($label,['start_ms'=>13000,'end_ms'=>13000]),1,$actor,null,'ip'),'retry cannot silently change original label');
ok(count($s->mine(1,$other))===0,'another browser cannot read contributor history');

ok((bool)$s->training()->fetch(),'public label immediately included without review');
ok($s->mine(1,$actor)[0]['review_state']==='contributed','new label is contributed, never pending');
$s->withdraw($label['id'],$other);ok((bool)$s->training()->fetch(),'other browser cannot undo label');
$s->withdraw($label['id'],$actor);ok(!$s->training()->fetch(),'undo removes label from future exports');
ok((int)$db->query('SELECT COUNT(*) FROM community_video_label_reviews')->fetchColumn()===1,'withdrawal history retained without approval workflow');
$label['id']=str_repeat('d',32);$label['certainty']='uncertain';$s->save($label,1,$actor,3,'ip');
$uncertain=$s->training()->fetch(PDO::FETCH_ASSOC);ok($uncertain['certainty']==='uncertain','uncertainty preserved without a review gate');
$db->exec("UPDATE community_video_labels SET review_state='pending' WHERE id='".$label['id']."'");
community_video_tags_remove_queue($db);
ok($s->mine(1,$actor)[0]['review_state']!=='pending','old pending label leaves queue');
ok($s->training()->fetch(PDO::FETCH_ASSOC)['certainty']==='uncertain','migration does not promote uncertainty to observed');
ok($db->query("SELECT review_state FROM community_video_labels WHERE id='".str_repeat('c',32)."'")->fetchColumn()==='withdrawn','migration preserves withdrawn installation tests');
$label['id']=str_repeat('e',32);$label['tag_key']='no_scoring';$label['scope']='match';$label['start_ms']=null;$label['end_ms']=null;$s->save($label,1,$actor,null,'ip');
$rows=$s->training()->fetchAll(PDO::FETCH_ASSOC);$absence=array_values(array_filter($rows,fn($r)=>$r['id']===$label['id']))[0];
ok($absence['label_scope']==='match'&&$absence['start_ms']===null&&$absence['end_ms']===null,'whole-match absence label stored without fake timestamps');
ok(!array_intersect(['contributor_key','user_id','ip_key'],array_keys($absence)),'public dataset excludes contributor and network identifiers');
$controls=community_video_tag_controls();$mapped=[];$shortcuts=[];
foreach($controls as $group=>$tags)foreach($tags as $key=>$control){$mapped[]=$key;$shortcuts[]=strtolower($control[1]);}
$expected=array_keys(community_video_tag_catalog());sort($expected);sort($mapped);
ok($mapped===$expected,'all 19 existing tags rendered once with no hidden category filter');
ok(count(array_unique($shortcuts))===19,'unique keyboard shortcut for every tag');
ok(!array_intersect(['r','u','1','2','3','4','5','6',' '],$shortcuts),'tag keys do not collide with playback, undo, or robot shortcuts');
ok(count($controls['Autonomous'])===4&&count($controls['Endgame'])===4,'complete autonomous and endgame sets visible together');

$counter=array_replace($label,['id'=>str_repeat('f',32),'tag_key'=>'scoring','scope'=>'moment','start_ms'=>20000,'end_ms'=>20000,'certainty'=>'observed','polarity'=>'absent']);
$s->save($counter,1,$actor,null,'ip');
$negative=array_values(array_filter($s->training()->fetchAll(PDO::FETCH_ASSOC),fn($r)=>$r['id']===$counter['id']))[0];
ok($negative['polarity']==='absent','explicit counterexample exported separately from positive tags');
rejects(fn()=>$s->save(array_replace($counter,['polarity'=>'present']),1,$actor,null,'ip'),'retry cannot change polarity');
rejects(fn()=>CommunityVideoTags::validate(array_replace($counter,['scope'=>'match']),$m),'counterexample cannot invent whole-match coverage');
