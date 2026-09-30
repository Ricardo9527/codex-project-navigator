import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from library import Library
from project_records import record_path


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root/'project';self.project.mkdir()
        self.docs = self.project/'docs';self.docs.mkdir()
        self.file = self.docs/'camera.md';self.file.write_text('# 镜头控制\n\n固定朝向旋转限幅。')
        self.data = self.root/'data';self.data.mkdir()
        (self.data/'projects.json').write_text(json.dumps([dict(id='a',name='Project',path=str(self.project))]))
        self.rollout = self.root/'session.jsonl'
        self.write_messages()
        self.source = self.root/'codex.sqlite'
        with sqlite3.connect(self.source) as db:
            db.executescript('''CREATE TABLE projects(id TEXT,name TEXT,position INTEGER);
                CREATE TABLE project_roots(project_id TEXT,path TEXT,position INTEGER);
                CREATE TABLE threads(id TEXT,name TEXT,title TEXT,cwd TEXT,updated_at INTEGER,archived INTEGER,
                git_branch TEXT,preview TEXT,project_id TEXT,agent_role TEXT,agent_path TEXT,thread_source TEXT,rollout_path TEXT);''')
            db.execute('INSERT INTO projects VALUES (?,?,?)',('native','Project',0))
            db.execute('INSERT INTO project_roots VALUES (?,?,?)',('native',str(self.project),0))
            db.execute('INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',('t','镜头控制','raw',str(self.project),1,0,'main','摘要','native',None,None,None,str(self.rollout)))
        self.original = self.source.read_bytes()
        self.hub = Library(self.source,self.data)

    def write_messages(self, extra=''):
        def item(role,text):return dict(type='response_item',payload=dict(type='message',role=role,phase='final_answer' if role=='assistant' else None,content=[dict(type='input_text' if role=='user' else 'output_text',text=text)]))
        records=[item('developer','不可检索的注入内容'),item('user','控制四元数过冲'),item('assistant',f'[成果]({self.file}) '+extra)]
        self.rollout.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))

    def tearDown(self):
        self.assertEqual(self.original,self.source.read_bytes())
        self.temp.cleanup()

    def test_discovery_search_sources_and_incremental_acceptance(self):
        result=self.hub.scan();self.assertEqual(result['errors'],[])
        detail=self.hub.detail(dict(projectId='native'))
        self.assertEqual(detail['totalArtifacts'],1)
        a=detail['artifacts'][0]
        self.assertEqual(a['title'],'镜头控制');self.assertEqual(a['status'],'review')
        self.assertEqual(a['sources'][0]['id'],'t')
        self.assertEqual(self.hub.detail(dict(projectId='a',query='四元数'))['totalThreads'],1)
        self.assertEqual(self.hub.detail(dict(projectId='a',query='注入内容'))['totalThreads'],0)
        self.assertEqual(self.hub.detail(dict(projectId='a',query='固定朝向'))['totalArtifacts'],1)
        self.hub.update_artifact(dict(id=a['id'],status='accepted',note='用于下一版',categoryIds=[]))
        self.hub.scan()
        self.assertEqual(self.hub.detail(dict(projectId='a'))['artifacts'][0]['status'],'accepted')
        self.write_messages('新增搜索关键词');self.file.write_text('# 镜头控制\n变化后的文档')
        self.hub.scan()
        saved=self.hub.detail(dict(projectId='a'))['artifacts'][0]
        self.assertEqual(saved['status'],'review');self.assertEqual(saved['note'],'用于下一版');self.assertEqual(saved['categoryIds'],[])
        self.assertEqual(self.hub.detail(dict(projectId='a',query='新增搜索关键词'))['totalThreads'],1)
        self.assertEqual(self.hub.detail(dict(projectId='a',query='变化后的文档'))['totalArtifacts'],1)

    def test_dependencies_and_symlinks_excluded_missing_file_retained(self):
        (self.project/'node_modules').mkdir();(self.project/'node_modules'/'private.md').write_text('skip')
        outside=self.root/'outside.md';outside.write_text('outside');(self.docs/'link.md').symlink_to(outside)
        self.hub.scan();self.assertEqual(self.hub.detail(dict(projectId='a'))['totalArtifacts'],1)
        self.file.unlink();self.hub.scan()
        self.assertFalse(self.hub.detail(dict(projectId='a'))['artifacts'][0]['exists'])

    def test_partial_jsonl_tail_retried(self):
        with self.rollout.open('a') as stream:stream.write('{"type":')
        self.assertEqual(self.hub.scan()['errors'],[])
        self.write_messages('写入已结束');self.hub.scan()
        self.assertEqual(self.hub.detail(dict(projectId='a',query='写入已结束'))['totalThreads'],1)

    def test_manual_thread_categories_survive_scan(self):
        self.hub.scan();self.hub.tag_thread(dict(threadId='t',categoryIds=[]));self.write_messages('changed');self.hub.scan()
        self.assertEqual(self.hub.detail(dict(projectId='a'))['threads'][0]['categoryIds'],[])

    def test_card_thread_link_uses_native_title_without_changing_source(self):
        self.hub.scan()
        path=record_path({'path':str(self.project)});path.parent.mkdir()
        path.write_text(json.dumps({'version':1,'projectId':'a','about':'Camera project','categories':[{'id':'camera','title':'Camera'}],'cards':[{'id':'camera','title':'Camera','summary':'Controls','kind':'功能','icon':'file','caption':'','sections':[],'records':[],'related':[],'categoryIds':['camera'],'requirements':[],'resources':[],'sources':[]}]}))
        args=dict(projectId='native',cardId='camera',threadId='t')
        self.hub.dispatch('linkCardThread',args)
        self.hub.dispatch('linkCardThread',args)
        sources=self.hub.detail(dict(projectId='a'))['contentPage']['cards'][0]['sources']
        self.assertEqual(len(sources),1)
        self.assertEqual(sources[0]['title'],'镜头控制')

    def test_scheduled_maintenance_is_excluded_without_touching_source_or_record(self):
        self.hub.refresh_projects()
        self.assertEqual(len(self.hub.maintenance_threads('a')),1)
        self.hub.register_scheduled_maintenance('a','t')
        self.hub.register_scheduled_maintenance('a','t')
        self.assertEqual(self.hub.maintenance_threads('a'),[])
        self.assertFalse(record_path({'path':str(self.project)}).exists())
        with self.assertRaisesRegex(ValueError,'不属于'):
            self.hub.register_scheduled_maintenance('another','t')

    def test_maintenance_cannot_finish_while_scope_is_unprocessed(self):
        self.hub.refresh_projects()
        path=self.data/'maintenance.json'
        path.write_text(json.dumps({'a':{'jobId':'job','batchId':'scope','state':'running'}}))
        folder=self.data/'review-batches';folder.mkdir();scope=folder/'scope.json';scope.write_text('{}')
        with self.assertRaisesRegex(ValueError,'不能标记完成'):
            self.hub.dispatch('finishMaintenance',{'projectId':'a','jobId':'job'})
        self.hub.dispatch('finishMaintenance',{'projectId':'a','jobId':'job','state':'failed'})
        self.assertTrue(scope.exists())
        scope.unlink()
        from unittest.mock import patch
        with patch('maintenance.records.checkpoint_state',return_value={'lastScope':'scope'}):
            self.hub.dispatch('finishMaintenance',{'projectId':'a','jobId':'job'})
        self.assertEqual(json.loads(path.read_text())['a']['state'],'completed')

    def test_maintenance_replacement_checkpoint_requires_original_coverage(self):
        from unittest.mock import patch
        import uuid
        self.hub.refresh_projects()
        batch_id=str(uuid.uuid4());replacement=str(uuid.uuid4())
        folder=self.data/'review-batches';folder.mkdir()
        (folder/(batch_id+'.json')).write_text(json.dumps({'projectId':'a','head':'head','pendingThreads':[{'id':'t','updated_at':1}],
            'workingTree':{'docs/camera.md':[1,2]},'changedResources':{'one/result':[1,2]}}))
        path=record_path({'path':str(self.project)});path.parent.mkdir();path.write_text(json.dumps({'reviewedThreads':{}}))
        jobs=self.data/'maintenance.json';jobs.write_text(json.dumps({'a':{'jobId':'job','batchId':batch_id,'startedAt':1,'state':'failed'}}))
        args={'projectId':'a','jobId':'job','completedBatchId':replacement}
        checkpoint={'lastScope':replacement,'commit':'head','updatedAt':2,'working':{'docs/camera.md':[1,3]},'resources':{'one/result':[1,3]}}
        with patch('maintenance.records.checkpoint_state',return_value=checkpoint):
            with self.assertRaisesRegex(ValueError,'未覆盖原整理范围'):self.hub.dispatch('finishMaintenance',args)
            path.write_text(json.dumps({'reviewedThreads':{'t':1}}))
            for field in ['working','resources']:
                with patch('maintenance.records.checkpoint_state',return_value={**checkpoint,field:{}}):
                    with self.assertRaisesRegex(ValueError,'未覆盖原整理范围'):self.hub.dispatch('finishMaintenance',args)
            self.hub.dispatch('finishMaintenance',args)
        job=json.loads(jobs.read_text())['a']
        self.assertEqual(job['state'],'completed');self.assertEqual(job['originalBatchId'],batch_id)
        self.assertEqual(job['batchId'],replacement)


if __name__=='__main__':unittest.main()
