"""Bounded durable next-action controller. Synthetic execution only in v0.1."""
import argparse
import copy
from pathlib import Path
from answers import resolve_question
from batches import submit_capacity
from config import configuration,local_now
from eligibility import evaluate
from questions import register,store as question_store
from queue_state import recompute,block_on_answers,execution_guard
from stops import record_stop,retry_eligible,browser_stopped
import submission as submission

class AdapterError(Exception):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)

class UnsupportedAdapter:
    def discover(self):raise AdapterError('unsupported_live_capability')
    def inspect(self,context):raise AdapterError('unsupported_live_capability')
    def prepare(self,context):raise AdapterError('unsupported_live_capability')
    def observe(self,context):raise AdapterError('unsupported_live_capability')
    def submit(self,context):raise AdapterError('unsupported_live_capability')

class SyntheticAdapter:
    """Fictional catalog and confirmations; never opens or contacts an employer."""
    def __init__(self,catalog,failures=None):self.catalog=copy.deepcopy(catalog);self.failures=failures or {};self.calls=[]
    def discover(self):self.calls.append('discover');return copy.deepcopy(self.catalog)
    def inspect(self,context):
        self.calls.append('inspect')
        job=next((j for j in self.catalog if j['listing_url']==context['listing_url']),None)
        if not job:raise AdapterError('page_changed')
        return {'observed_url':job['listing_url'],'listing_current':True,'requirements_verified':job.get('requirements_verified',False),'requirements':job.get('requirements',{}),'form':job.get('form',[]),'layout':'synthetic-v1'}
    def prepare(self,context):
        self.calls.append('prepare')
        from forms import fill_common,SyntheticFormDriver,FormError
        fields=context['form']['form'];driver=SyntheticFormDriver(fields,context.get('history'))
        try:verified=fill_common(driver,fields,context['answers'],context['resume'],context.get('history'))
        except FormError as exc:raise AdapterError(exc.reason) from None
        return {**verified,'observed_url':context['listing_url']}
    def observe(self,context):self.calls.append('observe');return {'observed_url':context['listing_url']}
    def submit(self,context):
        self.calls.append('submit')
        if context['listing_url'] in self.failures:raise AdapterError(self.failures[context['listing_url']])
        return {'confirmation':'Synthetic confirmation. No employer contacted.'}


def batch_path(root,batch_id):
    import workspace as w
    return root/'runtime/batches'/(w.slug(batch_id)+'.json')


def initialize_batch(root,batch_id,quota):
    import workspace as w
    if type(quota) is not int or quota<0:raise ValueError('invalid_quota')
    path=batch_path(root,batch_id)
    with w.writer(root):
        if path.exists():
            batch=w.read(path)
            if batch['quota']!=quota:raise ValueError('batch_quota_immutable_use_new_batch')
            return batch
        batch={'batch_id':batch_id,'quota':quota,'discovery_done':False,'steps':0,'checkpoint':None}
        w.atomic_json(path,batch);return batch


def next_action(root,batch,now):
    import workspace as w
    stop=browser_stopped(root)
    if stop:return {'action':'stop','reason':stop['reason']}
    records=w.records(root);capacity=submit_capacity(records,batch['batch_id'],batch['quota'])
    if capacity['confirmed']>=batch['quota']:return {'action':'stop','reason':'quota_complete'}
    candidates=sorted([r for r in records if not r.get('submissions') and r['status'] in {'discovered','preparing','ready','failed'} and retry_eligible(r,now)],key=lambda r:(r.get('priority',1),r.get('captured_at',''),r['application_id']))
    for r in candidates:
        if r['status']=='ready':
            if capacity['remaining']<=0:continue
            action='submit'
        else:action='prepare' if r['status']=='preparing' and r.get('workflow',{}).get('phase')=='inspected' else 'inspect'
        return {'action':action,'application_id':r['application_id']}
    if not batch['discovery_done']:return {'action':'discover'}
    return {'action':'stop','reason':'pending_confirmation' if capacity['reserved'] else 'waiting_or_complete'}


def action_context(record):
    return {'application_id':record['application_id'],'listing_url':record['canonical_listing_url']}


def persist_record(root,record):
    import workspace as w
    with w.writer(root):submission.save(root,record)


