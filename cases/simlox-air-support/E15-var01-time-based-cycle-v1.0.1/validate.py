"""Author replay for E15.var01 v1.0.1 from immutable native evidence."""
from __future__ import annotations
import hashlib, json, re, difflib
from pathlib import Path
from copy import deepcopy

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OLD_CASE=ROOT/'E15-var01-time-based-cycle-v1.0.0'
OLD=OLD_CASE/'runs/e15-var01-timecycle-v100-ssh-20261005-01'
RUN=HERE/'runs/e15-var01-timecycle-report-v101-ssh-20261005-01'
E15=ROOT/'E15-var07-explicit-istoh-v1.0.1'
PARENT=E15/'runs/e15-var07-default-v101-ssh-20261002-01'
PARENT_REPORT=E15/'runs/e15-var07-default-item-v101-ssh-20261002-01/item-report-raw.json'
checks=0;failures=[]
def check(ok,label):
 global checks
 checks+=1
 if not ok:failures.append(label)
def pin(path):
 raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sealed(path,expected):return path.is_file() and pin(path)==expected
contract=load(HERE/'contract.json');old_index=load(OLD_CASE/'evidence-index.json')
old_closure=load(OLD/'closure.json');old_outcome=load(OLD/'outcome.json')
closure=load(RUN/'closure.json');inv=load(RUN/'invocation.json');outcome=load(RUN/'outcome.json');steps=load(RUN/'steps.json')
check(contract['run_id']==RUN.name==closure['run_id']==inv['run_id'],'run identity')
check(old_index['publication_state']=='excluded_diagnostic' and old_index['run']['run_id']==OLD.name,'original exclusion')
check(pin(OLD_CASE/'evidence-index.json')['sha256']==contract['diagnostic_parent']['evidence_index_sha256'],'old index pin')
check(pin(OLD/'closure.json')['sha256']==contract['diagnostic_parent']['closure_sha256'],'old closure pin')
check(old_closure['error']=='unreviewed converter diagnostic' and old_closure['source_hashes_before']==old_closure['source_hashes_after'],'old frozen failure and source stability')
check(len(old_closure['raw'])==11 and old_index['run']['raw']==old_closure['raw'],'old raw inventory')
for name,expected in old_closure['raw'].items():check(sealed(OLD/name,expected),'old raw '+name)
check(closure['error'] is None and outcome['error'] is None and outcome['status']=='completed','report success')
check(closure['parent_run_id']==OLD.name and closure['parent_closure_sha256']==pin(OLD/'closure.json')['sha256'],'report lineage')
check(closure['source_hashes_before']==closure['source_hashes_after'],'report source stability')
check(pin(RUN/'invocation.json')['sha256']==closure['invocation_sha256'],'invocation seal')
check(len(closure['raw'])==4,'four new raw')
for name,expected in closure['raw'].items():check(sealed(RUN/name,expected),'new raw '+name)
check(pin(OLD/'model.sxo')['sha256']==contract['diagnostic_parent']['sxo_sha256'],'sealed SXO')
check(pin(OLD/'model.log')['sha256']==contract['diagnostic_parent']['event_log_sha256'],'sealed event log')
check(pin(PARENT/'model.log')['sha256']==contract['accepted_parent']['event_log_sha256'],'accepted event log')
check(pin(PARENT_REPORT)['sha256']==contract['accepted_parent']['selected_report_sha256'],'accepted report')
check(old_outcome['converter_summary']==[0,2,0] and old_outcome['warning_codes']==['108','376'],'converter summary and warnings')
calc=(OLD/'run.log').read_text(errors='replace')
check('Form: StockAllocation\nrec 2: (warning #376) ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01' in calc.replace('\r\n','\n'),'exact native warning attribution')
check(load(OLD/'roundtrip-check.json')=={'schema':'simlox-e15-var01-roundtrip/v1','passed':True,'authored_populated_tables':21,'native_export_populated_tables':31,'mismatches':[]},'21-table roundtrip')
parent=load(E15/'native-input-default.json');child=load(OLD_CASE/'native-input.json')
a={t['name']:t for t in parent['model']['tables']};b={t['name']:t for t in child['model']['tables']}
check(a.keys()==b.keys() and [n for n in a if a[n]!=b[n]]==['ItemReorder'],'sole changed table')
copy=deepcopy(a['ItemReorder']);row=copy['instances'][0]['rows'][0];cols=[x['name'] for x in copy['columns']]
check(row[:2]==['TEACH-DU-01','DEPOT-01'] and row[cols.index('ROINT')] is None,'parent target row')
row[cols.index('ROINT')]=16.0
check(copy==b['ItemReorder'],'sole RОINT null to16 delta')
check(inv['session_id']==0 and 'sshd.exe' in inv['ssh_ancestor_names'] and inv['queue_mutex']==r'Global\SimloxIssue18NativeQueue','SSH0 serial ownership')
check(inv['gui']=={'pid':13340,'session_id':1,'start_utc':'2026-09-28T10:09:56.8261381Z'},'GUI identity')
check(len(steps)==1 and steps[0]['name']=='selected_report_only' and steps[0]['status']=='completed' and steps[0]['exit_code']==0 and steps[0]['gui_preserved'],'single report step')
args=steps[0]['arguments']
check(all(x in args for x in ('model.sxo',' -report',' -rpts',' -rjexport')) and not any(re.search(r'(?<!\S)'+re.escape(x)+r'(?=\s|$)',args) for x in ('-calc','-jimport','-jexport','-save')),'report-only command')
check('Export completed!' in (RUN/'report-export.log').read_text(errors='replace'),'native report completed')
log=(OLD/'model.log').read_text(errors='replace');plog=(PARENT/'model.log').read_text(errors='replace')
diff=[x for x in difflib.ndiff(plog.splitlines(),log.splitlines()) if x[:2] in ('+ ','- ')]
check(len(diff)==6 and all(x.startswith('+ ') for x in diff),'exact six added event lines')
check('Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock' in log and 'Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>' in log,'h10 issue and h12 receipt')
check('Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task' not in log and log.count('reorder task 0 started')==1 and 'Time: 16 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1' in log,'no h10 order and h16 order')
check('Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives' in log and 'Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>' in log,'one h17 new ID6')
snaps=re.findall(r'Stock at: <TEACH-DU-01,0,(BASE-01|DEPOT-01),0> Level: (\d+) Items:([^\r\n]*)',log)
check(len(snaps)==6,'all six physical stock snapshots')
expected=[('DEPOT-01',4,[0,1,2,3]),('BASE-01',1,[4]),('BASE-01',0,[]),('DEPOT-01',3,[1,2,3]),('BASE-01',1,[0]),('DEPOT-01',4,[1,2,3,6])]
for i,(station,level,items) in enumerate(snaps):
 ids=[int(x) for x in re.findall(r'<TEACH-DU-01,0,(\d+)>',items)]
 check((station,int(level),ids)==expected[i],f'physical snapshot {i}')
