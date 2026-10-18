"""Offline initialization and diagnostics; no browser/session mutation."""
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from config import configuration


def initialize(root):
    from workspace import atomic_json
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    values={'config.json':{'schema_version':1,'timezone':'UTC','resume_scope':'backend','browser':'unsupported','rules':{}},'profile/answers.json':{'schema_version':1,'revision':0,'answers':[],'imports':{}},'resumes/registry.json':{'releases':[]},'projects/catalog.json':{'projects':[]},'resumes/presets.json':{},'questions.json':{'schema_version':1,'questions':[],'occurrences':[]}}
    from workspace import writer
    with writer(root):
        created=0
        for name,value in values.items():
            if not (root/name).exists():atomic_json(root/name,value);created+=1
    return {'initialized':True,'created_files':created,'existing_files_preserved':True}


def doctor(root,which=shutil.which):
    blockers=[];warnings=[]
    if sys.version_info<(3,10):blockers.append('python_3_10_required')
    if platform.system()=='Windows':blockers.append('posix_locking_required')
    if not root.is_dir():blockers.append('workspace_missing_run_init')
    if not (root/'config.json').exists():warnings.append('config_missing_legacy_defaults_in_use')
    try:configuration(root)
    except (ValueError,OSError,json.JSONDecodeError):blockers.append('invalid_config_set_timezone')
    node=which('node');node_ok=False
    if node:
        try:node_ok=int(subprocess.check_output([node,'--version'],text=True).lstrip('v').split('.')[0])>=18
        except (ValueError,OSError,subprocess.CalledProcessError):pass
    if not node_ok:warnings.append('node_18_required_for_js_tests')
    pdf=all(which(x) for x in ('pdftotext','pdfinfo')) and importlib.util.find_spec('fitz') is not None
    if not pdf:warnings.append('optional_pdf_import_unavailable')
    return {'ready':not blockers,'blockers':blockers,'warnings':warnings,'runtime':{'python_supported':sys.version_info>=(3,10),'node_tests':node_ok,'pdf_import':bool(pdf)},'live_browser':{'supported':False,'reason':'unsupported_live_capability'}}
