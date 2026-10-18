from datetime import timedelta
import unittest
import test_workflow
import workspace as w
from runner import run,SyntheticAdapter,UnsupportedAdapter,next_action
from questions import inbox
from answer_import import import_changes
from batches import submit_capacity
from stops import browser_stopped

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.jobs=[self.f.job(company='Fiction '+str(i),platform_job_id=str(i),listing_url='https://example.org/jobs/'+str(i),requirements_verified=True,requirements={},form=[]) for i in range(2)]
    def test_restart_from_verified_checkpoint_and_never_replay_confirmed_submit(self):
        a=SyntheticAdapter(self.jobs);run(self.f.root,'restart',a,2,2,lambda:self.f.now)
        self.assertEqual(sum(r['status']=='preparing' for r in w.records(self.f.root)),1)
        b=SyntheticAdapter(self.jobs);result=run(self.f.root,'restart',b,2,10,lambda:self.f.now)
        self.assertEqual(result['confirmed'],2);self.assertEqual(b.calls.count('submit'),2)
        c=SyntheticAdapter(self.jobs);self.assertEqual(run(self.f.root,'restart',c,2,10,lambda:self.f.now)['reason'],'quota_complete');self.assertEqual(c.calls,[])
    def test_shared_unknown_then_answer_once_and_resume(self):
        self.jobs[0]['form']=[{'key':'schedule','text':'Schedule?','field_type':'text'}]
        a=SyntheticAdapter(self.jobs);result=run(self.f.root,'answers',a,2,10,lambda:self.f.now)
        self.assertEqual(result['confirmed'],1);q=inbox(self.f.root,self.f.now)[0]
        import_changes(self.f.root,{'schema_version':1,'change_id':'one-answer','base_revision':0,'changes':[{'question_id':q['id'],'question_version':q['question_version'],'value':'Day','scope':{},'review_due_at':(self.f.now+timedelta(days=1)).isoformat()}]},self.f.now)
        result=run(self.f.root,'answers',SyntheticAdapter(self.jobs),2,10,lambda:self.f.now);self.assertEqual(result['confirmed'],2)
    def test_uncertain_submit_reserves_quota_but_independent_prepare_continues(self):
        adapter=SyntheticAdapter(self.jobs,{job['listing_url']:'timeout' for job in self.jobs})
        result=run(self.f.root,'reserved',adapter,1,12,lambda:self.f.now)
        self.assertEqual(result['confirmed'],0);self.assertEqual(result['reserved'],1);self.assertEqual(adapter.calls.count('submit'),1)
        self.assertEqual(sum(r['status']=='ready' for r in w.records(self.f.root)),1)
        self.assertEqual(result['reason'],'pending_confirmation')
    def test_login_during_submit_is_global_stop_and_unsupported_live_is_honest(self):
        result=run(self.f.root,'login',SyntheticAdapter(self.jobs,{self.jobs[0]['listing_url']:'login_required'}),2,10,lambda:self.f.now)
        self.assertEqual(result['reason'],'login_required');self.assertEqual(browser_stopped(self.f.root)['reason'],'login_required')
