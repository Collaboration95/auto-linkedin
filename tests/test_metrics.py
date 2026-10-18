import json
import unittest
import test_runner
import workspace as w
from metrics import record_stage,summary
from runner import run,SyntheticAdapter
from stops import clear_browser_stop,record_stop,acknowledge_resume

class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.f=test_runner.RunnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_attempted_vs_unique_measured_stages_and_missing_usage(self):
        f=self.f;counter=iter(range(100))
        run(f.f.root,'metrics',SyntheticAdapter(f.jobs,{job['listing_url']:'timeout' for job in f.jobs}),1,10,lambda:f.f.now,timer=lambda:next(counter))
        report=summary(f.f.root);self.assertEqual(report['attempted_submissions'],1);self.assertEqual(report['unique_confirmed'],0);self.assertIsNone(report['seconds_per_unique_confirmed']);self.assertIsNone(report['provider_usage']['tokens'])
        self.assertTrue(all(v>=0 for v in report['stage_seconds'].values()))
    def test_shareable_summary_drops_sensitive_content_and_identifiers(self):
        f=self.f;marker='PRIVATE_'+'CANARY_7f3b'
        record_stage(f.f.root,marker,'inspect',2.5,1,3,{'tokens':7,'cost_usd':None,'private':marker})
        p=f.f.root/'runtime/metrics.json';data=w.read(p);data['events'].append({'stage':marker,'duration_seconds':4,'private':marker});w.atomic_json(p,data)
        report=summary(f.f.root);self.assertNotIn(marker,json.dumps(report));self.assertEqual(report['stage_seconds'],{'inspect':2.5});self.assertEqual(report['provider_usage'],{'tokens':7,'cost_usd':None})
    def test_explicit_acknowledgement_resumes_login_without_clearing_guards(self):
        f=self.f
        class Login(SyntheticAdapter):
            def inspect(self,context):raise __import__('runner').AdapterError('login_required')
        self.assertEqual(run(f.f.root,'resume',Login([f.jobs[0]]),1,10,lambda:f.f.now)['reason'],'login_required')
        clear_browser_stop(f.f.root)
        self.assertEqual(run(f.f.root,'resume',SyntheticAdapter([f.jobs[0]]),1,10,lambda:f.f.now)['confirmed'],1)
        before=w.records(f.f.root)[0]
        acknowledge_resume(f.f.root,f.f.now);self.assertEqual(w.records(f.f.root)[0],before)

    def test_provider_cumulative_max_per_batch_then_sum_across_batches(self):
        root=self.f.f.root
        record_stage(root,'one','inspect',1,usage={'tokens':100,'cost_usd':1})
        record_stage(root,'one','prepare',1,usage={'tokens':80,'cost_usd':0.8})
        record_stage(root,'two','inspect',1,usage={'tokens':200,'cost_usd':2})
        self.assertEqual(summary(root)['provider_usage'],{'tokens':300,'cost_usd':3})
        record_stage(root,'unknown','inspect',1)
        self.assertIsNone(summary(root)['provider_usage']['tokens'])
    def test_acknowledgement_preserves_retry_count_and_reason_ledger(self):
        f=self.f.f;identity=w.capture(f.root,f.job(),f.now)['application_id']
        record_stop(f.root,identity,'timeout',f.now,4);record_stop(f.root,identity,'login_required',f.now,4)
        acknowledge_resume(f.root,f.now,identity)
        stop=record_stop(f.root,identity,'timeout',f.now,4)
        self.assertEqual(stop['retry_count'],2);self.assertEqual(stop['counts']['timeout'],2);self.assertEqual(stop['counts']['login_required'],1)
