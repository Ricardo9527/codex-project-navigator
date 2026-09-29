import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import Hub

class HubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root/'project';self.project.mkdir()
        self.child = self.project/'nested';self.child.mkdir()
        self.data=self.root/'data';self.data.mkdir()
        (self.data/'projects.json').write_text(json.dumps([{'id':'a','name':'A','path':str(self.project)},{'id':'b','name':'B','path':str(self.child)}]))
        self.source=self.root/'codex.sqlite'
        with sqlite3.connect(self.source) as db:
            db.executescript('CREATE TABLE project_roots(project_id TEXT,path TEXT); CREATE TABLE threads(id TEXT,name TEXT,title TEXT,cwd TEXT,updated_at INTEGER,archived INTEGER,git_branch TEXT,preview TEXT,project_id TEXT,agent_role TEXT,agent_path TEXT,thread_source TEXT);')
            db.executemany('INSERT INTO project_roots VALUES (?,?)',[('native-a',str(self.project)),('native-b',str(self.child))])
            for i in range(65):db.execute('INSERT INTO threads(id,name,title,cwd,updated_at,archived,git_branch,preview,project_id,agent_role,agent_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)',(str(i),'镜头 '+str(i),'raw',str(self.project),i,0,'main','控制摘要','native-a',None,None))
            db.execute('INSERT INTO threads(id,name,title,cwd,updated_at,archived,git_branch,preview,project_id,agent_role,agent_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)',('child','子项目','raw',str(self.child),100,0,'main',None,'native-b',None,None))
            db.execute('INSERT INTO threads(id,name,title,cwd,updated_at,archived,git_branch,preview,project_id,agent_role,agent_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)',('wt','工作树','raw','/tmp/worktree-demo',100,0,'feature',None,'native-a',None,None))
        self.digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.hub=Hub(self.source,self.data)
        self.file=self.project/'result.md';self.file.write_text('# 成果')
    def tearDown(self):
        self.assertEqual(self.digest,hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.tmp.cleanup()
    def artifact(self,**overrides):
        return dict(projectId='a',title='成果',path=str(self.file),kind='document',status='candidate',categoryIds=[],**overrides)
    def test_system_reviews_are_excluded(self):
        with sqlite3.connect(self.source) as db:
            db.execute("INSERT INTO threads(id,title,cwd,updated_at,archived,thread_source) VALUES ('review','Review',?,101,0,'guardian_review')",(str(self.project),))
        self.digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertNotIn('review',[t['id'] for t in self.hub.all_threads()])

    def test_search_pagination_and_worktree(self):
        self.assertEqual(self.hub.owner(self.child),'b')
        self.assertEqual(self.hub.overview({})['projects'][0]['threads'],66)
        result=self.hub.detail({'projectId':'a','query':'控制'})
        self.assertEqual(result['totalThreads'],65);self.assertEqual(len(result['threads']),60)
        self.assertEqual(len(self.hub.detail({'projectId':'a','query':'控制','offset':60})['threads']),5)
    def test_multiple_tags_persist_and_acceptance_explicit(self):
        ids=[self.hub.add_category({'projectId':'a','name':n})['id'] for n in ['镜头','控制']]
        self.hub.tag_thread({'threadId':'1','categoryIds':ids})
        a=self.artifact();a['categoryIds']=ids;a['sourceThreadId']='1'
        identity=self.hub.save_artifact(a)['id']
        saved=Hub(self.source,self.data).detail({'projectId':'a','categoryId':ids[0]})
        self.assertEqual(saved['artifacts'][0]['status'],'candidate');self.assertEqual(saved['threads'][0]['id'],'1')
        a.update(id=identity,status='accepted');self.hub.save_artifact(a)
        self.assertEqual(self.hub.detail({'projectId':'a'})['artifacts'][0]['status'],'accepted')
        self.assertEqual(self.hub.preview({'id':identity})['text'],'# 成果')
    def test_cross_project_and_symlink_rejected(self):
        category=self.hub.add_category({'projectId':'b','name':'独立'})['id']
        with self.assertRaises(ValueError):self.hub.tag_thread({'threadId':'1','categoryIds':[category]})
        a=self.artifact();a['sourceThreadId']='child'
        with self.assertRaises(ValueError):self.hub.save_artifact(a)
        outside=self.root/'outside.md';outside.write_text('outside');link=self.project/'link.md';link.symlink_to(outside)
        a=self.artifact();a['path']=str(link)
        with self.assertRaises(ValueError):self.hub.save_artifact(a)
    def test_missing_file_is_visible(self):
        identity=self.hub.save_artifact(self.artifact())['id'];self.file.unlink()
        self.assertFalse(self.hub.detail({'projectId':'a'})['artifacts'][0]['exists'])
        with self.assertRaisesRegex(ValueError,'移动或删除'):self.hub.preview({'id':identity})

if __name__=='__main__':unittest.main()
