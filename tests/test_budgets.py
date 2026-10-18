from datetime import timedelta
import unittest
import test_runner
import workspace as w
from runner import run,SyntheticAdapter
from submission import load
from budgets import policy,stop_reason

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.f=test_runner.RunnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_fake_clock_deadline_before_discovery_and_checkpoint_resume(self):
        f=self.f;start=f.f.now;adapter=SyntheticAdapter(f.jobs)
        clock=iter([start,start+timedelta(seconds=1),start+timedelta(seconds=3)])
        result=run(f.f.root,'deadline',adapter,2,10,lambda:next(clock),deadline=(start+timedelta(seconds=2)).isoformat())
        self.assertEqual(result['reason'],'deadline');self.assertEqual(adapter.calls,['discover'])
        self.assertEqual(len(w.records(f.f.root)),2)
        again=run(f.f.root,'deadline',SyntheticAdapter(f.jobs),2,10,lambda:start+timedelta(seconds=4));self.assertEqual(again['reason'],'deadline')
    def test_provider_unknown_stays_null_and_measured_limit_enforces(self):
        f=self.f;w.atomic_json(f.f.root/'config.json',{'budgets':{'provider_token_limit':10}})
        result=run(f.f.root,'unknown',SyntheticAdapter(f.jobs),1,5,lambda:f.f.now)
        self.assertEqual(result['reason'],'provider_usage_unavailable');self.assertIsNone(result['provider_usage'])
        class Measured(SyntheticAdapter):
            def measured_usage(self):return {'tokens':10,'cost_usd':None}
        self.assertEqual(run(f.f.root,'measured',Measured(f.jobs),1,5,lambda:f.f.now)['reason'],'provider_budget')
    def test_interrupt_during_submit_keeps_intent_reserved(self):
        f=self.f
        class Interrupt(SyntheticAdapter):
            def submit(self,context):raise KeyboardInterrupt()
        result=run(f.f.root,'interrupt',Interrupt(f.jobs),1,10,lambda:f.f.now)
        self.assertEqual(result['reason'],'interrupted');self.assertEqual(result['reserved'],1)
        self.assertEqual(sum(r['status']=='submission_uncertain' for r in w.records(f.f.root)),1)
    def test_durable_action_and_retry_limits(self):
        f=self.f;w.atomic_json(f.f.root/'config.json',{'budgets':{'max_actions':1,'max_retries':1}})
        result=run(f.f.root,'actions',SyntheticAdapter(f.jobs),2,10,lambda:f.f.now);self.assertEqual(result['reason'],'action_budget')
        batch={'steps':0,'retries':1,'budgets':policy({'budgets':{'max_retries':1}},f.f.now)}
        self.assertEqual(stop_reason(batch,f.f.now),'retry_budget')
