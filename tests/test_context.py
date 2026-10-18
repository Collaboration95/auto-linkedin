import unittest
from unittest.mock import patch
import test_workflow
from context import run_context
import workspace as w

class ContextTests(unittest.TestCase):
    def test_history_is_excluded_from_forms_that_do_not_use_it(self):
        f=test_workflow.WorkflowTests();f.setUp();self.addCleanup(f.doCleanups)
        w.atomic_json(f.root/'profile/history.json',{'entries':[]})
        first=run_context(f.root,include_history=False)
        (f.root/'profile/history.json').write_text('synthetic malformed history')
        with patch('workspace.read',wraps=w.read) as reader:
            self.assertEqual(first['version'],run_context(f.root,include_history=False)['version'])
            self.assertEqual(reader.call_count,1)
        updated={'entries':[{'company':'Fictional Systems'}]}
        w.atomic_json(f.root/'profile/history.json',updated)
        self.assertEqual(run_context(f.root)['snapshot']['history'],updated)

    def test_stable_inputs_answer_refresh_and_no_log_reread(self):
        f=test_workflow.WorkflowTests();f.setUp();self.addCleanup(f.doCleanups)
        w.atomic_json(f.root/'profile/answers.json',{'answers':[{'id':'sample','value':None}]})
        first=run_context(f.root)
        self.assertEqual(first['version'],run_context(f.root,True)['version'])
        w.atomic_json(f.root/'runtime/events.json',[{'status':'log'}])
        with patch('workspace.read',wraps=w.read) as reader:
            self.assertEqual(first['version'],run_context(f.root)['version'])
            self.assertEqual(reader.call_count,1)
        w.atomic_json(f.root/'profile/answers.json',{'answers':[{'id':'sample','value':'reviewed'}]})
        self.assertNotEqual(first['version'],run_context(f.root)['version'])
        self.assertTrue((f.root/'runtime/context.json').is_file())
