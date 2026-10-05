"""Pin E15.var01 time-cycle report extension and excluded diagnostic parent."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD_CASE=HERE.parent/'E15-var01-time-based-cycle-v1.0.0'
def pin(path):
 raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def main():
 contract=load(HERE/'contract.json');run=HERE/'runs'/contract['run_id'];closure=load(run/'closure.json')
 old_index=load(OLD_CASE/'evidence-index.json');old=OLD_CASE/'runs'/old_index['run']['run_id'];old_closure=load(old/'closure.json')
 assert old_index['publication_state']=='excluded_diagnostic'
 assert pin(OLD_CASE/'evidence-index.json')['sha256']==contract['diagnostic_parent']['evidence_index_sha256']
 assert pin(old/'closure.json')['sha256']==contract['diagnostic_parent']['closure_sha256']
 assert old_closure['error']=='unreviewed converter diagnostic' and len(old_closure['raw'])==11
 for name,expected in old_closure['raw'].items(): assert pin(old/name)==expected==old_index['run']['raw'][name],name
 assert closure['run_id']==run.name and closure['error'] is None and closure['parent_closure_sha256']==pin(old/'closure.json')['sha256']
 assert closure['source_hashes_before']==closure['source_hashes_after'] and pin(run/'invocation.json')['sha256']==closure['invocation_sha256']
 assert len(closure['raw'])==4
 for name,expected in closure['raw'].items():assert pin(run/name)==expected,name
 author=load(HERE/'review/author-validation-2026-10-05.json');ind=load(HERE/'review/independent-verdict.json')
 assert author['passed'] and author['checks']==author['checks_passed']==138
 assert ind['passed'] and ind['decision']=='GO_BOUNDED_TIME_CYCLE_REPORT' and ind['checks_passed']==ind['checks_total']==755 and ind['v100_frozen_warning_gate']=='NO_GO_UNCHANGED'
 assert author['report_closure_sha256']==ind['new_closure_sha256']==pin(run/'closure.json')['sha256']
 names=sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and 'runs' not in p.relative_to(HERE).parts and '__pycache__' not in p.relative_to(HERE).parts and p.name!='evidence-index.json')
 required={'.gitattributes','.gitignore','README.md','contract.json','run_report_ssh.ps1','validate.py','make_evidence_index.py','cli-scope-signoff-2026-10-05.md','review/author-validation-2026-10-05.json','review/independent_replay.py','review/independent-verdict.json','review/preflight-2026-10-05.md','review/postrun-2026-10-05.md','review/static-preflight-2026-10-05.md','review/static-postrun-2026-10-05.md'}
 assert required<=set(names),sorted(required-set(names))
 index={'schema':'simlox-e15-var01-timecycle-evidence-index/v1','case_id':'E15','variant_id':'E15.var01','version':'1.0.1','publication_state':'not_published','source':{name:pin(HERE/name) for name in names},'diagnostic_parent':{'package':OLD_CASE.name,'evidence_index':pin(OLD_CASE/'evidence-index.json'),'closure':pin(old/'closure.json'),'raw_files_total':11,'publication_state':'excluded_diagnostic'},'run':{'run_id':run.name,'local_directory':str(run),'invocation':pin(run/'invocation.json'),'closure':pin(run/'closure.json'),'raw':closure['raw']},'raw_files_total':4,'author_checks':138,'independent_checks':755,'limits':contract['limits']}
 path=HERE/'evidence-index.json';path.write_bytes((json.dumps(index,indent=2)+'\n').encode())
 print(json.dumps({'index_sha256':pin(path)['sha256'],'old_raw':11,'new_raw':4,'sources':len(names)}))
if __name__=='__main__':main()