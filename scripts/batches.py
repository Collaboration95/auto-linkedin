"""Quotas derive from first unique confirmations, never attempt counters."""
from resolve_resume import timestamp


def confirmed_totals(records,batch_id):
    first={}
    for r in records:
        key=r['canonical_listing_url']
        for sent in r.get('submissions',[]):
            at=timestamp(sent.get('occurred_at') or sent['submitted_at'])
            candidate=(at,sent.get('attempt_id',''),sent)
            if key not in first or candidate[:2]<first[key][:2]:first[key]=candidate
    categories={}
    for _,_,sent in first.values():
        if sent.get('batch_id')==batch_id:
            category=sent.get('category','default');categories[category]=categories.get(category,0)+1
    return {'confirmed':sum(categories.values()),'categories':dict(sorted(categories.items()))}


def batch_progress(records,batch_id,quota):
    totals=confirmed_totals(records,batch_id)
    return {**totals,'remaining':max(0,quota-totals['confirmed']),'submitted_exclusions':sum(bool(r.get('submissions')) for r in records),'waiting_answers':sum(r['status']=='awaiting_answer' for r in records),'retryable':sum(r['status'] in {'discovered','preparing','ready','failed'} and not r.get('submissions') for r in records)}


def submit_capacity(records,batch_id,quota):
    totals=confirmed_totals(records,batch_id)
    reserved={r['canonical_listing_url'] for r in records if not r.get('submissions') and r.get('intent',{}).get('state')=='begun' and r['intent'].get('batch_id')==batch_id}
    return {**totals,'reserved':len(reserved),'remaining':max(0,quota-totals['confirmed']-len(reserved))}
