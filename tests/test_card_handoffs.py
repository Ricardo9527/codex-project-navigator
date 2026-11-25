import json
import sqlite3
import time
import unittest

import test_full_workflow


class CardHandoffTests(unittest.TestCase):
    def setUp(self):
        self.f=test_full_workflow.FullWorkflowTests();self.f.setUp();self.f.seed()
        self.hub=self.f.hub
        f=self.f.fixture
        self.path=f.root/'new-work.jsonl'
        with sqlite3.connect(f.source) as db:
            db.execute('INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       ('new-work','从卡片工作','raw',str(f.project),int(time.time()),0,'main','','native',None,None,None,str(self.path)))
        f.original=f.source.read_bytes()

    def tearDown(self):self.f.tearDown()

    def link(self):
        return self.hub.dispatch('linkSentCardDraft',{'threadId':'new-work'})

    def write_context(self,project='a'):
        snapshot=json.dumps({'project':{'id':project},'card':{'id':'camera'}})
        attachment={'kind':'model_context','source':'mcp_app','server':'project-navigator-flow',
                    'text':'# 项目记录引用\n\n```json\n'+snapshot+'\n```'}
        events=[{'type':'response_item','payload':{'type':'function_call','name':'untrusted_input','call_id':'c'}},
                {'type':'response_item','payload':{'type':'function_call_output','call_id':'c',
                 'output':[{'type':'input_text','text':json.dumps(attachment)}]}}]
        self.path.write_text(''.join(json.dumps(e)+'\n' for e in events))

    def started(self):
        with self.path.open('a') as f:f.write('{"type":"event_msg","payload":{"type":"task_started"}}\n')

    def test_discarded_drafts_leave_no_pending_entry_and_sent_draft_links_once(self):
        before=self.f.record()
        for _ in range(10):
            self.hub.dispatch('prepareCardHandoff',{'projectId':'a','cardId':'camera'})
        self.assertFalse((self.hub.data_dir/'card-handoffs.json').exists())
        self.assertEqual(before,self.f.record())
        self.assertTrue(self.link()['retry'])
        self.write_context();self.assertTrue(self.link()['retry'])
        self.started();self.assertTrue(self.link()['linked']);self.link()
        self.assertEqual([s['id'] for s in self.f.record()['cards'][0]['sources']].count('new-work'),1)

    def test_unrelated_thread_and_wrong_project_do_not_link(self):
        self.started();self.assertFalse(self.link()['linked'])
        self.write_context('other');self.started();self.assertFalse(self.link()['linked'])
