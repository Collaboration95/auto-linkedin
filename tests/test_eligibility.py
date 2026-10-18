from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from eligibility import evaluate

class EligibilityTests(unittest.TestCase):
    def test_include_exclude_boundary_preferences_and_ambiguity(self):
        rules={'allowed_countries':['AA'],'experience_years':3,'requires_sponsorship':True}
        cases=[({},'include','eligible'),({'experience':{'minimum':'3+','strength':'hard'}},'include','eligible'),({'experience':{'minimum':4,'strength':'hard'}},'exclude','experience_minimum'),({'experience':{'minimum':4,'strength':'preference'}},'include','eligible'),({'country':{'value':'BB','strength':'hard'}},'exclude','location_excluded'),({'sponsorship':{'available':False,'strength':'hard'}},'exclude','sponsorship_unavailable'),({'experience':{'minimum':'roughly several','strength':'hard'}},'needs_review','experience_ambiguous')]
        for requirements,decision,reason in cases:
            with self.subTest(requirements=requirements):
                result=evaluate({'requirements_verified':True,'requirements':requirements},rules);self.assertEqual(result['decision'],decision);self.assertIn(reason,result['reasons'])
        self.assertEqual(evaluate({'job_description':'Maybe eligible'},rules)['decision'],'needs_review')
        self.assertEqual(evaluate({'requirements_verified':True,'requirements':{'sponsorship':{'available':True,'strength':'hard'}}},{})['decision'],'needs_review')
