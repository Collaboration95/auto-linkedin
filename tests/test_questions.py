import unittest
import test_workflow
from questions import register,store,inbox
from export_dashboard import export_dashboard
import workspace as w

class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.a=self.f.capture()
    def test_ids_survive_reorder_restart_and_explicit_alias_mapping(self):
        q={'text':'Preferred schedule?','field_type':'select','options':['Day','Night'],'scope':{}}
        first=register(self.f.root,self.a,'form','schedule',q)
        other=register(self.f.root,self.a,'form','other',{'text':'Different fact?'})
        self.assertNotEqual(first['question_id'],other['question_id'])
        register(self.f.root,self.a,'form','schedule',q)
        alias=register(self.f.root,self.a,'form','alias',{**q,'text':'Which schedule?'},first['question_id'])
        self.assertEqual(alias['question_id'],first['question_id']);self.assertNotEqual(alias['occurrence_id'],first['occurrence_id'])
        before=store(self.f.root);before['questions'].reverse();w.atomic_json(self.f.root/'questions.json',before)
        export_dashboard(self.f.root);payload=w.read(self.f.root/'dashboard/data/applications.json')
        item=next(q for q in payload['questions'] if q['id']==first['question_id'])
        self.assertEqual(item['status'],'unresolved');self.assertEqual(len(item['occurrences']),2)
        self.assertIn('record_url',item['occurrences'][0]);self.assertTrue((self.f.root/'dashboard/questions.js').exists())
    def test_incompatible_scope_mapping_stays_distinct(self):
        a=register(self.f.root,self.a,'form','one',{'text':'Consent?','scope':{'employer':'Example'}})
        with self.assertRaisesRegex(ValueError,'incompatible'):register(self.f.root,self.a,'form','two',{'text':'Consent?','scope':{}},a['question_id'])
