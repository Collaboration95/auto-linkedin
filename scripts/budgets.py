"""Enforce action-boundary budgets from measured time/counters only."""
from datetime import timedelta
import math
from resolve_resume import timestamp


def policy(config,now,deadline=None):
    options=config.get('budgets',{})
    duration=options.get('duration_seconds',900)
    if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0:raise ValueError('invalid_duration_budget')
    result={'deadline':timestamp(deadline).isoformat() if deadline else (now+timedelta(seconds=duration)).isoformat(),'max_actions':options.get('max_actions',100),'max_retries':options.get('max_retries',3),'provider_token_limit':options.get('provider_token_limit'),'provider_cost_limit':options.get('provider_cost_limit')}
    for key in ['max_actions','max_retries']:
        if type(result[key]) is not int or result[key]<0:raise ValueError('invalid_work_budget')
    for key in ['provider_token_limit','provider_cost_limit']:
        if result[key] is not None and (type(result[key]) not in (int,float) or not math.isfinite(result[key]) or result[key]<0):raise ValueError('invalid_provider_budget')
    return result


def stop_reason(batch,now,usage=None):
    limits=batch['budgets']
    if now>=timestamp(limits['deadline']):return 'deadline'
    if batch['steps']>=limits['max_actions']:return 'action_budget'
    if batch.get('retries',0)>=limits['max_retries'] and batch.get('retries',0)>0:return 'retry_budget'
    for limit_key,usage_key in [('provider_token_limit','tokens'),('provider_cost_limit','cost_usd')]:
        limit=limits.get(limit_key)
        if limit is None:continue
        measured=(usage or {}).get(usage_key)
        if type(measured) not in (int,float) or not math.isfinite(measured) or measured<0:return 'provider_usage_unavailable'
        if measured>=limit:return 'provider_budget'
    return None
