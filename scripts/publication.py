#!/usr/bin/env python3
"""Fail closed on unreviewed release paths or private markers; never print matches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT, markers=(), history=False):
    allowed = json.loads((root / 'publication.json').read_text())['paths']
    if allowed != sorted(set(allowed)):
        raise ValueError('Manifest must be sorted and unique')
    forbidden = [('PRIVATE_' + 'CANARY_7f3b').encode(), *[m.encode() for m in markers if m]]
    blobs = []
    for name in allowed:
        path = root / name
        if Path(name).is_absolute() or '..' in Path(name).parts or any((root / Path(*Path(name).parts[:i])).is_symlink() for i in range(1,len(Path(name).parts)+1)) or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('Invalid or missing publication path')
        blobs.append((name.encode(), path.read_bytes()))
    git = (root / '.git').exists()
    if git:
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
        if set(filter(None, tracked)) - set(allowed):
            raise ValueError('Unreviewed tracked or staged paths')
        staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'], cwd=root).decode().split('\0')
        for name in filter(None, staged):
            if name not in allowed:
                raise ValueError('Unreviewed staged path')
            blobs.append((name.encode(), subprocess.check_output(['git', 'show', ':' + name], cwd=root)))
        if history:
            commits = subprocess.check_output(['git', 'rev-list', '--all', 'HEAD'], cwd=root).decode().split()
            historical=set()
            for commit in commits:
                entries = subprocess.check_output(['git','ls-tree','-r','--format=%(objectname) %(path)',commit],cwd=root).decode().splitlines()
                for entry in entries:
                    oid, name = entry.split(' ',1)
                    if name not in allowed:
                        raise ValueError('Unreviewed historical path')
                    historical.add((name,oid))
            for name,oid in sorted(historical):
                blobs.append((name.encode(),subprocess.check_output(['git','cat-file','blob',oid],cwd=root)))
    if any(b'/' + b'Users/' in name + b'\n' + content for name, content in blobs) or any(marker.lower() in (name + b'\n' + content).lower() for name,content in blobs for marker in forbidden):
        raise ValueError('Publication privacy scan failed (matches withheld)')
    return {'audited_paths':len(allowed),'sha256':hashlib.sha256(b''.join(name+b'\0'+content for name,content in sorted(blobs[:len(allowed)]))).hexdigest()}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--forbidden-markers',type=Path,default=os.environ.get('AUTO_LINKEDIN_FORBIDDEN_MARKERS'));p.add_argument('--history',action='store_true');a=p.parse_args()
    try:
        markers=json.loads(Path(a.forbidden_markers).read_text()) if a.forbidden_markers else []
        if not isinstance(markers,list) or any(not isinstance(x,str) for x in markers): raise ValueError('Invalid marker file')
        print(json.dumps(audit(markers=markers,history=a.history),sort_keys=True))
    except (ValueError,OSError,subprocess.CalledProcessError):
        p.exit(1,'Publication check failed; details withheld.\n')

if __name__=='__main__': main()
