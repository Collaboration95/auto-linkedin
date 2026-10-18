import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from config import select_workspace,private_path,local_now,configuration,DEFAULT
from resolve_resume import resolve
import test_workflow

class ConfigurationTests(unittest.TestCase):
    def test_precedence_and_independence(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b'
            for root,tz in [(a,'UTC'),(b,'Pacific/Honolulu')]:
                root.mkdir();(root/'config.json').write_text(json.dumps({'timezone':tz}))
            with patch.dict(os.environ,{'AUTO_LINKEDIN_WORKSPACE':str(b)}):
                self.assertEqual(select_workspace(),b.resolve());self.assertEqual(select_workspace(a),a.resolve())
            self.assertNotEqual(local_now(a).utcoffset(),local_now(b).utcoffset())
            self.assertEqual(configuration(a)['timezone'],'UTC')
    def test_relocation_and_legacy_preservation(self):
        f=test_workflow.WorkflowTests();f.setUp()
        try:
            original={p.relative_to(f.root):p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
            with tempfile.TemporaryDirectory() as d:
                copied=Path(d)/'copy';shutil.copytree(f.root,copied)
                resolved=resolve(f.registry,'backend','application',f.now,copied)
                self.assertTrue(Path(resolved['path']).is_relative_to(copied.resolve()))
            self.assertEqual(original,{p.relative_to(f.root):p.read_bytes() for p in f.root.rglob('*') if p.is_file()})
        finally:f.doCleanups()
    def test_bad_timezone_and_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'config.json').write_text('{"timezone":"invalid"}')
            with self.assertRaisesRegex(ValueError,'timezone'):configuration(root)
            with self.assertRaises(ValueError):private_path(root,'../outside')
