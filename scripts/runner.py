"""Bounded durable next-action controller. Synthetic execution only in v0.1."""
import argparse
import copy
from pathlib import Path
from answers import resolve_question
from batches import submit_capacity
from config import configuration,local_now,private_path
from eligibility import evaluate
from questions import register,store as question_store
from queue_state import recompute,block_on_answers,execution_guard
from stops import record_stop,retry_eligible,browser_stopped
import submission as submission

class AdapterError(Exception):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)

class BoundaryStop(Exception):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)

class UnsupportedAdapter:
    def measured_usage(self):return None
    def discover(self):raise AdapterError('unsupported_live_capability')
    def inspect(self,context):raise AdapterError('unsupported_live_capability')
    def prepare(self,context):raise AdapterError('unsupported_live_capability')
    def observe(self,context):raise AdapterError('unsupported_live_capability')
    def submit(self,context):raise AdapterError('unsupported_live_capability')

class SyntheticAdapter:
    """Fictional catalog and confirmations; never opens or contacts an employer."""
    def __init__(self,catalog,failures=None):self.catalog=copy.deepcopy(catalog);self.failures=failures or {};self.calls=[];self.pages={};self.root=None
    def bind_workspace(self,root):
        import workspace as w
        self.root=root;p=root/'runtime/synthetic-pages.json'
        self.pages=w.read(p) if p.exists() else {}
    def job(self,url):
        import workspace as w
        job=next((j for j in self.catalog if isinstance(j,dict) and isinstance(j.get('listing_url'),str) and w.canonical_url(j['listing_url'])==url),None)
        if not job:raise AdapterError('page_changed')
        return job
    def measured_usage(self):return None
    def discover(self):self.calls.append('discover');return copy.deepcopy(self.catalog)
    def inspect(self,context):
        self.calls.append('inspect')
        job=self.job(context['listing_url'])
        if not job:raise AdapterError('page_changed')
        return {'observed_url':job['listing_url'],'listing_current':True,'requirements_verified':job.get('requirements_verified',False),'requirements':job.get('requirements',{}),'form':job.get('form',[]),'layout':'synthetic-v1'}
    def prepare(self,context):
        self.calls.append('prepare')
        from forms import fill_common,SyntheticFormDriver,FormError
        fields=context['form']['form'];job=self.job(context['listing_url']);driver=SyntheticFormDriver(job.get('form',[]),job.get('history'))
        try:verified=fill_common(driver,fields,context['answers'],context['resume'],context.get('history'))
        except FormError as exc:raise AdapterError(exc.reason) from None
        self.pages[context['listing_url']]=driver.snapshot()
        if self.root:
            import workspace as w
            w.atomic_json(self.root/'runtime/synthetic-pages.json',self.pages)
        return {**verified,'observed_url':context['listing_url']}
    def observe(self,context):
        self.calls.append('observe');job=self.job(context['listing_url'])
        page=copy.deepcopy(self.pages.get(context['listing_url'],{'values':{},'uploads':{},'history':None}))
        page['fields']=copy.deepcopy(job.get('form',[]))
        if 'page_values' in job:page['values']=job['page_values']
        if 'selected_resume_sha256' in job:page['uploads']={f['key']:job['selected_resume_sha256'] for f in page['fields'] if f.get('field_type')=='upload'}
        if 'history' in job:page['history']=job['history']
        return {'observed_url':job['listing_url'],'listing_current':True,'requirements_verified':job.get('requirements_verified',False),'requirements':copy.deepcopy(job.get('requirements',{})),'page':page}
    def submit(self,context):
        self.calls.append('submit')
        if context['listing_url'] in self.failures:raise AdapterError(self.failures[context['listing_url']])
        return {'confirmation':'Synthetic confirmation. No employer contacted.'}


def batch_path(root,batch_id):
    import workspace as w
    return root/'runtime/batches'/(w.slug(batch_id)+'.json')


def initialize_batch(root,batch_id,quota,now=None,deadline=None):
    import workspace as w
    if type(quota) is not int or quota<0:raise ValueError('invalid_quota')
    path=batch_path(root,batch_id)
    with w.writer(root):
        if path.exists():
            batch=w.read(path)
            if batch['quota']!=quota:raise ValueError('batch_quota_immutable_use_new_batch')
            return batch
        from budgets import policy
        batch={'budgets':policy(configuration(root),now or local_now(root),deadline),'retries':0,'batch_id':batch_id,'quota':quota,'discovery_done':False,'steps':0,'checkpoint':None}
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