def execute(root,batch,action,adapter,claim,now):
    import workspace as w
    kind=action['action'];identity=action.get('application_id')
    if kind=='discover':
        jobs=adapter.discover()
        if not isinstance(jobs,list):raise AdapterError('page_changed')
        for job in jobs:
            if not isinstance(job,dict):raise AdapterError('page_changed')
            w.capture(root,copy.deepcopy(job),now)
        batch['discovery_done']=True;return
    r=submission.load(root,identity);minimal=action_context(r)
    if kind=='inspect':
        observed=adapter.inspect(minimal)
        if w.canonical_url(observed['observed_url'])!=r['canonical_listing_url']:raise AdapterError('page_changed')
        eligibility=evaluate(observed,configuration(root)['rules']);r['eligibility']=eligibility
        r['listing_current']=observed.get('listing_current') is True
        if eligibility['decision']=='exclude':
            r.update(status='skipped',status_updated_at=now.isoformat());persist_record(root,r);return
        if eligibility['decision']=='needs_review':raise AdapterError('eligibility_review')
        fields=observed.get('form',[])
        if not isinstance(fields,list):raise AdapterError('unsupported_form')
        qids=[]
        for index,field in enumerate(fields):
            if field.get('field_type') in {'upload','history'}:continue
            if not field.get('key'):raise AdapterError('unsupported_form')
            spec={k:v for k,v in field.items() if k not in {'key','value'}}
            qid=register(root,identity,observed.get('layout','form'),field['key'],spec)['question_id'];qids.append(qid);field['question_id']=qid
        r.update(status='preparing',status_updated_at=now.isoformat(),required_question_ids=qids,workflow={'phase':'inspected','form':fields,'layout':observed.get('layout')})
        r.pop('stop',None);persist_record(root,r)
        questions={q['id']:q for q in question_store(root)['questions']}
        unresolved=[qid for qid in qids if questions[qid].get('required',True) and resolve_question(root,questions[qid],now)['status']!='resolved']
        if unresolved:block_on_answers(root,identity,unresolved,now)
        return
    if kind=='prepare':
        try:resume=execution_guard(root,r,now)
        except ValueError:raise AdapterError('resume_stale') from None
        questions={q['id']:q for q in question_store(root)['questions']};items=[];blocked=[]
        for qid in r.get('required_question_ids',[]):
            q=questions[qid];resolved=resolve_question(root,q,now)
            if resolved['status']!='resolved':
                if q.get('required',True):blocked.append(qid)
                continue
            answer=resolved['answer'];items.append({'question':q['text'],'question_spec':q,'answer':answer['value'],'source_answer_id':answer['id']})
        if blocked:block_on_answers(root,identity,blocked,now);return
        history=None
        if any(f.get('field_type')=='history' for f in r['workflow']['form']):
            from resolve_resume import timestamp
            path=root/'profile/history.json'
            if not path.is_file():raise AdapterError('outdated_fact')
            facts=w.read(path)
            if not facts.get('source',{}).get('id') or not facts.get('source',{}).get('version') or now>=timestamp(facts['review_due_at']):raise AdapterError('outdated_fact')
            history=facts['entries']
        verified=adapter.prepare({**minimal,'form':r['workflow'],'answers':items,'resume':resume,'history':history})
        if verified.get('verified') is not True or w.canonical_url(verified.get('observed_url',''))!=r['canonical_listing_url']:raise AdapterError('page_changed')
        target=root/'applications/records'/identity/'form-answers.json';w.atomic_json(target,items)
        with w.writer(root):w.event(root,argparse.Namespace(id=identity,status='ready',note='',resume_scope=resume['scope'],answers=target,evidence=None),now)
        return
    if kind=='submit':
        try:execution_guard(root,r,now);w.preflight(root,r,now)
        except ValueError:raise AdapterError('outdated_fact') from None
        observed=adapter.observe(minimal)
        intent=submission.begin_submit(root,identity,observed['observed_url'],claim,now,batch['batch_id'],r.get('category','default'),batch['quota'])
        confirmation=adapter.submit({**minimal,'attempt_id':intent['attempt_id'],'prepared':r['prepared']})
        if not confirmation or not confirmation.get('confirmation'):raise AdapterError('uncertain_submit')
        evidence=root/'applications/records'/identity/'adapter-confirmation.txt';evidence.write_text(confirmation['confirmation'])
        submission.confirm(root,identity,intent['attempt_id'],evidence,now,confirmation.get('occurred_at'))


def run(root,batch_id,adapter,quota=1,max_steps=10,clock=None):
    import workspace as w
    if type(max_steps) is not int or max_steps<0:raise ValueError('invalid_step_budget')
    clock=clock or (lambda:local_now(root));batch=initialize_batch(root,batch_id,quota);last={'action':'stop','reason':'step_budget'}
    with submission.browser_claim(root) as claim:
        for _ in range(max_steps):
            now=clock();recompute(root,now);last=next_action(root,batch,now)
            if last['action']=='stop':break
            batch['checkpoint']={**last,'phase':'started','at':now.isoformat()};w.atomic_json(batch_path(root,batch_id),batch)
            try:execute(root,batch,last,adapter,claim,now)
            except AdapterError as exc:
                if last.get('application_id'):record_stop(root,last['application_id'],exc.reason,now)
                else:
                    w.atomic_json(root/'runtime/browser-stop.json',{'reason':exc.reason,'at':now.isoformat(),'requires_resume':True})
                    last={'action':'stop','reason':exc.reason};break
            batch['steps']+=1;batch['checkpoint']={**last,'phase':'verified','at':now.isoformat()};w.atomic_json(batch_path(root,batch_id),batch)
        else:last={'action':'stop','reason':'step_budget'}
    capacity=submit_capacity(w.records(root),batch_id,quota)
    return {'reason':last.get('reason','checkpoint'),'steps':batch['steps'],**capacity,'export':w.refresh_export(root)}
