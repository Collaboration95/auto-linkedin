"""Content-addressed private run context; record logging is not an input."""
import hashlib
import json
from pathlib import Path
from config import configuration

INPUTS=('profile/answers.json','config.json','resumes/registry.json','profile/history.json')


def content_version(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def run_context(root,refresh=False):
    from workspace import read,atomic_json
    signatures={name:[(root/name).stat().st_mtime_ns,(root/name).stat().st_size] if (root/name).exists() else None for name in INPUTS}
    target=root/'runtime/context.json'
    if target.exists() and not refresh:
        cached=read(target)
        if cached['signatures']==signatures:return cached
    answers=read(root/'profile/answers.json').get('answers',[]) if (root/'profile/answers.json').exists() else []
    registry=read(root/'resumes/registry.json') if (root/'resumes/registry.json').exists() else {'releases':[]}
    cfg=configuration(root)
    payload={'schema_version':1,'answers':answers,'preferences':{k:cfg[k] for k in ('timezone','resume_scope','browser','rules')},'resumes':registry['releases'],'blockers':sorted(a['id'] for a in answers if a.get('value') is None)}
    history_path=root/'profile/history.json'
    payload['history']=read(history_path) if history_path.exists() else None
    result={'version':content_version(payload),'snapshot':payload,'signatures':signatures}
    atomic_json(target,result);return result