def execute(root,batch,action,adapter,claim,now,clock=None):
    import workspace as w
    clock=clock or (lambda:local_now(root))
    kind=action['action'];identity=action.get('application_id')
    if kind=='discover':
        jobs=adapter.discover()
        if not isinstance(jobs,list):raise AdapterError('page_changed')
        from context import content_version
        fingerprint=content_version(jobs)
        if batch.get('discovery_fingerprint',fingerprint)!=fingerprint:raise AdapterError('page_changed')
        batch['discovery_fingerprint']=fingerprint
        limit=configuration(root).get('max_discovery_items',100)
        if type(limit) is not int or limit<1:raise ValueError('invalid_discovery_budget')
        for index in range(batch.get('discovery_cursor',0),min(len(jobs),limit)):
            try:
                if not isinstance(jobs[index],dict):raise ValueError('invalid_discovery_item')
                w.capture(root,copy.deepcopy(jobs[index]),now)
            except (ValueError,KeyError,TypeError,OSError):
                batch.setdefault('discovery_failures',[]).append({'item_index':index,'reason':'invalid_discovery_item'})
            batch['discovery_cursor']=index+1;w.atomic_json(batch_path(root,batch['batch_id']),batch)
        if len(jobs)>limit:batch.setdefault('discovery_failures',[]).append({'reason':'discovery_item_budget'})
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
        observed=adapter.observe(minimal)
        submit_now=clock()
        from budgets import stop_reason
        budget_reason=stop_reason(batch,submit_now,adapter.measured_usage() if hasattr(adapter,'measured_usage') else None)
        if budget_reason:raise BoundaryStop(budget_reason)
        if observed.get('listing_current') is not True:raise AdapterError('page_changed')
        current_eligibility=evaluate(observed,configuration(root)['rules'])
        if current_eligibility['decision']!='include':raise AdapterError('eligibility_review')
        from forms import verify_common,FormError
        try:
            execution_guard(root,r,submit_now);w.preflight(root,r,submit_now)
            items=w.read(private_path(root,r['prepared']['answers_path']))
            exact={'path':str(private_path(root,r['prepared']['exact_resume_copy'])),'sha256':r['prepared']['sha256']}
            history=w.read(root/'profile/history.json')['entries'] if (root/'profile/history.json').exists() else None
            verify_common(observed.get('page',{}),r.get('workflow',{}).get('form',[]),items,exact,history)
        except FormError as exc:raise AdapterError(exc.reason) from None
        except (ValueError,KeyError,OSError):raise AdapterError('outdated_fact') from None
        intent=submission.begin_submit(root,identity,observed['observed_url'],claim,submit_now,batch['batch_id'],r.get('category','default'),batch['quota'])
        confirmation=adapter.submit({**minimal,'attempt_id':intent['attempt_id'],'prepared':r['prepared']})
        if not confirmation or not confirmation.get('confirmation'):raise AdapterError('uncertain_submit')
        evidence=root/'applications/records'/identity/'adapter-confirmation.txt';evidence.write_text(confirmation['confirmation'])
        submission.confirm(root,identity,intent['attempt_id'],evidence,clock(),confirmation.get('occurred_at'))


def run(root,batch_id,adapter,quota=1,max_steps=10,clock=None,deadline=None,timer=None):
    import workspace as w
    if type(max_steps) is not int or max_steps<0:raise ValueError('invalid_step_budget')
    import time
    timer=timer or time.perf_counter
    clock=clock or (lambda:local_now(root));batch=initialize_batch(root,batch_id,quota,clock(),deadline);last={'action':'stop','reason':'step_budget'}
    if hasattr(adapter,'bind_workspace'):adapter.bind_workspace(root)
    with submission.browser_claim(root) as claim:
        for _ in range(max_steps):
            now=clock()
            from budgets import stop_reason
            usage=adapter.measured_usage() if hasattr(adapter,'measured_usage') else None
            budget_reason=stop_reason(batch,now,usage)
            if budget_reason:last={'action':'stop','reason':budget_reason};break
            recompute(root,now);last=next_action(root,batch,now)
            if last['action']=='stop':break
            batch['checkpoint']={**last,'phase':'started','at':now.isoformat()};w.atomic_json(batch_path(root,batch_id),batch)
            stage_start=timer();stage_retry=0
            try:execute(root,batch,last,adapter,claim,now,clock)
            except AdapterError as exc:
                if exc.reason in {'timeout','throttled'}:batch['retries']+=1;stage_retry=1
                if last.get('application_id'):record_stop(root,last['application_id'],exc.reason,now,batch['budgets']['max_retries'])
                else:
                    w.atomic_json(root/'runtime/browser-stop.json',{'reason':exc.reason,'at':now.isoformat(),'requires_resume':True})
                    last={'action':'stop','reason':exc.reason};break
            except BoundaryStop as exc:
                last={'action':'stop','reason':exc.reason};break
            except KeyboardInterrupt:
                batch['checkpoint']={**last,'phase':'interrupted','at':clock().isoformat()};w.atomic_json(batch_path(root,batch_id),batch)
                last={'action':'stop','reason':'interrupted'};break
            from metrics import record_stage
            reused=0
            if last['action']=='prepare':
                prepared=submission.load(root,last['application_id']).get('prepared')
                if prepared:reused=len(w.read(private_path(root,prepared['answers_path'])))
            record_stage(root,batch_id,last['action'],max(0,timer()-stage_start),stage_retry,reused,adapter.measured_usage() if hasattr(adapter,'measured_usage') else None)
            batch['steps']+=1;batch['checkpoint']={**last,'phase':'verified','at':now.isoformat()};w.atomic_json(batch_path(root,batch_id),batch)
        else:last={'action':'stop','reason':'step_budget'}
    capacity=submit_capacity(w.records(root),batch_id,quota)
    handoff={'reason':last.get('reason','checkpoint'),'steps':batch['steps'],**capacity,'provider_usage':adapter.measured_usage() if hasattr(adapter,'measured_usage') else None}
    batch['handoff']=handoff;w.atomic_json(batch_path(root,batch_id),batch)
    return {**handoff,'export':w.refresh_export(root)}
