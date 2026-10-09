"""Independent I05.var07 source and recovered-byte reader. No author imports."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

METHOD = Path(__file__).resolve()
CASE = METHOD.parent.parent
REPO = CASE.parents[2]
RUN_ID = 'i05-var07-turnround-v101-ssh-20261009-01'
RUN = REPO / 'tmp/i05-var07-native-v101-20261009-01'
RECOVERED = CASE / 'runs' / RUN_ID
PARENT = REPO / 'cases/simlox-air-support/B04-cross-midnight-turnround-v1.0.1'
PARENT_RUN = PARENT / 'runs/b04-v101-turnround-20260930-01'
BASE = '120adb3d8912acfe9965ea04c939867721f3ede3'
CONTRACT_SHA = 'c34bb3d2b9c88763347f63e5bb111389db00e800d743ff74102e810eab6df0b7'
INPUT_PIN = {'bytes':43997,'sha256':'1dc116829e92845735440f6e7e49b0f1b768247b59af651538ae23db450a6619'}
EXPORT_PIN = {'bytes':48181,'sha256':'4faa5ce52c1bf53b8ea6c1082304ae8429169ae19d496a680bcb4ef7a380a3d4'}
LOG_PIN = {'bytes':9108,'sha256':'dc00ee98683714508de8ef483b19d9efc7484c24a08f57886250c902a2c8e445'}
REPORT_PIN = {'bytes':93721,'sha256':'30ca074dacfdb854f561453ca0d16a384a8b0dbae957b78da2edca4cc4cf9fc3'}
PARENT_PINS = {
    'input':(PARENT/'turnround-input.json',42867,'9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5'),
    'export':(PARENT_RUN/'roundtrip-raw.json',58901,'f16c59e16c7fadbf52a94fced3a15d389abeac647301601a434fb16dca8f2677'),
    'log':(PARENT_RUN/'model.log',9088,'ea2cd9cd124b499f69674a9bb8a70d44ec2ab9ffa0fa8b602f34b45f9e37163e'),
    'report':(PARENT_RUN/'report-raw.json',103976,'ea429a8c563f50256ca24168e8ae103222e5fe01918fbb52c40c6adf64a66897'),
    'converter':(PARENT_RUN/'run.log',1040,'6cf26d35c8c47032e006eea125162f3a1aa15485cfa48c2d794191f83b20eb85'),
}
SELECTION_PIN = {'bytes':35711,'sha256':'83896d1ba886926df481d4ae2f6addb0c9f1dba7fd6a7065e8df18e022d9a593'}
LOCAL_CATALOG_PIN = {'bytes':551394,'sha256':'3946c8b0e849a2c4fec850e0866b3095a97db235def11682a7108a35bc081539'}
GIT_CATALOG_PIN = {'bytes':546569,'sha256':'139dae3260e764a90c4f4d228a4fd34eda98c9b6baf17904ff0727ee08fc7fde'}
PYTHON = Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
PYTHON_PIN = {'bytes':106448,'sha256':'10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1','mode':511,'attributes':32}
EXE = r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
TOOLS = ['build.py','source_gate.py','self_check.py','make_source_inventory.py','make_prelaunch_manifest.py']
STAGES = ['import','export','check_import_export','calc','jsonreport','check_behavior']
SOURCE_LIST_SHA = 'bfee2a0c61d632324e8d3549264713293f0a3741985e8520f3fe35233a02ec42'

def sha(data:bytes)->str: return hashlib.sha256(data).hexdigest()

def no_reparse(path:Path)->None:
    assert path.is_absolute()
    for node in (path,*path.parents):
        if node.exists():
            assert not node.is_symlink() and not node.is_junction(),node
            assert not (getattr(node.stat(),'st_file_attributes',0)&0x400),node

def seal(path:Path)->dict:
    no_reparse(path)
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':sha(data)}

def exact(path:Path,spec:dict,mode:int|None=None,attributes:int|None=None)->bytes:
    no_reparse(path)
    data=path.read_bytes()
    assert len(data)==spec['bytes'] and sha(data)==spec['sha256'],path
    st=path.stat()
    if mode is not None: assert stat.S_IMODE(st.st_mode)==mode,(path,'mode')
    if attributes is not None: assert st.st_file_attributes==attributes,(path,'attributes')
    return data

def strict_json(data:bytes,allow_bom:bool=False):
    if data.startswith(b'\xef\xbb\xbf'):
        assert allow_bom
        data=data[3:]
        assert not data.startswith(b'\xef\xbb\xbf')
    def pairs(items):
        result={}
        for k,v in items:
            assert k not in result,k
            result[k]=v
        return result
    def bad(token): raise AssertionError(('nonfinite',token))
    value=json.loads(data.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad)
    def finite(v):
        if type(v) is float: assert math.isfinite(v)
        elif type(v) is list:
            for x in v: finite(x)
        elif type(v) is dict:
            for x in v.values(): finite(x)
    finite(value)
    return value

def native_report_json(raw:bytes):
    assert raw and not raw.startswith(b'\xef\xbb\xbf') and raw.endswith(b'\r\n')
    assert raw.count(b'\n')==raw.count(b'\r\n')
    marker=b',\r\n      ]'
    assert raw.count(marker)==1
    return strict_json(raw.replace(marker,b'\r\n      ]',1))

def typed(a,b)->bool:
    if type(a) is not type(b): return False
    if type(a) is dict: return set(a)==set(b) and all(typed(a[k],b[k]) for k in a)
    if type(a) is list: return len(a)==len(b) and all(typed(x,y) for x,y in zip(a,b,strict=True))
    return a==b

def keys(value,wanted): assert type(value) is dict and set(value)==set(wanted),(set(value) if type(value) is dict else type(value),set(wanted))
def integer(value,wanted): assert type(value) is int and value==wanted,(value,wanted)
def boolean(value,wanted): assert type(value) is bool and value is wanted
def absolute(value)->Path:
    assert type(value) is str
    path=Path(value)
    assert path.is_absolute() and str(path)==value
    no_reparse(path)
    return path
def utc(value):
    assert type(value) is str and value.endswith('Z')
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def table_counts(doc:dict,root:str)->tuple[int,int,int]:
    keys(doc,{root})
    body=doc[root]
    keys(body,{'database_version','tables'} if root=='model' else {'tables'})
    tables=body['tables']; assert type(tables) is list
    rows=[r for t in tables for ins in t['instances'] for r in ins['rows']]
    return len(tables),len(rows),sum(len(r) for r in rows)

def change_table(time:float|int)->dict:
    return {'name':'ChangesMissionTurnround','columns':[
        {'name':'MTID','datatype':'string','key':True},
        {'name':'SID','datatype':'string','key':True},
        {'name':'STID','datatype':'string','key':True},
        {'name':'TIMEC','datatype':'double','key':True},
        {'name':'DURN','datatype':'double'},
        {'name':'DURND','datatype':'string'},
        {'name':'NOTE','datatype':'string'}],
        'instances':[{'instance_name':'','rows':[['BASIC-MISSION','TEACH-AIR-01','BASE-01',time,1.5,None,None]]}]}

def projected_model(parent:dict,time:float|int,rows:int,cells:int)->dict:
    assert table_counts(parent,'model') in ((32,22,204),(32,36,367))
    names=[t['name'] for t in parent['model']['tables']]
    assert len(names)==32 and names[-1]=='MissionTurnround' and 'ChangesMissionTurnround' not in names
    child=copy.deepcopy(parent)
    child['model']['tables'].append(change_table(time))
    assert table_counts(child,'model')==(33,rows,cells)
    assert [t['name'] for t in child['model']['tables']]==names+['ChangesMissionTurnround']
    return child

def physical_lines(raw:bytes)->list[str]:
    assert raw and not raw.startswith(b'\xef\xbb\xbf') and raw.endswith(b'\r\n')
    assert raw.count(b'\r\n')==raw.count(b'\n')
    lines=raw.decode('utf-8').split('\r\n')
    assert lines.pop()==''
    return lines

def projected_log(parent:bytes)->bytes:
    lines=physical_lines(parent)
    assert len(lines)==115 and sum(x.startswith('Time: ') for x in lines)==107
    assert 'planned to last for 1 hours' in lines[46] and 'planned to last for 1 hours' in lines[101]
    edits={102:('planned to last for 1 hours','planned to last for 1.5 hours')}
    edits.update({n:('Time: 28 ','Time: 28.5 ') for n in (104,105,106,107,110,111,112,113,114)})
    for ordinal,(old,new) in edits.items():
        assert lines[ordinal-1].count(old)==1,ordinal
        lines[ordinal-1]=lines[ordinal-1].replace(old,new,1)
    assert 'planned to last for 1 hours' in lines[46] and 'planned to last for 1.5 hours' in lines[101]
    assert all(lines[n-1].startswith('Time: 28.5 ') for n in (104,105,106,107,110,111,112,113,114))
    result=('\r\n'.join(lines)+'\r\n').encode('utf-8')
    assert len(result)==9108 and len(physical_lines(result))==115
    assert sum(x.startswith('Time: ') for x in lines)==107
    return result

def report_counts(doc:dict)->None:
    assert table_counts(doc,'report')==(4,146,4044)
    tables=doc['report']['tables']
    assert [t['name'] for t in tables]==['ProblemDescription','ResultSummary','SystemResults','StockTotalResults']
    assert [len(t['columns']) for t in tables]==[1,11,40,16]
    assert [len(t['instances'][0]['rows']) for t in tables]==[1,1,72,72]

def projected_report(parent:dict)->dict:
    report_counts(parent)
    child=copy.deepcopy(parent)
    table=child['report']['tables'][2]
    names=[x['name'] for x in table['columns']]
    row=table['instances'][0]['rows'][56]
    assert row[2:4]==[28,28.5]
    for name,before,after in [('NSYRY',1,0),('NSYMA',0,1),('NSYMT',0,1)]:
        index=names.index(name)
        assert type(row[index]) is int and row[index]==before
        row[index]=after
    report_counts(child)
    return child

def source_oracles():
    parent={k:exact(path,{'bytes':size,'sha256':digest}) for k,(path,size,digest) in PARENT_PINS.items()}
    authored=projected_model(strict_json(parent['input']),25.0,23,211)
    exported=projected_model(strict_json(parent['export']),25,37,374)
    log=projected_log(parent['log'])
    report=projected_report(native_report_json(parent['report']))
    assert typed(authored,strict_json(exact(CASE/'native-input.json',INPUT_PIN,292,33)))
    assert typed(exported,strict_json(exact(CASE/'preserved-design/expected-export.json',EXPORT_PIN,292,33)))
    assert log==exact(CASE/'preserved-design/expected-model.log',LOG_PIN,292,33)
    assert typed(report,strict_json(exact(CASE/'preserved-design/expected-report.json',REPORT_PIN,292,33)))
    return authored,exported,log,report,parent

MANIFEST_KEYS=set('schema run_id native_run_directory file_line_ascii_bytes file_line_ascii_max base_commit contract_sha256 execution_binding_sha256 input_sha256 source_inventory_sha256 runner_sha256 validator_sha256 independent_reader_sha256 source_count source_files owned_source_count selected_reference_count selected_unique_original_count accepted_source_pair_count accepted_source_pair_unique_count accepted_raw_count excluded_raw_count archived_catalog_count installed_source_count runtime_source_count historical_source_count catalog_prefix_entries live_catalog_prelaunch_pin pure_tools stages native_commands pure_checkers new_native_runs_authorized_by_manifest independent_method_state'.split())
PREFLIGHT_KEYS=set('schema run_id native_run_directory run_dirs_absent file_line_ascii_bytes file_line_ascii_max native_run_path_ancestors_no_reparse ssh_session ps_major ssh_ancestors mutex_free wts_active_gui_count gui selected_reference_count selected_unique_original_count accepted_source_pair_count accepted_source_pair_unique_count accepted_raw_count excluded_raw_count archived_catalog_count installed_source_count runtime_source_count historical_source_count catalog_prefix_entries manifest_sha256 source_map_sha256 source_hashes source_hashes_after_pure pure_proof_directory pure_proof_path pure_proof_sha256 pure_checks native_process_started'.split())
PROOF_KEYS=set('schema mode run_id native_run_directory manifest_sha256 source_map_sha256 started_utc completed_utc status error checks source_hashes_after'.split())
PURE_STEP_KEYS=set('tool program arguments started_utc completed_utc status error child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256'.split())
APPROVAL_KEYS=set('schema decision run_id native_run_directory manifest_sha256 runner_sha256 validator_sha256 contract_sha256 execution_binding_sha256 input_sha256 source_map_sha256 independent_reader_sha256 preflight_relative_path preflight_sha256'.split())
INVOCATION_KEYS=set('schema run_id created_utc original_run_dir native_run_directory input_sha256 contract_sha256 manifest_sha256 approval_sha256 approved_preflight_path approved_preflight_sha256 independent_reader_sha256 runner_script_sha256 session_id ssh_ancestors gui queue_mutex working_directory planned_commands planned_checkers source_hashes_before source_hashes_after_pure pure_proof_path pure_proof_sha256 pure_checks publication_state'.split())
CLOSURE_KEYS=set('schema run_id native_run_directory invocation_sha256 manifest_sha256 approval_sha256 approved_preflight_sha256 source_hashes_before source_hashes_after raw step_error error publication_state'.split())
STEP_KEYS=set('sequence name program arguments started_utc completed_utc child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256 converter_log_bytes converter_log_sha256 converter_log_validated gui_preserved status error'.split())
RAW_NAMES=set('input.json model.sxi import.log import-stdout.txt import-stderr.txt roundtrip-raw.json export.log export-stdout.txt export-stderr.txt roundtrip-validation.json check_import_export-stderr.txt model.sxo model.log model-run.log calc-stdout.txt calc-stderr.txt report-raw.json report-export.log jsonreport-stdout.txt jsonreport-stderr.txt author-validation.json check_behavior-stderr.txt steps.json'.split())

def catalog505(phase:str)->None:
    assert phase in ('prelaunch','historical')
    local=strict_json(exact(CASE/'source-maps/catalog-local-505.json.bytes',LOCAL_CATALOG_PIN,292,33))
    git=strict_json(exact(CASE/'source-maps/catalog-git-505.json.bytes',GIT_CATALOG_PIN,292,33))
    assert typed(local,git)
    assert type(local) is dict and type(local['entries']) is list and len(local['entries'])==505
    path=REPO/'cases/simlox-air-support/publication-index-v1.json'
    no_reparse(path)
    live=strict_json(path.read_bytes())
    assert type(live) is dict and set(live)==set(local) and type(live['entries']) is list
    assert len(live['entries'])>=505 and typed(live['entries'][:505],local['entries'])
    for key in local:
        if key not in ('entries','as_of'): assert typed(live[key],local[key])
    ids=[entry['publication_id'] for entry in live['entries']]
    assert len(ids)==len(set(ids))
    if phase=='prelaunch':
        assert len(live['entries'])==505 and seal(path)==LOCAL_CATALOG_PIN
    elif len(live['entries'])>505:
        assert len(live['entries'])==506
        entry_path=CASE/'publication-entry.json'
        assert entry_path.is_file()
        assert typed(live['entries'][505],strict_json(entry_path.read_bytes()))

def owned_list()->list[str]:
    raw=exact(CASE/'source-list.json',{'bytes':1526,'sha256':SOURCE_LIST_SHA},292,33)
    body=strict_json(raw); keys(body,{'schema','files'})
    assert body['schema']=='i05-var07-owned-source-list/v101'
    names=body['files']
    assert type(names) is list and len(names)==40 and len(names)==len(set(names))==len({x.casefold() for x in names})
    for name in names:
        assert type(name) is str and Path(name).as_posix()==name and not Path(name).is_absolute() and '..' not in Path(name).parts
    for required in ('review/independent_reader.py','review/independent_self_check.py','review/independent-static-go-2026-10-09.md'):
        assert names.count(required)==1
    return names

def source_inventory(candidate:Path|None=None)->dict:
    names=owned_list()
    path=CASE/'source-inventory.json' if candidate is None else candidate
    assert path.is_file() and path.stat().st_file_attributes==33
    doc=strict_json(path.read_bytes()); keys(doc,{'schema','source_count','source_files'})
    assert doc['schema']=='i05-var07-source-inventory/v101'
    integer(doc['source_count'],40)
    rows=doc['source_files']; assert type(rows) is list and len(rows)==40
    for name,row in zip(names,rows,strict=True):
        keys(row,{'path','bytes','sha256'})
        assert row['path']==name
        exact(CASE/name,row,292,33)
    return doc

def selection_roles(phase:str)->list[dict]:
    selection=strict_json(exact(CASE/'source-maps/root-selection-record.json',SELECTION_PIN,292,33))
    assert selection['schema']=='i05-var07-root-selection-byte-audit/v100'
    assert selection['decision']=='ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_REVIEW_ONLY'
    integer(selection['catalog_entries'],505)
    boolean(selection['candidate_published'],False)
    integer(selection['protected_original_count'],98)
    integer(selection['role_reference_count'],100)
    assert selection['selected_parent_arm']['role']=='B04 turnround, not B04 no-turnround control'
    refs=[('selected:live',REPO/'tmp/i05-var07-root-live-eligibility-v100-20261009-01.json',{'bytes':2184,'sha256':'d2339daa9773dc4c2ff7f5c4fb47a669751d0a517c53fccb3f812a0544fd4995','mode':292,'attributes':33}),
          ('selected:catalog',REPO/'cases/simlox-air-support/publication-index-v1.json',selection['catalog_local']),
          ('selected:prior-map',REPO/'cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.3/source-maps/root-selection-record.json',{'bytes':9645,'sha256':'57d53ce82f61d7408c33ab9380e6b5cf4921e93846bb470d7b3fd61b19004b25','mode':292,'attributes':33}),
          ('selected:manual-sources',REPO/'cases/simlox-air-support/manual-sources-v2.json',{'bytes':6199,'sha256':'9f145c99fefe9cb751b763331ca983dc889f0fd4e003af3ac466efd25f5e5608','mode':438,'attributes':32})]
    for group,rows in (('dependency',selection['prior_dependency_pairs']),('parent-source',selection['accepted_parent_source_pairs'])):
        for i,row in enumerate(rows): refs.append((f'selected:{group}:{i:02d}',REPO/row['path'],row))
    for group,rows in (('parent-raw',selection['accepted_parent_raw_originals']),('excluded-v100-raw',selection['excluded_v100_raw_observed'])):
        for i,row in enumerate(rows): refs.append((f'selected:{group}:{i:02d}',Path(row['path']),row))
    for group,runs in (('parent-receipt',selection['accepted_parent_runs']),('excluded-v100-receipt',selection['excluded_v100_receipts_observed'])):
        for i,run in enumerate(runs):
            for name in ('invocation','closure'):
                refs.append((f'selected:{group}:{i:02d}:{name}',Path(run[name+'_path']),run[name]))
    assert list(selection['installed_sources'])==['dictionary','executable','manual']
    for name,row in selection['installed_sources'].items(): refs.append((f'selected:installed:{name}',Path(row['path']),row))
    assert len(refs)==100
    out=[]; seen={}
    for key,path,pin in refs:
        assert path.is_absolute()
        assert type(pin['bytes']) is type(pin['mode']) is type(pin['attributes']) is int
        resolved=path.resolve(strict=True)
        assert str(resolved).casefold()==str(path).casefold(),(key,'path alias')
        if key=='selected:catalog' and phase=='historical' and seal(resolved)!=LOCAL_CATALOG_PIN:
            st=resolved.stat()
            assert stat.S_IMODE(st.st_mode)==pin['mode'] and st.st_file_attributes==pin['attributes']
        else:
            exact(resolved,pin,pin['mode'],pin['attributes'])
        ident=str(resolved).casefold()
        data=(pin['bytes'],pin['sha256'],pin['mode'],pin['attributes'])
        assert seen.setdefault(ident,data)==data,(key,'alias')
        out.append({'key':key,'path':str(resolved),**{k:pin[k] for k in ('bytes','sha256','mode','attributes')}})
    assert len(seen)==98
    by_key={row['key']:row for row in out}
    for left,right in (('selected:dependency:04','selected:parent-source:04'),
                       ('selected:dependency:05','selected:parent-source:06')):
        assert {k:v for k,v in by_key[left].items() if k!='key'}=={k:v for k,v in by_key[right].items() if k!='key'}
    direct=selection['selected_parent_arm']
    assert any(row['path'].casefold()==direct['path'].casefold() and row['sha256']==direct['sha256'] for row in out)
    assert out[1]['sha256']==LOCAL_CATALOG_PIN['sha256']
    git_pairs(selection['prior_dependency_pairs']+selection['accepted_parent_source_pairs'])
    return out

def git_pairs(pairs:list[dict])->None:
    assert type(pairs) is list and len(pairs)==37
    distinct={}
    for row in pairs:
        path=row['path']
        assert type(path) is str and path and '\\' not in path
        if path in distinct:
            prior=distinct[path]
            assert all(row[field]==prior[field] for field in ('oid','bytes','sha256','mode','attributes'))
        else: distinct[path]=row
    assert len(distinct)==35 and len({row['oid'] for row in distinct.values()})==35
    proc=subprocess.run(['git','ls-tree','-r','--full-tree',BASE,'--',*distinct],cwd=REPO,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    got={}
    for line in proc.stdout.decode('ascii').splitlines():
        fields,path=line.split('\t',1)
        mode,kind,oid=fields.split()
        assert mode=='100644' and kind=='blob' and path not in got
        got[path]=oid
    assert set(got)==set(distinct)
    for path,row in distinct.items():
        assert got[path]==row['oid']
        blob=subprocess.run(['git','cat-file','blob',row['oid']],cwd=REPO,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
        assert len(blob)==row['bytes'] and sha(blob)==row['sha256']

def history_roles()->list[dict]:
    freeze=REPO/'tmp/i05-var07-author-freeze-case-v100-20261009-01.json'
    nogo=REPO/'tmp/i05-var07-root-static-nogo-v100-20261009-01.json'
    pins=[('historical:v100-author-freeze',freeze,{'bytes':6474,'sha256':'92a612a9821ae04c78c26f71684e66751c5ea6975e8b71917a4bce538c9ea182','mode':292,'attributes':33}),
          ('historical:v100-static-no-go',nogo,{'bytes':2975,'sha256':'65528d82ad38be5c1f52c3b0635570b11863fb85b5de4e4a369f25d7031376c7','mode':292,'attributes':33})]
    out=[]
    for key,path,pin in pins:
        exact(path,pin,pin['mode'],pin['attributes'])
        out.append({'key':key,'path':str(path),**pin})
    old=strict_json(freeze.read_bytes())
    keys(old,{'schema','source_list_count','present_author_count','reserved_review_paths','files'})
    assert old['schema']=='i05-var07-author-freeze-case/v100'
    integer(old['source_list_count'],40); integer(old['present_author_count'],37)
    assert type(old['files']) is list and len(old['files'])==37
    old_root=REPO/'tmp/i05-var07-package-author-v100-20261009-01/package'
    names=set()
    for row in old['files']:
        keys(row,{'path','bytes','sha256'})
        rel=row['path']
        assert type(rel) is str and not Path(rel).is_absolute() and '..' not in Path(rel).parts
        assert rel not in names; names.add(rel)
        exact(old_root/rel,row,292,33)
    old_nogo=strict_json(nogo.read_bytes())
    assert old_nogo['schema']=='i05-var07-root-static-source-nogo/v100'
    assert old_nogo['decision']=='STATIC_NO_GO'
    integer(old_nogo['package_method_invocations'],0)
    integer(old_nogo['ssh_preflight_invocations'],0)
    boolean(old_nogo['native_dispatch'],False)
    assert old_nogo['actual_failed_invocation'] is None
    return out

def source_map_digest(source_map:dict)->str:
    return sha(json.dumps(source_map,separators=(',',':'),ensure_ascii=False).encode('utf-8'))

def manifest_document(candidate:Path|None=None,phase:str='prelaunch')->tuple[dict,dict]:
    assert phase in ('prelaunch','historical')
    catalog505(phase)
    inventory=source_inventory()
    path=CASE/'prelaunch-manifest.json' if candidate is None else candidate
    assert path.is_file() and path.stat().st_file_attributes==33
    doc=strict_json(path.read_bytes()); keys(doc,MANIFEST_KEYS)
    assert doc['schema']=='i05-var07-prelaunch-manifest/v101'
    assert doc['run_id']==RUN_ID and type(doc['native_run_directory']) is str and doc['native_run_directory']==str(RUN)
    assert doc['base_commit']==BASE and doc['contract_sha256']==CONTRACT_SHA
    for field,want in [('file_line_ascii_bytes',119),('file_line_ascii_max',199),('selected_reference_count',100),
        ('selected_unique_original_count',98),('accepted_source_pair_count',37),('accepted_source_pair_unique_count',35),
        ('accepted_raw_count',24),('excluded_raw_count',24),('archived_catalog_count',2),('installed_source_count',3),
        ('runtime_source_count',1),('historical_source_count',2),('catalog_prefix_entries',505),
        ('native_commands',4),('pure_checkers',2),('new_native_runs_authorized_by_manifest',0)]: integer(doc[field],want)
    assert doc['pure_tools']==TOOLS and doc['stages']==STAGES
    assert doc['independent_method_state']=='SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL'
    line_bodies=['Input file: '+str(RUN/'model.sxi'),'Output file: '+str(RUN/'model.sxo'),'File: '+str(RUN/'model.sxi').replace('\\','/')]
    assert all(s.isascii() for s in line_bodies) and [len(s.encode('ascii')) for s in line_bodies]==[125,126,119]
    binding_path=CASE/'execution-contract.json'
    binding=strict_json(binding_path.read_bytes())
    assert binding['schema']=='i05-var07-execution-contract/v101'
    assert binding['logical_run_id']==RUN_ID and binding['native_run_directory']==str(RUN)
    assert binding['recovered_run_directory']==str(RECOVERED)
    assert binding['prospective_contract_sha256']==CONTRACT_SHA
    for field,want in [('authored_insertion_index',32),('export_insertion_index',32),('accepted_source_disk_git_pairs',37),
                       ('accepted_source_disk_git_unique_paths',35),('selected_reference_count',100),('selected_unique_original_count',98),
                       ('historical_source_count',2),('catalog_prefix_entries',505),('native_commands',4),('pure_checkers',2)]: integer(binding[field],want)
    assert binding['superseded_unexecuted_v100']['planned_package']=='I05-var07-scheduled-mission-turnround-v1.0.0'
    assert binding['superseded_unexecuted_v100']['author_freeze']['sha256']=='92a612a9821ae04c78c26f71684e66751c5ea6975e8b71917a4bce538c9ea182'
    assert binding['superseded_unexecuted_v100']['static_no_go']['sha256']=='65528d82ad38be5c1f52c3b0635570b11863fb85b5de4e4a369f25d7031376c7'
    assert binding['source_only_approval_state']=='SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL'
    source_fields={'execution_binding_sha256':'execution-contract.json','input_sha256':'native-input.json',
                   'source_inventory_sha256':'source-inventory.json','runner_sha256':'run_native_ssh.ps1',
                   'validator_sha256':'validate_native_cli.py','independent_reader_sha256':'review/independent_reader.py'}
    for field,rel in source_fields.items(): assert doc[field]==seal(CASE/rel)['sha256'],field
    assert doc['input_sha256']==INPUT_PIN['sha256']
    rows=[]
    for entry in inventory['source_files']:
        target=CASE/entry['path']
        rows.append({'key':'owned:'+entry['path'],'path':str(target),**seal(target),'mode':292,'attributes':33})
    target=CASE/'source-inventory.json'
    rows.append({'key':'owned:source-inventory.json','path':str(target),**seal(target),'mode':292,'attributes':33})
    rows.extend(selection_roles(phase))
    exact(PYTHON,PYTHON_PIN,PYTHON_PIN['mode'],PYTHON_PIN['attributes'])
    rows.append({'key':'runtime:python','path':str(PYTHON),**PYTHON_PIN})
    rows.extend(history_roles())
    integer(doc['owned_source_count'],41); integer(doc['source_count'],144)
    assert type(doc['source_files']) is list and len(doc['source_files'])==144
    assert typed(rows,doc['source_files'])
    seen_keys=set(); seen_paths={}
    for row in doc['source_files']:
        keys(row,{'key','path','bytes','sha256','mode','attributes'})
        assert type(row['key']) is str and row['key'].casefold() not in seen_keys
        seen_keys.add(row['key'].casefold())
        target=absolute(row['path'])
        resolved=str(target.resolve(strict=True)).casefold()
        pin=(row['bytes'],row['sha256'],row['mode'],row['attributes'])
        assert seen_paths.setdefault(resolved,pin)==pin
    keys(doc['live_catalog_prelaunch_pin'],{'path','bytes','sha256'})
    assert doc['live_catalog_prelaunch_pin']=={'path':str(REPO/'cases/simlox-air-support/publication-index-v1.json'),**LOCAL_CATALOG_PIN}
    return doc,{row['key']:row['sha256'] for row in rows}

def receipt_json(raw:bytes): return strict_json(raw,allow_bom=True)

def pure_proof(receipt:dict,source_map:dict,mode:str)->dict:
    proof_dir=absolute(receipt['pure_proof_directory'])
    assert proof_dir.parent==CASE/'test-output'
    assert re.fullmatch(rf'{mode}-pure-[0-9]{{8}}T[0-9]{{13}}Z-[0-9a-f]{{8}}',proof_dir.name)
    proof_path=proof_dir/'pure-proof.json'
    assert receipt['pure_proof_path']==str(proof_path)
    assert receipt['pure_proof_sha256']==seal(proof_path)['sha256']
    proof=receipt_json(proof_path.read_bytes()); keys(proof,PROOF_KEYS)
    assert proof['schema']=='i05-var07-pure-proof/v101' and proof['mode']==mode
    assert proof['run_id']==RUN_ID and type(proof['native_run_directory']) is str and proof['native_run_directory']==str(RUN)
    assert proof['status']=='passed' and proof['error'] is None
    assert proof['manifest_sha256']==receipt['manifest_sha256'] and proof['source_map_sha256']==receipt['source_map_sha256']
    assert typed(proof['source_hashes_after'],source_map) and typed(receipt['source_hashes_after_pure'],source_map)
    assert typed(proof['checks'],receipt['pure_checks'])
    checks=proof['checks']; assert type(checks) is list and len(checks)==len(TOOLS)
    previous=utc(proof['started_utc'])
    for tool,step in zip(TOOLS,checks,strict=True):
        keys(step,PURE_STEP_KEYS)
        assert step['tool']==tool and step['program']==str(PYTHON)
        assert step['arguments']==f'-X utf8 -B "{CASE/tool}"'
        assert step['status']=='completed' and step['error'] is None and step['capture_error'] is None
        integer(step['exit_code'],0); integer(step['child_session_id'],0); integer(step['stderr_bytes'],0)
        assert type(step['child_pid']) is int and step['child_pid']>0
        start,end=utc(step['started_utc']),utc(step['completed_utc'])
        assert previous<=start<=end; previous=end
        for stream in ('stdout','stderr'):
            expected=proof_dir/(Path(tool).stem+'-'+stream+'.bin')
            assert step[stream+'_path']==str(expected)
            exact(expected,{'bytes':step[stream+'_bytes'],'sha256':step[stream+'_sha256']})
    assert utc(proof['completed_utc'])>=previous
    return proof

def preflight_receipt(path:Path,phase:str='prelaunch')->tuple[dict,dict]:
    manifest,source_map=manifest_document(phase=phase)
    receipt=receipt_json(path.read_bytes()); keys(receipt,PREFLIGHT_KEYS)
    assert receipt['schema']=='i05-var07-ssh-preflight/v101' and receipt['run_id']==RUN_ID
    assert type(receipt['native_run_directory']) is str and receipt['native_run_directory']==str(RUN)
    assert receipt['manifest_sha256']==seal(CASE/'prelaunch-manifest.json')['sha256']
    assert receipt['source_map_sha256']==source_map_digest(source_map)
    assert typed(receipt['source_hashes'],source_map) and typed(receipt['source_hashes_after_pure'],source_map)
    for field,want in [('file_line_ascii_bytes',119),('file_line_ascii_max',199),('ssh_session',0),('ps_major',5),
        ('wts_active_gui_count',1),('selected_reference_count',100),('selected_unique_original_count',98),
        ('accepted_source_pair_count',37),('accepted_source_pair_unique_count',35),('accepted_raw_count',24),
        ('excluded_raw_count',24),('archived_catalog_count',2),('installed_source_count',3),('runtime_source_count',1),
        ('historical_source_count',2),('catalog_prefix_entries',505)]: integer(receipt[field],want)
    for field,want in [('run_dirs_absent',True),('native_run_path_ancestors_no_reparse',True),
                       ('mutex_free',True),('native_process_started',False)]: boolean(receipt[field],want)
    assert type(receipt['ssh_ancestors']) is list and 'sshd.exe' in receipt['ssh_ancestors']
    keys(receipt['gui'],{'pid','session_id','start_unix_ms','responding'})
    for field,want in [('pid',13340),('session_id',1),('start_unix_ms',1790590196826)]: integer(receipt['gui'][field],want)
    boolean(receipt['gui']['responding'],True)
    pure_proof(receipt,source_map,'preflight')
    assert path.parent==CASE/'review' and re.fullmatch(r'preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json',path.name)
    return receipt,source_map

def approval_document(path:Path,phase:str='prelaunch')->tuple[dict,dict]:
    body=receipt_json(path.read_bytes()); keys(body,APPROVAL_KEYS)
    assert body['schema']=='i05-var07-independent-prelaunch-go/v101' and body['decision']=='GO_PRELAUNCH'
    assert body['run_id']==RUN_ID and type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    manifest,source_map=manifest_document(phase=phase)
    for field,want in [('manifest_sha256',seal(CASE/'prelaunch-manifest.json')['sha256']),
        ('runner_sha256',manifest['runner_sha256']),('validator_sha256',manifest['validator_sha256']),
        ('contract_sha256',CONTRACT_SHA),('execution_binding_sha256',manifest['execution_binding_sha256']),
        ('input_sha256',INPUT_PIN['sha256']),('source_map_sha256',source_map_digest(source_map)),
        ('independent_reader_sha256',seal(CASE/'review/independent_reader.py')['sha256'])]: assert body[field]==want,field
    rel=body['preflight_relative_path'].replace('\\','/')
    assert re.fullmatch(r'review/preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json',rel)
    receipt_path=CASE/rel
    assert receipt_path.is_file() and receipt_path.resolve(strict=True).parent==(CASE/'review').resolve(strict=True)
    assert body['preflight_sha256']==seal(receipt_path)['sha256']
    return body,preflight_receipt(receipt_path,phase)[0]

def converter_bytes(raw:bytes,run:Path=RUN)->int:
    assert raw and not raw.startswith(b'\xef\xbb\xbf') and raw.endswith(b'\r\n')
    assert raw.count(b'\r\n')==raw.count(b'\n')==17
    lines=raw.decode('utf-8').split('\r\n')
    assert lines.pop()=='' and len(lines)==17
    fixed=['Performing simulation','Input file: '+str(run/'model.sxi'),
           'Output file: '+str(run/'model.sxo'),'Simulating.','Converting input data ...',
           'File: '+str(run/'model.sxi').replace('\\','/'),
           'Form: Control','rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',
           'Form: System','rec 1: (warning #126) This system contains no items: TEACH-AIR-01',
           'Input conversion completed. Errors: 0, Warnings: 2, Notes: 0',
           None,'Starting simulation...',None,'Saving results ...',None,None]
    for observed,want in zip(lines,fixed,strict=True):
        if want is not None: assert observed==want,(observed,want)
    for index,label in ((11,'Input data conversion time'),(13,'Simulation time'),
                        (15,'Result saving time'),(16,'Total execution time')):
        match=re.fullmatch(re.escape(label)+r': ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) secs\.',lines[index])
        assert match and math.isfinite(float(match.group(1))) and float(match.group(1))>=0
    assert len(lines[1].encode('ascii'))==125 and len(lines[2].encode('ascii'))==126
    assert len(lines[5].encode('ascii'))==119 and len(lines[5].encode('ascii'))<=199
    return 17

def checker_receipt(raw:bytes,name:str,run:Path)->dict:
    body=strict_json(raw)
    common={'schema','passed','run_id','native_run_directory','input_sha256','export_sha256','native_calls','issues'}
    if name=='check_import_export':
        wanted=common|{'authored_tables','authored_rows','authored_cells','exported_tables','exported_rows','exported_cells'}
        schema='i05-var07-roundtrip-check/v101'
    else:
        assert name=='check_behavior'
        wanted=common|{'log_sha256','report_sha256','physical_log_lines','timed_log_lines','report_typed_cells',
                       'authored_cells','exported_cells','turnround_cycles'}
        schema='i05-var07-native-behavior-check/v101'
    keys(body,wanted)
    assert body['schema']==schema and body['run_id']==RUN_ID
    boolean(body['passed'],True)
    assert type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    assert body['input_sha256']==INPUT_PIN['sha256'] and body['export_sha256']==seal(run/'roundtrip-raw.json')['sha256']
    integer(body['native_calls'],0); assert body['issues']==[]
    if name=='check_import_export':
        for field,want in [('authored_tables',33),('authored_rows',23),('authored_cells',211),
                           ('exported_tables',33),('exported_rows',37),('exported_cells',374)]: integer(body[field],want)
    else:
        assert body['log_sha256']==seal(run/'model.log')['sha256'] and body['report_sha256']==seal(run/'report-raw.json')['sha256']
        for field,want in [('physical_log_lines',115),('timed_log_lines',107),('report_typed_cells',4044),
                           ('authored_cells',211),('exported_cells',374),('turnround_cycles',2)]: integer(body[field],want)
    return body

def planned()->tuple[list[dict],list[dict]]:
    def rf(name): return str(RUN/name)
    commands=[
        {'name':'import','program':EXE,'arguments':f'-silent -jimport "{rf("input.json")}" -save "{rf("model.sxi")}" -log "{rf("import.log")}" -close'},
        {'name':'export','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -jexport "{rf("roundtrip-raw.json")}" -log "{rf("export.log")}" -close'},
        {'name':'calc','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -threads 1 -calc -log "{rf("model-run.log")}" -close'},
        {'name':'jsonreport','program':EXE,'arguments':f'"{rf("model.sxo")}" -silent -jsonreport "{rf("report-raw.json")}" -log "{rf("report-export.log")}" -close'}]
    checkers=[
        {'name':'check_import_export','program':str(PYTHON),'arguments':f'-X utf8 -B "{CASE/"check_roundtrip.py"}" --run-dir "{RUN}"'},
        {'name':'check_behavior','program':str(PYTHON),'arguments':f'-X utf8 -B "{CASE/"validate_native_cli.py"}" --run-dir "{RUN}"'}]
    return commands,checkers

def converter_fixture()->bytes:
    parent=exact(*_parent_spec('converter')).decode('utf-8')
    old=str(PARENT_RUN); new=str(RUN)
    assert parent.count(old)==2 and parent.count(old.replace('\\','/'))==1
    changed=parent.replace(old,new).replace(old.replace('\\','/'),new.replace('\\','/'))
    raw=changed.encode('utf-8')
    assert converter_bytes(raw)==17
    return raw

def _parent_spec(name:str):
    path,size,digest=PARENT_PINS[name]
    return path,{'bytes':size,'sha256':digest}

def sealed_replay(raw:Path)->dict:
    assert raw.is_dir() and raw.resolve(strict=True)==RECOVERED.resolve(strict=True)
    assert raw.resolve(strict=True)!=RUN.resolve(strict=True)
    manifest,source_map=manifest_document(phase='historical')
    approval,preflight=approval_document(CASE/'review/independent-prelaunch-go.json',phase='historical')
    invocation=receipt_json((raw/'invocation.json').read_bytes())
    closure=receipt_json((raw/'closure.json').read_bytes())
    keys(invocation,INVOCATION_KEYS); keys(closure,CLOSURE_KEYS)
    assert invocation['schema']=='i05-var07-invocation/v101' and closure['schema']=='i05-var07-closure/v101'
    for body in (invocation,closure):
        assert body['run_id']==RUN_ID and type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
        assert body['manifest_sha256']==approval['manifest_sha256']
        assert body['approval_sha256']==seal(CASE/'review/independent-prelaunch-go.json')['sha256']
        assert body['approved_preflight_sha256']==approval['preflight_sha256']
        assert typed(body['source_hashes_before'],source_map)
    assert invocation['original_run_dir']==str(RUN)
    assert invocation['input_sha256']==INPUT_PIN['sha256'] and invocation['contract_sha256']==CONTRACT_SHA
    assert invocation['approved_preflight_path']==str(CASE/approval['preflight_relative_path'])
    assert invocation['independent_reader_sha256']==manifest['independent_reader_sha256']
    assert invocation['runner_script_sha256']==manifest['runner_sha256']
    assert typed(invocation['source_hashes_after_pure'],source_map)
    assert invocation['queue_mutex']==r'Global\SimloxIssue18NativeQueue'
    assert invocation['working_directory']==str(REPO)
    assert invocation['publication_state']==closure['publication_state']=='not_published'
    integer(invocation['session_id'],0)
    assert type(invocation['ssh_ancestors']) is list and 'sshd.exe' in invocation['ssh_ancestors']
    assert typed(preflight['gui'],invocation['gui'])
    commands,checkers=planned()
    assert typed(invocation['planned_commands'],commands) and typed(invocation['planned_checkers'],checkers)
    native_proof_path=absolute(invocation['pure_proof_path'])
    assert native_proof_path.parent.parent==CASE/'test-output'
    native_receipt={'pure_proof_directory':str(native_proof_path.parent),'pure_proof_path':str(native_proof_path),
                    'pure_proof_sha256':invocation['pure_proof_sha256'],'manifest_sha256':approval['manifest_sha256'],
                    'source_map_sha256':approval['source_map_sha256'],'source_hashes_after_pure':source_map,
                    'pure_checks':invocation['pure_checks']}
    native_proof=pure_proof(native_receipt,source_map,'native')
    assert utc(native_proof['started_utc'])>=utc(pure_proof(preflight,source_map,'preflight')['completed_utc'])
    started=utc(invocation['created_utc'])
    assert started>=utc(native_proof['completed_utc'])
    assert closure['invocation_sha256']==seal(raw/'invocation.json')['sha256']
    assert typed(closure['source_hashes_after'],source_map)
    assert closure['error'] in (None,'') and closure['step_error'] in (None,'')
    raw_map=closure['raw']
    assert type(raw_map) is dict and len(raw_map)==23 and set(raw_map)==RAW_NAMES
    assert {p.name for p in raw.iterdir() if p.is_file()}==RAW_NAMES|{'invocation.json','closure.json'}
    for name,spec in raw_map.items():
        assert type(name) is str and '/' not in name and '\\' not in name
        keys(spec,{'bytes','sha256'})
        exact(raw/name,spec,292,33)
    for name in ('invocation.json','closure.json'):
        path=raw/name; exact(path,seal(path),292,33)
    steps=receipt_json((raw/'steps.json').read_bytes())
    assert type(steps) is list and len(steps)==6 and [step['name'] for step in steps]==STAGES
    previous=started
    for index,step in enumerate(steps):
        keys(step,STEP_KEYS)
        integer(step['sequence'],index); integer(step['exit_code'],0); integer(step['child_session_id'],0)
        assert type(step['child_pid']) is int and step['child_pid']>0
        assert step['capture_error'] is None and step['error'] is None and step['status']=='completed'
        boolean(step['gui_preserved'],True); boolean(step['converter_log_validated'],index==3)
        start,end=utc(step['started_utc']),utc(step['completed_utc'])
        assert previous<=start<=end; previous=end
        command=checkers[0] if index==2 else checkers[1] if index==5 else commands[0 if index==0 else 1 if index==1 else 2 if index==3 else 3]
        keys(command,{'name','program','arguments'})
        assert all(step[field]==command[field] for field in ('name','program','arguments'))
        stdout='roundtrip-validation.json' if index==2 else 'author-validation.json' if index==5 else step['name']+'-stdout.txt'
        stderr=step['name']+'-stderr.txt'
        for stream,filename in (('stdout',stdout),('stderr',stderr)):
            assert step[stream+'_path']==str(RUN/filename)
            exact(raw/filename,{'bytes':step[stream+'_bytes'],'sha256':step[stream+'_sha256']},292,33)
        integer(step['stderr_bytes'],0)
        if index==3:
            exact(raw/'model-run.log',{'bytes':step['converter_log_bytes'],'sha256':step['converter_log_sha256']},292,33)
        else:
            assert step['converter_log_bytes'] is None and step['converter_log_sha256'] is None
    assert seal(raw/'input.json')==INPUT_PIN
    assert converter_bytes((raw/'model-run.log').read_bytes())==17
    authored,exported,log,report,parent=source_oracles()
    actual_input=strict_json((raw/'input.json').read_bytes())
    actual_export=strict_json((raw/'roundtrip-raw.json').read_bytes())
    assert table_counts(actual_input,'model')==(33,23,211)
    assert table_counts(actual_export,'model')==(33,37,374)
    assert typed(actual_input,authored) and typed(actual_export,exported)
    native_log=(raw/'model.log').read_bytes()
    assert native_log==log and len(physical_lines(native_log))==115
    assert sum(s.startswith('Time: ') for s in physical_lines(native_log))==107
    native_report=native_report_json((raw/'report-raw.json').read_bytes())
    report_counts(native_report)
    assert typed(native_report,report)
    checker_receipt((raw/'roundtrip-validation.json').read_bytes(),'check_import_export',raw)
    checker_receipt((raw/'author-validation.json').read_bytes(),'check_behavior',raw)
    return {'decision':'GO_BOUNDED','physical_lines':115,'timed_lines':107,'report_cells':4044,
            'authored_cells':211,'export_cells':374,'raw_files':25}

def main()->dict:
    assert CASE.name=='I05-var07-scheduled-mission-turnround-v1.0.1'
    assert REPO.name=='repo' and METHOD==CASE/'review/independent_reader.py'
    if len(sys.argv)==3 and sys.argv[1] in ('--inventory-candidate','--manifest-candidate'):
        candidate=absolute(sys.argv[2])
        assert candidate.is_file() and not candidate.is_relative_to(CASE) and candidate.stat().st_file_attributes==33
        if sys.argv[1]=='--inventory-candidate':
            doc=source_inventory(candidate)
            return {'decision':'PASS_INVENTORY_CANDIDATE','source_count':doc['source_count'],'candidate_sha256':seal(candidate)['sha256']}
        doc,_=manifest_document(candidate)
        return {'decision':'PASS_MANIFEST_CANDIDATE','source_count':doc['source_count'],'candidate_sha256':seal(candidate)['sha256']}
    if len(sys.argv)==2 and sys.argv[1]=='--pure':
        source_oracles()
        assert converter_bytes(converter_fixture())==17
        manifest_document()
        return {'decision':'PASS_PURE_ORACLES','physical_lines':115,'report_cells':4044}
    if len(sys.argv)==2 and sys.argv[1]=='--preflight':
        receipts=list((CASE/'review').glob('preflight-ssh0-*.json'))
        assert len(receipts)==1
        preflight_receipt(receipts[0])
        return {'decision':'PASS_ACTUAL_ZERO_NATIVE_PREFLIGHT'}
    if len(sys.argv)==3 and sys.argv[1]=='--evidence-dir':
        return sealed_replay(absolute(sys.argv[2]))
    raise AssertionError('Use --inventory-candidate, --manifest-candidate, --pure, --preflight, or --evidence-dir')

if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True))
