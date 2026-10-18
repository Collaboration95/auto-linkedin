import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from forms import fill_common,SyntheticFormDriver,FormError

class FormTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'synthetic-resume.pdf';self.path.write_bytes(b'Synthetic selected bytes')
        self.resume={'path':str(self.path),'sha256':hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.fields=[{'key':'name','text':'Name','field_type':'text','question_id':'name'},{'key':'schedule','text':'Schedule','field_type':'select','options':['Day','Night'],'question_id':'schedule'},{'key':'resume','text':'Resume','field_type':'upload'},{'key':'history','text':'Work history','field_type':'history'}]
        self.answers=[{'question_spec':{'id':'name'},'answer':'Fictional Candidate'},{'question_spec':{'id':'schedule'},'answer':'Day'}];self.history=[{'company':'Fictional Systems','role':'Engineer'}]
    def test_known_fields_verify_values_resume_and_history(self):
        driver=SyntheticFormDriver(self.fields,self.history);self.assertTrue(fill_common(driver,self.fields,self.answers,self.resume,self.history)['verified'])
        self.assertEqual(driver.snapshot()['values']['schedule'],'Day');self.assertEqual(driver.snapshot()['uploads']['resume'],self.resume['sha256'])
    def test_changed_options_history_or_upload_stop(self):
        changed=copy.deepcopy(self.fields);changed[1]['options'].append('Other')
        with self.assertRaisesRegex(FormError,'page_changed'):fill_common(SyntheticFormDriver(changed,self.history),self.fields,self.answers,self.resume,self.history)
        with self.assertRaisesRegex(FormError,'outdated_fact'):fill_common(SyntheticFormDriver(self.fields,[]),self.fields,self.answers,self.resume,self.history)
        class BadUpload(SyntheticFormDriver):
            def upload(self,field,path):self.uploads[field['key']]='wrong'
        with self.assertRaisesRegex(FormError,'resume_stale'):fill_common(BadUpload(self.fields,self.history),self.fields,self.answers,self.resume,self.history)
    def test_unknown_layout_falls_back_before_filling(self):
        fields=[{'key':'unknown','text':'Unfamiliar','field_type':'canvas'}];driver=SyntheticFormDriver(fields)
        with self.assertRaisesRegex(FormError,'unsupported_form'):fill_common(driver,fields,[],self.resume)
        self.assertEqual(driver.values,{})

    def test_runner_queues_unfamiliar_form_as_typed_blocker(self):
        import test_runner
        import workspace as w
        from runner import run,SyntheticAdapter
        f=test_runner.RunnerTests();f.setUp();self.addCleanup(f.doCleanups)
        job=f.jobs[0];job['form']=[{'key':'drawing','text':'Draw a response','field_type':'canvas'}]
        run(f.f.root,'unfamiliar',SyntheticAdapter([job]),1,5,lambda:f.f.now)
        self.assertEqual(w.records(f.f.root)[0]['stop']['reason'],'unsupported_form')
        self.assertFalse(w.records(f.f.root)[0].get('intent'))
