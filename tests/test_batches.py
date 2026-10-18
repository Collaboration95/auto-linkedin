from datetime import timedelta
import unittest
import test_workflow
from batches import batch_progress,confirmed_totals
import submission as s
from export_dashboard import export_dashboard
import workspace as w

class BatchTests(unittest.TestCase):
    def test_first_unique_confirmation_and_retryable_waiters(self):
        a={'canonical_listing_url':'https://example.org/one','status':'submitted','submissions':[{'submitted_at':'2026-10-18T23:50:00Z','batch_id':'old','category':'default'}]}
        duplicate={**a,'submissions':[{'submitted_at':'2026-10-19T00:10:00Z','batch_id':'new','category':'default'}]}
        waiter={'canonical_listing_url':'https://example.org/two','status':'awaiting_answer','submissions':[]}
        result=batch_progress([a,duplicate,waiter],'new',2)
        self.assertEqual(result['confirmed'],0);self.assertEqual(result['waiting_answers'],1)
        waiter['status']='discovered';self.assertEqual(batch_progress([a,waiter],'new',2)['retryable'],1)
    def test_delayed_confirmation_preserves_actual_time_and_offsets(self):
        f=test_workflow.WorkflowTests();f.setUp();self.addCleanup(f.doCleanups);identity=f.ready()
        with s.browser_claim(f.root) as claim:intent=s.begin_submit(f.root,identity,f.record(identity)['canonical_listing_url'],claim,f.now,'batch-one','eligible')
        occurred='2026-10-18T23:50:00+00:00';recorded=f.now+timedelta(days=1)
        with self.assertRaises(ValueError):s.confirm(f.root,identity,intent['attempt_id'],f.evidence(),recorded,'2026-10-18T23:50:00')
        s.confirm(f.root,identity,intent['attempt_id'],f.evidence(),recorded,occurred)
        export_dashboard(f.root);sent=w.read(f.root/'dashboard/data/applications.json')['applications'][0]['submissions'][0]
        self.assertEqual(sent['at'],occurred);self.assertEqual(sent['recorded_at'],recorded.isoformat())
        self.assertEqual(confirmed_totals(w.records(f.root),'batch-one')['categories'],{'eligible':1})
