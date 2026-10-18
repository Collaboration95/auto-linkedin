"""Canonical question specifications and stable per-form occurrences."""
import copy
import unicodedata
from context import content_version


def normalize(text):return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def signature(q,wording=True):
    result={k:copy.deepcopy(q.get(k,default)) for k,default in [('field_type','text'),('options',[]),('scope',{}),('units',None),('semantic',None),('required',True)]}
    if wording:result['text']=normalize(q['text'])
    return result


def store(root):
    from workspace import read
    p=root/'questions.json'
    return read(p) if p.exists() else {'schema_version':1,'questions':[],'occurrences':[]}


def register(root,application_id,form_key,field_key,spec,canonical_id=None):
    import workspace as w
    from submission import load
    if not all(isinstance(v,str) and v.strip() for v in [form_key,field_key,spec.get('text')]):raise ValueError('question_keys_and_text_required')
    with w.writer(root):
        record=load(root,application_id);data=store(root)
        qid=canonical_id or 'q-'+content_version(signature(spec))[:24]
        matches=[q for q in data['questions'] if q['id']==qid]
        if matches and signature(matches[0],False)!=signature(spec,False):raise ValueError('incompatible_canonical_mapping')
        if not matches:data['questions'].append({**copy.deepcopy(spec),'id':qid,'answer_id':None})
        oid='o-'+content_version([application_id,form_key,field_key])[:24]
        old=next((o for o in data['occurrences'] if o['id']==oid),None)
        occurrence={'id':oid,'question_id':qid,'application_id':application_id,'form_key':form_key,'field_key':field_key,'text':spec['text'],'options':spec.get('options',[]),'company':record['company'],'listing_url':record['canonical_listing_url'],'record_url':'../applications/records/'+application_id+'/record.json'}
        if old and (old['question_id']!=qid or old['text']!=spec['text'] or old['options']!=spec.get('options',[])):raise ValueError('page_changed')
        if not old:data['occurrences'].append(occurrence)
        w.atomic_json(root/'questions.json',data);return {'question_id':qid,'occurrence_id':oid}


def inbox(root,now):
    from answers import by_id,validate
    data=store(root);result=[]
    for q in data['questions']:
        reason='unknown_answer';answer=None
        try:
            answer=validate(by_id(root,q['answer_id']),q,now);reason=None
        except (ValueError,KeyError):pass
        result.append({**q,'status':'resolved' if reason is None else 'unresolved','reason':reason,'saved_value':answer['value'] if reason is None else None,'occurrences':[o for o in data['occurrences'] if o['question_id']==q['id']]})
    return sorted(result,key=lambda q:(q['status']=='resolved',q['id']))
