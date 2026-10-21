import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import neptune_action_labels as actions
import neptune_events as events
import neptune_games as games
import neptune_training as training
import neptune_video_labels as labels
import test_training
from test_video_labels import label, ndjson


def game_label(i=1, code='score_10_fuel', **overrides):
    r=label(i=i,tag='gb:'+code,start=93000)
    r.update(season=2026,game_key='2026-rebuilt',polarity='present',tag_label='Score 10 fuel',tag_category='Scoring & Defense',
             definition_version='neptune-game-v1-'+'a'*32,scoring=None)
    r.update(overrides)
    return r


class GameActions(unittest.TestCase):
    def game(self):
        return games.select('2026test',Path('/__neptune_test_without_user_packs__'))

    def test_contract_and_ledger_retain_exact_labels(self):
        rows=[game_label(1),game_label(2,'score_25_fuel',tag_label='Score 25 fuel'),
              game_label(3,'feed',tag_label='Feed'),label(i=4)]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'export.ndjson';source.write_text(ndjson(rows))
            store=labels.Store(Path(tmp)/'store');labels.ingest(store,path=source)
            got,rejected=training.corpus(store,self.game())
            self.assertEqual(rejected,{})
            self.assertEqual({r['tag_key'] for r in got},{r['tag_key'] for r in rows})
            inv=training.inventory(got,self.game())
            self.assertEqual(inv['counts']['gb:score_10_fuel']['present'],1)
            self.assertEqual(inv['action_definitions']['gb:score_10_fuel']['action_code'],'score_10_fuel')
            self.assertEqual(next(r for r in got if r['tag_key']=='gb:feed')['label_scope'],'moment')
            self.assertEqual(next(r for r in got if r['tag_key']=='gb:score_10_fuel')['scoring'],None)

    def test_unknown_valid_game_code_is_retained_and_invalid_contract_is_reported(self):
        future=game_label(code='new_2026_action')
        self.assertIsNone(labels.validate_label(future))
        for update,reason in [({'time_basis':'phase_elapsed_ms'},'game_action_requires_video_moment'),
            ({'definition_version':'neptune-match-tags-v1'},'invalid_game_definition_revision'),
            ({'schema_version':1},'unsupported_game_action_contract'),
            ({'start_ms':True,'end_ms':True},'invalid_game_action_timestamp')]:
            self.assertEqual(labels.validate_label(dict(future,**update)),reason)
        self.assertEqual(actions.error(dict(future,game_key='2025-reefscape'),self.game()),'invalid_game_action_season')

    def test_published_revision_format_from_deployed_game_builder(self):
        row=game_label(definition_version='neptune-game-rev-42-'+'b'*32)
        self.assertIsNone(actions.error(row,self.game()))
        self.assertTrue(actions.valid_definition(row['tag_key'],actions.definitions([row])[row['tag_key']],'2026-rebuilt'))
        result=subprocess.run(['php',str(Path(__file__).resolve().parents[1]/'tests/community-analysis/game-action-contract.php')],input=ndjson([row]),capture_output=True,text=True,check=True)
        self.assertIn(row['tag_key'],json.loads(result.stdout)['definitions'])
        self.assertEqual(actions.error(dict(row,definition_version='neptune-game-rev-0-'+'b'*32)),'invalid_game_definition_revision')

    def test_actual_fit_keeps_distinct_action_heads_and_revision_metadata(self):
        records=[game_label(1),game_label(2,'score_25_fuel',tag_label='Score 25 fuel')]
        inventory=training.inventory(records,self.game())
        rows=[]
        for record in records:
            for example in test_training.Learning().rows():
                rows.append(dict(example,tag=record['tag_key']))
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';result=training.train_actions(rows,self.game(),run,inventory)
            model=json.loads((run/'model.json').read_text())
            self.assertEqual(set(model['heads']),{'gb:score_10_fuel','gb:score_25_fuel'})
            training.model_valid(model,self.game())
            self.assertFalse(result['release_ready'])
            self.assertEqual(model['action_definitions']['gb:score_10_fuel']['variants'][0]['definition_version'],records[0]['definition_version'])
            bad=copy.deepcopy(model);bad['action_definitions']={};bad['model_id']=training.digest({k:v for k,v in bad.items() if k!='model_id'})
            with self.assertRaisesRegex(ValueError,'Invalid model head'):training.model_valid(bad,self.game())

    def test_moment_predictions_keep_names_and_do_not_become_durations_or_points(self):
        definition=actions.definitions([game_label()])
        samples=[{'team':1,'t':t,'tag_key':'gb:score_10_fuel','score':.9,'threshold':.5,'identity_evidence':'actual-frame'} for t in (93,94)]
        decoded=events.decode(samples,{'periods':{'teleop':{'start':25,'end':165}}},'model',definition)
        self.assertEqual(len(decoded),1)
        self.assertEqual(decoded[0]['start_ms'],decoded[0]['end_ms'])
        self.assertEqual(decoded[0]['tag_label'],'Score 10 fuel')
        self.assertNotIn('points',decoded[0])
        self.assertEqual(decoded[0]['certainty'],'uncertain')
        self.assertEqual(decoded[0]['tag_key'],'gb:score_10_fuel')

    def test_no_localized_clips_still_reports_the_game_action_class(self):
        inventory=training.inventory([game_label()],self.game())
        with tempfile.TemporaryDirectory() as tmp:
            result=training.train_actions([],self.game(),Path(tmp)/'run',inventory)
            self.assertIn('gb:score_10_fuel',result['tags'])
            self.assertEqual(result['tags']['gb:score_10_fuel']['status'],'needs_positive_and_negative_training_examples')

    def test_localized_example_retains_original_click_provenance(self):
        row=game_label()
        facts={'source':{'sha256':'source'},'periods':{'teleop':{'start':25,'end':165}}}
        sight={'team':row['team_number'],'t':93,'box':[.1,.2,.1,.1]}
        sources={row['video_id']:{'status':'verified','sha256':'source','file':'video.mp4','duration_ms':180000}}
        with patch.object(training,'sightings',return_value=[sight]):
            examples,rejected=training.labeled_examples([row],{row['video_id']:facts},sources,'unused',extractor=lambda *_:[0.]*1296)
        self.assertEqual(rejected,{})
        self.assertEqual(examples[0]['tag'],'gb:score_10_fuel')
        provenance=examples[0]['label_metadata'][0]
        self.assertEqual(provenance['definition_version'],row['definition_version'])
        self.assertEqual(provenance['start_ms'],93000)
        self.assertEqual(provenance['end_ms'],93000)
        self.assertEqual(provenance['game_key'],'2026-rebuilt')

    def test_php_python_contract_agree(self):
        fixture=[game_label(),game_label(2,'feed',tag_label='Feed')]
        script=Path(__file__).parents[1]/'tests/community-analysis/game-action-contract.php'
        result=subprocess.run(['php',str(script)],input=ndjson(fixture),text=True,capture_output=True,check=True)
        data=json.loads(result.stdout)
        self.assertEqual(data['definitions'],actions.definitions(fixture))
        self.assertTrue(data['preflight']['can_run_baseline'])
        self.assertEqual(data['preflight']['actions'],4)

    def test_same_definition_changes_are_retained_as_ledger_revision(self):
        first=game_label();changed=dict(first,game_key='2026-other')
        self.assertNotEqual(labels.CONTENT_FIELDS,())
        self.assertIn('game_key',labels.CONTENT_FIELDS)
        self.assertIn('season',labels.CONTENT_FIELDS)
        self.assertIsNone(actions.error(first,self.game()))
        self.assertEqual(actions.error(changed,self.game()),'game_action_game_mismatch')


if __name__=='__main__':unittest.main()
