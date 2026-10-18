from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from smoke import scenario

class ReleaseSmokeTests(unittest.TestCase):
    def test_full_synthetic_scenario(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);result=scenario(root);self.assertEqual(result['scenario'],'passed');self.assertFalse(result['live_employer_submission'])
            self.assertTrue((root/'form-smoke/form.html').is_file())
            with self.assertRaisesRegex(ValueError,'empty_synthetic'):scenario(root)
