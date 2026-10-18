"""Private workspace selection; legacy layout is read in place without migration."""
import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PUBLIC_ROOT=Path(__file__).resolve().parents[1]
DEFAULT=Path('~/.local/share/auto-linkedin')


def select_workspace(explicit=None):
    root=Path(explicit or os.environ.get('AUTO_LINKEDIN_WORKSPACE') or DEFAULT).expanduser().resolve()
    if root==PUBLIC_ROOT or root.is_relative_to(PUBLIC_ROOT):
        raise ValueError('Select an external private workspace with --workspace')
    return root


def configuration(root):
    path=root/'config.json'
    # Legacy profile/resume/application layout remains valid and untouched.
    data=json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data,dict):raise ValueError('config.json must be an object')
    result={'timezone':'UTC','resume_scope':'backend','browser':'unsupported','rules':{},**data}
    try:ZoneInfo(result['timezone'])
    except (ZoneInfoNotFoundError,TypeError):raise ValueError('Set a valid timezone in private config.json') from None
    return result


def local_now(root):return datetime.now(ZoneInfo(configuration(root)['timezone']))


def private_path(root,relative):
    p=(root/relative).resolve()
    if p==root.resolve() or not p.is_relative_to(root.resolve()):raise ValueError('Artifact must stay inside selected workspace')
    return p
