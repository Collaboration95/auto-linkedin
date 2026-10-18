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
        if not (root/'.git').exists():self.skipTest('Git-only containment; archive paths are checked by manifest')
        for name in ['profile/answers.json','resumes/private.pdf','dashboard/data.js','private-workspace/state.json','screenshots/local.png']:
            self.assertEqual(subprocess.run(['git','check-ignore','-q',name],cwd=root).returncode,0)

    def test_history_scans_side_branches_and_removed_ancestors(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'safe.txt').write_text('safe');(root/'publication.json').write_text(json.dumps({'paths':['publication.json','safe.txt']}))
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
            git('init','-q','-b','main');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.org');git('add','.');git('commit','-qm','safe')
            git('checkout','-qb','side');(root/'safe.txt').write_text('PRIVATE_'+'CANARY_7f3b');git('commit','-qam','synthetic canary')
            (root/'safe.txt').write_text('safe again');git('commit','-qam','remove canary');git('checkout','-q','main')
            with self.assertRaises(ValueError):audit(root,history=True)
            git('branch','-D','side')
            self.assertEqual(audit(root,history=True)['audited_paths'],2)
    def test_parent_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
            root=Path(d);external=Path(outside);(external/'public.txt').write_text('synthetic safe bytes');(root/'sub').symlink_to(external,target_is_directory=True)
            (root/'publication.json').write_text(json.dumps({'paths':['sub/public.txt']}))
            with self.assertRaisesRegex(ValueError,'Invalid'):audit(root)
