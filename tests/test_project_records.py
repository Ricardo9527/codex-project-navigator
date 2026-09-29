import copy
import json
from pathlib import Path
import tempfile
import unittest
import project_records as records


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.project={'id':'a','name':'Project','path':str(self.root/'project')};Path(self.project['path']).mkdir()
        self.data=self.root/'data';self.data.mkdir()
        records.git(self.project,'init')
        records.git(self.project,'config','user.name','Test')
        records.git(self.project,'config','user.email','test@example.invalid')
        self.record={'version':1,'projectId':'a','about':'Purpose','categories':[{'id':'tools','title':'Tools'}],
                     'cards':[{'id':'one','title':'One','summary':'Purpose','kind':'工作记录','icon':'file','caption':'','sections':[],'records':[],'requirements':[],'categoryIds':['tools'],'resources':[],'sources':[],'related':[]}],'reviewedThreads':{}}
    def tearDown(self):self.temp.cleanup()

    def test_conflict_and_manual_changes_are_preserved(self):
        saved=records.save(self.project,copy.deepcopy(self.record),None)
        edited=copy.deepcopy(self.record);edited['cards'][0].update(summary='User purpose',manualFields=['summary'])
        new=records.save(self.project,edited,saved['revision'],'user')
        with self.assertRaisesRegex(ValueError,'其他对话'):
            records.save(self.project,copy.deepcopy(self.record),saved['revision'])
        with self.assertRaisesRegex(ValueError,'用户修改'):
            records.save(self.project,copy.deepcopy(self.record),new['revision'])
        self.assertEqual(json.loads(records.record_path(self.project).read_text())['cards'][0]['summary'],'User purpose')

    def test_git_checkpoint_preserves_unrelated_staging_and_is_incremental(self):
        saved=records.save(self.project,copy.deepcopy(self.record),None)
        unrelated=Path(self.project['path'])/'unfinished.txt';unrelated.write_text('ongoing')
        records.git(self.project,'add','unfinished.txt')
        state=records.checkpoint(self.data,self.project,saved['revision'],'docs: record',None,initial_review_complete=True)
        saved={'revision':state['recordRevision']}
        self.assertIn('unfinished.txt',records.git(self.project,'diff','--cached','--name-only').stdout)
        self.assertNotIn('unfinished.txt',records.git(self.project,'ls-tree','--name-only','HEAD').stdout)
        delta=records.changes(self.data,self.project,[])
        self.assertEqual(delta['baseline'],state['commit']);self.assertEqual(delta['commits'],'')
        self.assertEqual(delta['workingTree'],{})
        unrelated.write_text('changed after checkpoint')
        self.assertIn('unfinished.txt',records.changes(self.data,self.project,[])['workingTree'])
        records.git(self.project,'commit','-m','new change')
        delta=records.changes(self.data,self.project,[])
        self.assertIn('new change',delta['commits'])
        with self.assertRaisesRegex(ValueError,'新提交'):
            records.checkpoint(self.data,self.project,saved['revision'],'docs',state['commit'])

    def test_directory_cycles_rejected_and_context_derived_from_record(self):
        bad=copy.deepcopy(self.record);bad['categories'][0]['parentId']='tools'
        with self.assertRaisesRegex(ValueError,'循环'):
            records.save(self.project,bad,None)
        records.save(self.project,copy.deepcopy(self.record),None)
        context=records.export_context(self.project,'one')
        text=Path(context['path']).read_text()
        self.assertIn(str(records.record_path(self.project)),text)
        self.assertIn('Purpose',text)

    def test_cards_belong_to_leaf_categories(self):
        r=copy.deepcopy(self.record)
        r['categories'].append({'id':'sub','title':'子分类','parentId':'tools'})
        with self.assertRaisesRegex(ValueError,'末级分类'):
            records.save(self.project,r,None)
        r['cards'][0]['categoryIds']=['sub']
        records.save(self.project,r,None)

    def test_full_scope_includes_old_chats_and_exceeds_previous_caps(self):
        saved=records.save(self.project,copy.deepcopy(self.record),None)
        initial=records.checkpoint(self.data,self.project,saved['revision'],'baseline',None,initial_review_complete=True)
        saved={'revision':initial['recordRevision']}
        work=Path(self.project['path'])
        for i in range(12):
            (work/'feature.txt').write_text(str(i))
            records.git(self.project,'add','feature.txt');records.git(self.project,'commit','-m',f'feature {i}')
        for i in range(22):(work/f'pending-{i:02}.txt').write_text('new work')
        record=json.loads(records.record_path(self.project).read_text())
        record['cards'][0]['resources']=[dict(id=f'r{i:02}',label='Feature',path='feature.txt',format='text',role='result') for i in range(21)]
        saved=records.save(self.project,record,saved['revision'])
        def thread(i,updated):return dict(id=f't{i}',title=f'Thread {i}',updated_at=updated,archived=0)
        threads=[thread(i,initial['updatedAt']+i+1) for i in range(6)]+[thread('old',initial['updatedAt']-1)]
        batch=records.prepare_batch(self.data,self.project,threads)
        self.assertEqual(len(batch['commits']),12)
        self.assertEqual(len(batch['pendingThreads']),7)
        self.assertEqual(len(batch['workingTree']),22)
        self.assertEqual(len(batch['changedResources']),21)
        self.assertEqual(batch['pendingThreads'][0]['id'],'told')
        self.assertEqual(batch['pendingThreads'][0]['reviewedUntil'],0)
        with self.assertRaisesRegex(ValueError,'尚未完成'):
            records.checkpoint(self.data,self.project,saved['revision'],'partial',batch['head'],batch_id=batch['batchId'])
        with self.assertRaisesRegex(ValueError,'未登记'):
            records.checkpoint(self.data,self.project,saved['revision'],'missing chats',batch['head'],batch_id=batch['batchId'],complete=True)
        for t in batch['pendingThreads']:record['reviewedThreads'][t['id']]=t['updated_at']
        saved=records.save(self.project,record,saved['revision'])
        (work/'pending-00.txt').write_text('changed after observation')
        state=records.checkpoint(self.data,self.project,saved['revision'],'batch complete',batch['head'],batch_id=batch['batchId'],complete=True)
        self.assertEqual(state['commit'],batch['head'])
        threads.append(thread(7,initial['updatedAt']+100))
        delta=records.changes(self.data,self.project,threads)
        self.assertEqual(delta['commits'],'')
        self.assertEqual([t['id'] for t in delta['pendingThreads']],['t7'])
        self.assertEqual(len(delta['workingTree']),1)
        self.assertEqual(delta['changedResources'],{})

    def test_first_review_is_explicit_and_unchanged_project_needs_no_batch(self):
        saved=records.save(self.project,copy.deepcopy(self.record),None)
        first=records.prepare_batch(self.data,self.project,[])
        self.assertTrue(first['initialReview'])
        with self.assertRaisesRegex(ValueError,'首次基线'):
            records.checkpoint(self.data,self.project,saved['revision'],'implicit baseline',None)
        records.checkpoint(self.data,self.project,saved['revision'],'baseline',None,initial_review_complete=True)
        self.assertTrue(records.prepare_batch(self.data,self.project,[])['noChanges'])
        self.assertTrue(records.record_path(self.project).exists())

    def test_removed_resource_is_consumed_once(self):
        (Path(self.project['path'])/'file.txt').write_text('test')
        self.record['cards'][0]['resources']=[dict(id='r',label='Resource',path='file.txt',format='text',role='result')]
        saved=records.save(self.project,copy.deepcopy(self.record),None)
        state=records.checkpoint(self.data,self.project,saved['revision'],'baseline',None,initial_review_complete=True)
        saved={'revision':state['recordRevision']}
        self.record['cards'][0]['resources']=[]
        saved=records.save(self.project,self.record,saved['revision'])
        batch=records.prepare_batch(self.data,self.project,[])
        records.checkpoint(self.data,self.project,saved['revision'],'remove resource',batch['head'],batch_id=batch['batchId'],complete=True)
        self.assertTrue(records.prepare_batch(self.data,self.project,[])['noChanges'])
