import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publication import audit

class PublicationTests(unittest.TestCase):
    def test_content_and_filename_canaries_and_optional_marker(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'safe.txt';p.write_text('safe')
            def manifest(name): (root/'publication.json').write_text(json.dumps({'paths':[name]}))
            manifest('safe.txt');self.assertEqual(audit(root)['audited_paths'],1)
            p.write_text('PRIVATE_'+'CANARY_7f3b')
            with self.assertRaises(ValueError):audit(root)
            p.write_text('synthetic private phrase')
            with self.assertRaises(ValueError):audit(root,['synthetic private phrase'])
            name='PRIVATE_'+'CANARY_7f3b';p.rename(root/name);manifest(name)
            with self.assertRaises(ValueError):audit(root)
    def test_normal_git_add_boundary(self):
        import subprocess
        root=Path(__file__).resolve().parents[1]
        for name in ['profile/answers.json','resumes/private.pdf','dashboard/data.js','private-workspace/state.json','screenshots/local.png']:
            self.assertEqual(subprocess.run(['git','check-ignore','-q',name],cwd=root).returncode,0)
