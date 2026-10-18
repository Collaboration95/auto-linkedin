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

    def test_legacy_submit_event_is_rejected(self):
        import argparse
        import workspace as w
        with self.assertRaisesRegex(ValueError,'requires_intent'):
            w.event(self.root,argparse.Namespace(id=self.identity,status='submitted'),self.now)
        self.assertEqual(s.load(self.root,self.identity)['status'],'ready')
    def test_submit_refresh_detects_restored_mtime_same_size_change(self):
        import os
        import workspace as w
        from context import run_context
        p=self.root/'config.json';p.write_text('{"rules":{"minimum":3}}')
        r=s.load(self.root,self.identity);r['prepared']['context_version']=run_context(self.root,True)['version'];s.save(self.root,r)
        stat=p.stat();p.write_text('{"rules":{"minimum":4}}');os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        self.assertEqual(r['prepared']['context_version'],run_context(self.root)['version'])
        with s.browser_claim(self.root) as claim:
            with self.assertRaisesRegex(ValueError,'context_changed'):s.begin_submit(self.root,self.identity,r['canonical_listing_url'],claim,self.now)
