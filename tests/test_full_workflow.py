import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import test_library
import project_records as records
import project_search
import project_resources
import maintenance
from content_pages import read_page,resource_action


class FullWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_library.LibraryTests();self.fixture.setUp()
        self.hub=self.fixture.hub;self.hub.refresh_projects();self.p=self.hub.project('a')
    def tearDown(self):self.fixture.tearDown()
    def record(self):return json.loads(records.record_path(self.p).read_text())
    def seed(self):
        records.ensure(self.p);records.git(self.p,'config','user.name','Test');records.git(self.p,'config','user.email','test@example.invalid')
        r=self.record();r['about']='镜头控制';r['categories']=[{'id':'features','title':'功能'}]
        r['cards']=[{'id':'camera','title':'摄像机功能','summary':'调整镜头','kind':'功能','icon':'file','caption':'','categoryIds':['features'],'resources':[{'id':'doc','label':'功能说明','path':'docs/camera.md','format':'文档','role':'result','note':'','origin':{'threadId':'t','turnId':'turn-t','itemId':'doc-message'}}],'sources':[{'id':'t','title':'镜头控制','label':'相关讨论'}],'sections':[],'records':[],'requirements':[],'related':[]}]
        records.save(self.p,r,records.revision(records.record_path(self.p)));return r
    def complete(self, batch):
        r=self.record()
        for t in batch['pendingThreads']:r['reviewedThreads'][t['id']]=t['updated_at']
        saved=records.save(self.p,r,records.revision(records.record_path(self.p)))
        return records.checkpoint(self.hub.data_dir,self.p,saved['revision'],'docs: completed',batch['head'],batch_id=batch['batchId'],complete=True)

    def test_first_review_same_entry_then_progress_survives_cache_loss(self):
        context=self.hub.dispatch('maintenanceContext',{'projectId':'a'})
        job=json.loads((self.hub.data_dir/'maintenance.json').read_text())['a']
        batch=records.read_batch(self.hub.data_dir,job['batchId'])
        self.assertTrue(batch['initialReview']);self.assertIn('docs/camera.md',batch['initialFiles'])
        self.seed();state=self.complete(batch)
        self.assertIn('reviewState',self.record())
        self.hub.dispatch('finishMaintenance',{'projectId':'a','jobId':context['jobId']})
        with tempfile.TemporaryDirectory() as cache:
            self.assertEqual(records.checkpoint_state(cache,self.p)['commit'],state['commit'])
            self.assertFalse(records.changes(cache,self.p,self.hub.all_threads())['initialReview'])
        self.assertTrue(records.prepare_batch(self.hub.data_dir,self.p,self.hub.maintenance_threads('a'))['noChanges'])

    def test_new_commits_during_review_are_kept_pending(self):
        self.seed();self.complete(records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads()))
        (Path(self.p['path'])/'one.txt').write_text('first')
        records.git(self.p,'add','one.txt');records.git(self.p,'commit','-m','feature one')
        batch=records.prepare_batch(self.hub.data_dir,self.p,[])
        (Path(self.p['path'])/'two.txt').write_text('later')
        records.git(self.p,'add','two.txt');records.git(self.p,'commit','-m','feature two')
        state=self.complete(batch)
        self.assertEqual(state['commit'],batch['head'])
        self.assertIn('feature two',records.changes(self.hub.data_dir,self.p,[])['commits'])

    def test_cancelled_or_abandoned_launch_can_retry_and_finished_native_task_recovers(self):
        self.seed();first=self.hub.dispatch('maintenanceContext',{'projectId':'a'})
        self.hub.dispatch('cancelMaintenanceLaunch',{'projectId':'a','jobId':first['jobId']})
        second=self.hub.dispatch('maintenanceContext',{'projectId':'a'});self.assertNotEqual(first['jobId'],second['jobId'])
        self.hub.dispatch('markMaintenance',{'projectId':'a','jobId':second['jobId'],'threadId':'t'})
        with patch('maintenance.native_state',return_value='finished'):
            state=self.hub.dispatch('record',{'projectId':'a'})['maintenance'];self.assertEqual(state['state'],'interrupted')
            third=self.hub.dispatch('maintenanceContext',{'projectId':'a'});self.assertNotEqual(second['jobId'],third['jobId'])
        with maintenance.jobs_file(self.hub) as jobs:jobs['a']['startedAt']=1
        fourth=self.hub.dispatch('maintenanceContext',{'projectId':'a'});self.assertNotEqual(third['jobId'],fourth['jobId'])

    def test_registered_external_result_search_and_adoption_versions(self):
        self.seed();outside=self.fixture.root/'外部成品.txt';outside.write_text('外部成果正文星轨环绕')
        args={'projectId':'a','cardId':'camera','path':str(outside),'external':True,'expectedRevision':records.revision(records.record_path(self.p))}
        self.hub.dispatch('registerResource',args)
        r=self.record()['cards'][0]['resources'][-1]
        self.assertEqual(r['source'],'external')
        self.assertIn('星轨环绕',resource_action(self.hub.data_dir,self.p,'pagePreview',{'cardId':'camera','resourceId':r['id']})['text'])
        self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':r['id'],'expectedRevision':records.revision(records.record_path(self.p))})
        self.assertEqual(next(x for x in read_page(self.hub.data_dir,self.p)['cards'][0]['resources'] if x['id']==r['id'])['effectiveAdoption'],'accepted')
        outside.write_text('全新版本，还没有被用户确认采用。')
        changed=next(x for x in read_page(self.hub.data_dir,self.p)['cards'][0]['resources'] if x['id']==r['id'])
        self.assertEqual(changed['effectiveAdoption'],'review');self.assertTrue(changed['versionChanged'])
        self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':r['id'],'expectedRevision':records.revision(records.record_path(self.p))})
        self.assertEqual(len(self.record()['cards'][0]['resources'][-1]['adoptionHistory']),1)

    def test_search_finds_file_body_chat_body_and_unorganized_sources_but_obeys_ignore(self):
        self.seed();root=Path(self.p['path']);(root/'.gitignore').write_text('ignored/\n');(root/'ignored').mkdir();(root/'ignored'/'hidden.txt').write_text('不应出现的关键词')
        (root/'新成果.txt').write_text('尚未归卡的星云内容')
        project_search.initialize(self.hub);self.hub.search_jobs['a']={'running':True,'errors':[]};project_search.refresh(self.hub,self.p)
        def search(q):return project_search.search(self.hub,self.p,{'query':q,'refresh':False})
        self.assertIn('camera',search('固定朝向')['cardIds'])
        self.assertEqual(search('四元数过冲')['hits'][0]['kind'],'thread')
        self.assertTrue(search('星云内容')['hits'])
        self.assertEqual(search('不应出现的关键词')['total'],0)
        self.assertEqual(search('不可检索的注入内容')['total'],0)
        self.hub.register_scheduled_maintenance('a','t')
        self.hub.search_jobs['a']={'running':True,'errors':[]};project_search.refresh(self.hub,self.p)
        self.assertEqual(search('四元数过冲')['total'],0)

    def test_new_project_automation_plan_and_registered_task_are_not_duplicated(self):
        import automation_setup
        self.seed();self.complete(records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads()))
        fake_home=self.fixture.root/'home';(fake_home/'.codex/automations').mkdir(parents=True)
        (fake_home/'.codex/config.toml').write_text('model="gpt-6-astra"\nmodel_reasoning_effort="high"\n')
        with patch('automation_setup.Path.home',return_value=fake_home):
            plan=self.hub.dispatch('automationPlan',{'projectId':'a'})
            self.assertTrue(plan['needsCreate']);self.assertEqual(plan['arguments']['projectId'],'a')
            folder=fake_home/'.codex/automations/task';folder.mkdir()
            (folder/'automation.toml').write_text('id="task"\nkind="cron"\nstatus="ACTIVE"\nprompt="use project-records/SKILL.md"\n[target]\ntype="project"\nproject_id="a"\n')
            self.assertFalse(self.hub.dispatch('automationPlan',{'projectId':'a'})['needsCreate'])
            self.hub.dispatch('linkAutomation',{'projectId':'a','automationId':'task','expectedRevision':records.revision(records.record_path(self.p))})
            self.assertEqual(self.record()['maintenanceAutomation']['id'],'task')

    def test_failed_git_commit_does_not_advance_record_progress(self):
        self.seed();batch=records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads())
        before=self.record()
        with patch('project_records.commit_record',side_effect=ValueError('commit failed')):
            with self.assertRaisesRegex(ValueError,'commit failed'):self.complete(batch)
        self.assertEqual(self.record().get('reviewState'),before.get('reviewState'))
        self.assertTrue((self.hub.data_dir/'review-batches'/(batch['batchId']+'.json')).exists())

    def test_reading_scope_pages_preserves_the_full_scope(self):
        self.seed();batch=records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads())
        items=[];offset=0
        while offset is not None:
            page=records.scope_page(self.hub.data_dir,self.p,{'batchId':batch['batchId'],'kind':'initialFiles','offset':offset,'limit':1})
            items.extend(page['items']);offset=page['nextOffset']
        self.assertEqual(items,batch['initialFiles'])

    def test_word_excel_and_pdf_body_extraction(self):
        import zipfile
        root=self.fixture.root
        word=root/'sample.docx'
        with zipfile.ZipFile(word,'w') as archive:archive.writestr('word/document.xml','<document><p><t>文档正文检索验证</t></p></document>')
        self.assertIn('文档正文检索验证',project_search.document_text(word))
        excel=root/'sample.xlsx'
        with zipfile.ZipFile(excel,'w') as archive:archive.writestr('xl/sharedStrings.xml','<sst><si><t>表格台词检索验证</t></si></sst>')
        self.assertIn('表格台词检索验证',project_search.document_text(excel))
        stream=b'BT /F1 12 Tf 72 720 Td (PDFSearchProof) Tj ET'
        objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
        data=b'%PDF-1.4\n';offsets=[0]
        for i,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
        start=len(data);data+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
        for offset in offsets[1:]:data+=f'{offset:010d} 00000 n \n'.encode()
        data+=f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()
        pdf=root/'sample.pdf';pdf.write_bytes(data)
        self.assertIn('PDFSearchProof',project_search.document_text(pdf))

    def test_imported_project_rebinds_without_losing_review_progress(self):
        import shutil
        self.seed();self.complete(records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads()))
        original=self.record()['reviewState']
        imported=self.fixture.root/'imported';shutil.copytree(self.p['path'],imported)
        p={'id':'new-desktop-id','name':'Imported','path':str(imported)}
        records.ensure(p)
        r=json.loads(records.record_path(p).read_text())
        self.assertEqual(r['projectId'],'new-desktop-id');self.assertEqual(r['reviewState'],original)
        self.assertFalse(records.changes(self.fixture.root/'no-cache',p,[])['initialReview'])

    def test_adoption_rejects_file_changed_since_visible_version(self):
        self.seed();page=read_page(self.hub.data_dir,self.p)
        viewed=page['cards'][0]['resources'][0]['versionStamp']
        self.fixture.file.write_text('另一个尚未看到的新版本')
        with self.assertRaisesRegex(ValueError,'文件版本已变化'):
            self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':'doc','expectedRevision':page['revision'],'expectedStamp':viewed})

    def test_adoption_wire_stamp_and_refresh(self):
        import os
        self.seed()
        os.utime(self.fixture.file,ns=(1790539017002695308,1790539017002695308))
        page=read_page(self.hub.data_dir,self.p)
        token=page['cards'][0]['resources'][0]['versionStamp']
        self.assertIsInstance(token,str)
        self.assertEqual(json.loads(json.dumps(token)),token)
        self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':'doc','expectedRevision':page['revision'],'expectedStamp':token})
        self.fixture.file.write_text('新版字幕')
        result=resource_action(self.hub.data_dir,self.p,'pagePreview',{'cardId':'camera','resourceId':'doc'})
        self.assertEqual(result['text'],'新版字幕');self.assertNotEqual(result['versionStamp'],token)
        self.hub.dispatch('adoptResource',{'projectId':'a','cardId':'camera','resourceId':'doc','expectedRevision':records.revision(records.record_path(self.p)),'expectedStamp':result['versionStamp']})

    def test_review_thread_pages_preserve_middle_and_exclude_tool_text(self):
        self.fixture.write_messages('开头'+('连续正文'*4000)+'末尾')
        batch=records.prepare_batch(self.hub.data_dir,self.p,self.hub.all_threads())
        args={'projectId':'a','batchId':batch['batchId'],'threadId':'t'}
        first=self.hub.dispatch('reviewThread',args);parts=[first['text']];page=first
        while page['nextOffset'] is not None:
            page=self.hub.dispatch('reviewThread',{**args,'offset':page['nextOffset']});parts.append(page['text'])
        combined=''.join(parts)
        self.assertEqual(combined,self.hub.messages(self.fixture.rollout,labelled=True))
        self.assertIn('连续正文'*4000,combined);self.assertNotIn('不可检索的注入内容',combined)
        with self.assertRaisesRegex(ValueError,'清单内'):
            self.hub.dispatch('reviewThread',{**args,'threadId':'outside'})

    def test_future_thread_watermark_cannot_hide_unread_messages(self):
        r=self.seed();r['reviewedThreads']={'t':9999999999}
        with self.assertRaisesRegex(ValueError,'未来或猜测'):
            self.hub.dispatch('saveRecord',{'projectId':'a','record':r,'expectedRevision':records.revision(records.record_path(self.p))})
