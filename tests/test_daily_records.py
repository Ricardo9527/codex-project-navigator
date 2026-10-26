import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_full_workflow
import conversation_assets
import delivery_audit
import project_records as records


class DailyRecordTests(unittest.TestCase):
    def setUp(self):
        self.base=test_full_workflow.FullWorkflowTests();self.base.setUp();self.base.seed()
        self.hub=self.base.hub;self.p=self.base.p;self.root=self.base.fixture.root
        self.first=self.root/'first.txt';self.first.write_text('first result')
        self.second=self.root/'second.txt';self.second.write_text('second result')
        events=[{'type':'turn_context','payload':{'turn_id':'turn'}}]
        events.append({'type':'response_item','timestamp':'1970-01-01T00:00:01Z','payload':{'type':'message','role':'assistant','phase':'final','id':'message','content':[{'type':'output_text','text':f'[one]({self.first}) [two]({self.second})'}]}})
        self.base.fixture.rollout.write_text(''.join(json.dumps(e)+'\n' for e in events))
    def tearDown(self):self.base.tearDown()
    def prepare(self,**args):return self.hub.dispatch('prepareDailyRecord',{'projectId':'a','threadId':'t','cardId':'camera',**args})
    def save(self,scope,**args):return self.hub.dispatch('saveDailyRecord',{'projectId':'a','scopeId':scope['scopeId'],'threadCoverage':'complete','updates':[{'cardId':'camera','changes':{'notes':['本轮完成，待确认。']},'deliveries':[{'assetId':a['assetId']} for a in scope['assets']]}],**args})

    def test_one_delta_once_and_retry_without_global_audit_or_full_page(self):
        r=self.base.record();r['cards'].append({**copy.deepcopy(r['cards'][0]),'id':'unrelated','title':'旧工作'})
        # An unrelated legacy origin gap must not block today's update.
        r['cards'][1]['resources'][0].pop('origin')
        records.save(self.p,r,records.revision(records.record_path(self.p)))
        with patch('library.read_page',side_effect=AssertionError('full page forbidden')),patch('delivery_audit.gaps',side_effect=AssertionError('audit forbidden')),patch('conversation_assets.thread_assets',wraps=conversation_assets.thread_assets) as assets:
            scope=self.prepare();self.assertNotIn('resources',scope['card'])
            later=self.base.record();later['cards'][1]['summary']='其他对话刚更新'
            records.save(self.p,later,records.revision(records.record_path(self.p)))
            with patch('daily_records.records.save',wraps=records.save) as save:
                result=self.save(scope);self.assertEqual(save.call_count,1)
            replay=self.save(scope);self.assertTrue(replay['replayed'])
            self.assertEqual(assets.call_count,1)
        r=self.base.record();self.assertEqual(len(r['cards'][0]['resources']),3)
        self.assertEqual(r['cards'][1]['summary'],'其他对话刚更新')
        self.assertEqual(r['reviewedThreads']['t'],1)
        self.assertEqual(result['cardIds'],['camera'])
        self.assertLess(len(json.dumps(result)),1000)
        self.assertTrue(all(x.get('origin',{}).get('itemId')=='message' for x in r['cards'][0]['resources'][1:]))

    def test_fixed_boundary_and_explicit_unchanged_coverage(self):
        scope=self.prepare()
        self.save(scope,threadCoverage='unchanged')
        self.assertNotIn('t',self.base.record()['reviewedThreads'])
        scope=self.prepare();original=self.hub.thread
        with patch.object(self.hub,'thread',side_effect=lambda identity:{**original(identity),'updated_at':2}):self.save(scope)
        self.assertEqual(self.base.record()['reviewedThreads']['t'],1)

    def test_failure_is_atomic_and_conflict_is_specific(self):
        scope=self.prepare();before=records.record_path(self.p).read_bytes()
        with self.assertRaisesRegex(ValueError,'交付不在'):
            self.save(scope,updates=[{'cardId':'camera','changes':{'summary':'must not save'},'deliveries':[{'assetId':'wrong'}]}])
        self.assertEqual(records.record_path(self.p).read_bytes(),before)
        r=self.base.record();r['cards'][0]['summary']='另一对话修改'
        records.save(self.p,r,records.revision(records.record_path(self.p)))
        before=records.record_path(self.p).read_bytes()
        with self.assertRaisesRegex(ValueError,'字段已变化'):
            self.save(scope,updates=[{'cardId':'camera','changes':{'summary':'conflicting'}}])
        self.assertEqual(records.record_path(self.p).read_bytes(),before)

    def test_same_message_different_files_are_not_silenced_and_copies_reuse_entry(self):
        scope=self.prepare();first=scope['assets'][0]
        self.save(scope,threadCoverage='unchanged',updates=[{'cardId':'camera','deliveries':[{'assetId':first['assetId']}]}])
        gaps=delivery_audit.gaps(self.hub,self.p)
        missing=[g for g in gaps if g['kind']=='unregistered_delivery']
        self.assertEqual(len(missing),1)
        self.assertNotEqual(missing[0]['assetId'],first['assetId'])
        # A new path with identical bytes must not produce a second resource.
        other=self.root/'copy.txt';other.write_bytes(self.first.read_bytes())
        scope=self.prepare()
        result=self.save(scope,threadCoverage='unchanged',updates=[{'cardId':'camera','files':[{'path':str(other),'external':True,'sourceReason':'用户提供的同内容副本'}]}])
        self.assertEqual(len(self.base.record()['cards'][0]['resources']),2)

    def test_import_source_and_new_card_defaults(self):
        scope=self.prepare(cardId=None)
        updates=[{'changes':{'title':'独立工作','summary':'新工作成果','categoryId':'features'},'files':[{'path':str(self.first),'external':True,'sourceReason':'用户导入，无聊天交付消息'}]}]
        self.save(scope,updates=updates)
        c=self.base.record()['cards'][-1]
        self.assertEqual(c['title'],'独立工作');self.assertEqual(c['resources'][0]['sourceDeclaration']['type'],'import')
        self.assertFalse(any(g['kind']=='missing_origin' and g['cardId']==c['id'] for g in delivery_audit.gaps(self.hub,self.p)))

    def test_selected_generated_image_gets_stable_copy_and_keeps_source(self):
        home=self.root/'home';generated=home/'.codex/generated_images/test';generated.mkdir(parents=True)
        image=generated/'image.png';image.write_bytes(b'image')
        events=[{'type':'turn_context','payload':{'turn_id':'turn'}},{'type':'response_item','timestamp':'1970-01-01T00:00:01Z','payload':{'type':'message','role':'assistant','id':'image-msg','content':[{'type':'output_text','text':f'[image]({image})'}]}}]
        self.base.fixture.rollout.write_text(''.join(json.dumps(e)+'\n' for e in events))
        scope=self.prepare()
        with patch('daily_records.Path.home',return_value=home):self.save(scope)
        r=self.base.record()['cards'][0]['resources'][-1]
        target=Path(self.p['path'])/r['path']
        self.assertEqual(target.read_bytes(),b'image')
        self.assertEqual(r['deliveries'][0]['path'],str(image))
        image.unlink();self.assertTrue(target.exists())

    def test_changed_file_after_prepare_does_not_bind_old_delivery(self):
        scope=self.prepare();self.first.write_text('updated since form was prepared')
        before=records.record_path(self.p).read_bytes()
        with self.assertRaisesRegex(ValueError,'已变化'):self.save(scope)
        self.assertEqual(records.record_path(self.p).read_bytes(),before)
