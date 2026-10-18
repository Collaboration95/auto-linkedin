"""Semantic common-field handlers with before/after verification, no submit action."""
import copy
import hashlib
from pathlib import Path
from context import content_version
from questions import signature

class FormError(Exception):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)


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
    after=driver.snapshot()
    if layout_version(after['fields'])!=layout_version(expected):raise FormError('page_changed')
    for field in expected:
        kind=field.get('field_type','text')
        if kind=='upload' and after.get('uploads',{}).get(field['key'])!=resume['sha256']:raise FormError('resume_stale')
        if kind not in {'upload','history'} and field.get('question_id') in selected and after.get('values',{}).get(field['key'])!=selected[field['question_id']]:raise FormError('page_changed')
    if history is not None and after.get('history')!=history:raise FormError('outdated_fact')
    return {'verified':True,'layout_version':layout_version(expected),'resume_sha256':resume['sha256']}

class SyntheticFormDriver:
    def __init__(self,fields,history=None):self.fields=copy.deepcopy(fields);self.values={};self.uploads={};self.history=copy.deepcopy(history)
    def snapshot(self):return copy.deepcopy({'fields':self.fields,'values':self.values,'uploads':self.uploads,'history':self.history})
    def fill(self,field,value):self.values[field['key']]=value
    def upload(self,field,path):self.uploads[field['key']]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
