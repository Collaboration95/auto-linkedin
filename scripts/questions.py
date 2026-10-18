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
        old=next((o for o in data['occurrences'] if o['application_id']==application_id and o['form_key']==form_key and o['field_key']==field_key and o.get('active',True)),None)
        changed=old and (old['question_id']!=qid or old['text']!=spec['text'] or old['options']!=spec.get('options',[]))
        if changed:
            if not record.get('reviewed_form_change'):raise ValueError('page_changed')
            oid='o-'+content_version([application_id,form_key,field_key,qid,spec['text'],spec.get('options',[])])[:24]
            old.update(active=False,superseded_by=oid)
        elif old:oid=old['id']
        occurrence={'id':oid,'question_id':qid,'application_id':application_id,'form_key':form_key,'field_key':field_key,'text':spec['text'],'options':spec.get('options',[]),'company':record['company'],'listing_url':record['canonical_listing_url'],'record_url':'../applications/records/'+application_id+'/record.json','active':True}
        if not old or changed:data['occurrences'].append(occurrence)
        w.atomic_json(root/'questions.json',data);return {'question_id':qid,'occurrence_id':oid}


def inbox(root,now,answer_data=None):
    from answers import resolve_question
    data=store(root);result=[]
    for q in data['questions']:
        resolved=resolve_question(root,q,now,answer_data);answer=resolved['answer']
        occurrences=[o for o in data['occurrences'] if o['question_id']==q['id']]
        if occurrences and not any(o.get('active',True) for o in occurrences):resolved['status']='archived'
        result.append({**q,'question_version':content_version(signature(q)),'status':resolved['status'],'reason':resolved['reason'],'saved_value':answer['value'] if answer else None,'resolved_answer_id':answer['id'] if answer else None,'occurrences':occurrences})
    return sorted(result,key=lambda q:(q['status']=='resolved',q['id']))
