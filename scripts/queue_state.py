"""Answer-derived queue state; confirmed and uncertain applications are immutable here."""
from answers import resolve_question
from config import configuration
from questions import store
from resolve_resume import resolve


def block_on_answers(root,identity,question_ids,now):
    import workspace as w
    from submission import load,save
    with w.writer(root):
        r=load(root,identity)
        if r.get('submissions') or r['status']=='submission_uncertain':raise ValueError('terminal_submission_state')
        known={q['id'] for q in store(root)['questions']}
        if not question_ids or not set(question_ids)<=known:raise ValueError('unknown_question_blocker')
        r['required_question_ids']=sorted(set(r.get('required_question_ids',[])+question_ids))
        r.update(blocked_on_answer_ids=sorted(set(question_ids)),status='awaiting_answer',status_updated_at=now.isoformat());save(root,r)


def recompute(root,now):
    import workspace as w
    from submission import save
    with w.writer(root):
        questions={q['id']:q for q in store(root)['questions']};requeued=[]
        for r in w.records(root):
            if r['status']!='awaiting_answer' or r.get('submissions'):continue
            unresolved=[qid for qid in r.get('required_question_ids',r.get('blocked_on_answer_ids',[])) if qid not in questions or resolve_question(root,questions[qid],now)['status']!='resolved']
            r['blocked_on_answer_ids']=unresolved
            if not unresolved:
                r.update(status='discovered',priority=0,requeued_at=now.isoformat(),status_updated_at=now.isoformat());requeued.append(r['application_id'])
            save(root,r)
        return {'requeued':requeued}


def unlock_counts(records,questions):
    resolved={q['id'] for q in questions if q['status']=='resolved'};result={q['id']:0 for q in questions}
    for r in records:
        if r['status']!='awaiting_answer' or r.get('submissions'):continue
        remaining=set(r.get('required_question_ids',r.get('blocked_on_answer_ids',[])))-resolved
        if len(remaining)==1:
            qid=next(iter(remaining))
            if qid in result:result[qid]+=1
    return result


def execution_guard(root,record,now):
    import workspace as w
    if record.get('submissions') or record['status']=='submission_uncertain':raise ValueError('submission_not_retryable')
    if record.get('blocked_on_answer_ids'):raise ValueError('unknown_answer')
    if not record.get('listing_current'):raise ValueError('current_listing_review_required')
    return resolve(w.read(root/'resumes/registry.json'),configuration(root)['resume_scope'],'application',now,root)
