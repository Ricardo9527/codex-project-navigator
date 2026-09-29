import copy
import json
from pathlib import Path
import unittest
import test_full_workflow
import delivery_audit
import project_records as records


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.base=test_full_workflow.FullWorkflowTests();self.base.setUp();self.base.seed()
        self.hub=self.base.hub;self.p=self.base.p
        self.base.complete(records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads()))
    def tearDown(self):self.base.tearDown()
    def delivered_image(self):
        image=self.base.fixture.root/'late-image.png';image.write_bytes(b'recovered image')
        event={'type':'event_msg','timestamp':'2026-09-20T00:00:00Z','payload':{'type':'item_completed','turn_id':'old-turn','item':{'kind':'image_gen.generation','id':'image-one','status':'completed','savedPath':str(image)}}}
        with self.base.fixture.rollout.open('a') as f:f.write(json.dumps(event)+'\n')
        return image
    def test_already_reviewed_thread_delivery_is_in_scope_and_must_be_handled(self):
        self.delivered_image()
        batch=self.hub.prepare_record_batch(self.p)
        self.assertEqual(batch['pendingThreads'],[])
        self.assertEqual(len(batch['deliveryGaps']),1)
        gap=batch['deliveryGaps'][0]
        with self.assertRaisesRegex(ValueError,'成果缺口'):
            self.hub.dispatch('checkpoint',{'projectId':'a','batchId':batch['batchId'],'complete':True,'expectedHead':batch['head'],'expectedRevision':records.revision(records.record_path(self.p))})
        self.hub.dispatch('registerDelivery',{'projectId':'a','threadId':'t','assetId':gap['assetId'],'cardId':'camera','label':'后续交付','expectedRevision':records.revision(records.record_path(self.p))})
        self.assertEqual(delivery_audit.gaps(self.hub,self.p),[])
        self.hub.dispatch('checkpoint',{'projectId':'a','batchId':batch['batchId'],'complete':True,'expectedHead':batch['head'],'expectedRevision':records.revision(records.record_path(self.p))})
    def test_missing_delivery_note_is_quiet_until_file_returns(self):
        image=self.delivered_image();image.unlink()
        gap=delivery_audit.gaps(self.hub,self.p)[0]
        self.hub.dispatch('resolveDeliveryGap',{'projectId':'a','gapId':gap['id'],'signature':gap['signature'],'status':'unavailable','reason':'原始交付位置已失效，关联对话中未找到替代文件。','expectedRevision':records.revision(records.record_path(self.p))})
        self.assertEqual(delivery_audit.gaps(self.hub,self.p),[])
        image.write_bytes(b'restored')
        self.assertEqual(delivery_audit.gaps(self.hub,self.p)[0]['id'],gap['id'])
    def test_existing_unregistered_file_cannot_be_marked_unavailable(self):
        self.delivered_image();gap=delivery_audit.gaps(self.hub,self.p)[0]
        with self.assertRaisesRegex(ValueError,'文件存在'):
            self.hub.dispatch('resolveDeliveryGap',{'projectId':'a','gapId':gap['id'],'signature':gap['signature'],'status':'unavailable','reason':'尚未归卡','expectedRevision':records.revision(records.record_path(self.p))})
    def test_manual_category_order_and_names_survive_agent_updates(self):
        path=records.record_path(self.p);r=self.base.record();r['categories'].append({'id':'history','title':'历史','manualFields':['title']});r['manualCategoryOrder']=True
        records.save(self.p,r,records.revision(path),'user')
        original=self.base.record();changed=copy.deepcopy(original);changed['categories'].reverse()
        with self.assertRaisesRegex(ValueError,'目录顺序'):records.save(self.p,changed,records.revision(path))
        changed=copy.deepcopy(original);changed['categories'][-1]['title']='过往材料'
        with self.assertRaisesRegex(ValueError,'分类'):records.save(self.p,changed,records.revision(path))
        changed=copy.deepcopy(original);changed['categories'][-1].pop('manualFields')
        records.save(self.p,changed,records.revision(path))
        self.assertEqual(self.base.record()['categories'][-1]['manualFields'],['title'])
