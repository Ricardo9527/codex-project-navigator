import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location('navigator_query', Path(__file__).resolve().parents[1] / 'experimental/project-navigator/query.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProjectNavigationQueryTests(unittest.TestCase):
    def test_project_identity_keeps_same_named_cards_and_context_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            projects = []
            for identity in ['first', 'second']:
                root = Path(folder) / identity
                (root / '.project-library').mkdir(parents=True)
                record = {'version': 1, 'projectId': identity, 'about': identity,
                          'categories': [{'id': 'work', 'title': '工作'}],
                          'cards': [{'id': 'same-card', 'title': '同名卡片', 'summary': identity,
                                     'categoryIds': ['work'], 'resources': [], 'sources': [], 'sections': [],
                                     'requirements': [], 'records': [], 'related': []}]}
                (root / '.project-library/record.json').write_text(json.dumps(record))
                projects.append({'id': identity, 'name': identity, 'path': str(root)})
            catalog = {'projects': projects, 'aliases': {'second-native': 'second'}}
            default = Path(projects[0]['path'])
            first = MODULE.query({'cardId': 'same-card', 'context': True}, default, catalog)
            second = MODULE.query({'projectId': 'second-native', 'cardId': 'same-card', 'context': True}, default, catalog)
            self.assertEqual(first['card']['summary'], 'first')
            self.assertEqual(second['card']['summary'], 'second')
            self.assertEqual(second['project']['id'], 'second')
            self.assertIn(projects[1]['path'], second['context']['text'])
            self.assertNotIn(projects[0]['path'], second['context']['text'])
            with self.assertRaisesRegex(ValueError, '找不到这个项目'):
                MODULE.query({'projectId': 'unknown'}, default, catalog)
            with self.assertRaisesRegex(ValueError, '找不到这张卡片'):
                MODULE.query({'projectId': 'second', 'cardId': 'missing'}, default, catalog)
            empty = Path(folder) / 'empty'
            empty.mkdir()
            catalog['projects'].append({'id': 'empty', 'name': 'empty', 'path': str(empty)})
            result = MODULE.query({'projectId': 'empty'}, default, catalog)
            self.assertTrue(result['uninitialized'])
            self.assertEqual(result['cards'], [])
            self.assertFalse((empty / '.project-library').exists())

    def test_plugin_checkout_without_private_record_uses_registered_project(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'plugin'
            root.mkdir()
            project=Path(folder)/'project'
            project.mkdir()
            catalog={'projects':[{'id':'public-user-project','name':'Project','path':str(project)}],'aliases':{}}
            value=MODULE.query({},root,catalog)
            self.assertEqual(value['project']['id'],'public-user-project')
            self.assertTrue(value['uninitialized'])
            self.assertFalse((root/'.project-library').exists())

    def test_draft_context_stays_within_stdout_budget_as_project_and_card_grow(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            project={'id':'test','name':'test','path':folder}
            catalog={'projects':[project],'aliases':{}}
            target={'id':'target','title':'目标','summary':'简短说明','resources':[]}
            large={**target,'id':'large','summary':'大'*710_000}
            record={'version':1,'projectId':'test','about':'测试','cards':[target,large]}
            path=root/'.project-library/record.json'
            path.parent.mkdir();path.write_text(json.dumps(record,ensure_ascii=False))
            def query(card_id,**extra):
                result=MODULE.query({'cardId':card_id,'context':True,**extra},root,catalog)
                self.assertLess(len(json.dumps(result,ensure_ascii=False).encode()),2_000_000)
                return result
            old=query('target')
            self.assertEqual(old['card']['summary'],'简短说明')
            self.assertNotIn('contentPage',old)
            oversized=query('large',compact=True)
            self.assertIn(oversized['context']['path'],oversized['context']['text'])
            draft=query('large',contextFileOnly=True)
            self.assertNotIn('text',draft['context'])
            self.assertIn(large['summary'],Path(draft['context']['path']).read_text())
