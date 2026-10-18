import copy
from datetime import timedelta
import unittest
import test_workflow
from answers import store
from answer_import import import_changes
from questions import register,inbox
from export_dashboard import export_dashboard
import workspace as w

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        identity=self.f.capture();self.ids=[]
        for key in ['one','two']:self.ids.append(register(self.f.root,identity,'form',key,{'text':key+' question?','field_type':'text','scope':{}})['question_id'])
    def payload(self):
        qs=inbox(self.f.root,self.f.now)
        return {'schema_version':1,'change_id':'synthetic-batch','base_revision':0,'changes':[{'question_id':q['id'],'question_version':q['question_version'],'value':'Reviewed','scope':q.get('scope',{}),'review_due_at':(self.f.now+timedelta(days=1)).isoformat()} for q in qs]}
    def test_round_trip_duplicate_and_authoritative_export(self):
        p=self.payload();result=import_changes(self.f.root,p,self.f.now);self.assertEqual(result['changed'],2)
        self.assertEqual(import_changes(self.f.root,p,self.f.now)['mutation'],'already_imported')
        export_dashboard(self.f.root);export=w.read(self.f.root/'dashboard/data/applications.json')
        self.assertEqual(export['answer_revision'],1);self.assertIn(p['change_id'],export['answer_import_ids']);self.assertTrue(all(q['status']=='resolved' for q in export['questions']))
    def test_stale_malformed_and_changed_id_have_no_partial_write(self):
        p=self.payload();bad=copy.deepcopy(p);bad['changes'][1]['value']=None
        before=(self.f.root/'profile/answers.json').read_bytes()
        with self.assertRaises(ValueError):import_changes(self.f.root,bad,self.f.now)
        self.assertEqual(before,(self.f.root/'profile/answers.json').read_bytes())
        import_changes(self.f.root,p,self.f.now);before=(self.f.root/'profile/answers.json').read_bytes()
        bad=copy.deepcopy(p);bad['change_id']='new'
        with self.assertRaisesRegex(ValueError,'stale'):import_changes(self.f.root,bad,self.f.now)
        bad=copy.deepcopy(p);bad['changes'][0]['value']='Different'
        with self.assertRaisesRegex(ValueError,'reused'):import_changes(self.f.root,bad,self.f.now)
        self.assertEqual(before,(self.f.root/'profile/answers.json').read_bytes())
