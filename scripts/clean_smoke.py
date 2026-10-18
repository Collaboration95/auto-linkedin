#!/usr/bin/env python3
"""Copy only audited paths and verify without the source/private workspace."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from publication import ROOT,audit


def verify(destination):
    audit(history=(ROOT/'.git').exists())
    if destination.exists() and any(destination.iterdir()):raise ValueError('empty_export_destination_required')
    destination.mkdir(parents=True,exist_ok=True)
    for name in json.loads((ROOT/'publication.json').read_text())['paths']:
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    # No original workspace data is available to the copied helpers.
    import os
    environment={k:v for k,v in os.environ.items() if k not in {'AUTO_LINKEDIN_WORKSPACE','AUTO_LINKEDIN_FORBIDDEN_MARKERS','PYTHONPATH'}}
    commands=[[sys.executable,'-m','unittest','discover','-s','tests','-v'],['node','--test','tests/run-grouping.test.cjs'],[sys.executable,'scripts/smoke.py'],[sys.executable,'scripts/publication.py']]
    for command in commands:subprocess.run(command,cwd=destination,env=environment,check=True)
    with tempfile.TemporaryDirectory(prefix='clean-workspace-') as directory:
        for command in ('init','doctor','export'):
            subprocess.run([sys.executable,'scripts/workspace.py','--workspace',directory,command],cwd=destination,env=environment,check=True,stdout=subprocess.DEVNULL)
        if not (Path(directory)/'dashboard/index.html').is_file():raise ValueError('clean_dashboard_missing')
    return {'clean_export':'passed','checks':len(commands)+3}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path);args=p.parse_args()
    try:
        if args.destination:result=verify(args.destination.expanduser().resolve())
        else:
            with tempfile.TemporaryDirectory(prefix='clean-release-') as directory:result=verify(Path(directory))
        print(json.dumps(result,sort_keys=True))
    except (ValueError,OSError,subprocess.CalledProcessError):p.exit(1,'Clean export verification failed; details withheld.\n')

if __name__=='__main__':main()
