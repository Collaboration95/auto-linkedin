import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from setup_workspace import initialize,doctor

class SetupTests(unittest.TestCase):
    def test_offline_init_is_non_destructive_and_doctor_is_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'workspace';self.assertTrue(initialize(root)['initialized'])
            original={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(initialize(root)['created_files'],0)
            report=doctor(root,which=lambda name:None)
            self.assertTrue(report['ready']);self.assertIn('optional_pdf_import_unavailable',report['warnings'])
            self.assertFalse(report['live_browser']['supported']);self.assertNotIn(str(root),json.dumps(report))
            self.assertEqual(original,{p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()})
    def test_missing_workspace_actionable(self):
        with tempfile.TemporaryDirectory() as d:self.assertIn('workspace_missing_run_init',doctor(Path(d)/'absent')['blockers'])

    def test_export_installs_static_assets(self):
        from export_dashboard import export_dashboard
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);initialize(root);result=export_dashboard(root)
            self.assertTrue(Path(result['path']).is_file())
            for name in ('app.js','style.css','runs.js','data.js'):self.assertTrue((root/'dashboard'/name).is_file())
