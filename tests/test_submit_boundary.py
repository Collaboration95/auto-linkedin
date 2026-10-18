import copy
from datetime import timedelta
import unittest
import test_runner
import workspace as w
from runner import run,SyntheticAdapter,batch_path
from answers import store
from submission import load

class SubmitBoundaryTests(unittest.TestCase):
    def setUp(self):
        f=test_runner.RunnerTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f.f
        self.job=f.jobs[0];self.job['requirements']={'country':{'value':'AA','strength':'hard'}}
        w.atomic_json(self.f.root/'config.json',{'rules':{'allowed_countries':['AA']}})
    def prepared(self,adapter=None):
        adapter=adapter or SyntheticAdapter([self.job]);run(self.f.root,'boundary',adapter,1,3,lambda:self.f.now)
        self.assertEqual(w.records(self.f.root)[0]['status'],'ready');return adapter
    def assert_no_intent(self):
        r=w.records(self.f.root)[0];self.assertFalse(r.get('intent'));self.assertFalse(r['submissions'])
    def test_listing_changes_after_ready_block_before_intent(self):
        adapter=self.prepared();adapter.catalog[0]['requirements']['country']['value']='BB'
        result=run(self.f.root,'boundary',adapter,1,1,lambda:self.f.now);self.assert_no_intent();self.assertEqual(w.records(self.f.root)[0]['stop']['reason'],'eligibility_review')
    def test_layout_options_selected_value_or_resume_change_blocks(self):
        self.job['form']=[{'key':'upload','text':'Resume','field_type':'upload'}]
        adapter=self.prepared();adapter.catalog[0]['selected_resume_sha256']='wrong'
        run(self.f.root,'boundary',adapter,1,1,lambda:self.f.now);self.assert_no_intent();self.assertEqual(w.records(self.f.root)[0]['stop']['reason'],'resume_stale')
    def test_layout_options_change_after_ready_blocks(self):
        self.job['form']=[{'key':'schedule','text':'Schedule','field_type':'select','options':['Day','Night']}]
        a=store(self.f.root)['answers'][0];a.update(id='schedule',value='Day',field_type='select',options=['Day','Night'],aliases=['Schedule'])
        w.atomic_json(self.f.root/'profile/answers.json',{'answers':[a]})
        adapter=self.prepared();adapter.catalog[0]['form'][0]['options'].append('Other')
        run(self.f.root,'boundary',adapter,1,1,lambda:self.f.now);self.assert_no_intent();self.assertEqual(w.records(self.f.root)[0]['stop']['reason'],'page_changed')
    def test_expiry_during_observe_rechecks_injected_clock(self):
        self.job['form']=[{'key':'known','text':'Sponsorship required?','field_type':'text'}]
        a=store(self.f.root)['answers'][0];a['aliases']=['Sponsorship required?'];a['review_due_at']=(self.f.now+timedelta(seconds=2)).isoformat();w.atomic_json(self.f.root/'profile/answers.json',{'answers':[a]})
        now=[self.f.now]
        class Delayed(SyntheticAdapter):
            def observe(driver,context):now[0]+=timedelta(seconds=3);return super().observe(context)
        adapter=self.prepared(Delayed([self.job]));run(self.f.root,'boundary',adapter,1,1,lambda:now[0]);self.assert_no_intent();self.assertEqual(w.records(self.f.root)[0]['stop']['reason'],'outdated_fact')
    def test_deadline_crossing_observe_stops_before_intent(self):
        now=[self.f.now]
        class Delayed(SyntheticAdapter):
            def observe(driver,context):now[0]+=timedelta(seconds=3);return super().observe(context)
        adapter=self.prepared(Delayed([self.job]));batch=w.read(batch_path(self.f.root,'boundary'));batch['budgets']['deadline']=(self.f.now+timedelta(seconds=2)).isoformat();w.atomic_json(batch_path(self.f.root,'boundary'),batch)
        result=run(self.f.root,'boundary',adapter,1,1,lambda:now[0]);self.assert_no_intent();self.assertEqual(result['reason'],'deadline')
    def test_malformed_discovery_item_does_not_starve_later_valid_job(self):
        other=copy.deepcopy(self.job);other.update(company='Second Fiction',platform_job_id='other',listing_url='https://example.org/jobs/other')
        result=run(self.f.root,'mixed',SyntheticAdapter([self.job,{'invalid':'synthetic'},other]),2,20,lambda:self.f.now)
        self.assertEqual(result['confirmed'],2);batch=w.read(batch_path(self.f.root,'mixed'));self.assertEqual(batch['discovery_failures'],[{'item_index':1,'reason':'invalid_discovery_item'}])
