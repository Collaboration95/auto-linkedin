import subprocess
import sys
from pathlib import Path
import unittest
import test_workflow
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import submission as s

class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.now=self.f.now;self.identity=self.f.ready()
    def test_stale_page_crash_and_duplicate(self):
        with s.browser_claim(self.root) as claim:
            with self.assertRaisesRegex(ValueError,'mismatch'):s.begin_submit(self.root,self.identity,'https://example.org/other',claim,self.now)
            intent=s.begin_submit(self.root,self.identity,self.f.record(self.identity)['canonical_listing_url'],claim,self.now)
            self.assertEqual(s.load(self.root,self.identity)['status'],'submission_uncertain')
            with self.assertRaisesRegex(ValueError,'reconciliation'):s.begin_submit(self.root,self.identity,intent['observed_job'],claim,self.now)
        s.confirm(self.root,self.identity,intent['attempt_id'],self.f.evidence(),self.now)
        self.assertTrue(s.confirm(self.root,self.identity,intent['attempt_id'],self.f.evidence(),self.now)['duplicate'])
        with s.browser_claim(self.root) as claim:
            with self.assertRaisesRegex(ValueError,'already_confirmed'):s.begin_submit(self.root,self.identity,intent['observed_job'],claim,self.now)
    def test_competing_claim_has_one_winner(self):
        code="from pathlib import Path;import submission;\ntry:\n with submission.browser_claim(Path(__import__('sys').argv[1])):pass\nexcept ValueError:raise SystemExit(7)"
        import os
        with s.browser_claim(self.root):
            result=subprocess.run([sys.executable,'-c',code,str(self.root)],env={**os.environ,'PYTHONPATH':str(Path('scripts').resolve())},capture_output=True)
            self.assertEqual(result.returncode,7)
        with s.browser_claim(self.root):pass
    def test_negative_reconciliation_needs_evidence(self):
        with s.browser_claim(self.root) as claim:s.begin_submit(self.root,self.identity,self.f.record(self.identity)['canonical_listing_url'],claim,self.now)
        with self.assertRaises(ValueError):s.reconcile_not_submitted(self.root,self.identity,self.root/'absent',self.now)
        s.reconcile_not_submitted(self.root,self.identity,self.f.evidence(),self.now)
        self.assertEqual(s.load(self.root,self.identity)['status'],'failed')
