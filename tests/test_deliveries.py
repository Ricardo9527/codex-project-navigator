import json
from pathlib import Path
import tempfile
import unittest
from conversation_assets import scan
import test_full_workflow
from content_pages import read_page
import project_records as records


class DeliveryParserTests(unittest.TestCase):
    def test_generated_images_and_links_keep_time_and_native_message_target(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'draft (2).txt';p.write_text('text');img=root/'exec-image.png';img.write_bytes(b'image')
            events=[
                {'type':'event_msg','payload':{'type':'task_started','turn_id':'turn1'}},
                {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'生成红夹克三视图'}]}},
                {'type':'response_item','timestamp':'2026-09-20T01:00:00Z','payload':{'type':'message','role':'assistant','id':'msg1','phase':'final_answer','content':[{'type':'output_text','text':f'[文件](<{p}>)'}]}},
                {'type':'event_msg','timestamp':'2026-09-21T01:00:00Z','payload':{'type':'item_completed','turn_id':'turn2','item':{'kind':'image_gen.generation','id':'exec-image','status':'completed','savedPath':str(img)}}},
            ]
            rollout=root/'session.jsonl';rollout.write_text(''.join(json.dumps(e)+'\n' for e in events))
            assets=scan(rollout,'thread1')
            self.assertEqual([a['path'] for a in assets],[str(img),str(p)])
            self.assertEqual(assets[0]['origin']['itemId'],'exec-image')
            self.assertEqual(assets[0]['origin']['turnId'],'turn2')
            self.assertEqual(assets[0]['origin']['prompt'],'生成红夹克三视图')


class DeliveryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.base=test_full_workflow.FullWorkflowTests();self.base.setUp();self.base.seed()
        self.hub=self.base.hub;self.p=self.base.p
    def tearDown(self):self.base.tearDown()

    def test_latest_order_does_not_depend_on_selection_and_can_cancel(self):
        p=records.record_path(self.p);r=self.base.record();c=r['cards'][0]
        c['resources'][0]['deliveredAt']='2026-09-10T00:00:00Z'
        other=Path(self.p['path'])/'new.md';other.write_text('new')
        c['resources'].append(dict(id='new',label='新版本',path='new.md',format='文档',role='result',deliveredAt='2026-09-20T00:00:00Z'))
        records.save(self.p,r,records.revision(p))
        self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':'doc','expectedRevision':records.revision(p)})
        page=read_page(self.hub.data_dir,self.p)
        self.assertEqual([r['id'] for r in page['cards'][0]['resources']],['new','doc'])
        self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':'doc','adoption':'review','expectedRevision':page['revision']})
        self.assertEqual(read_page(self.hub.data_dir,self.p)['cards'][0]['resources'][1]['effectiveAdoption'],'review')
        r=self.base.record();r['cards'][0]['resources'][0]['role']='process';records.save(self.p,r,records.revision(p))
        with self.assertRaisesRegex(ValueError,'辅助文件'):
            self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':'doc','expectedRevision':records.revision(p)})
