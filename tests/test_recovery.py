import unittest
from unittest.mock import patch
import test_workflow
import test_queue
import test_answer_import
import workspace as w
from answer_import import import_changes
from queue_state import block_on_answers
from answers import store
from submission import load
from export_dashboard import export_dashboard

class RecoveryTests(unittest.TestCase):
    def test_export_failure_preserves_mutation_and_retry_uses_one_snapshot(self):
        f=test_workflow.WorkflowTests();f.setUp();self.addCleanup(f.doCleanups)
        with patch('workspace.export_dashboard',side_effect=OSError('synthetic failure')):
            result=w.capture(f.root,f.job(),f.now)
        self.assertEqual(result['mutation'],'persisted');self.assertEqual(result['export']['status'],'failed')
        with patch('workspace.records',wraps=w.records) as scan:self.assertEqual(w.refresh_export(f.root,False)['status'],'exported');self.assertEqual(scan.call_count,1)
        self.assertEqual(len(w.records(f.root)),1);self.assertEqual(len(w.records(f.root)[0]['events']),1)
    def test_deferred_and_default_exports_match(self):
        f=test_workflow.WorkflowTests();f.setUp();self.addCleanup(f.doCleanups)
        w.atomic_json(f.root/'config.json',{'defer_export':True})
        self.assertEqual(w.capture(f.root,f.job(),f.now)['export']['status'],'deferred')
        w.refresh_export(f.root,False);first=w.read(f.root/'dashboard/data/applications.json');w.refresh_export(f.root,False);second=w.read(f.root/'dashboard/data/applications.json')
        first.pop('generated_at');second.pop('generated_at');self.assertEqual(first,second)
    def test_duplicate_answer_import_repairs_failed_queue_recompute(self):
        f=test_answer_import.ImportTests();f.setUp();self.addCleanup(f.doCleanups)
        identity=w.records(f.f.root)[0]['application_id'];block_on_answers(f.f.root,identity,f.ids,f.f.now)
        payload=f.payload()
        with patch('queue_state.recompute',side_effect=OSError('synthetic interruption')):
            with self.assertRaises(OSError):import_changes(f.f.root,payload,f.f.now)
        self.assertEqual(store(f.f.root)['revision'],1);self.assertEqual(load(f.f.root,identity)['status'],'awaiting_answer')
        result=import_changes(f.f.root,payload,f.f.now)
        self.assertEqual(result['mutation'],'already_imported');self.assertEqual(store(f.f.root)['revision'],1);self.assertEqual(load(f.f.root,identity)['status'],'discovered')
