import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from conversation_assets import source_origin

class ResourceSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'.project-library').mkdir()
        self.target=self.root/'copy.png';self.target.write_bytes(b'original image')
        self.record=self.root/'.project-library/record.json'
        self.record.write_text(json.dumps({'cards':[{'id':'card','resources':[{'id':'file','path':'copy.png','origin':{'threadId':'thread','prompt':'summary, not a search key'}}]}]}))
        self.project={'id':'project','path':str(self.root)}
        self.hub=SimpleNamespace(thread=lambda _: {'cwd':str(self.root),'project_id':'project'},owner=lambda *_:'project')
    def asset(self,path,turn='turn'):
        return {'path':str(path),'origin':{'threadId':'thread','turnId':turn,'itemId':'message'}}
    def resolve(self,assets):
        with patch('conversation_assets.thread_assets',return_value=assets):return source_origin(self.hub,self.project,{'cardId':'card','resourceId':'file'})
    def test_exact_file_position_and_read_only_record(self):
        before=self.record.read_bytes();self.assertEqual(self.resolve([self.asset(self.target)])['itemId'],'message');self.assertEqual(self.record.read_bytes(),before)
    def test_copied_file_resolves_by_content_not_summary(self):
        original=self.root/'generated.png';original.write_bytes(self.target.read_bytes())
        self.assertEqual(self.resolve([self.asset(original)])['turnId'],'turn')
    def test_missing_and_ambiguous_evidence_do_not_open_latest(self):
        with self.assertRaisesRegex(ValueError,'未找到'):self.resolve([])
        with self.assertRaisesRegex(ValueError,'出现多次'):self.resolve([self.asset(self.target),self.asset(self.target,'other-turn')])
    def test_cross_project_source_is_rejected(self):
        self.hub.owner=lambda *_:'other'
        with self.assertRaisesRegex(ValueError,'不属于'):self.resolve([])
