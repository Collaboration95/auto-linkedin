import unittest
import test_submit_boundary
import workspace as w
from runner import run,SyntheticAdapter
from stops import acknowledge_resume
from questions import store as question_store,inbox
from answers import store

class ReviewedFormTests(unittest.TestCase):
    def setUp(self):
        self.f=test_submit_boundary.SubmitBoundaryTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.job['form']=[{'key':'schedule','text':'Schedule','field_type':'select','options':['Day','Night']}]
        a=store(self.f.f.root)['answers'][0];a.update(id='schedule',value='Day',field_type='select',options=['Day','Night'],aliases=['Schedule'])
        w.atomic_json(self.f.f.root/'profile/answers.json',{'answers':[a]})
    def test_acknowledged_option_change_versions_occurrence_and_preserves_snapshot(self):
        f=self.f;adapter=f.prepared();root=f.f.root;before=w.records(root)[0]['prepared'];original=(root/before['answers_path']).read_bytes()
        adapter.catalog[0]['form'][0]['options'].append('Other');run(root,'boundary',adapter,1,1,lambda:f.f.now)
        acknowledge_resume(root,f.f.now);run(root,'boundary',adapter,1,2,lambda:f.f.now)
        self.assertEqual(w.records(root)[0]['status'],'awaiting_answer');occurrences=question_store(root)['occurrences']
        self.assertEqual(len(occurrences),2);self.assertEqual([o['options'] for o in occurrences],[['Day','Night'],['Day','Night','Other']]);self.assertFalse(occurrences[0]['active'])
        self.assertIn('archived',[q['status'] for q in inbox(root,f.f.now)]);self.assertEqual(original,(root/before['answers_path']).read_bytes())
    def test_same_clock_reprepare_uses_unique_snapshot_and_keeps_prior_bytes(self):
        f=self.f;adapter=f.prepared();root=f.f.root;before=w.records(root)[0]['prepared'];original=(root/before['answers_path']).read_bytes()
        adapter.catalog[0]['page_values']={'schedule':'Night'};run(root,'boundary',adapter,1,1,lambda:f.f.now)
        acknowledge_resume(root,f.f.now);adapter.catalog[0].pop('page_values');run(root,'boundary',adapter,1,2,lambda:f.f.now)
        current=w.records(root)[0];self.assertEqual(current['status'],'ready');self.assertNotEqual(current['prepared']['answers_path'],before['answers_path']);self.assertEqual(original,(root/before['answers_path']).read_bytes())
        self.assertEqual(run(root,'boundary',adapter,1,2,lambda:f.f.now)['confirmed'],1)
