"""Semantic common-field handlers with before/after verification, no submit action."""
import copy
import hashlib
from pathlib import Path
from context import content_version
from questions import signature

class FormError(Exception):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)


def needs_history(fields):
    return any(field.get('field_type')=='history' for field in fields)


def _valid_history_scope(scope):
    return isinstance(scope,dict) and all(
        isinstance(key,str) and key.strip() and isinstance(value,str) and value.strip()
        for key,value in scope.items())


def resolve_history(root,now,record=None):
    """Read reviewed facts only for a form that uses history; never supply defaults."""
    from config import private_path
    from resolve_resume import timestamp
    from workspace import read
    try:
        facts=read(private_path(root,'profile/history.json'))
        source=facts.get('source',{})
        version=source.get('version')
        if (not isinstance(source.get('id'),str) or not source['id'].strip()
                or type(version) not in (int,str) or not version
                or isinstance(version,str) and not version.strip()
                or source.get('kind') not in {None,'user','verified_fact'}):
            raise FormError('outdated_fact')
        if not isinstance(facts.get('entries'),list) or any(not isinstance(entry,dict) for entry in facts['entries']):
            raise FormError('outdated_fact')
        record=record or {}
        bindings={'employer':record.get('company'),'application_id':record.get('application_id')}
        base={key:value for key,value in bindings.items() if isinstance(value,str) and value.strip()}
        contexts=[]
        for field in record.get('workflow',{}).get('form',[]):
            if field.get('field_type')!='history':continue
            declared=field.get('scope',{})
            if not _valid_history_scope(declared) or any(key in bindings and bindings[key]!=value for key,value in declared.items()):
                raise FormError('outdated_fact')
            contexts.append({**base,**declared})
        contexts=contexts or [base]
        for item in (facts,source,*facts['entries']):
            scope=item.get('scope',{})
            if (not _valid_history_scope(scope)
                    or any(any(context.get(key)!=value for key,value in scope.items()) for context in contexts)):
                raise FormError('outdated_fact')
        for field in ('review_due_at','valid_until'):
            deadline=facts.get(field)
            if field=='valid_until' and deadline is None:continue
            if not isinstance(deadline,str) or not deadline.strip() or now>=timestamp(deadline):
                raise FormError('outdated_fact')
        return copy.deepcopy(facts)
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise FormError('outdated_fact') from None


def layout_version(fields):
    return content_version(sorted([{'key':f['key'],**signature(f)} for f in fields],key=lambda f:f['key']))


def fill_common(driver,expected,answers,resume,history=None):
    actual=driver.snapshot()
    if layout_version(actual['fields'])!=layout_version(expected):raise FormError('page_changed')
    supported={'text','select','number','boolean','upload','history'}
    if any(f.get('field_type','text') not in supported for f in expected):raise FormError('unsupported_form')
    selected={a['question_spec']['id']:a['answer'] for a in answers}
    if hashlib.sha256(Path(resume['path']).read_bytes()).hexdigest()!=resume['sha256']:raise FormError('resume_stale')
    # Work history is verified against saved facts; handlers do not edit the profile.
    if any(f.get('field_type')=='history' for f in expected):
        if history is None or actual.get('history')!=history:raise FormError('outdated_fact')
    for field in expected:
        kind=field.get('field_type','text')
        if kind=='upload':driver.upload(field,resume['path'])
        elif kind=='history':continue
        elif field.get('question_id') in selected:driver.fill(field,selected[field['question_id']])
        elif field.get('required',True):raise FormError('unknown_answer')
    return verify_common(driver.snapshot(),expected,answers,resume,history)


def verify_common(after,expected,answers,resume,history=None):
    if layout_version(after['fields'])!=layout_version(expected):raise FormError('page_changed')
    selected={a['question_spec']['id']:a['answer'] for a in answers}
    for field in expected:
        kind=field.get('field_type','text')
        if kind=='upload' and after.get('uploads',{}).get(field['key'])!=resume['sha256']:raise FormError('resume_stale')
        if kind not in {'upload','history'} and field.get('question_id') in selected and after.get('values',{}).get(field['key'])!=selected[field['question_id']]:raise FormError('page_changed')
    if any(f.get('field_type')=='history' for f in expected) and (history is None or after.get('history')!=history):raise FormError('outdated_fact')
    return {'verified':True,'layout_version':layout_version(expected),'resume_sha256':resume['sha256']}

class SyntheticFormDriver:
    def __init__(self,fields,history=None):self.fields=copy.deepcopy(fields);self.values={};self.uploads={};self.history=copy.deepcopy(history)
    def snapshot(self):return copy.deepcopy({'fields':self.fields,'values':self.values,'uploads':self.uploads,'history':self.history})
    def fill(self,field,value):self.values[field['key']]=value
    def upload(self,field,path):self.uploads[field['key']]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
