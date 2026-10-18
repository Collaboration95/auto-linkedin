import unittest
from pathlib import Path
import tempfile
import test_queue
from export_dashboard import export_dashboard
from questions import register
from queue_state import block_on_answers
from submission import load,save
import workspace as w

class AttentionTests(unittest.TestCase):
    def test_attention_and_unlocks_are_derived_and_timezone_is_configured(self):
        fixture=test_queue.QueueTests();fixture.setUp();self.addCleanup(fixture.doCleanups);f=fixture.f
        q=register(f.root,fixture.ids[0],'form','shared',{'text':'Schedule?'})['question_id']
        other=register(f.root,fixture.ids[1],'form','other',{'text':'Other?'})['question_id']
        block_on_answers(f.root,fixture.ids[0],[q],f.now);block_on_answers(f.root,fixture.ids[1],[q,other],f.now)
        r=load(f.root,fixture.ids[2]);r['status']='submission_uncertain';save(f.root,r)
        w.atomic_json(f.root/'config.json',{'timezone':'Pacific/Honolulu'})
        export_dashboard(f.root);data=w.read(f.root/'dashboard/data/applications.json')
        self.assertEqual(data['timezone'],'Pacific/Honolulu');self.assertEqual(data['attention']['uncertain'],[fixture.ids[2]])
        self.assertEqual(next(x for x in data['questions'] if x['id']==q)['unlock_count'],1)
        app=(f.root/'dashboard/app.js').read_text();self.assertNotIn('SGT',app);self.assertNotIn('Asia/Singapore',app)
