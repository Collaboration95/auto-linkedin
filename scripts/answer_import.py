"""One locked all-or-nothing answer batch; duplicate delivery is harmless."""
import copy
from answers import store,validate
from context import content_version
from questions import store as question_store,signature
from resolve_resume import timestamp


def import_changes(root,payload,now):
    import workspace as w
    if not isinstance(payload,dict) or set(payload)!={'schema_version','change_id','base_revision','changes'}:raise ValueError('invalid_change_schema')
    if payload['schema_version']!=1 or not isinstance(payload['change_id'],str) or not payload['change_id'] or type(payload['base_revision']) is not int or not isinstance(payload['changes'],list) or not payload['changes']:raise ValueError('invalid_change_schema')
    with w.writer(root):
        data=copy.deepcopy(store(root));revision=data.get('revision',0);imports=data.setdefault('imports',{})
        fingerprint=content_version(payload)
        if payload['change_id'] in imports:
            if imports[payload['change_id']]['hash']!=fingerprint:raise ValueError('change_id_reused')
            return {'mutation':'already_imported','revision':revision,'changed':0}
        if payload['base_revision']!=revision:raise ValueError('stale_answer_revision_refresh_export')
        questions={q['id']:q for q in question_store(root)['questions']};seen=set()
        for change in payload['changes']:
            if not isinstance(change,dict) or set(change)!={'question_id','question_version','value','scope','review_due_at'}:raise ValueError('invalid_change_schema')
            qid=change['question_id']
            if qid in seen or qid not in questions:raise ValueError('unknown_or_duplicate_question')
            seen.add(qid);q=questions[qid]
            if change['question_version']!=content_version(signature(q)):raise ValueError('stale_question_specification')
            if change['scope']!=q.get('scope',{}):raise ValueError('review_scope_mismatch')
            answer={k:copy.deepcopy(q[k]) for k in ('field_type','options','scope','units','semantic') if k in q}
            answer.update(id=qid,value=change['value'],aliases=[q['text']],review_due_at=timestamp(change['review_due_at']).isoformat(),reviewed_at=now.isoformat(),revision=revision+1,source={'id':payload['change_id'],'version':revision+1,'kind':'user'})
            validate(answer,q,now)
            data['answers']=[a for a in data['answers'] if a['id']!=qid]+[answer]
            data.setdefault('bindings',{})[qid]=qid
        data['schema_version']=1;data['revision']=revision+1;imports[payload['change_id']]={'hash':fingerprint,'revision':revision+1,'recorded_at':now.isoformat()}
        w.atomic_json(root/'profile/answers.json',data)
        return {'mutation':'persisted','revision':revision+1,'changed':len(seen)}
