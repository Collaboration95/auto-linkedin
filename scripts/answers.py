"""Deterministic scoped answers with immutable provenance and submit-time checks."""
import copy
import math
from context import content_version
from resolve_resume import timestamp


def store(root):
    from workspace import read
    p=root/'profile/answers.json'
    return read(p) if p.exists() else {'schema_version':1,'revision':0,'answers':[],'imports':{}}


def validate(answer,question,now):
    if answer.get('value') is None:raise ValueError('unknown_answer')
    source=answer.get('source',{})
    if not source.get('id') or not source.get('version') or source.get('kind') not in {'user','authorized_default','verified_fact'}:
        raise ValueError('answer_provenance_required')
    if source['kind']=='authorized_default' and not source.get('basis'):raise ValueError('default_basis_required')
    if not answer.get('review_due_at'):raise ValueError('answer_review_required')
    for field in ('review_due_at','valid_until'):
        if answer.get(field) and now>=timestamp(answer[field]):raise ValueError('answer_expired')
    if answer.get('semantic')!=question.get('semantic'):raise ValueError('answer_semantic_mismatch')
    a_scope=answer.get('scope',{});q_scope=question.get('scope',{})
    if not isinstance(a_scope,dict) or not isinstance(q_scope,dict):raise ValueError('answer_scope_invalid')
    if question.get('semantic') in {'sponsorship','work_authorization','residency'} and (not a_scope.get('country') or a_scope.get('country') != q_scope.get('country')):
        raise ValueError('legal_country_scope_required')
    if any(q_scope.get(k)!=v for k,v in a_scope.items()):raise ValueError('answer_scope_mismatch')
    # Legal concepts are explicit semantic keys, never inferred from similar wording.
    if question.get('semantic')=='employer_consent' and (not a_scope.get('employer') or a_scope.get('employer')!=q_scope.get('employer')):
        raise ValueError('consent_scope_required')
    if answer.get('field_type','text')!=question.get('field_type','text') or answer.get('units')!=question.get('units'):
        raise ValueError('answer_field_or_units_mismatch')
    value=answer['value'];kind=question.get('field_type','text')
    if kind not in {'text','select','number','boolean'}:raise ValueError('unsupported_answer_type')
    if kind=='text' and (not isinstance(value,str) or (question.get('required',True) and not value.strip())):raise ValueError('invalid_answer_value')
    if kind=='number' and (type(value) not in (int,float) or not math.isfinite(value)):raise ValueError('invalid_answer_value')
    if kind=='boolean' and type(value) is not bool:raise ValueError('invalid_answer_value')
    if question.get('options') and value not in question['options']:raise ValueError('answer_option_mismatch')
    if kind=='select' and not question.get('options'):raise ValueError('answer_options_required')
    return copy.deepcopy(answer)


def by_id(root,identity):
    candidates=[a for a in store(root)['answers'] if a['id']==identity]
    if len(candidates)!=1:raise ValueError('answer_missing_or_ambiguous')
    return candidates[0]


def snapshot(root,items,record,now):
    saved=[]
    for item in items:
        identity=item.get('source_answer_id')
        if not identity:raise ValueError('source_answer_id_required')
        answer=by_id(root,identity)
        question=copy.deepcopy(item.get('question_spec') or {'text':item['question'],'field_type':'text','scope':{},'semantic':answer.get('semantic')})
        # Employer binding comes from the saved application, never caller claims.
        if 'employer' in question.get('scope',{}) and question['scope']['employer']!=record['company']:raise ValueError('application_scope_mismatch')
        validated=validate(answer,question,now)
        if item.get('answer')!=validated['value']:raise ValueError('selected_answer_mismatch')
        saved.append({'question':item['question'],'question_spec':question,'answer':validated['value'],'source_answer_id':identity,'source_version':content_version(answer),'provenance':validated['source']})
    return saved


def revalidate(root,items,now):
    for item in items:
        answer=by_id(root,item['source_answer_id'])
        if content_version(answer)!=item.get('source_version'):raise ValueError('answer_changed_after_preparation')
        validate(answer,item['question_spec'],now)
        if answer['value']!=item['answer']:raise ValueError('answer_changed_after_preparation')


def resolve_question(root,question,now,data=None):
    """Only approved exact normalized aliases; ambiguity remains unresolved."""
    from questions import normalize
    data=store(root) if data is None else data;bound=data.get('bindings',{}).get(question.get('id')) or question.get('answer_id')
    candidates=[]
    for answer in data['answers']:
        explicit=answer['id']==bound
        aliases=answer.get('aliases',[])
        if not explicit and normalize(question['text']) not in [normalize(t) for t in aliases]:continue
        if answer.get('options',[])!=question.get('options',[]):continue
        try:validated=validate(answer,question,now)
        except ValueError:continue
        candidates.append((0 if explicit else 2 if answer['source']['kind']=='authorized_default' else 1,validated))
    if not candidates:return {'status':'unresolved','reason':'unknown_or_invalid_answer','answer':None}
    best=min(rank for rank,_ in candidates);winners=[a for rank,a in candidates if rank==best]
    if len(winners)!=1:return {'status':'unresolved','reason':'ambiguous_alias','answer':None}
    return {'status':'resolved','reason':None,'answer':winners[0]}
