import copy
import io
import sys
from contextlib import redirect_stderr
from datetime import timedelta
from pathlib import Path
import unittest
from unittest.mock import patch
import test_runner
import workspace as w
from runner import run,SyntheticAdapter,batch_path
from answers import store
from submission import load
import submission

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


class RequiredHistoryTests(unittest.TestCase):
    def setUp(self):
        self.scenario=SubmitBoundaryTests();self.scenario.setUp();self.addCleanup(self.scenario.doCleanups)
        self.root=self.scenario.f.root;self.now=self.scenario.f.now
        self.history=[{'company':'Fictional Systems','role':'Engineer'}]
        self.scenario.job['form']=[{'key':'history','text':'Current work history','field_type':'history'}]
        self.scenario.job['history']=self.history
        self.save_history(review_due_at=(self.now+timedelta(days=1)).isoformat())

    def save_history(self,**changes):
        facts={'source':{'id':'synthetic-review','version':1,'kind':'user'},'entries':self.history,
               'review_due_at':(self.now+timedelta(days=1)).isoformat(),**changes}
        w.atomic_json(self.root/'profile/history.json',facts)
        return facts

    def test_history_expiry_during_observation_blocks_before_intent(self):
        self.save_history(review_due_at=(self.now+timedelta(seconds=2)).isoformat())
        now=[self.now]
        class Delayed(SyntheticAdapter):
            def observe(driver,context):
                now[0]+=timedelta(seconds=3)
                return super().observe(context)
        adapter=self.scenario.prepared(Delayed([self.scenario.job]))
        result=run(self.root,'boundary',adapter,1,1,lambda:now[0])
        self.scenario.assert_no_intent()
        self.assertEqual(result['confirmed'],0)
        self.assertEqual(w.records(self.root)[0]['stop']['reason'],'outdated_fact')

    def assert_direct_expiry_blocked(self,field):
        self.save_history(**{field:(self.now+timedelta(seconds=2)).isoformat()})
        self.scenario.prepared();record=w.records(self.root)[0]
        with submission.browser_claim(self.root) as claim:
            with self.assertRaisesRegex(ValueError,'outdated_fact'):
                submission.begin_submit(self.root,record['application_id'],record['canonical_listing_url'],claim,self.now+timedelta(seconds=3))
        self.scenario.assert_no_intent()
        self.assertEqual(w.records(self.root)[0],record)

    def test_direct_begin_submit_rechecks_history_review_deadline(self):
        self.assert_direct_expiry_blocked('review_due_at')

    def test_direct_begin_submit_rechecks_history_valid_until(self):
        self.assert_direct_expiry_blocked('valid_until')

    def test_cli_preflight_rejects_both_history_expiry_fields(self):
        self.scenario.prepared();identity=w.records(self.root)[0]['application_id']
        for field in ('review_due_at','valid_until'):
            with self.subTest(field=field):
                self.save_history(**{field:(self.now+timedelta(seconds=2)).isoformat()})
                error=io.StringIO()
                argv=['workspace.py','--workspace',str(self.root),'preflight','--id',identity]
                with patch.object(w,'ROOT',w.ROOT),patch.object(sys,'argv',argv),patch('workspace.local_now',return_value=self.now+timedelta(seconds=3)),redirect_stderr(error):
                    with self.assertRaises(SystemExit) as stopped:w.main()
                self.assertEqual(stopped.exception.code,1)
                self.assertIn('outdated_fact',error.getvalue());self.assertNotIn('Traceback',error.getvalue())
        self.scenario.assert_no_intent()

    def test_preparation_rejects_expired_valid_until(self):
        self.save_history(valid_until=(self.now-timedelta(seconds=1)).isoformat())
        adapter=SyntheticAdapter([self.scenario.job])
        run(self.root,'boundary',adapter,1,3,lambda:self.now)
        record=w.records(self.root)[0]
        self.assertEqual(record['stop']['reason'],'outdated_fact')
        self.assertNotIn('prepare',adapter.calls);self.assertNotIn('prepared',record)
        self.scenario.assert_no_intent()

    def test_history_scope_matches_application_and_explicit_form_scope(self):
        self.scenario.job['form'][0]['scope']={'country':'AA'}
        self.save_history(scope={'employer':self.scenario.job['company'],'country':'AA'})
        self.scenario.prepared();record=w.records(self.root)[0]
        self.assertTrue(w.preflight(self.root,record,self.now)['ready'])

    def test_incompatible_or_unknown_history_scopes_are_rejected(self):
        from forms import resolve_history,FormError
        record={'company':self.scenario.job['company'],'workflow':{'form':self.scenario.job['form']}}
        variants=[{'scope':{'employer':'Other Fiction Inc.'}},
                  {'source':{'id':'synthetic-review','version':1,'scope':{'country':'BB'}}},
                  {'entries':[{'company':'Fictional Systems','scope':{'employer':'Other Fiction Inc.'}}]},
                  {'scope':{'country':None}}]
        for changes in variants:
            with self.subTest(changes=changes):
                self.save_history(**changes)
                with self.assertRaisesRegex(FormError,'outdated_fact'):resolve_history(self.root,self.now,record)
        self.save_history(scope={'employer':'Other Fiction Inc.'})
        adapter=SyntheticAdapter([self.scenario.job]);run(self.root,'boundary',adapter,1,3,lambda:self.now)
        self.assertEqual(w.records(self.root)[0]['stop']['reason'],'outdated_fact')
        self.assertNotIn('prepare',adapter.calls);self.scenario.assert_no_intent()

    def test_malformed_explicit_form_scopes_fail_closed(self):
        from forms import resolve_history,FormError
        record={'company':self.scenario.job['company'],'application_id':'synthetic-job',
                'workflow':{'form':self.scenario.job['form']}}
        scopes=[None,{'country':None},{'country':''},{'country':'   '},{'country':False},
                {'country':0},{'country':[]},{'country':{}},{'':'AA'},
                {'employer':'Other Fiction Inc.'},{'application_id':'another-synthetic-job'}]
        for scope in scopes:
            with self.subTest(scope=scope):
                self.scenario.job['form'][0]['scope']=scope
                with self.assertRaisesRegex(FormError,'outdated_fact'):resolve_history(self.root,self.now,record)
        record.pop('company')
        self.scenario.job['form'][0]['scope']={'employer':'Other Fiction Inc.'}
        with self.assertRaisesRegex(FormError,'outdated_fact'):resolve_history(self.root,self.now,record)

    def test_changed_missing_invalid_or_tampered_history_prevents_intent(self):
        original=self.save_history();self.scenario.prepared();record=w.records(self.root)[0]
        history_path=self.root/record['prepared']['history_path'];snapshot=history_path.read_bytes()
        variants=[None,{**original,'entries':[{'company':'Fictional Revised','role':'Engineer'}]},
                  {**original,'source':{'id':'synthetic-review','version':2,'kind':'user'}},
                  {**original,'source':{'id':'synthetic-policy','version':1,'kind':'authorized_default'}},
                  {**original,'review_due_at':None},{**original,'entries':None}]
        for facts in variants:
            with self.subTest(facts=facts):
                if facts is None:(self.root/'profile/history.json').unlink()
                else:w.atomic_json(self.root/'profile/history.json',facts)
                with submission.browser_claim(self.root) as claim:
                    with self.assertRaises(ValueError):
                        submission.begin_submit(self.root,record['application_id'],record['canonical_listing_url'],claim,self.now)
                self.scenario.assert_no_intent()
                self.assertEqual(history_path.read_bytes(),snapshot)
                w.atomic_json(self.root/'profile/history.json',original)
        history_path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'history_changed'):w.preflight(self.root,record,self.now)

    def test_unrelated_application_ignores_changed_or_invalid_history(self):
        self.scenario.job['form']=[];self.scenario.job.pop('history')
        adapter=self.scenario.prepared();record=w.records(self.root)[0]
        self.assertNotIn('history_path',record['prepared'])
        self.save_history(source={'id':'synthetic-review','version':2},entries=[{'company':'Fictional Revised'}])
        self.assertTrue(w.preflight(self.root,record,self.now)['ready'])
        (self.root/'profile/history.json').write_text('synthetic malformed history')
        self.assertTrue(w.preflight(self.root,record,self.now)['ready'])
        self.assertEqual(run(self.root,'boundary',adapter,1,1,lambda:self.now)['confirmed'],1)

    def test_confirmed_history_snapshot_remains_exact_after_facts_expire_or_change(self):
        original=self.save_history(review_due_at=(self.now+timedelta(seconds=2)).isoformat())
        self.scenario.prepared();record=w.records(self.root)[0]
        relative=record['prepared']['history_path'];self.assertFalse(Path(relative).is_absolute())
        snapshot=(self.root/relative).read_bytes()
        with submission.browser_claim(self.root) as claim:
            intent=submission.begin_submit(self.root,record['application_id'],record['canonical_listing_url'],claim,self.now)
        self.save_history(source={'id':'synthetic-review','version':2},entries=[])
        submission.confirm(self.root,record['application_id'],intent['attempt_id'],self.scenario.f.evidence(),self.now+timedelta(seconds=3))
        confirmed=w.records(self.root)[0]
        self.assertEqual(confirmed['status'],'submitted')
        self.assertEqual(confirmed['submissions'][0]['history_path'],relative)
        self.assertEqual((self.root/relative).read_bytes(),snapshot)
        self.assertEqual(w.read(self.root/relative),original)
        self.assertEqual(w.digest(self.root/relative),confirmed['submissions'][0]['history_sha256'])
