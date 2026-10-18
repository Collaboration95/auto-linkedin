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
        counts=r.get('stop_counts',previous.get('counts',{})).copy();counts[reason]=counts.get(reason,0)+1
        total=max(previous.get('retry_count',0),r.get('retry_count',0))+(1 if reason in TRANSIENT else 0)
        incoming_reason=reason
        uncertain=r['status']=='submission_uncertain' or r.get('intent',{}).get('state')=='begun'
        if uncertain:reason='uncertain_submit'
        exhausted=total>=max_retries if reason in TRANSIENT else False
        retryable=reason in TRANSIENT and not exhausted and not uncertain
        stop={'reason':reason,'counts':counts,'retry_count':total,'retryable':retryable,'exhausted':exhausted,'recorded_at':now.isoformat(),'next_eligible_at':(now+timedelta(seconds=min(300,2**min(total,8)))).isoformat() if retryable else None}
        r['stop']=stop;r['retry_count']=total;r['stop_counts']=counts
        if not uncertain:r.update(status='awaiting_answer' if reason=='unknown_answer' else 'failed',status_updated_at=now.isoformat())
        save(root,r)
        if incoming_reason in BROWSER_STOP:w.atomic_json(root/'runtime/browser-stop.json',{'reason':incoming_reason,'at':now.isoformat(),'requires_resume':True})
        return stop


def retry_eligible(record,now):
    stop=record.get('stop')
    return not stop or bool(stop['retryable'] and not stop['exhausted'] and stop['next_eligible_at'] and now>=timestamp(stop['next_eligible_at']))


def browser_stopped(root):
    import workspace as w
    p=root/'runtime/browser-stop.json'
    return w.read(p) if p.exists() else None


REVIEWABLE={'login_required','page_changed','unsupported_live_capability','unsupported_form','eligibility_review','resume_stale','outdated_fact'}


def acknowledge_resume(root,now,identity=None):
    """Explicit review acknowledgement, never an uncertainty/exhaustion reset."""
    import workspace as w
    from submission import save
    resumed=[]
    with w.writer(root):
        for r in w.records(root):
            if identity is not None and r['application_id']!=identity:continue
            stop=r.get('stop',{})
            if r.get('submissions') or r['status']=='submission_uncertain' or r.get('intent',{}).get('state')=='begun' or stop.get('exhausted'):continue
            if stop.get('reason') in REVIEWABLE:
                r['retry_count']=max(r.get('retry_count',0),stop.get('retry_count',0));r.setdefault('stop_counts',stop.get('counts',{}))
                r.setdefault('reviewed_stops',[]).append({'reason':stop['reason'],'acknowledged_at':now.isoformat()})
                if stop['reason'] in {'page_changed','unsupported_form'}:r['reviewed_form_change']=True
                r.pop('stop',None);r.update(status='discovered',priority=0,status_updated_at=now.isoformat());save(root,r);resumed.append(r['application_id'])
        marker=root/'runtime/browser-stop.json'
        if marker.exists() and w.read(marker).get('reason') in REVIEWABLE:marker.unlink()
    return {'resumed':resumed,'uncertain_and_confirmed_preserved':True}


def clear_browser_stop(root):
    from config import local_now
    return acknowledge_resume(root,local_now(root))
