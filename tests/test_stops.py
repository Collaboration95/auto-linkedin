from datetime import timedelta
import unittest
import test_submission
from stops import record_stop,retry_eligible,browser_stopped
import submission as s

class StopTests(unittest.TestCase):
    def setUp(self):
        self.f=test_submission.SubmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_repeated_timeouts_exhaust_finite_budget(self):
        f=self.f
        for n in range(3):result=record_stop(f.root,f.identity,'timeout',f.now+timedelta(minutes=n),3)
        self.assertTrue(result['exhausted']);self.assertFalse(retry_eligible(s.load(f.root,f.identity),f.now+timedelta(days=1)))
        self.assertEqual(result['retry_count'],3)
    def test_login_and_page_change_halt_browser_durably(self):
        for reason in ['login_required','page_changed']:
            result=record_stop(self.f.root,self.f.identity,reason,self.f.now)
            self.assertFalse(result['retryable']);self.assertEqual(browser_stopped(self.f.root)['reason'],reason)
    def test_uncertain_never_retries_timeout(self):
        f=self.f
        with s.browser_claim(f.root) as claim:s.begin_submit(f.root,f.identity,f.f.record(f.identity)['canonical_listing_url'],claim,f.now)
        result=record_stop(f.root,f.identity,'timeout',f.now)
        self.assertEqual(result['reason'],'uncertain_submit');self.assertFalse(result['retryable']);self.assertEqual(s.load(f.root,f.identity)['status'],'submission_uncertain')
