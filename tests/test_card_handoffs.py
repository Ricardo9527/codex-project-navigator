import json
import sqlite3
import time
import unittest
from pathlib import Path
import test_full_workflow
import card_handoffs

class CardHandoffTests(unittest.TestCase):
    def setUp(self):
        self.f=test_full_workflow.FullWorkflowTests();self.f.setUp();self.f.seed()
        self.hub=self.f.hub
    def tearDown(self):self.f.tearDown()
    def add_thread(self,identity,token,cwd=None):
        f=self.f.fixture;path=f.root/(identity+'.jsonl')
        path.write_text(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':token}]}},ensure_ascii=False)+'\n')
        with sqlite3.connect(f.source) as db:
            db.execute('INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(identity,'从卡片工作','raw',cwd or str(f.project),int(time.time()),0,'main','',('other-project' if cwd else 'native'),None,None,None,str(path)))
        f.original=f.source.read_bytes()
        return path
    def test_links_only_new_matching_project_thread_and_is_idempotent(self):
        handoff=card_handoffs.prepare(self.hub,self.f.p,'camera')
        self.add_thread('wrong-project',handoff['token'],'/different-project')
        self.add_thread('no-marker','ordinary work')
        self.assertEqual(card_handoffs.reconcile(self.hub)['linked'],[])
        path=self.add_thread('new-work','')
        path.write_text(json.dumps({'type':'response_item','payload':{'type':'function_call','name':'untrusted_input','call_id':'context'}})+'\n'+json.dumps({'type':'response_item','payload':{'type':'function_call_output','call_id':'context','output':handoff['token']}})+'\n')
        result=card_handoffs.reconcile(self.hub)
        self.assertEqual(result['linked'][0]['threadId'],'new-work')
        self.assertEqual(card_handoffs.reconcile(self.hub)['linked'],[])
        self.assertEqual([s['id'] for s in self.f.record()['cards'][0]['sources']].count('new-work'),1)
    def test_cancelled_handoff_does_not_link(self):
        handoff=card_handoffs.prepare(self.hub,self.f.p,'camera')
        card_handoffs.cancel(self.hub,handoff['token'])
        self.add_thread('cancelled',handoff['token'])
        self.assertEqual(card_handoffs.reconcile(self.hub)['linked'],[])
