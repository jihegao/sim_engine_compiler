"""Freeze exact v106 replay-only sources and observed evidence once; no native calls."""
import datetime as dt
import hashlib
import json
import stat
from pathlib import Path
CASE=Path(__file__).resolve().parent
OUT=CASE/'replay-source-freeze-v106.json'
OLD=CASE.with_name('I05-var01-scheduled-cm-location-v1.0.5')
METHOD=CASE/'review/independent-method-source-review-v106.md'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def seal(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def main():
 if OUT.exists():raise FileExistsError('frozen replay manifest already exists')
 c=load(CASE/'contract.json');binding=load(CASE/'evidence-reference.json')
 assert c['schema']=='simlox-i05-var01-contract/v106' and c['version']=='1.0.6'
 assert c['candidate']['run_id']=='i05-var01-cmloc-v106-replay-20261010-01' and c['candidate']['native_dispatch_allowed'] is False
 assert binding['observed_native_run_id']=='i05-var01-cmloc-v105-ssh-20261010-01' and binding['new_native_calls']==0
 assert 'GO_METHOD_ONLY' in METHOD.read_text(encoding='utf-8')
 assert seal(CASE/'report-oracle.json')['sha256']==c['report_oracle']['sha256']
 assert seal(CASE/'native-input.json')['sha256']==c['candidate']['native_input_sha256']
 original=Path(binding['original_directory']);recovered=Path(binding['recovered_directory'])
 assert len(binding['raw'])==26
 sources=[];paths=set()
 def add(key,p,role):
  p=p.resolve();assert p.is_file() and str(p) not in paths
  paths.add(str(p));sources.append({'key':key,'role':role,'path':str(p),**seal(p)})
 for p in sorted(CASE.rglob('*')):
  if p.is_file() and 'review' not in p.relative_to(CASE).parts and '__pycache__' not in p.parts and p!=OUT:
   add('current:'+p.relative_to(CASE).as_posix(),p,'current_replay_source')
 add('review:independent-method-source-review-v106',METHOD,'independent_method_review')
 for name,s in sorted(binding['raw'].items()):
  for role,d in [('original',original),('recovered',recovered)]:
   p=d/name;assert seal(p)==s and not p.stat().st_mode & stat.S_IWRITE
   add(role+':'+name,p,'sealed_observed_raw')
 for key,s in binding['original_context'].items():
  p=Path(s['path']);assert seal(p)=={k:s[k] for k in ('bytes','sha256')}
  if str(p.resolve()) not in paths:add('observed-context:'+key,p,'observed_native_context')
 for key in ['author_custody','original_independent_no_go','original_independent_diagnosis']:
  s=binding[key];p=Path(s['path']);assert seal(p)=={k:s[k] for k in ('bytes','sha256')};add('custody:'+key,p,'preserved_failure_diagnosis')
 prior=load(OLD/'prelaunch-manifest-v105-run01.json');historical=[]
 for s in prior['sources']:
  p=Path(s['path']);actual=seal(p);assert actual=={k:s[k] for k in ('bytes','sha256')},s['key']
  historical.append({**s,'matched_at_freeze':True})
 python=Path(c['execution_environment']['tooling_python']['path'])
 assert seal(python)=={k:c['execution_environment']['tooling_python'][k] for k in ('bytes','sha256')}
 add('environment:python',python,'tooling_runtime')
 pins=load(CASE/'parent-evidence-pins.json')
 # The accepted parent raw path is declared by the preserved report/event source contracts.
 oracle=load(CASE/'report-oracle.json');parent=Path(oracle['parent_report_raw_path']).parent
 for name in ['model.log','report-raw.json','invocation.json','closure.json']:
  add('accepted-parent:'+name,parent/name,'accepted_parent_raw')
 manual=Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf')
 assert seal(manual)['sha256']==c['manual_basis']['sha256'];add('primary:manual',manual,'primary_semantic_source')
 result={'schema':'simlox-i05-var01-replay-source-freeze/v106','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'replay_id':c['candidate']['run_id'],'observed_native_run_id':binding['observed_native_run_id'],'native_calls':0,'accepted_parent_runs_repeated':0,'method_review_sha256':seal(METHOD)['sha256'],'source_count':len(sources),'sources':sources,'historical_v105_prelaunch_sources':historical,'historical_source_count':241,'historical_source_check':'All241 matched at freeze. Original v105 manifest is historical and must not be edited/reused. Its live publication index may advance after authorized publication; immutable selection snapshot is included as current source. Postrun behavior reader uses current oracle/parent/raw, not live publication index.','expected_log_line_count':128,'expected_event_substitutions':18,'expected_report_typed_cells':4044,'original_native_status':'NO_GO_REPORT_PROJECTION','current_replay_acceptance':'pending_independent_exact_source_and_raw_review','publication_state':'not_published'}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 for s in sources:
  if s['role'] in ('current_replay_source','independent_method_review'):Path(s['path']).chmod(stat.S_IREAD)
 OUT.chmod(stat.S_IREAD)
 print(json.dumps({'manifest':str(OUT),**seal(OUT),'source_count':len(sources),'historical_sources':len(historical),'native_calls':0},ensure_ascii=False))
if __name__=='__main__':main()