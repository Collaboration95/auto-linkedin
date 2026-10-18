"""Local measured effort and a strict numeric-only shareable summary."""
import math

STAGES={'discover','inspect','prepare','submit'}


def number(value):return value if type(value) in (int,float) and math.isfinite(value) and value>=0 else None


def usage_values(usage):return {key:number((usage or {}).get(key)) for key in ('tokens','cost_usd')}


def record_stage(root,batch_id,stage,duration,retries=0,answer_reuse=0,usage=None):
    import workspace as w
    if stage not in STAGES or number(duration) is None:raise ValueError('invalid_metric')
    with w.writer(root):
        path=root/'runtime/metrics.json';data=w.read(path) if path.exists() else {'schema_version':1,'events':[]}
        data['events'].append({'batch_id':batch_id,'stage':stage,'duration_seconds':duration,'retries':retries,'answer_reuse':answer_reuse,'provider_usage':usage_values(usage)})
        w.atomic_json(path,data)


def summary(root,batch_id=None):
    import workspace as w
    path=root/'runtime/metrics.json';data=w.read(path) if path.exists() else {'events':[]};stages={};retries=0;reuse=0;usage={'tokens':None,'cost_usd':None}
    for event in data['events']:
        if batch_id is not None and event.get('batch_id')!=batch_id:continue
        stage=event.get('stage');duration=number(event.get('duration_seconds'))
        if stage not in STAGES or duration is None:continue
        stages[stage]=stages.get(stage,0)+duration;retries+=number(event.get('retries')) or 0;reuse+=number(event.get('answer_reuse')) or 0
        measured=usage_values(event.get('provider_usage'))
        for k,v in measured.items():
            if v is not None:usage[k]=max(usage[k] or 0,v)
    records=w.records(root);attempts=set();confirmed=set()
    for r in records:
        attempts.update(a['attempt_id'] for a in r.get('attempts',[]) if batch_id is None or a.get('batch_id')==batch_id)
        if any(batch_id is None or s.get('batch_id')==batch_id for s in r.get('submissions',[])):confirmed.add(r['canonical_listing_url'])
    total=sum(stages.values())
    return {'attempted_submissions':len(attempts),'unique_confirmed':len(confirmed),'stage_seconds':dict(sorted(stages.items())),'seconds_per_unique_confirmed':total/len(confirmed) if confirmed else None,'retries':retries,'answer_reuse':reuse,'provider_usage':usage}
