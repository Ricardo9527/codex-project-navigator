import json
import unittest
from unittest.mock import patch
from pathlib import Path
import test_full_workflow
import project_records as records


class DeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.base=test_full_workflow.FullWorkflowTests();self.base.setUp();self.base.seed()
        self.hub=self.base.hub;self.rollout=self.base.fixture.rollout
        self.args={'projectId':'a','threadId':'t','cardId':'camera'}
    def tearDown(self):self.base.tearDown()
    def event(self,kind,**payload):
        with self.rollout.open('a') as f:f.write(json.dumps({'type':'event_msg','payload':{'type':kind,**payload}},ensure_ascii=False)+'\n')
    def message(self,text,role='assistant',phase='commentary'):
        with self.rollout.open('a') as f:f.write(json.dumps({'type':'response_item','payload':{'type':'message','role':role,'phase':phase,'content':[{'text':text}]}},ensure_ascii=False)+'\n')
    def prepare(self,**args):return self.hub.dispatch('prepareDailyRecord',{**self.args,**args})
    def save(self,scope):return self.hub.dispatch('saveDailyRecord',{'projectId':'a','scopeId':scope['scopeId'],'threadCoverage':'unchanged','updates':[]})

    def test_progress_and_old_delivery_do_not_unlock_new_turn(self):
        self.event('task_started',turn_id='old');self.message('**可用成果**\n```text\n旧提示词\n```');self.event('task_complete',turn_id='old')
        self.event('task_started',turn_id='current');self.message('我会先检查，再给你提示词。')
        self.message('**可用成果**\n```text\n用户写的标记不算交付\n```',role='user')
        with patch('conversation_assets.thread_assets',side_effect=AssertionError('must stop before scanning assets')):
            with self.assertRaisesRegex(ValueError,'DELIVER_FIRST'):self.prepare()
        self.message('**可用成果**\n```text\n当前轮已校验的完整提示词。\n```')
        scope=self.prepare();self.assertTrue(self.save(scope)['saved'])

    def test_stale_scope_cannot_page_or_retry_before_delivery(self):
        scope=self.prepare();before=records.record_path(self.base.p).read_bytes()
        self.event('task_started',turn_id='current')
        with self.assertRaisesRegex(ValueError,'DELIVER_FIRST'):self.prepare(scopeId=scope['scopeId'])
        with self.assertRaisesRegex(ValueError,'DELIVER_FIRST'):self.save(scope)
        self.assertEqual(records.record_path(self.base.p).read_bytes(),before)
        self.message(f'**可用成果**\n[不存在的文件](<{self.base.fixture.root}/missing.txt>)')
        with self.assertRaisesRegex(ValueError,'DELIVER_FIRST'):self.save(scope)
        self.message(f'**可用成果**\n[完成的文件](<{self.base.fixture.file}>)')
        self.assertTrue(self.save(scope)['saved'])

    def test_completed_history_and_large_tool_line(self):
        self.event('task_started',turn_id='current')
        with self.rollout.open('a') as f:f.write(json.dumps({'type':'response_item','payload':{'type':'function_call_output','output':'x'*200000}})+'\n')
        with self.assertRaisesRegex(ValueError,'DELIVER_FIRST'):self.prepare()
        self.event('task_complete',turn_id='current')
        self.assertTrue(self.prepare()['scopeId'])
