import json
import unittest
from unittest.mock import patch
import test_full_workflow


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.base=test_full_workflow.FullWorkflowTests();self.base.setUp();self.base.seed();self.hub=self.base.hub
    def tearDown(self):self.base.tearDown()

    def test_success_failure_and_retry_are_recorded_without_content(self):
        scope=self.hub.dispatch('prepareDailyRecord',{'projectId':'a','threadId':'t','cardId':'camera'})
        args={'projectId':'a','scopeId':scope['scopeId'],'threadCoverage':'unchanged','updates':[{'cardId':'camera','changes':{'notes':['private-content-not-in-log']}}]}
        first=self.hub.dispatch('saveDailyRecord',args)
        retry=self.hub.dispatch('saveDailyRecord',args)
        self.assertTrue(retry['replayed']);self.assertGreaterEqual(first['measurement']['backendMs'],0)
        with self.assertRaisesRegex(ValueError,'已提交'):
            self.hub.dispatch('saveDailyRecord',{**args,'threadCoverage':'complete'})
        report=self.hub.dispatch('dailyTiming',{'projectId':'a','scopeId':scope['scopeId']})
        self.assertEqual(len(report['events']),4)
        self.assertEqual(report['events'][0]['success'],0)
        self.assertTrue(report['events'][1]['replayed'])
        self.assertEqual(report['events'][2]['noteLines'],1)
        self.assertNotIn('private-content-not-in-log',json.dumps(report))
        self.assertIn('不包括 Agent',report['timingBasis'])

    def test_observation_failure_does_not_turn_a_saved_result_into_failure(self):
        with patch('daily_observation._write',side_effect=OSError('disk failure')),self.assertLogs(level='ERROR'):
            scope=self.hub.dispatch('prepareDailyRecord',{'projectId':'a','threadId':'t','cardId':'camera'})
        self.assertIn('observationWarning',scope)
        self.assertIn('scopeId',scope)
