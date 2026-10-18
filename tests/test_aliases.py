import copy
from datetime import timedelta
import unittest
import test_workflow
import workspace as w
from answers import resolve_question,validate

class AliasTests(unittest.TestCase):
    def setUp(self):
        self.f=test_workflow.WorkflowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.a={'id':'schedule','value':'Day','field_type':'select','options':['Day','Night'],'aliases':['Preferred schedule?','Which schedule?'],'scope':{'country':'AA'},'source':{'id':'review','version':1,'kind':'user'},'review_due_at':(self.f.now+timedelta(days=1)).isoformat()}
        self.q={'text':'  WHICH schedule?  ','field_type':'select','options':['Day','Night'],'scope':{'country':'AA'}}
        self.save([self.a])
    def save(self,answers):w.atomic_json(self.f.root/'profile/answers.json',{'answers':answers})
    def test_approved_alias_reuses_and_negative_cases_queue(self):
        self.assertEqual(resolve_question(self.f.root,self.q,self.f.now)['answer']['value'],'Day')
        for change in [{'text':'Unfamiliar schedule wording'},{'scope':{'country':'BB'}},{'units':'USD/month'},{'field_type':'text'},{'options':['Day','Evening']}]:
            with self.subTest(change=change):self.assertEqual(resolve_question(self.f.root,{**self.q,**change},self.f.now)['status'],'unresolved')
    def test_explicit_beats_default_and_ambiguity_is_not_guessed(self):
        default={**self.a,'id':'default','value':'Night','source':{'id':'policy','version':1,'kind':'authorized_default','basis':'User approved'}}
        self.save([default,self.a]);self.assertEqual(resolve_question(self.f.root,self.q,self.f.now)['answer']['id'],'schedule')
        self.save([self.a,{**self.a,'id':'other'}]);self.assertEqual(resolve_question(self.f.root,self.q,self.f.now)['reason'],'ambiguous_alias')
    def test_legal_country_and_nonfinite_numbers_fail(self):
        for semantic in ['sponsorship','work_authorization','residency']:
            a={**self.a,'semantic':semantic,'scope':{}};q={**self.q,'semantic':semantic,'scope':{}}
            with self.assertRaisesRegex(ValueError,'country'):validate(a,q,self.f.now)
        a={**self.a,'field_type':'number','value':float('nan')};q={**self.q,'field_type':'number','options':[]}
        with self.assertRaisesRegex(ValueError,'invalid_answer'):validate(a,q,self.f.now)
        a['value']=float('inf')
        with self.assertRaises(ValueError):validate(a,q,self.f.now)
