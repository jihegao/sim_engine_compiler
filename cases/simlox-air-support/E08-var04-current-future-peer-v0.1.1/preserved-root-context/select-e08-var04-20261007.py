import hashlib,json,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[1];cases=r/'cases/simlox-air-support';ref='66eefcedd8108249ebd73eebdc0a205e15ae84e2'
def git(*args):return subprocess.check_output(['git',*args],cwd=r)
assert git('rev-parse','HEAD').decode().strip()==ref
assert not git('status','--porcelain','--untracked-files=no').strip()
catalog=json.loads((cases/'publication-index-v1.json').read_bytes());assert len(catalog['entries'])==488
assert not any(x.get('variant_id')=='E08.var04' for x in catalog['entries'])
assert not (cases/'E08-var04-current-future-peer-v0.1.0').exists()
packages=['E08-var01-immediate-lateral-v1.0.2','E08-var03-delayed-lateral-v1.0.0'];parents=[]
for name in packages:
 p=cases/name;index=json.loads((p/'evidence-index.json').read_bytes());records=[]
 for file,sha in index['source_files_sha256'].items():
  f=p/file;b=f.read_bytes();g=git('show',ref+':'+f.relative_to(r).as_posix());assert hashlib.sha256(b).hexdigest()==sha,file
  assert b==g,(name,file)
  records.append({'path':file,'bytes':len(b),'local_sha256':sha,'git_sha256':hashlib.sha256(g).hexdigest()})
 b=(p/'evidence-index.json').read_bytes();assert b==git('show',ref+':'+(p/'evidence-index.json').relative_to(r).as_posix())
 parents.append({'package':name,'source_files':records,'index_sha256':hashlib.sha256(b).hexdigest(),'index_keys':list(index),'publication_entry':next(e for e in catalog['entries'] if e['package']==name)})
receipt={'decision':'ELIGIBLE_FOR_INDEPENDENT_CONTRACT_ONLY','variant_id':'E08.var04','package':'E08-var04-current-future-peer-v0.1.0','base':ref,'branch':git('branch','--show-current').decode().strip(),'catalog_entries':488,'parents':parents,'native_plan':'read-only reuse; no native or report export','ownership':{'app_inventory_50':'only original issue18 Codex chat active','authenticated_open_pr_search':'E08 var04 zero results','remote_var04_branch_search':'zero results','worktree_var04_owner':'none'},'actual_ssh_observation':{'utc':'2026-10-07T10:16:50.1385474Z','self_pid':8352,'session':0,'ps_major':5,'mutex_free':True,'gui_pid':13340,'gui_session':1,'gui_start_ms':1790590196826,'responding':True,'active_wts_session1':1,'runner_candidates':[]},'limits':'Cross-package source topologies differ; not isolated causal timing test. Contract must enumerate every delta and use only accepted bounded observations.','issue18_unfinished':True,'k01_k08':'blocked, no retries','i07_opening_three':'excluded'}
out=r/'tmp/e08-var04-root-owner-selection-20261007.json';assert not out.exists();out.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');out.chmod(0o444)
print(json.dumps({'decision':receipt['decision'],'source_pins':sum(len(x['source_files']) for x in parents),'receipt_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'index_keys':{x['package']:x['index_keys'] for x in parents}}))
