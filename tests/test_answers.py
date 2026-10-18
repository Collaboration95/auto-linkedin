from datetime import timedelta
import copy
import unittest
import test_workflow
from answers import validate,store
import workspace as w

class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.a=store(self.f.root)['answers'][0];self.q={'field_type':'text','scope':{}}
    def test_expiry_and_change_after_preparation(self):
        self.a["review_due_at"]=(self.f.now+timedelta(hours=1)).isoformat()
        w.atomic_json(self.f.root/"profile/answers.json",{"answers":[self.a]})
        identity=self.f.ready();record=self.f.record(identity)
        before=(self.f.root/record['prepared']['answers_path']).read_bytes()
        with self.assertRaisesRegex(ValueError,'expired'):w.preflight(self.f.root,record,self.f.now+timedelta(hours=2))
        a=copy.deepcopy(self.a);a['value']='No';w.atomic_json(self.f.root/'profile/answers.json',{'answers':[a]})
        with self.assertRaisesRegex(ValueError,'changed'):w.preflight(self.f.root,record,self.f.now)
        self.assertEqual(before,(self.f.root/record['prepared']['answers_path']).read_bytes())
    def test_scope_legal_options_and_defaults(self):
        for change,qchange,reason in [({'scope':{'country':'AA'}},{'scope':{'country':'BB'}},'scope'),({'semantic':'sponsorship'},{'semantic':'work_authorization'},'semantic'),({'semantic':'employer_consent'},{'semantic':'employer_consent'},'consent'),({}, {'options':['No']},'option'),({'units':'USD/year'},{'units':'USD/month'},'units')]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):validate({**self.a,**change},{**self.q,**qchange},self.f.now)
        a={**self.a,'source':{'id':'policy','version':1,'kind':'authorized_default'}}
        with self.assertRaisesRegex(ValueError,'basis'):validate(a,self.q,self.f.now)
        a['source']['basis']='Explicit user authorization';self.assertEqual(validate(a,self.q,self.f.now)['value'],'Yes')
    def test_null_blocks_only_preparing_record(self):
        identity=self.f.capture();a={**self.a,'value':None}
        with self.assertRaisesRegex(ValueError,'unknown'):validate(a,self.q,self.f.now)
        self.assertEqual(self.f.record(identity)['status'],'discovered')
