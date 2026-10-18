"""Typed durable blockers; finite retries never include an uncertain submit."""
from datetime import timedelta
from resolve_resume import timestamp

REASONS={'unknown_answer','login_required','page_changed','throttled','timeout','uncertain_submit','unsupported_live_capability','unsupported_form','outdated_fact','eligibility_review','resume_stale','retry_exhausted'}
TRANSIENT={'throttled','timeout'}
BROWSER_STOP={'login_required','page_changed','unsupported_live_capability'}


def record_stop(root,identity,reason,now,max_retries=3):
    import workspace as w
    from submission import load,save
    if reason not in REASONS or type(max_retries) is not int or max_retries<0:raise ValueError('invalid_stop_policy')
    with w.writer(root):
        r=load(root,identity);previous=r.get('stop',{})
        counts=previous.get('counts',{}).copy();counts[reason]=counts.get(reason,0)+1
        total=previous.get('retry_count',0)+(1 if reason in TRANSIENT else 0)
        uncertain=r['status']=='submission_uncertain' or r.get('intent',{}).get('state')=='begun'
        if uncertain:reason='uncertain_submit'
        exhausted=total>=max_retries if reason in TRANSIENT else False
        retryable=reason in TRANSIENT and not exhausted and not uncertain
        stop={'reason':reason,'counts':counts,'retry_count':total,'retryable':retryable,'exhausted':exhausted,'recorded_at':now.isoformat(),'next_eligible_at':(now+timedelta(seconds=min(300,2**min(total,8)))).isoformat() if retryable else None}
        r['stop']=stop
        if not uncertain:r.update(status='awaiting_answer' if reason=='unknown_answer' else 'failed',status_updated_at=now.isoformat())
        save(root,r)
        if reason in BROWSER_STOP:w.atomic_json(root/'runtime/browser-stop.json',{'reason':reason,'at':now.isoformat(),'requires_resume':True})
        return stop


def retry_eligible(record,now):
    stop=record.get('stop')
    return not stop or bool(stop['retryable'] and not stop['exhausted'] and stop['next_eligible_at'] and now>=timestamp(stop['next_eligible_at']))


def browser_stopped(root):
    import workspace as w
    p=root/'runtime/browser-stop.json'
    return w.read(p) if p.exists() else None


def clear_browser_stop(root):
    # Explicit local acknowledgement after prerequisites/layout are reviewed.
    p=root/'runtime/browser-stop.json'
    if p.exists():p.unlink()
