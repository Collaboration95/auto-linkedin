#!/usr/bin/env python3
"""Offline synthetic release scenario. Requires an empty disposable workspace."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from config import select_workspace
from setup_workspace import initialize,doctor
from runner import run,SyntheticAdapter,batch_path
from questions import inbox
from answer_import import import_changes
from answers import store
from metrics import summary
import submission as submission
import workspace as w


def pdf_bytes():
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>',b'<< /Length 0 >>\nstream\n\nendstream']
    result=b'%PDF-1.4\n';offsets=[0]
    for index,value in enumerate(objects,1):offsets.append(len(result));result+=str(index).encode()+b' 0 obj\n'+value+b'\nendobj\n'
    start=len(result);result+=b'xref\n0 5\n0000000000 65535 f \n'+b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:]);result+=f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode();return result


def scenario(root):
    if root.exists() and any(root.iterdir()):raise ValueError('empty_synthetic_workspace_required')
    initialize(root);now=datetime.now(timezone.utc);due=(now+timedelta(days=30)).isoformat()
    w.atomic_json(root/'config.json',{'timezone':'UTC','resume_scope':'backend','browser':'unsupported','defer_export':True,'rules':{'allowed_countries':['AA'],'experience_years':3,'requires_sponsorship':False}})
    master=root/'resumes/master.md';master.write_text('# Fictional Candidate\nSynthetic reference only.\n')
    original=root/'resumes/synthetic-resume.pdf';original.write_bytes(pdf_bytes());before=original.read_bytes()
    releases=[]
    for identity,scope,purpose,path in [('master-v1','master','reference',master),('selected-v1','backend','application',original)]:
        releases.append({'id':identity,'scope':scope,'purpose':purpose,'status':'active','path':str(path.relative_to(root)),'sha256':w.digest(path),'released_at':(now-timedelta(days=1)).isoformat(),'effective_from':(now-timedelta(days=1)).isoformat(),'review_due_at':due,'valid_until':None,'selected_projects':[],'source_master_id':None if scope=='master' else 'master-v1'})
    releases[1].update(original_source={'path':'resumes/synthetic-resume.pdf','sha256':w.digest(original)},selected_with_master_id='master-v1')
    w.atomic_json(root/'resumes/registry.json',{'releases':releases})
    w.atomic_json(root/'profile/answers.json',{'schema_version':1,'revision':0,'answers':[{'id':'name','value':'Fictional Candidate','field_type':'text','scope':{},'aliases':['Application name'],'source':{'id':'synthetic-review','version':1,'kind':'user'},'review_due_at':due}],'imports':{}})
    history=[{'company':'Fictional Systems','role':'Engineer'}];w.atomic_json(root/'profile/history.json',{'entries':history,'source':{'id':'synthetic-review','version':1},'review_due_at':due})
    fields=[{'key':'name','text':'Application name','field_type':'text'},{'key':'schedule','text':'Preferred schedule?','field_type':'select','options':['Day','Night']},{'key':'resume','text':'Selected resume','field_type':'upload'},{'key':'history','text':'Work history','field_type':'history'}]
    jobs=[]
    for index in range(4):
        jobs.append({'company':'Fictional Employer '+str(index),'role':'Engineer','location':'Synthetic region','platform':'synthetic','platform_job_id':str(index),'listing_url':'https://example.org/jobs/'+str(index),'job_description':'Synthetic complete job description.','requirements_verified':True,'requirements':{'country':{'value':'BB' if index==2 else 'AA','strength':'hard'},'experience':{'minimum':'3+','strength':'hard'}},'form':fields if index<2 else [],'history':history})
    adapter=SyntheticAdapter(jobs,{jobs[3]['listing_url']:'timeout'});first=run(root,'scenario',adapter,3,30,lambda:now)
    assert first['confirmed']==0 and first['reserved']==1
    records=w.records(root);assert sum(r['status']=='awaiting_answer' for r in records)==2 and sum(r['status']=='skipped' for r in records)==1
    questions=inbox(root,now);unknown=[q for q in questions if q['status']=='unresolved'];assert len(unknown)==1 and len(unknown[0]['occurrences'])==2
    q=unknown[0];payload={'schema_version':1,'change_id':'synthetic-reviewed-batch','base_revision':0,'changes':[{'question_id':q['id'],'question_version':q['question_version'],'value':'Day','scope':q.get('scope',{}),'review_due_at':due}]}
    w.atomic_json(root/'answer-changes.json',payload);import_changes(root,payload,now);assert import_changes(root,payload,now)['mutation']=='already_imported'
    second=run(root,'scenario',SyntheticAdapter(jobs),3,30,lambda:now);assert second['confirmed']==2 and second['reserved']==1
    records=w.records(root);confirmed=next(r for r in records if r.get('submissions'))
    with submission.browser_claim(root) as claim:
        try:submission.begin_submit(root,confirmed['application_id'],confirmed['canonical_listing_url'],claim,now,'scenario')
        except ValueError as exc:assert str(exc)=='already_confirmed'
        else:raise AssertionError('duplicate_submit_not_blocked')
    uncertain=next(r for r in records if r['status']=='submission_uncertain');evidence=root/'synthetic-reconciliation.txt';evidence.write_text('Synthetic delayed observed confirmation; no employer contacted.')
    submission.confirm(root,uncertain['application_id'],uncertain['intent']['attempt_id'],evidence,now+timedelta(seconds=1),now.isoformat())
    with patch('workspace.export_dashboard',side_effect=OSError('synthetic export fault')):assert w.refresh_export(root,False)['status']=='failed'
    assert w.refresh_export(root,False)['status']=='exported'
    final=run(root,'scenario',SyntheticAdapter(jobs),3,5,lambda:now);assert final['confirmed']==3 and final['reserved']==0 and final['reason']=='quota_complete'
    deadline=run(root,'deadline-check',SyntheticAdapter([]),1,3,lambda:now,deadline=now.isoformat());assert deadline['reason']=='deadline'
    fixture=Path(__file__).resolve().parents[1]/'fixtures';destination=root/'form-smoke';destination.mkdir()
    for name in ('form.html','form-adapter.js'):shutil.copyfile(fixture/name,destination/name)
    assert original.read_bytes()==before and (root/'dashboard/index.html').is_file()
    data=w.read(root/'dashboard/data/applications.json');assert data['questions'] and len(data['applications'])==4 and all(q['status']=='resolved' for q in data['questions'])
    assert doctor(root)['ready'];metrics=summary(root,'scenario');assert metrics['unique_confirmed']==3
    return {'scenario':'passed','unique_confirmed':3,'shared_answer_imports':1,'excluded':1,'duplicate_refused':True,'uncertain_reconciled':True,'export_recovered':True,'deadline_and_quota_enforced':True,'local_form_fixture':'available','live_employer_submission':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path);args=parser.parse_args()
    try:
        if args.workspace:result=scenario(select_workspace(args.workspace))
        else:
            with tempfile.TemporaryDirectory(prefix='synthetic-smoke-') as directory:result=scenario(Path(directory))
        import json
        print(json.dumps(result,sort_keys=True))
    except (ValueError,OSError,AssertionError):parser.exit(1,'Synthetic smoke failed; private details withheld.\n')

if __name__=='__main__':main()
