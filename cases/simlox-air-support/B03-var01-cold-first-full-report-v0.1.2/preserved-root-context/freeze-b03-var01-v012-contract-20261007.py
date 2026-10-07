from pathlib import Path
import hashlib,json,stat,subprocess,sys
from datetime import datetime,timezone
r=Path(__file__).resolve().parents[1]
p=r/'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.2'
expected_sha=sys.argv[1]
b=(p/'contract.json').read_bytes()
assert hashlib.sha256(b).hexdigest()==expected_sha
c=json.loads(b);checks=[]
def check(data,pin,label):
    actual={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    assert actual=={k:pin[k] for k in actual},(label,actual,pin)
    checks.append(label)
assert c['version']=='0.1.2' and c['preservation_and_limits']['no_new_native']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()==c['base_commit']
for rec in c['accepted_source_files']:
    check((r/rec['path']).read_bytes(),rec['local_disk'],'disk:'+rec['path'])
    check(subprocess.check_output(['git','show',c['base_commit']+':'+rec['path']],cwd=r),rec['published_git_at_base'],'git:'+rec['path'])
for rec in c['installed'].values():check(Path(rec['path']).read_bytes(),rec,rec['path'])
for run in c['parent_runs']:
    d=Path(run['original_directory'])
    for field,name in [('closure','closure.json'),('invocation','invocation.json')]:check((d/name).read_bytes(),run[field],run['run_id']+'/'+name)
    for group in ['raw','other_local_files']:
        for name,pin in run[group].items():check((d/name).read_bytes(),pin,run['run_id']+'/'+name)
    closure=json.loads((d/'closure.json').read_text(encoding='utf-8-sig'))
    assert closure['raw']==run['raw'] and closure['invocation_sha256']==run['invocation']['sha256']
    v=json.loads((d/'validation.json').read_text(encoding='utf-8-sig'))
    assert v['passed']==(run['status']=='ACCEPTED_PARENT_RUN')
    assert bool(v['differences'])!=(run['status']=='ACCEPTED_PARENT_RUN')
g=c['full_report_gate'];z=g['system_zero_field_basis']
assert g['total_cells']==sum(t['rows']*t['columns'] for t in g['native_tables_in_order'])==4044
assert z['bounded_native_presentation_fields']==dict.fromkeys(['NSYAL','STREQ','STF','STLOW','SYDTU'],0)
assert z['bounded_native_presentation_cells']==360
rec=g['B02_format_corroboration'];check(Path(rec['original_path']).read_bytes(),rec['local_disk'],'B02 presentation context')
copies=[]
for section in ['excluded_v010','excluded_v011']:
    for key in ['files','root_probe_context']:
        for rec in c[section].get(key,[]):
            orig=(r/rec['original_path']).read_bytes();check(orig,rec,'archive original:'+rec['original_path'])
            assert (p/rec['inert_copy_path']).read_bytes()==orig,rec
            copies.append(rec['inert_copy_path'])
assert not list(p.glob('*.py')) and not (p/'review').exists()
assert all(f.name not in ['.gitattributes','.gitignore'] for f in (p/'preserved-v011').rglob('*') if f.is_file())
files=[]
for f in sorted(p.rglob('*')):
    if f.is_file():
        data=f.read_bytes();files.append({'path':f.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});f.chmod(stat.S_IREAD)
assert len(files)==3+len(set(copies)),(len(files),len(set(copies)))
out=r/'tmp/b03-var01-v012-root-contract-freeze-20261007.json';assert not out.exists()
v={'decision':'ROOT_V012_CONTRACT_FROZEN_AWAIT_INDEPENDENT_GO','utc':datetime.now(timezone.utc).isoformat(),'contract_sha256':expected_sha,'checks':checks,'files':files,'new_native_runs':0,'active_methods':0,'old_versions_remain_no_go':True,'overall_goal':'unfinished'}
out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');out.chmod(stat.S_IREAD)
print(json.dumps({'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(files),'checks':len(checks),'contract_sha256':expected_sha}))
