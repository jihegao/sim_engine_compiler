"""Independent prospective A17.var06 semantic predicates. Draft; no author imports."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

METHOD = Path(__file__).resolve()
if METHOD.parent.name == 'tmp':
    REPO = METHOD.parent.parent
    CASE = REPO / 'cases/simlox-air-support/A17-var06-unit-group-xtime-v1.0.0'
elif METHOD.parent.name == 'review' and METHOD.parent.parent.name == 'A17-var06-unit-group-xtime-v1.0.0':
    CASE = METHOD.parent.parent
    REPO = CASE.parents[2]
else:
    raise AssertionError('independent reader is outside the approved tmp or owned review directory')
PARENT = REPO / 'cases/simlox-air-support/A17-multi-unit-group-v1.0.0'
PARENT_RUN = PARENT / 'runs/a17-v100-ssh-20260929-01'
CONTROL = REPO / 'cases/simlox-air-support/J07-unit-type-report-v1.0.0/runs/report-settings/a17-group-report-20261001-01/report-raw.json'
RUN_ID = 'a17-var06-xtime-v100-ssh-20261009-01'
RUN = CASE / 'runs' / RUN_ID
PARENT_INPUT_SHA = '66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974'
PARENT_EXPORT_SHA = '819bbdd65799d20441191f41ca4a5d4df9aaf658466dd49dd952707d96943a42'
PARENT_LOG_SHA = 'ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e'
CONTROL_SHA = '2c0894b74bab55c1d6cb239089e66980c7cd3d214bbab8b2b334bd89f7525474'
INPUT_SHA = '21a88bfe7eb34c42e2f11f541f624c42c3530ffc849af475c6fd31909350d22a'
EXPORT_ORACLE_SHA = '92c83e28dbdd44be0f89c4355b693bd7df4099a96b577161a7839cf4a4b2213e'
TABLES = ['ProblemDescription','ResultSummary','MissionResults','MissionResultsTotal','FixedMissionResults','FixedMissionResultsTotal','SystemResults','StockTotalResults']
COLS = [1,11,12,10,25,23,40,16]
ROWS = [1,1,72,1,1,1,72,72]


def pin(path: Path, digest: str) -> bytes:
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest, str(path)
    return data


def strict_json(data: bytes) -> dict:
    assert not data.startswith(b'\xef\xbb\xbf')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, key
            result[key] = value
        return result
    def invalid(value):
        raise AssertionError(value)
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)


def typed(expected, actual, datatype=None):
    if expected is None or actual is None:
        return expected is None and actual is None
    if datatype == 'double':
        return (type(expected) in (int,float) and type(actual) in (int,float)
                and math.isfinite(expected) and math.isfinite(actual) and expected == actual)
    if datatype == 'integer':
        return type(expected) is type(actual) is int and expected == actual
    if datatype == 'string':
        return type(expected) is type(actual) is str and expected == actual
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(typed(expected[k], actual[k]) for k in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(typed(a,b) for a,b in zip(expected,actual,strict=True))
    return expected == actual


def compare_model(expected: dict, actual: dict) -> tuple[int,int,int]:
    assert type(expected) is type(actual) is dict and set(expected) == set(actual) == {'model'}
    em, am = expected['model'], actual['model']
    assert type(em) is type(am) is dict and set(em) == set(am) == {'database_version','tables'}
    assert typed(em['database_version'],am['database_version'])
    et, at = em['tables'],am['tables']
    assert type(et) is type(at) is list and len(et) == len(at) == 33
    rows = cells = 0
    for e,a in zip(et,at,strict=True):
        assert type(e) is type(a) is dict and set(e) == set(a) == {'name','columns','instances'} and e['name'] == a['name']
        assert type(e['columns']) is type(a['columns']) is list and all(type(x) is dict for x in e['columns']+a['columns'])
        assert typed(e['columns'],a['columns'])
        assert type(e['instances']) is type(a['instances']) is list and len(e['instances']) == len(a['instances'])
        for ei,ai in zip(e['instances'],a['instances'],strict=True):
            assert type(ei) is type(ai) is dict and set(ei) == set(ai) == {'instance_name','rows'} and ei['instance_name'] == ai['instance_name']
            assert type(ei['rows']) is type(ai['rows']) is list and len(ei['rows']) == len(ai['rows'])
            for er,ar in zip(ei['rows'],ai['rows'],strict=True):
                rows += 1
                assert type(er) is type(ar) is list and len(er) == len(ar) == len(e['columns'])
                for col,ev,av in zip(e['columns'],er,ar,strict=True):
                    assert typed(ev,av,col['datatype']), (e['name'],col['name'],ev,av)
                    cells += 1
    return len(et),rows,cells


def one_xtime(parent: dict) -> dict:
    child = copy.deepcopy(parent)
    matches = []
    for t in child['model']['tables']:
        if t['name'] != 'UnitGroupMember':
            continue
        assert len(t['instances']) == 1 and t['instances'][0]['instance_name'] == ''
        names = [c['name'] for c in t['columns']]
        assert names == ['UGID','USTID','PRI','XTIME','NOTE']
        for row in t['instances'][0]['rows']:
            if row[names.index('UGID')] == 'TEACH-GROUP' and row[names.index('USTID')] == 'TEACH-UNIT-2':
                assert type(row[names.index('XTIME')]) in (int,float) and row[names.index('XTIME')] == 0
                row[names.index('XTIME')] = 1.0
                matches.append(row)
    assert len(matches) == 1
    return child


def source_oracles() -> dict:
    parent = strict_json(pin(PARENT/'native-input.json',PARENT_INPUT_SHA))
    child = strict_json(pin(CASE/'native-input.json',INPUT_SHA))
    expected = one_xtime(parent)
    assert compare_model(expected,child) == (33,20,203)
    parent_export = strict_json(pin(PARENT_RUN/'roundtrip-raw.json',PARENT_EXPORT_SHA))
    child_export = strict_json(pin(CASE/'child-roundtrip-oracle.json',EXPORT_ORACLE_SHA))
    expected_export = one_xtime(parent_export)
    assert compare_model(expected_export,child_export) == (33,38,387)
    return {'authored_cells':203,'export_cells':387}


def physical_log(raw: bytes) -> dict:
    parent = pin(PARENT_RUN/'model.log',PARENT_LOG_SHA)
    assert raw == parent
    assert raw.count(b'\n') == raw.count(b'\r\n') and raw.endswith(b'\r\n')
    lines = raw.decode('ascii').splitlines()
    assert len(lines) == 60 and sum(line.startswith('Time:') for line in lines) == 52
    assert lines.count('Time: 7 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission allocates system: <TEACH-AIR-01,0>') == 1
    assert lines.count('Time: 7 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission allocates system: <TEACH-AIR-01,1>') == 1
    assert lines.index('Time: 7 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission allocates system: <TEACH-AIR-01,0>') < lines.index('Time: 7 <BASIC-MISSION,TEACH-GROUP,0,0,0> mission allocates system: <TEACH-AIR-01,1>')
    return {'physical_lines':60,'timed_lines':52}


def compare_report(expected: dict, actual: dict) -> int:
    assert type(expected) is type(actual) is dict and set(expected) == set(actual) == {'report'}
    er,ar = expected['report'],actual['report']
    assert type(er) is type(ar) is dict and set(er) == set(ar) == {'database_version','tables'}
    assert typed(er['database_version'],ar['database_version'])
    et,at=er['tables'],ar['tables']
    assert type(et) is type(at) is list and all(type(t) is dict for t in et+at)
    assert [t['name'] for t in et] == [t['name'] for t in at] == TABLES
    assert [len(t['columns']) for t in et] == [len(t['columns']) for t in at] == COLS
    assert [sum(len(i['rows']) for i in t['instances']) for t in et] == [sum(len(i['rows']) for i in t['instances']) for t in at] == ROWS
    cells = 0
    for e,a in zip(et,at,strict=True):
        assert type(e) is type(a) is dict and set(e) == set(a) == {'name','columns','instances'} and e['name'] == a['name']
        assert type(e['columns']) is type(a['columns']) is list and all(type(x) is dict for x in e['columns']+a['columns'])
        assert typed(e['columns'],a['columns'])
        assert type(e['instances']) is type(a['instances']) is list and len(e['instances']) == len(a['instances'])
        for ei,ai in zip(e['instances'],a['instances'],strict=True):
            assert type(ei) is type(ai) is dict and set(ei) == set(ai) == {'instance_name','rows'} and ei['instance_name'] == ai['instance_name']
            assert type(ei['rows']) is type(ai['rows']) is list and len(ei['rows']) == len(ai['rows'])
            for erow,arow in zip(ei['rows'],ai['rows'],strict=True):
                assert type(erow) is type(arow) is list and len(erow) == len(arow) == len(e['columns'])
                for col,ev,av in zip(e['columns'],erow,arow,strict=True):
                    assert typed(ev,av,col['datatype']), (e['name'],col['name'],ev,av)
                    cells += 1
    assert cells == 4966
    return cells


def selected_report(raw: bytes) -> dict:
    assert raw.count(b'\n') == raw.count(b'\r\n') and not raw.startswith(b'\xef\xbb\xbf')
    expected = copy.deepcopy(strict_json(pin(CONTROL,CONTROL_SHA)))
    table = expected['report']['tables'][4]
    assert table['name'] == 'FixedMissionResults' and len(table['instances']) == 1
    ins = table['instances'][0]
    assert ins['instance_name'] == '' and len(ins['rows']) == 1
    row = ins['rows'][0]
    columns = table['columns']; names = [x['name'] for x in columns]
    assert [row[names.index(x)] for x in ('UNID','MTID','STIM')] == ['TEACH-GROUP','Total over all Missions',8]
    idx = names.index('STOTD')
    assert columns[idx]['datatype'] == 'double' and type(row[idx]) is int and row[idx] == 0
    row[idx] = 1
    actual = strict_json(raw)
    return {'typed_cells':compare_report(expected,actual),'stotd':1}


def behavior(run: Path) -> dict:
    a = source_oracles()
    a.update(physical_log((run/'model.log').read_bytes()))
    a.update(selected_report((run/'report-raw.json').read_bytes()))
    return a
# Independent byte and protocol custody. No author imports, native invocation, or Git calls.
import datetime
import re
import sys

BASE='270740a51e937be00b6975ab2960c16ccb131f5a'
EXE=r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
PYTHON=r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
SETTINGS=REPO/'cases/simlox-air-support/J07-unit-type-report-v1.0.0/runs/report-settings/group.sxs'
SETTINGS_PIN={'bytes':119120,'sha256':'e78466cc27d8c213e4d9bf4ed0065844471593069e81abe665cbd7fa4e9172ea'}
NEGATIVE=REPO/'cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0/runs/i04-var05-zero-transport-between-v100-ssh-20261008-01/model-run.log'
NEGATIVE_PIN={'bytes':1122,'sha256':'ca209899bce7e299b49d9a482469efd8c0fee0d9f56673ffb99783cbf689457a'}
EXE_PIN={'bytes':33196032,'sha256':'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'}
PYTHON_PIN={'bytes':106448,'sha256':'10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1'}
CONTRACT_SHA='58c12480998f691b619f305922eace2eb1b4aede71fbb779de77ad0085bb15e7'
SOURCE_PINS_SHA='621ef7d779a93d243d04faf3769929ad9695d04d0f66f339b2fc7a56c7e9f049'
PAIRS_SHA='66d9993d8ca7a3113811761b66e087574c3e8ca8c91ca295c0b651b8999ad541'
SELECTION_SHA='04d57600dd94386e2fd929bc3b01e2eab5f5c5cb21f23f130399b46a0dbfa7c2'
TOOLS=['build.py','source_gate.py','self_check.py','make_source_inventory.py','make_prelaunch_manifest.py']
STAGES=['import','export','check_import_export','calc','selectedreport','check_behavior']
SPECIAL={'run_native_ssh.ps1':'runner_script','validate_native_cli.py':'behavior_validator','preserved-design/contract.json':'prospective_contract','execution-contract.json':'execution_binding','native-input.json':'child_input'}
OWNED=(
'.gitattributes','build.py','captured_process.ps1','check_roundtrip.py','checker_receipt.ps1','child-roundtrip-oracle.json','event_ledger.py','execution-contract.json','make_prelaunch_manifest.py','make_source_inventory.py','model_common.py','native-input.json','preflight_receipt.ps1','prospective-log-oracle.bytes','report_oracle.py','run_native_ssh.ps1','self_check.py','source_gate.py','ssh_transport.py','test_converter_gate.ps1','validate_native_cli.py',
'preserved-context/root-selection-receipt.json','preserved-design/contract.json','preserved-design/oracle-map.json','preserved-design/README.md','preserved-design/independent-contract-go.md','preserved-design/author-child-build-v100.py.bytes','preserved-design/independent-audit-v100-unexecuted.py.bytes','preserved-design/independent-audit-v101.py.bytes','preserved-design/independent-audit-receipt.json','preserved-design/independent-audit-stdout.bin','preserved-design/independent-audit-stderr.bin',
'preserved-development/self-check-v1-log-index-assumption.py.bytes','preserved-development/self-check-v1-log-index-assumption.md','preserved-development/self-check-v2-bool-equality-assumption.py.bytes','preserved-development/self-check-v2-bool-equality-assumption.md','preserved-development/template-a17-var01-captured_process.ps1.bytes','preserved-development/template-a17-var01-checker_receipt.ps1.bytes','preserved-development/template-a17-var01-make_prelaunch_manifest.py.bytes','preserved-development/template-a17-var01-make_source_inventory.py.bytes','preserved-development/template-a17-var01-preflight_receipt.ps1.bytes','preserved-development/template-a17-var01-run_native_ssh.ps1.bytes','preserved-development/template-a17-var01-ssh_transport.py.bytes','preserved-development/template-a17-var01-test_converter_gate.ps1.bytes',
'review/independent_reader.py','review/independent_self_check.py','review/independent-static-go-2026-10-09.md','source-maps/accepted-source-pairs.json','source-maps/prospective-source-pins.json')
MANIFEST_KEYS=set('schema run_id native_run_directory file_line_ascii_bytes file_line_ascii_max base_commit contract_sha256 execution_binding_sha256 input_sha256 source_inventory_sha256 runner_sha256 validator_sha256 independent_reader_sha256 report_settings source_count source_files owned_source_count accepted_source_pair_count required_local_source_count mandatory_original_count archived_catalog_count converter_negative_original_count installed_executable_count catalog_prefix_entries live_catalog_prelaunch_pin pure_tools stages native_commands pure_checkers new_native_runs_authorized_by_manifest independent_method_state'.split())
PREFLIGHT_KEYS=set('schema run_id native_run_directory run_dirs_absent file_line_ascii_bytes file_line_ascii_max native_run_path_ancestors_no_reparse ssh_session ps_major ssh_ancestors mutex_free wts_active_gui_count gui accepted_source_pair_count required_local_source_count mandatory_original_count archived_catalog_count converter_negative_original_count installed_executable_count catalog_prefix_entries manifest_sha256 source_map_sha256 source_hashes source_hashes_after_pure pure_proof_directory pure_proof_path pure_proof_sha256 pure_checks native_process_started'.split())
PROOF_KEYS=set('schema mode run_id native_run_directory manifest_sha256 source_map_sha256 started_utc completed_utc status error checks source_hashes_after'.split())
PURE_STEP_KEYS=set('tool program arguments started_utc completed_utc status error child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256'.split())
APPROVAL_KEYS=set('schema decision run_id native_run_directory manifest_sha256 runner_sha256 validator_sha256 contract_sha256 execution_binding_sha256 input_sha256 source_map_sha256 independent_reader_sha256 preflight_relative_path preflight_sha256'.split())
INVOCATION_KEYS=set('schema run_id created_utc original_run_dir native_run_directory input_sha256 contract_sha256 manifest_sha256 approval_sha256 approved_preflight_path approved_preflight_sha256 independent_reader_sha256 runner_script_sha256 session_id ssh_ancestors gui queue_mutex working_directory planned_commands planned_checkers source_hashes_before source_hashes_after_pure pure_proof_path pure_proof_sha256 pure_checks publication_state'.split())
CLOSURE_KEYS=set('schema run_id native_run_directory invocation_sha256 manifest_sha256 approval_sha256 approved_preflight_sha256 source_hashes_before source_hashes_after raw step_error error publication_state'.split())
STEP_KEYS=set('sequence name program arguments started_utc completed_utc child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256 converter_log_bytes converter_log_sha256 converter_log_validated gui_preserved status error'.split())


def seal(path:Path)->dict:
    data=path.read_bytes(); return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def exact(path:Path,spec:dict,readonly=False):
    assert type(spec) is dict and set(spec)=={'bytes','sha256'}
    assert seal(path)==spec,str(path)
    if readonly: assert path.stat().st_file_attributes&1,str(path)

def keys(body,wanted):
    assert type(body) is dict and set(body)==set(wanted),(set(body)^set(wanted))

def integer(value,wanted): assert type(value) is int and value==wanted

def boolean(value,wanted): assert type(value) is bool and value is wanted

def absolute(value):
    assert type(value) is str
    path=Path(value)
    assert path.is_absolute() and '..' not in path.parts
    return path

def utc(value):
    assert type(value) is str
    moment=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    assert moment.tzinfo is not None and moment.utcoffset()==datetime.timedelta(0)
    return moment

def source_inventory(candidate:Path|None=None):
    path=CASE/'source-inventory.json' if candidate is None else candidate
    doc=strict_json(path.read_bytes())
    keys(doc,{'schema','source_count','source_files'})
    assert doc['schema']=='a17-var06-source-inventory/v100'
    integer(doc['source_count'],len(OWNED))
    assert type(doc['source_files']) is list and len(doc['source_files'])==len(OWNED)
    for rel,row in zip(OWNED,doc['source_files'],strict=True):
        keys(row,{'path','bytes','sha256'})
        assert row['path']==rel
        exact(CASE/rel,{'bytes':row['bytes'],'sha256':row['sha256']},readonly=True)
    return doc

def manifest_document(candidate:Path|None=None):
    inventory=source_inventory()
    path=CASE/'prelaunch-manifest.json' if candidate is None else candidate
    doc=strict_json(path.read_bytes())
    keys(doc,MANIFEST_KEYS)
    assert doc['schema']=='a17-var06-prelaunch-manifest/v100'
    assert doc['run_id']==RUN_ID and type(doc['native_run_directory']) is str and doc['native_run_directory']==str(RUN)
    fileline='File: '+str(RUN/'model.sxi').replace('\\','/')
    assert fileline.isascii() and len(fileline.encode('ascii'))==182
    integer(doc['file_line_ascii_bytes'],182); integer(doc['file_line_ascii_max'],199)
    assert doc['base_commit']==BASE and doc['contract_sha256']==CONTRACT_SHA
    for field,rel in {'execution_binding_sha256':'execution-contract.json','input_sha256':'native-input.json','source_inventory_sha256':'source-inventory.json','runner_sha256':'run_native_ssh.ps1','validator_sha256':'validate_native_cli.py','independent_reader_sha256':'review/independent_reader.py'}.items():
        assert doc[field]==seal(CASE/rel)['sha256'],field
    assert doc['input_sha256']==INPUT_SHA
    for field,wanted in [('accepted_source_pair_count',59),('required_local_source_count',12),('mandatory_original_count',66),('archived_catalog_count',2),('converter_negative_original_count',1),('installed_executable_count',2),('catalog_prefix_entries',502),('native_commands',4),('pure_checkers',2),('new_native_runs_authorized_by_manifest',0)]: integer(doc[field],wanted)
    assert doc['pure_tools']==TOOLS and doc['stages']==STAGES
    assert doc['independent_method_state']=='METHOD_ONLY_NO_NATIVE_APPROVAL'
    pairpath=CASE/'source-maps/accepted-source-pairs.json'; pinpath=CASE/'source-maps/prospective-source-pins.json'
    assert seal(pairpath)=={'bytes':25276,'sha256':PAIRS_SHA}
    assert seal(pinpath)['sha256']==SOURCE_PINS_SHA
    pairs=strict_json(pairpath.read_bytes()); pins=strict_json(pinpath.read_bytes())
    assert type(pairs) is list and len(pairs)==59
    assert len(pins['required_local_sources'])==12 and len(pins['mandatory_originals'])==66
    assert pins['accepted_source_pairs']['sha256']==PAIRS_SHA
    assert pins['selection_receipt']['sha256']==SELECTION_SHA
    expected=[]
    for row in inventory['source_files']:
        rel=row['path']; expected.append({'key':SPECIAL.get(rel,'owned:'+rel),'path':str(CASE/rel),'bytes':row['bytes'],'sha256':row['sha256']})
    expected.append({'key':'owned:source-inventory.json','path':str(CASE/'source-inventory.json'),**seal(CASE/'source-inventory.json')})
    for row in pairs:
        keys(row,{'path','oid','disk','git','byte_equal'})
        path=REPO/row['path']; exact(path,row['disk'])
        expected.append({'key':'accepted:'+row['path'],'path':str(path),**row['disk']})
    for prefix,records in [('required-local',pins['required_local_sources']),('mandatory',pins['mandatory_originals'])]:
        for i,row in enumerate(records):
            path=absolute(row['path']); spec={'bytes':row['bytes'],'sha256':row['sha256']}; exact(path,spec)
            if prefix=='mandatory':
                assert path.stat().st_mode==row['original_mode'] and path.stat().st_file_attributes==row['original_attributes']
            expected.append({'key':f'{prefix}:{i:02d}','path':str(path),**spec})
    for label in ('catalog_local_502','catalog_git_502'):
        row=pins[label]; path=absolute(row['path']); spec={'bytes':row['bytes'],'sha256':row['sha256']}; exact(path,spec)
        expected.append({'key':'archive:'+label,'path':str(path),**spec})
    exact(NEGATIVE,NEGATIVE_PIN)
    expected.append({'key':'converter:failed-file-line-v100','path':str(NEGATIVE),**NEGATIVE_PIN})
    for role,path,spec in [('installed:simlox-exe',Path(EXE),EXE_PIN),('installed:python-runtime',Path(PYTHON),PYTHON_PIN)]:
        exact(path,spec); expected.append({'key':role,'path':str(path),**spec})
    exact(SETTINGS,SETTINGS_PIN)
    expected.append({'key':'instrumentation:j07-group-settings','path':str(SETTINGS),**SETTINGS_PIN})
    keys(doc['report_settings'],{'path','bytes','sha256'})
    assert doc['report_settings']=={'path':str(SETTINGS),**SETTINGS_PIN}
    integer(doc['owned_source_count'],len(OWNED)+1)
    integer(doc['source_count'],len(expected))
    assert len(expected)==len(OWNED)+144 and doc['source_files']==expected
    rolekeys=set(); paths={}
    for row in doc['source_files']:
        keys(row,{'key','path','bytes','sha256'})
        key=row['key'].casefold(); assert key not in rolekeys; rolekeys.add(key)
        resolved=str(Path(row['path']).resolve(strict=True)).replace('/','\\').casefold()
        identity=(row['bytes'],row['sha256'])
        assert resolved not in paths or paths[resolved]==identity
        paths[resolved]=identity
    keys(doc['live_catalog_prelaunch_pin'],{'path','bytes','sha256'})
    catalog=REPO/'cases/simlox-air-support/publication-index-v1.json'
    assert doc['live_catalog_prelaunch_pin']['path']==str(catalog)
    exact(catalog,{'bytes':doc['live_catalog_prelaunch_pin']['bytes'],'sha256':doc['live_catalog_prelaunch_pin']['sha256']})
    return doc,{row['key']:row['sha256'] for row in expected}


def source_map_digest(source_map):
    return hashlib.sha256(json.dumps(source_map,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()

def pure_proof(receipt:dict,source_map:dict,mode:str):
    proof_dir=absolute(receipt['pure_proof_directory'])
    assert proof_dir.parent==CASE/'test-output'
    assert re.fullmatch(rf'{mode}-pure-[0-9]{{8}}T[0-9]{{13}}Z-[0-9a-f]{{8}}',proof_dir.name)
    proof_path=proof_dir/'pure-proof.json'
    assert receipt['pure_proof_path']==str(proof_path) and receipt['pure_proof_sha256']==seal(proof_path)['sha256']
    proof=receipt_json(proof_path.read_bytes()); keys(proof,PROOF_KEYS)
    assert proof['schema']=='a17-var06-pure-proof/v100' and proof['mode']==mode
    assert proof['run_id']==RUN_ID and type(proof['native_run_directory']) is str and proof['native_run_directory']==str(RUN)
    assert proof['status']=='passed' and proof['error'] is None
    assert proof['manifest_sha256']==receipt['manifest_sha256'] and proof['source_map_sha256']==receipt['source_map_sha256']
    assert proof['source_hashes_after']==source_map and receipt['source_hashes_after_pure']==source_map
    assert proof['checks']==receipt['pure_checks'] and type(proof['checks']) is list and len(proof['checks'])==len(TOOLS)
    previous=utc(proof['started_utc'])
    for tool,step in zip(TOOLS,proof['checks'],strict=True):
        keys(step,PURE_STEP_KEYS)
        assert step['tool']==tool and step['program']==PYTHON
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


def preflight_receipt(path:Path):
    manifest,source_map=manifest_document()
    receipt=receipt_json(path.read_bytes()); keys(receipt,PREFLIGHT_KEYS)
    assert receipt['schema']=='a17-var06-ssh-preflight/v100' and receipt['run_id']==RUN_ID
    assert type(receipt['native_run_directory']) is str and receipt['native_run_directory']==str(RUN)
    assert receipt['manifest_sha256']==seal(CASE/'prelaunch-manifest.json')['sha256']
    assert receipt['source_map_sha256']==source_map_digest(source_map)
    assert receipt['source_hashes']==source_map and receipt['source_hashes_after_pure']==source_map
    for field,wanted in [('file_line_ascii_bytes',182),('file_line_ascii_max',199),('ssh_session',0),('ps_major',5),('wts_active_gui_count',1),('accepted_source_pair_count',59),('required_local_source_count',12),('mandatory_original_count',66),('archived_catalog_count',2),('converter_negative_original_count',1),('installed_executable_count',2),('catalog_prefix_entries',502)]: integer(receipt[field],wanted)
    for field,wanted in [('run_dirs_absent',True),('native_run_path_ancestors_no_reparse',True),('mutex_free',True),('native_process_started',False)]: boolean(receipt[field],wanted)
    assert type(receipt['ssh_ancestors']) is list and 'sshd.exe' in receipt['ssh_ancestors']
    keys(receipt['gui'],{'pid','session_id','start_unix_ms','responding'})
    for field,wanted in [('pid',13340),('session_id',1),('start_unix_ms',1790590196826)]: integer(receipt['gui'][field],wanted)
    boolean(receipt['gui']['responding'],True)
    pure_proof(receipt,source_map,'preflight')
    assert path.parent==CASE/'review' and re.fullmatch(r'preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json',path.name)
    return receipt,source_map


def approval_document(path:Path):
    body=receipt_json(path.read_bytes()); keys(body,APPROVAL_KEYS)
    assert body['schema']=='a17-var06-independent-prelaunch-go/v100' and body['decision']=='GO_PRELAUNCH'
    assert body['run_id']==RUN_ID and type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    manifest,source_map=manifest_document()
    for field,wanted in [('manifest_sha256',seal(CASE/'prelaunch-manifest.json')['sha256']),('runner_sha256',manifest['runner_sha256']),('validator_sha256',manifest['validator_sha256']),('contract_sha256',CONTRACT_SHA),('execution_binding_sha256',manifest['execution_binding_sha256']),('input_sha256',INPUT_SHA),('source_map_sha256',source_map_digest(source_map)),('independent_reader_sha256',seal(CASE/'review/independent_reader.py')['sha256'])]:
        assert body[field]==wanted,field
    rel=body['preflight_relative_path'].replace('\\','/')
    assert re.fullmatch(r'review/preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json',rel)
    receipt_path=CASE/rel
    assert receipt_path.is_file() and receipt_path.resolve(strict=True).parent==(CASE/'review').resolve(strict=True)
    assert body['preflight_sha256']==seal(receipt_path)['sha256']
    return body,preflight_receipt(receipt_path)[0]

def converter_bytes(data:bytes)->int:
    assert data and b'\n' not in data.replace(b'\r\n',b'')
    lines=data.decode('utf-8').split('\r\n')
    if lines[-1]=='': lines.pop()
    assert len(lines)==17
    expected=[
        'Performing simulation',
        'Input file: '+str(RUN/'model.sxi'),
        'Output file: '+str(RUN/'model.sxo'),
        'Simulating.','Converting input data ...',
        'File: '+str(RUN/'model.sxi').replace('\\','/'),
        'Form: Control',
        'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',
        'Form: System',
        'rec 1: (warning #126) This system contains no items: TEACH-AIR-01',
        'Input conversion completed. Errors: 0, Warnings: 2, Notes: 0',
        None,'Starting simulation...',None,'Saving results ...',None,None,
    ]
    for actual,predicted in zip(lines,expected,strict=True):
        if predicted is not None: assert actual==predicted,(actual,predicted)
    for index,label in [(11,'Input data conversion time'),(13,'Simulation time'),(15,'Result saving time'),(16,'Total execution time')]:
        match=re.fullmatch(re.escape(label)+r': ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) secs\.',lines[index])
        assert match and math.isfinite(float(match.group(1))) and float(match.group(1))>=0
    assert len(lines[1].encode('ascii'))==188 and len(lines[2].encode('ascii'))==189
    assert len(lines[5].encode('ascii'))==182 and len(lines[5].encode('ascii'))<=199
    return len(lines)


def checker_receipt(data:bytes,name:str,raw:Path):
    body=strict_json(data)
    common={'schema','passed','run_id','native_run_directory','input_sha256','export_sha256','native_calls','issues'}
    if name=='check_import_export':
        wanted=common|{'authored_tables','authored_rows','authored_cells','exported_tables','exported_rows','exported_cells'}
        schema='a17-var06-roundtrip-check/v100'
    else:
        assert name=='check_behavior'
        wanted=common|{'log_sha256','report_sha256','physical_log_lines','timed_log_lines','report_typed_cells','stotd','authored_cells','exported_cells'}
        schema='a17-var06-native-behavior-check/v100'
    keys(body,wanted)
    assert body['schema']==schema and body['run_id']==RUN_ID
    boolean(body['passed'],True)
    assert type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    assert body['input_sha256']==INPUT_SHA and body['export_sha256']==seal(raw/'roundtrip-raw.json')['sha256']
    integer(body['native_calls'],0); assert body['issues']==[]
    if name=='check_import_export':
        for field,wanted in [('authored_tables',33),('authored_rows',20),('authored_cells',203),('exported_tables',33),('exported_rows',38),('exported_cells',387)]: integer(body[field],wanted)
    else:
        assert body['log_sha256']==seal(raw/'model.log')['sha256'] and body['report_sha256']==seal(raw/'report-raw.json')['sha256']
        for field,wanted in [('physical_log_lines',60),('timed_log_lines',52),('report_typed_cells',4966),('stotd',1),('authored_cells',203),('exported_cells',387)]: integer(body[field],wanted)
    return body


def receipt_json(data:bytes):
    return strict_json(data[3:] if data.startswith(b'\xef\xbb\xbf') else data)

def planned():
    def rf(name): return str(RUN/name)
    commands=[
        {'name':'import','program':EXE,'arguments':f'-silent -jimport "{rf("input.json")}" -save "{rf("model.sxi")}" -log "{rf("import.log")}" -close'},
        {'name':'export','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -jexport "{rf("roundtrip-raw.json")}" -log "{rf("export.log")}" -close'},
        {'name':'calc','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -threads 1 -calc -log "{rf("model-run.log")}" -close'},
        {'name':'selectedreport','program':EXE,'arguments':f'"{rf("model.sxo")}" -silent -report -rpts "{SETTINGS}" -rjexport "{rf("report-raw.json")}" -log "{rf("report-export.log")}" -close'},
    ]
    checkers=[
        {'name':'check_import_export','program':PYTHON,'arguments':f'-X utf8 -B "{CASE/"check_roundtrip.py"}" --run-dir "{RUN}"'},
        {'name':'check_behavior','program':PYTHON,'arguments':f'-X utf8 -B "{CASE/"validate_native_cli.py"}" --run-dir "{RUN}"'},
    ]
    return commands,checkers


def sealed_replay(raw:Path):
    assert raw.is_dir() and raw.resolve(strict=True)!=RUN.resolve(strict=True)
    manifest,source_map=manifest_document()
    approval,preflight=approval_document(CASE/'review/independent-prelaunch-go.json')
    invocation=receipt_json((raw/'invocation.json').read_bytes())
    closure=receipt_json((raw/'closure.json').read_bytes())
    keys(invocation,INVOCATION_KEYS); keys(closure,CLOSURE_KEYS)
    assert invocation['schema']=='a17-var06-invocation/v100' and closure['schema']=='a17-var06-closure/v100'
    for body in (invocation,closure):
        assert body['run_id']==RUN_ID and type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
        assert body['manifest_sha256']==approval['manifest_sha256']
        assert body['approval_sha256']==seal(CASE/'review/independent-prelaunch-go.json')['sha256']
        assert body['approved_preflight_sha256']==approval['preflight_sha256']
        assert body['source_hashes_before']==source_map
    assert invocation['original_run_dir']==str(RUN)
    assert invocation['input_sha256']==INPUT_SHA and invocation['contract_sha256']==CONTRACT_SHA
    assert invocation['approved_preflight_path']==str(CASE/approval['preflight_relative_path'])
    assert invocation['independent_reader_sha256']==manifest['independent_reader_sha256']
    assert invocation['runner_script_sha256']==manifest['runner_sha256']
    assert invocation['source_hashes_after_pure']==source_map
    assert invocation['queue_mutex']==r'Global\SimloxIssue18NativeQueue'
    assert invocation['working_directory']==r'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
    assert invocation['publication_state']==closure['publication_state']=='not_published'
    integer(invocation['session_id'],0)
    assert type(invocation['ssh_ancestors']) is list and 'sshd.exe' in invocation['ssh_ancestors']
    assert invocation['gui']==preflight['gui']
    commands,checkers=planned()
    assert invocation['planned_commands']==commands and invocation['planned_checkers']==checkers
    native_path=absolute(invocation['pure_proof_path'])
    assert native_path.parent.parent==CASE/'test-output'
    native_receipt={'pure_proof_directory':str(native_path.parent),'pure_proof_path':str(native_path),
        'pure_proof_sha256':invocation['pure_proof_sha256'],'manifest_sha256':approval['manifest_sha256'],
        'source_map_sha256':approval['source_map_sha256'],'source_hashes_after_pure':source_map,
        'pure_checks':invocation['pure_checks']}
    native_proof=pure_proof(native_receipt,source_map,'native')
    started=utc(invocation['created_utc'])
    assert started>=utc(native_proof['completed_utc'])
    assert closure['invocation_sha256']==seal(raw/'invocation.json')['sha256']
    assert closure['source_hashes_after']==source_map
    assert closure['error'] in (None,'') and closure['step_error'] in (None,'')
    raw_map=closure['raw']
    assert type(raw_map) is dict and len(raw_map)==23
    assert {p.name for p in raw.iterdir() if p.is_file()}==set(raw_map)|{'invocation.json','closure.json'}
    for name,spec in raw_map.items():
        assert type(name) is str and '/' not in name and '\\' not in name and name not in ('invocation.json','closure.json')
        path=raw/name
        assert not path.is_symlink() and not (path.stat().st_file_attributes&0x400)
        exact(path,spec,readonly=True)
    for special in ('invocation.json','closure.json'):
        path=raw/special
        assert not path.is_symlink() and not (path.stat().st_file_attributes&0x400)
        exact(path,seal(path),readonly=True)
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
        command=(checkers[0] if index==2 else checkers[1] if index==5 else commands[0 if index==0 else 1 if index==1 else 2 if index==3 else 3])
        keys(command,{'name','program','arguments'})
        assert all(step[field]==command[field] for field in ('name','program','arguments'))
        stdout='roundtrip-validation.json' if index==2 else 'author-validation.json' if index==5 else step['name']+'-stdout.txt'
        stderr=step['name']+'-stderr.txt'
        for stream,filename in [('stdout',stdout),('stderr',stderr)]:
            assert step[stream+'_path']==str(RUN/filename)
            exact(raw/filename,{'bytes':step[stream+'_bytes'],'sha256':step[stream+'_sha256']},readonly=True)
        integer(step['stderr_bytes'],0)
        if index==3:
            exact(raw/'model-run.log',{'bytes':step['converter_log_bytes'],'sha256':step['converter_log_sha256']},readonly=True)
        else:
            assert step['converter_log_bytes'] is None and step['converter_log_sha256'] is None
    assert seal(raw/'input.json')['sha256']==INPUT_SHA
    assert converter_bytes((raw/'model-run.log').read_bytes())==17
    actual_export=strict_json((raw/'roundtrip-raw.json').read_bytes())
    expected_export=strict_json(pin(CASE/'child-roundtrip-oracle.json',EXPORT_ORACLE_SHA))
    assert compare_model(expected_export,actual_export)==(33,38,387)
    assert physical_log((raw/'model.log').read_bytes())['timed_lines']==52
    assert selected_report((raw/'report-raw.json').read_bytes())['typed_cells']==4966
    checker_receipt((raw/'roundtrip-validation.json').read_bytes(),'check_import_export',raw)
    checker_receipt((raw/'author-validation.json').read_bytes(),'check_behavior',raw)
    return {'decision':'GO_BOUNDED','full_lines':60,'timed_lines':52,'report_cells':4966,
            'stotd':1,'authored_cells':203,'export_cells':387,'raw_files':25}


def converter_fixture():
    parent=(PARENT_RUN/'run.log').read_bytes().decode('utf-8')
    old=str(PARENT_RUN); new=str(RUN)
    assert parent.count(old)==2 and parent.count(old.replace('\\','/'))==1
    return parent.replace(old,new).replace(old.replace('\\','/'),new.replace('\\','/')).encode('utf-8')


def main():
    if len(sys.argv)==3 and sys.argv[1] in ('--inventory-candidate','--manifest-candidate'):
        candidate=absolute(sys.argv[2])
        assert candidate.is_file() and not candidate.is_relative_to(CASE) and candidate.stat().st_file_attributes&1
        if sys.argv[1]=='--inventory-candidate':
            doc=source_inventory(candidate)
            return {'decision':'PASS_INVENTORY_CANDIDATE','source_count':doc['source_count'],'candidate_sha256':seal(candidate)['sha256']}
        doc,_=manifest_document(candidate)
        return {'decision':'PASS_MANIFEST_CANDIDATE','source_count':doc['source_count'],'candidate_sha256':seal(candidate)['sha256']}
    if len(sys.argv)==2 and sys.argv[1]=='--pure':
        source_oracles()
        parent_log=pin(PARENT_RUN/'model.log',PARENT_LOG_SHA)
        physical_log(parent_log)
        assert converter_bytes(converter_fixture())==17
        return {'decision':'PASS_PURE_ORACLES','physical_lines':60,'report_cells':4966}
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
