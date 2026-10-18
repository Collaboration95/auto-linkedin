from datetime import timedelta
import unittest
import test_workflow
import workspace as w
from questions import register,inbox
from queue_state import block_on_answers,recompute,execution_guard,unlock_counts
from answer_import import import_changes
from submission import load,save

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.ids=[]
        for n in range(3):self.ids.append(w.capture(self.f.root,self.f.job(company='Synthetic '+str(n),platform_job_id=str(n),listing_url='https://example.org/jobs/'+str(n)),self.f.now)['application_id'])
    def test_shared_answer_requeues_all_and_extra_blocker_waits(self):
        q=register(self.f.root,self.ids[0],'form','shared',{'text':'Schedule?'})['question_id']
        extra=register(self.f.root,self.ids[1],'form','extra',{'text':'Other fact?'})['question_id']
        for identity in self.ids:block_on_answers(self.f.root,identity,[q]+([extra] if identity==self.ids[1] else []),self.f.now)
        r=load(self.f.root,self.ids[2]);r['status']='submitted';r['submissions']=[{'synthetic':True}];save(self.f.root,r)
        qs=inbox(self.f.root,self.f.now);self.assertEqual(unlock_counts(w.records(self.f.root),qs)[q],1)
        item=next(x for x in qs if x['id']==q)
        payload={'schema_version':1,'change_id':'review-shared','base_revision':0,'changes':[{'question_id':q,'question_version':item['question_version'],'value':'Day','scope':{},'review_due_at':(self.f.now+timedelta(days=1)).isoformat()}]}
        import_changes(self.f.root,payload,self.f.now)
        self.assertEqual(load(self.f.root,self.ids[0])['status'],'discovered')
        self.assertEqual(load(self.f.root,self.ids[1])['blocked_on_answer_ids'],[extra])
        self.assertEqual(load(self.f.root,self.ids[2])['status'],'submitted')
    def test_execution_rechecks_listing_and_resume(self):
        r=load(self.f.root,self.ids[0])
        with self.assertRaisesRegex(ValueError,'listing'):execution_guard(self.f.root,r,self.f.now)
        r['listing_current']=True;self.assertEqual(execution_guard(self.f.root,r,self.f.now)['id'],'backend-v1')
        with self.assertRaisesRegex(ValueError,'review_due'):execution_guard(self.f.root,r,self.f.now+timedelta(days=31))
