from pathlib import Path
import shutil
import tempfile
import unittest
import test_workflow
import submission as s
import workspace as w
from export_dashboard import export_dashboard

class PreparedRelocationTests(unittest.TestCase):
    def test_prepared_and_confirmed_artifacts_stay_relative(self):
        f=test_workflow.WorkflowTests();f.setUp();self.addCleanup(f.doCleanups);identity=f.ready()
        serialized=(f.root/'applications/records'/identity/'record.json').read_text()
        self.assertNotIn(str(f.root),serialized);self.assertNotIn(str(f.root.resolve()),serialized)
        self.assertFalse(Path(f.record(identity)['prepared']['path']).is_absolute())
        with tempfile.TemporaryDirectory() as d:
            moved=Path(d)/'moved';shutil.copytree(f.root,moved)
            self.assertTrue(w.preflight(moved,s.load(moved,identity),f.now)['ready'])
            with s.browser_claim(moved) as claim:intent=s.begin_submit(moved,identity,f.record(identity)['canonical_listing_url'],claim,f.now)
            s.confirm(moved,identity,intent['attempt_id'],f.evidence(),f.now)
            r=s.load(moved,identity);self.assertFalse(Path(r['submissions'][0]['path']).is_absolute())
            export_dashboard(moved);payload=w.read(moved/'dashboard/data/applications.json')
            url=payload['applications'][0]['submissions'][0]['resume']['url'];self.assertTrue((moved/'dashboard'/url).resolve().is_file())