check(log.count('mission success:')==2 and log.count('mission aborted:')==1 and 'Time: 34 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>' in log,'mission and terminal state')
report=load(RUN/'selected-report-raw.json');parent_report=load(PARENT_REPORT)
t={x['name']:x for x in report['report']['tables']};p={x['name']:x for x in parent_report['report']['tables']}
check(len(t)==len(p)==10 and set(t)==set(p),'ten selected tables')
check({n for n in t if t[n]!=p[n]}=={'ItemResults','ItemResultsTotal'},'changed table scope')
cols=[x['name'] for x in t['ItemResults']['columns']];rows=t['ItemResults']['instances'][0]['rows'];prows=p['ItemResults']['instances'][0]['rows']
check(len(rows)==len(prows)==72,'72 depot bins')
diffs=[]
for i,(raw,pr) in enumerate(zip(rows,prows)):
 row=dict(zip(cols,raw));hour=i/2
 check(row['IID']=='TEACH-DU-01' and row['STID']=='DEPOT-01' and row['STINT']==hour and row['ETINT']==hour+0.5 and row['STSZ']==4 and row['STOHA']==(4 if hour<10 or hour>=17 else 3) and row['NRO']==(1 if hour==16 else 0) and row['NBO']==0,f'depot bin {hour}')
 for j,(x,y) in enumerate(zip(raw,pr)):
  if x!=y:diffs.append((i,cols[j],x,y))
expected_diffs={(32,'NRO',1,0)}|{(i,'STOHA',4,3) for i in range(34,72)}
check(set(diffs)==expected_diffs and len(diffs)==39,'exact 39 ItemResults cell differences')
cols2=[x['name'] for x in t['ItemResultsTotal']['columns']];total=dict(zip(cols2,t['ItemResultsTotal']['instances'][0]['rows'][0]));ptotal=dict(zip(cols2,p['ItemResultsTotal']['instances'][0]['rows'][0]))
check({k for k in total if total[k]!=ptotal[k]}=={'STOHA','NRO'} and total['NRO']==1 and ptotal['NRO']==0 and abs(total['STOHA']-3.805555582046509)<1e-10 and abs(ptotal['STOHA']-3.277777671813965)<1e-10,'item total cells')
for name in set(t)-{'ItemResults','ItemResultsTotal'}:check(t[name]==p[name],'unchanged table '+name)
result={'schema':'simlox-e15-var01-timecycle-author-replay/v1','run_id':RUN.name,'old_closure_sha256':pin(OLD/'closure.json')['sha256'],'report_closure_sha256':pin(RUN/'closure.json')['sha256'],'passed':not failures,'checks':checks,'checks_passed':checks-len(failures),'failures':failures,'observed':{'old_raw_files':11,'new_raw_files':4,'physical_snapshots':len(snaps),'depot_bins':len(rows),'item_row_cell_differences':len(diffs),'changed_tables':sorted(n for n in t if t[n]!=p[n]),'report_sha256':pin(RUN/'selected-report-raw.json')['sha256']},'limits':contract['limits']}
target=HERE/'review/author-validation-2026-10-05.json';target.parent.mkdir(exist_ok=True);target.write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps({'passed':result['passed'],'checks':checks,'failures':failures},indent=2))
if failures:raise SystemExit(1)