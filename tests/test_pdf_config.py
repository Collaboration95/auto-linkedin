import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import import_pdf

class PdfConfigurationTests(unittest.TestCase):
    def test_optional_import_uses_explicit_workspace_and_timezone_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);source=base/'synthetic-input.pdf';source.write_bytes(b'Synthetic original PDF bytes');before=source.read_bytes()
            explicit=base/'explicit';env=base/'environment';explicit.mkdir();env.mkdir();(explicit/'config.json').write_text('{"timezone":"Pacific/Honolulu"}')
            class Document:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def __len__(self):return 0
                def __iter__(self):return iter([])
            with patch.dict(os.environ,{'AUTO_LINKEDIN_WORKSPACE':str(env)}),patch.dict(sys.modules,{'fitz':types.SimpleNamespace(open=lambda path:Document())}),patch('subprocess.run',return_value=types.SimpleNamespace(stdout='Synthetic extracted metadata')),patch.object(sys,'argv',['import_pdf.py',str(source),'--id','synthetic','--destination','sources/synthetic','--workspace',str(explicit)]),contextlib.redirect_stdout(io.StringIO()):import_pdf.main()
            metadata=json.loads((explicit/'sources/synthetic/metadata.json').read_text())
            self.assertTrue(metadata['imported_at'].endswith('-10:00'));self.assertTrue(metadata['filesystem_modified_at'].endswith('-10:00'));self.assertEqual(source.read_bytes(),before);self.assertEqual((explicit/'sources/synthetic/original.pdf').read_bytes(),before);self.assertEqual(list(env.iterdir()),[])
