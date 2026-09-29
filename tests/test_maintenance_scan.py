from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
from library import Library
import project_records as records


class MaintenanceScanTests(unittest.TestCase):
    def test_scan_returns_all_changed_projects_and_reports_missing_baselines(self):
        with tempfile.TemporaryDirectory() as temp:
            projects=[]
            for i in range(7):
                p=dict(id=str(i),name=f'Project {i}',path=str(Path(temp)/str(i)))
                if i!=6:
                    path=records.record_path(p);path.parent.mkdir(parents=True);path.write_text('{}')
                projects.append(p)
            hub=SimpleNamespace(data_dir=Path(temp),refresh_projects=lambda:None,all_threads=lambda:[],projects=lambda:projects,maintenance_threads=lambda pid,threads:[])
            calls=[]
            def delta(data,project,threads):
                calls.append(project['id'])
                return dict(commits='abc feature' if project['id']!='4' else '',pendingThreads=[],historyThreads=[],workingTree={},changedResources={},recordChanged=False)
            def state(data,project):return None if project['id']=='5' else {'commit':'abc','updatedAt':int(project['id'])}
            with patch('project_records.changes',side_effect=delta),patch('project_records.checkpoint_state',side_effect=state):
                result=Library.maintenance_scan(hub)
            self.assertEqual([p['project']['id'] for p in result['projects']],['0','1','2','3'])
            self.assertEqual(result['initialReviewNeeded'][0]['project']['id'],'5')
            self.assertNotIn('5',calls);self.assertNotIn('6',calls)
