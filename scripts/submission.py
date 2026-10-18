"""Single browser writer and durable intent: an interrupted click is uncertain."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import uuid
from config import private_path
from resolve_resume import timestamp

class Claim:
    def __init__(self,root,handle):self.root=root.resolve();self.handle=handle;self.active=True

@contextmanager
def browser_claim(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.browser.lock').open('a') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('browser_claim_conflict') from None
        claim=Claim(root,handle)
        try:yield claim
        finally:claim.active=False;fcntl.flock(handle,fcntl.LOCK_UN)


def require_claim(root,claim):
    if not isinstance(claim,Claim) or not claim.active or claim.root!=root.resolve() or claim.handle.closed:
        raise ValueError('browser_claim_required')


def load(root,identity):
    import workspace as w
    return w.read(private_path(root,'applications/records/'+w.slug(identity)+'/record.json'))


def save(root,record):
    import workspace as w
    w.atomic_json(root/'applications/records'/record['application_id']/'record.json',record)


def begin_submit(root,identity,observed_url,claim,now,batch_id='manual',category='default',quota=None):
    import workspace as w
    require_claim(root,claim)
    with w.writer(root):
        r=load(root,identity)
        if w.canonical_url(observed_url)!=r['canonical_listing_url']:raise ValueError('observed_job_mismatch')
        if r.get('submissions') or any(x.get('submissions') and x['canonical_listing_url']==r['canonical_listing_url'] for x in w.records(root)):
            raise ValueError('already_confirmed')
        if r.get('intent') and r['intent']['state'] in {'begun','confirmed'}:raise ValueError('reconciliation_required')
        from batches import submit_capacity
        batch_file=root/'runtime/batches'/(w.slug(batch_id)+'.json')
        if batch_file.exists():quota=w.read(batch_file)['quota']
        if quota is not None and submit_capacity(w.records(root),batch_id,quota)['remaining']<=0:raise ValueError('submit_budget_reserved_or_complete')
        w.preflight(root,r,now)
        intent={'attempt_id':uuid.uuid4().hex,'observed_job':r['canonical_listing_url'],'state':'begun','begun_at':now.isoformat(),'batch_id':batch_id,'category':category}
        r.setdefault('attempts',[]).append(intent.copy())
        r.update(intent=intent,status='submission_uncertain',status_updated_at=now.isoformat())
        r.setdefault('events',[]).append({'at':now.isoformat(),'status':'submission_uncertain','reason':'submit_intent'})
        save(root,r)
        w.refresh_export(root)
        return intent.copy()


def confirm(root,identity,attempt_id,evidence,now,occurred_at=None):
    import workspace as w
    occurred=timestamp(occurred_at or now.isoformat()).isoformat()
    with w.writer(root):
        r=load(root,identity);intent=r.get('intent',{})
        if intent.get('attempt_id')!=attempt_id:raise ValueError('attempt_mismatch')
        if intent.get('state')=='confirmed':return {'confirmed':True,'duplicate':True,'export':w.refresh_export(root)}
        if intent.get('state')!='begun' or not evidence.is_file():raise ValueError('confirmation_evidence_required')
        directory=root/'applications/records'/identity/'submissions'/attempt_id
        directory.mkdir(parents=True,exist_ok=True);target=directory/'confirmation.txt';shutil.copyfile(evidence,target)
        sent={**r['prepared'],'attempt_id':attempt_id,'batch_id':intent['batch_id'],'category':intent['category'],'submitted_at':occurred,'occurred_at':occurred,'recorded_at':now.isoformat(),'confirmation_path':str(target.relative_to(root)),'confirmation_sha256':w.digest(target)}
        r['submissions'].append(sent);r['intent']['state']='confirmed'
        for attempt in r.get('attempts',[]):
            if attempt['attempt_id']==attempt_id:attempt['state']='confirmed'
        r.update(status='submitted',submitted_at=occurred,status_updated_at=now.isoformat())
        r['events'].append({'at':occurred,'occurred_at':occurred,'recorded_at':now.isoformat(),'status':'submitted'})
        save(root,r);return {'confirmed':True,'duplicate':False,'mutation':'persisted','export':w.refresh_export(root)}


def reconcile_not_submitted(root,identity,evidence,now):
    import workspace as w
    with w.writer(root):
        r=load(root,identity)
        if r['status']!='submission_uncertain' or not evidence.is_file():raise ValueError('reconciliation_evidence_required')
        target=root/'applications/records'/identity/'reconciliation.txt';shutil.copyfile(evidence,target)
        r['intent']['state']='reconciled_not_submitted';r.pop('stop',None);r['listing_current']=False
        for attempt in r.get('attempts',[]):
            if attempt['attempt_id']==r['intent']['attempt_id']:attempt['state']='reconciled_not_submitted'
        r.update(status='failed',status_updated_at=now.isoformat())
        r['events'].append({'at':now.isoformat(),'status':'failed','reason':'reconciled_not_submitted','evidence_sha256':w.digest(target)})
        save(root,r)


def record_historical_confirmation(root,identity,observed_url,evidence,now,occurred_at):
    """Explicit evidence import only; this API never calls a browser or submits."""
    import workspace as w
    timestamp(occurred_at)
    if not evidence.is_file():raise ValueError('confirmation_evidence_required')
    with w.writer(root):
        r=load(root,identity)
        if w.canonical_url(observed_url)!=r['canonical_listing_url']:raise ValueError('observed_job_mismatch')
        if r.get('submissions'):raise ValueError('already_confirmed')
        if not r.get('prepared'):raise ValueError('historical_snapshot_required')
        if r.get('intent',{}).get('state')=='begun':raise ValueError('use_existing_attempt_confirmation')
        attempt_id=uuid.uuid4().hex
        r['intent']={'attempt_id':attempt_id,'state':'begun','begun_at':now.isoformat(),'observed_job':r['canonical_listing_url'],'batch_id':'historical','category':'reconciled_history','basis':'explicit_evidence_import'}
        r['status']='submission_uncertain';save(root,r)
    return confirm(root,identity,attempt_id,evidence,now,occurred_at)
