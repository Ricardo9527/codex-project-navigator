import json
import unittest
from unittest.mock import patch
import test_full_workflow
import project_records as records


class DailyCoverageTests(unittest.TestCase):
    def setUp(self):
        self.base=test_full_workflow.FullWorkflowTests();self.base.setUp();self.base.seed()
        self.hub=self.base.hub;self.p=self.base.p
        self.base.complete(records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads()))
    def tearDown(self):self.base.tearDown()
    def save(self,coverage,record=None,revision=None):
        return self.hub.dispatch('saveRecord',{'projectId':'a','record':record or self.base.record(),
            'expectedRevision':revision or records.revision(records.record_path(self.p)),'coverage':coverage})
    def commit(self,text):
        self.base.fixture.file.write_text(text)
        records.git(self.p,'add','docs/camera.md');records.git(self.p,'commit','-m',text)
        return records.git(self.p,'rev-parse','HEAD').stdout.strip()

    def test_daily_save_covers_exact_commits_and_resources_without_skipping_other_work(self):
        earlier=self.commit('earlier');latest=self.commit('latest')
        baseline=self.base.record()['reviewState']['commit']
        r=self.base.record();r['cards'][0]['summary']='新的镜头行为'
        self.save({'cardIds':['camera'],'commits':[latest]},r)
        record=self.base.record()
        self.assertEqual(record['reviewedCommits'][latest],['camera'])
        self.assertEqual(record['reviewState']['commit'],baseline)
        delta=records.changes(self.hub.data_dir,self.p,self.hub.all_threads())
        self.assertIn(earlier,delta['commits']);self.assertNotIn(latest,delta['commits'])
        self.assertEqual(delta['changedResources'],{})
        self.base.fixture.file.write_text('subsequent change')
        self.assertIn('camera/doc',records.changes(self.hub.data_dir,self.p,self.hub.all_threads())['changedResources'])

    def test_daily_chat_boundary_excludes_messages_written_after_capture(self):
        def event(second,text):return {'type':'response_item','timestamp':f'1970-01-01T00:00:{second:02d}Z',
            'payload':{'type':'message','role':'user','content':[{'type':'input_text','text':text}]}}
        self.base.fixture.rollout.write_text(''.join(json.dumps(event(n,t))+'\n' for n,t in [(2,'决定甲'),(3,'稍后新增')]))
        original=self.hub.thread('t');current={**original,'updated_at':2}
        with patch.object(self.hub,'thread',return_value=current):
            scope=self.hub.dispatch('reviewThread',{'projectId':'a','threadId':'t'})
        self.assertIn('决定甲',scope['text']);self.assertNotIn('稍后新增',scope['text'])
        with patch.object(self.hub,'thread',return_value={**original,'updated_at':3}):
            self.save({'cardIds':[],'thread':{k:scope[k] for k in ['reviewedUntil','updated_at']}|{'id':'t'}})
        self.assertEqual(self.base.record()['reviewedThreads']['t'],2)
        delta=records.changes(self.hub.data_dir,self.p,[{**original,'updated_at':3}])
        self.assertEqual(delta['pendingThreads'][0]['reviewedUntil'],2)
        self.assertEqual(delta['pendingThreads'][0]['updated_at'],3)

    def test_invalid_coverage_and_revision_conflict_do_not_save_partial_progress(self):
        before=records.record_path(self.p).read_bytes()
        for coverage in [
            {'cardIds':['missing'],'commits':[]},
            {'cardIds':['camera'],'commits':['f'*40]},
            {'cardIds':[],'thread':{'id':'t','reviewedUntil':0,'updated_at':1}},
            {'cardIds':[],'thread':{'id':'t','reviewedUntil':1,'updated_at':999}},
        ]:
            with self.assertRaises(ValueError):self.save(coverage)
            self.assertEqual(records.record_path(self.p).read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'其他对话'):
            self.save({'cardIds':['camera'],'commits':[]},revision='stale')
        self.assertEqual(records.record_path(self.p).read_bytes(),before)
