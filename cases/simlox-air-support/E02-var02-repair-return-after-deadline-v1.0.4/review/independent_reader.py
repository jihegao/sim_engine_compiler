"""Independent E02.var02 v104 source, prospective behavior, and custody reader.

No author or accepted-checker imports. No native, SSH, or Git mutation.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import re
import sys
from pathlib import Path

METHOD = Path(__file__).resolve()
if METHOD.parent.name == 'tmp':
    REPO = METHOD.parent.parent
    CASE = REPO / 'cases/simlox-air-support/E02-var02-repair-return-after-deadline-v1.0.4'
elif METHOD.parent.name == 'review' and METHOD.parent.parent.name == 'E02-var02-repair-return-after-deadline-v1.0.4':
    CASE = METHOD.parent.parent
    REPO = CASE.parents[2]
else:
    raise AssertionError('independent reader outside approved tmp or case review path')

RUN_ID = 'e02-var02-repair-deadline-v104-ssh-20261009-01'
RUN = REPO / 'tmp/e02-var02-native-v104-20261009-01'
RECOVERED = CASE / 'runs' / RUN_ID
PARENT = REPO / 'cases/simlox-air-support/E02-zero-stock-local-backorder-v1.0.0'
PARENT_RUN = PARENT / 'runs/e02-v100-ssh-20260929-01'
PROSPECTIVE = REPO / 'tmp/e02-var02-prospective-v104-20261009-01'
BASE = '7b9dc461d629e28ed6f719d6c155dad9db9dca60'
CONTRACT_SHA = 'f8de374b6f78e661d9f453b96fe701db321f94686d02fbec92b8e4095f8fea3b'
INPUT_SHA = 'fe9579fc77222196ffcd942fb5a09e98e8ebfca5208f7b954dcfcf1c6f05f98b'
EXPORT_SHA = 'e1559006606357ad8525dc129ad77e9bdb52e7364da14143ab2ed302ae50990a'
REPORT_SHA = '910f3495d9217cb47e884f6a2adabee45b76add700c90c4340c636c1867af7a4'
PATTERN_SHA = 'b11b963d2572af36b159326c606ae71f0e525edd0d0b1c3d985e19e96e87b332'
TEMPLATE_SHA = '2ac25ce130a7c4c6f078fdf9aa2ed379dba4fa093380ec0601fc7f9628d777c9'
PARENT_INPUT_SHA = '12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd'
PARENT_EXPORT_SHA = 'c4dad7079837d761dff5ac8285a84441cb2b21e0f8b1bb52d137f00bafdf935a'
PARENT_LOG_SHA = 'bdea346172a799f2c4c1630fe5f9f132dda6d5f4f6c439fc024ed329bc09dd0c'
PARENT_CONVERTER_SHA = 'fae5fb871950de469211bbd2ce2d6dd1b084e6a5c2212b935d22e2350b71f895'
SELECTION_SHA = '1207a61dc842fba2c0102c4ea03bbc142b7fd8f560ae3970df67bcc47e3a12f5'
EXE = r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
PYTHON = r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
TOOLS = ['build.py','source_gate.py','self_check.py','make_source_inventory.py','make_prelaunch_manifest.py']
STAGES = ['import','export','check_import_export','calc','jsonreport','check_behavior']
SPECIAL = {'run_native_ssh.ps1':'runner_script','validate_native_cli.py':'behavior_validator',
           'preserved-design/contract.json':'prospective_contract','execution-contract.json':'execution_binding',
           'native-input.json':'child_input'}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': sha(data)}


def exact(path: Path, spec: dict, readonly: bool = False) -> bytes:
    assert type(spec) is dict and set(spec) == {'bytes','sha256'}
    assert type(spec['bytes']) is int and spec['bytes'] >= 0
    assert type(spec['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',spec['sha256'])
    data = path.read_bytes()
    assert {'bytes': len(data), 'sha256': sha(data)} == spec, str(path)
    if readonly:
        assert not path.is_symlink() and not (path.stat().st_file_attributes & 0x400), str(path)
        assert path.stat().st_file_attributes & 1, str(path)
    return data


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        assert key not in obj, key
        obj[key] = value
    return obj


def reject_constant(value):
    raise AssertionError(('nonfinite JSON token', value))


def strict_json(data: bytes, *, allow_bom: bool = False):
    if allow_bom and data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    else:
        assert not data.startswith(b'\xef\xbb\xbf')
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)


def keys(value, wanted):
    assert type(value) is dict and set(value) == set(wanted), (set(value) ^ set(wanted))


def integer(value, wanted):
    assert type(value) is int and value == wanted, (value, wanted)


def boolean(value, wanted):
    assert type(value) is bool and value is wanted


def absolute(value):
    assert type(value) is str
    path = Path(value)
    assert path.is_absolute() and '..' not in path.parts
    return path


def utc(value):
    assert type(value) is str
    moment = datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    assert moment.tzinfo is not None and moment.utcoffset() == datetime.timedelta(0)
    return moment


def typed(expected, actual, datatype=None, tolerance=0.0):
    if expected is None or actual is None:
        return expected is None and actual is None
    if datatype == 'integer':
        return type(expected) is type(actual) is int and expected == actual
    if datatype == 'double':
        return (type(expected) in (int,float) and type(actual) in (int,float)
                and math.isfinite(expected) and math.isfinite(actual)
                and abs(expected-actual) <= tolerance)
    if datatype == 'string':
        return type(expected) is type(actual) is str and expected == actual
    if type(expected) is not type(actual):
        return False
    if type(expected) is dict:
        return set(expected) == set(actual) and all(typed(expected[k],actual[k]) for k in expected)
    if type(expected) is list:
        return len(expected) == len(actual) and all(typed(a,b) for a,b in zip(expected,actual,strict=True))
    return expected == actual


def compare_tables(expected, actual, tolerance=0.0):
    assert type(expected) is type(actual) is list and len(expected) == len(actual)
    rows = cells = 0
    for et, at in zip(expected, actual, strict=True):
        keys(et, {'name','columns','instances'}); keys(at, {'name','columns','instances'})
        assert et['name'] == at['name'] and type(et['name']) is str
        ec, ac = et['columns'], at['columns']
        assert type(ec) is type(ac) is list and len(ec) == len(ac)
        for x,y in zip(ec,ac,strict=True):
            assert type(x) is type(y) is dict and set(x) == set(y)
            assert set(x) in ({'name','datatype'}, {'name','datatype','key'})
            assert type(x['name']) is type(y['name']) is str
            assert type(x['datatype']) is type(y['datatype']) is str
            if 'key' in x:
                assert type(x['key']) is type(y['key']) is bool
            assert typed(x,y)
        ei, ai = et['instances'], at['instances']
        assert type(ei) is type(ai) is list and len(ei) == len(ai)
        for x,y in zip(ei,ai,strict=True):
            keys(x, {'instance_name','rows'}); keys(y, {'instance_name','rows'})
            assert typed(x['instance_name'],y['instance_name'])
            xr, yr = x['rows'], y['rows']
            assert type(xr) is type(yr) is list and len(xr) == len(yr)
            for a,b in zip(xr,yr,strict=True):
                assert type(a) is type(b) is list and len(a) == len(b) == len(ec)
                rows += 1
                for col, ev, av in zip(ec,a,b,strict=True):
                    assert typed(ev,av,col['datatype'],tolerance), (et['name'],col['name'],ev,av)
                    cells += 1
    return len(expected), rows, cells


def one_dirpt(parent):
    child = copy.deepcopy(parent)
    keys(child, {'model'}); keys(child['model'], {'database_version','tables'})
    matches = [t for t in child['model']['tables'] if t['name'] == 'ItemRepair']
    assert len(matches) == 1
    table = matches[0]
    cols = [c['name'] for c in table['columns']]
    assert cols[:3] == ['IID','STID','DIRPT']
    assert len(table['instances']) == 1 and len(table['instances'][0]['rows']) == 1
    row = table['instances'][0]['rows'][0]
    assert row[0] == 'TEACH-LRU-01' and row[1] == 'BASE-01'
    assert type(row[2]) in (int,float) and row[2] == 1.0
    row[2] = 10.75
    return child


def source_oracles():
    parent = strict_json(exact(PARENT/'native-input.json',{'bytes':43699,'sha256':PARENT_INPUT_SHA}))
    child = strict_json(exact(CASE/'native-input.json',{'bytes':43701,'sha256':INPUT_SHA},readonly=True))
    predicted = one_dirpt(parent)
    keys(child, {'model'}); keys(child['model'], {'database_version','tables'})
    assert typed(predicted['model']['database_version'],child['model']['database_version'])
    assert compare_tables(predicted['model']['tables'],child['model']['tables']) == (31,24,274)
    parent_export = strict_json(exact(PARENT_RUN/'roundtrip-raw.json',{'bytes':57995,'sha256':PARENT_EXPORT_SHA}))
    export = strict_json(exact(CASE/'child-roundtrip-oracle.json',{'bytes':46241,'sha256':EXPORT_SHA},readonly=True))
    predicted_export = one_dirpt(parent_export)
    keys(export, {'model'}); keys(export['model'], {'database_version','tables'})
    assert typed(predicted_export['model']['database_version'],export['model']['database_version'])
    assert compare_tables(predicted_export['model']['tables'],export['model']['tables']) == (31,35,369)
    return {'authored_cells':274,'exported_cells':369}


def log_patterns():
    p = strict_json(exact(CASE/'preserved-oracle/log-patterns.json',
                          {'bytes':16033,'sha256':PATTERN_SHA},readonly=True))
    keys(p, {'schema','physical_lines','timed_lines','line_ending','status','lines'})
    assert p['schema'] == 'e02-var02-prospective-full-log-patterns/v104'
    integer(p['physical_lines'],123); integer(p['timed_lines'],99)
    assert p['line_ending'] == 'CRLF' and type(p['lines']) is list and len(p['lines']) == 123
    bounded = [i for i,row in enumerate(p['lines']) if row.get('kind') == 'bounded_numeric']
    assert bounded == [103]
    return p['lines']


def physical_log(raw: bytes, patterns=None):
    if patterns is None:
        patterns = log_patterns()
    assert not raw.startswith(b'\xef\xbb\xbf') and raw.endswith(b'\r\n')
    assert raw.count(b'\r\n') == raw.count(b'\n') == 123
    lines = raw.decode('utf-8').splitlines()
    assert len(lines) == 123
    for i,(line,row) in enumerate(zip(lines,patterns,strict=True)):
        if row['kind'] == 'literal':
            keys(row, {'kind','text'})
            assert line == row['text'], (i,line)
        else:
            keys(row, {'kind','prefix','number_regex','finite','greater_than_hour'})
            assert i == 103 and row['kind'] == 'bounded_numeric'
            boolean(row['finite'],True)
            assert row['greater_than_hour'] == 34
            assert line.startswith(row['prefix'])
            number = line[len(row['prefix']):]
            assert re.fullmatch(row['number_regex'],number)
            assert math.isfinite(float(number)) and float(number) > 34
    assert sum(line.startswith('Time:') for line in lines) == 99
    return {'physical_lines':123,'timed_lines':99}


def native_report_json(raw: bytes):
    assert not raw.startswith(b'\xef\xbb\xbf') and raw.count(b'\n') == raw.count(b'\r\n')
    marker = b',\r\n      ]'
    assert raw.count(marker) == 1
    return strict_json(raw.replace(marker,b'\r\n      ]',1))


def report_cells(actual):
    expected = strict_json(exact(CASE/'preserved-oracle/expected-report.json',
                                 {'bytes':100409,'sha256':REPORT_SHA},readonly=True))
    keys(expected, {'report'}); keys(actual, {'report'})
    keys(expected['report'], {'tables'}); keys(actual['report'], {'tables'})
    tables = expected['report']['tables']
    assert [t['name'] for t in tables] == ['ProblemDescription','ResultSummary','SystemResults','StockTotalResults']
    assert compare_tables(tables,actual['report']['tables'],1e-5) == (4,146,4044)
    return 4044


def behavior(run: Path):
    source_oracles()
    log = physical_log((run/'model.log').read_bytes())
    report = report_cells(native_report_json((run/'report-raw.json').read_bytes()))
    return {**log,'report_cells':report}

# Independent byte and protocol custody. No author imports, native invocation, or Git calls.
SOURCE_LIST_SHA = 'b8d33d13047367931b16987c46954ad74b1ee2e3ceb6825b19c51c4c3051f459'
MANIFEST_KEYS=set('schema run_id native_run_directory file_line_ascii_bytes file_line_ascii_max base_commit contract_sha256 execution_binding_sha256 input_sha256 source_inventory_sha256 runner_sha256 validator_sha256 independent_reader_sha256 source_count source_files owned_source_count accepted_source_pair_count required_local_source_count mandatory_original_count archived_catalog_count converter_negative_original_count installed_executable_count excluded_source_count excluded_failed_original_count excluded_diagnostic_copy_count excluded_custody_receipt_count catalog_prefix_entries live_catalog_prelaunch_pin pure_tools stages native_commands pure_checkers new_native_runs_authorized_by_manifest independent_method_state'.split())
PREFLIGHT_KEYS=set('schema run_id native_run_directory run_dirs_absent file_line_ascii_bytes file_line_ascii_max native_run_path_ancestors_no_reparse ssh_session ps_major ssh_ancestors mutex_free wts_active_gui_count gui accepted_source_pair_count required_local_source_count mandatory_original_count archived_catalog_count converter_negative_original_count installed_executable_count catalog_prefix_entries manifest_sha256 source_map_sha256 source_hashes source_hashes_after_pure pure_proof_directory pure_proof_path pure_proof_sha256 pure_checks native_process_started'.split())
PROOF_KEYS=set('schema mode run_id native_run_directory manifest_sha256 source_map_sha256 started_utc completed_utc status error checks source_hashes_after'.split())
PURE_STEP_KEYS=set('tool program arguments started_utc completed_utc status error child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256'.split())
APPROVAL_KEYS=set('schema decision run_id native_run_directory manifest_sha256 runner_sha256 validator_sha256 contract_sha256 execution_binding_sha256 input_sha256 source_map_sha256 independent_reader_sha256 preflight_relative_path preflight_sha256'.split())
INVOCATION_KEYS=set('schema run_id created_utc original_run_dir native_run_directory input_sha256 contract_sha256 manifest_sha256 approval_sha256 approved_preflight_path approved_preflight_sha256 independent_reader_sha256 runner_script_sha256 session_id ssh_ancestors gui queue_mutex working_directory planned_commands planned_checkers source_hashes_before source_hashes_after_pure pure_proof_path pure_proof_sha256 pure_checks publication_state'.split())
CLOSURE_KEYS=set('schema run_id native_run_directory invocation_sha256 manifest_sha256 approval_sha256 approved_preflight_sha256 source_hashes_before source_hashes_after raw step_error error publication_state'.split())
STEP_KEYS=set('sequence name program arguments started_utc completed_utc child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256 converter_log_bytes converter_log_sha256 converter_log_validated gui_preserved status error'.split())


def owned_list():
    body = (CASE/'source-list.json').read_bytes()
    assert sha(body) == SOURCE_LIST_SHA
    roster = strict_json(body)
    keys(roster, {'schema','files'})
    assert roster['schema'] == 'e02-var02-owned-source-list/v104'
    files = roster['files']
    assert type(files) is list and len(files) == 42
    assert all(type(x) is str and x == Path(x).as_posix() and not Path(x).is_absolute()
               and '..' not in Path(x).parts for x in files)
    assert len(files) == len(set(files)) == len({x.casefold() for x in files})
    assert files.count('review/independent_reader.py') == 1
    assert files.count('review/independent_self_check.py') == 1
    assert files.count('review/independent-static-go-2026-10-09.md') == 1
    return files


def source_inventory(candidate:Path|None=None):
    owned = owned_list()
    path=CASE/'source-inventory.json' if candidate is None else candidate
    assert path.stat().st_file_attributes & 1
    doc=strict_json(path.read_bytes())
    keys(doc,{'schema','source_count','source_files'})
    assert doc['schema']=='e02-var02-source-inventory/v104'
    integer(doc['source_count'],len(owned))
    assert type(doc['source_files']) is list and len(doc['source_files'])==len(owned)
    for rel,row in zip(owned,doc['source_files'],strict=True):
        keys(row,{'path','bytes','sha256'})
        assert row['path']==rel
        exact(CASE/rel,{'bytes':row['bytes'],'sha256':row['sha256']},readonly=True)
    return doc

EXCLUDED = REPO / 'cases/simlox-air-support/E02-var02-repair-return-after-deadline-v1.0.3'
EXCLUDED_INVENTORY_SPEC = {'bytes':13804,'sha256':'35f7cec140d2404a5692c7f8853ccf2fd01beb73b48c3446f0b689a3d7db3e97'}
EXCLUDED_MANIFEST_SPEC = {'bytes':64182,'sha256':'ef5675a7054f43bbbfe26376b8cc411678533e7b28054db9116737407271d123'}
EXCLUDED_CUSTODY = REPO / 'tmp/e02-var02-failed-native-custody-v103-20261009-01/receipt.json'
EXCLUDED_CUSTODY_SPEC = {'bytes':30795,'sha256':'b81c5abb847f8d16819cdcb18419a680da6ad5b53c1977f2f46b783e41e6a98f'}


def excluded_roles():
    old_inventory = strict_json(exact(EXCLUDED/'source-inventory.json', EXCLUDED_INVENTORY_SPEC, readonly=True))
    keys(old_inventory, {'schema','source_count','source_files'})
    assert old_inventory['schema']=='e02-var02-source-inventory/v103'
    integer(old_inventory['source_count'],77)
    assert type(old_inventory['source_files']) is list and len(old_inventory['source_files'])==77
    roles=[]; seen=set()
    for row in old_inventory['source_files']:
        keys(row, {'path','bytes','sha256'})
        rel=row['path']; assert type(rel) is str and rel==Path(rel).as_posix()
        assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
        assert rel.casefold() not in seen; seen.add(rel.casefold())
        path=(EXCLUDED/rel).resolve(strict=True)
        assert path.is_relative_to(EXCLUDED.resolve(strict=True))
        exact(path, {'bytes':row['bytes'],'sha256':row['sha256']}, readonly=True)
        roles.append({'key':'excluded-source:'+rel,'path':str(path),
                      'bytes':row['bytes'],'sha256':row['sha256']})
    exact(EXCLUDED/'prelaunch-manifest.json', EXCLUDED_MANIFEST_SPEC, readonly=True)
    roles.append({'key':'excluded-source-inventory','path':str(EXCLUDED/'source-inventory.json'),**EXCLUDED_INVENTORY_SPEC})
    roles.append({'key':'excluded-prelaunch-manifest','path':str(EXCLUDED/'prelaunch-manifest.json'),**EXCLUDED_MANIFEST_SPEC})
    custody=strict_json(exact(EXCLUDED_CUSTODY,EXCLUDED_CUSTODY_SPEC,readonly=True))
    assert custody['schema']=='e02-var02-root-excluded-failure-custody/v100'
    assert custody['decision']=='NO_GO_PRESERVED'
    boolean(custody['semantic_acceptance'],False)
    boolean(custody['native_retry_authorized'],False)
    boolean(custody['source_bytes_modes_attributes_stable'],True)
    originals=custody['originals_after_freeze']; copies=custody['copies']
    assert type(originals) is type(copies) is dict and len(originals)==40 and len(copies)==26
    before=custody['originals_before_freeze']
    assert type(before) is dict and set(before)==set(originals)
    for name in originals:
        assert before[name]['bytes']==originals[name]['bytes']
        assert before[name]['sha256']==originals[name]['sha256']
    for index,name in enumerate(sorted(originals,key=str.casefold)):
        pin=originals[name]
        keys(pin,{'bytes','sha256','mode','attributes'})
        path=absolute(name)
        exact(path,{'bytes':pin['bytes'],'sha256':pin['sha256']},readonly=True)
        st=path.stat(); integer(st.st_mode,pin['mode']); integer(st.st_file_attributes,pin['attributes'])
        roles.append({'key':f'excluded-failed-original:{index:02d}','path':str(path),
                      'bytes':pin['bytes'],'sha256':pin['sha256']})
    base=absolute(custody['diagnostic_copy'])
    for index,name in enumerate(sorted(copies,key=str.casefold)):
        pin=copies[name]
        keys(pin,{'bytes','sha256'})
        assert type(name) is str and name==Path(name).name and name not in ('.','..')
        path=base/name
        exact(path,pin,readonly=True)
        roles.append({'key':f'excluded-diagnostic-copy:{index:02d}','path':str(path),**pin})
    roles.append({'key':'excluded-failure-custody','path':str(EXCLUDED_CUSTODY),**EXCLUDED_CUSTODY_SPEC})
    assert len(roles)==146
    return roles


def historical_proofs():
    path=CASE/'preserved-history/original-proof-map.json'
    mapping=strict_json(exact(path,{'bytes':8922,'sha256':'06907f4e8c5bc837d429d8ce111a2df54384f9dad24874a15656079c958d84ed'},readonly=True))
    keys(mapping,{'schema','semantic_acceptance','native_authorization','records'})
    assert mapping['schema']=='e02-var02-v104-original-proof-map/v1'
    boolean(mapping['semantic_acceptance'],False)
    boolean(mapping['native_authorization'],False)
    rows=mapping['records']
    assert type(rows) is list and len(rows)==23
    seen=set()
    for row in rows:
        keys(row,{'role','path','bytes','sha256','state'})
        role=row['role']; rel=row['path']
        assert type(role) is type(rel) is str and role.casefold() not in seen
        seen.add(role.casefold())
        assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
        target=(REPO/rel).resolve(strict=True)
        assert target.is_relative_to(REPO.resolve(strict=True))
        exact(target,{'bytes':row['bytes'],'sha256':row['sha256']},readonly=True)
    return 23


def manifest_document(candidate:Path|None=None):
    inventory=source_inventory()
    historical_proofs()
    path=CASE/'prelaunch-manifest.json' if candidate is None else candidate
    assert path.stat().st_file_attributes & 1
    doc=strict_json(path.read_bytes())
    keys(doc,MANIFEST_KEYS)
    assert doc['schema']=='e02-var02-prelaunch-manifest/v104'
    assert doc['run_id']==RUN_ID and type(doc['native_run_directory']) is str and doc['native_run_directory']==str(RUN)
    fileline='File: '+str(RUN/'model.sxi').replace('\\','/')
    assert fileline.isascii() and len(fileline.encode('ascii'))==119
    integer(doc['file_line_ascii_bytes'],119); integer(doc['file_line_ascii_max'],199)
    assert doc['base_commit']==BASE and doc['contract_sha256']==CONTRACT_SHA
    for field,rel in {'execution_binding_sha256':'execution-contract.json','input_sha256':'native-input.json','source_inventory_sha256':'source-inventory.json','runner_sha256':'run_native_ssh.ps1','validator_sha256':'validate_native_cli.py','independent_reader_sha256':'review/independent_reader.py'}.items():
        assert doc[field]==seal(CASE/rel)['sha256'],field
    assert doc['input_sha256']==INPUT_SHA
    for field,wanted in [('accepted_source_pair_count',39),('required_local_source_count',0),('mandatory_original_count',42),('archived_catalog_count',2),('converter_negative_original_count',0),('installed_executable_count',4),('catalog_prefix_entries',503),('excluded_source_count',79),('excluded_failed_original_count',40),('excluded_diagnostic_copy_count',26),('excluded_custody_receipt_count',1),('native_commands',4),('pure_checkers',2),('new_native_runs_authorized_by_manifest',0)]: integer(doc[field],wanted)
    assert doc['pure_tools']==TOOLS and doc['stages']==STAGES
    assert doc['independent_method_state']=='METHOD_ONLY_NO_NATIVE_APPROVAL'
    selection=strict_json(exact(CASE/'source-maps/root-selection-receipt.json',
                                {'bytes':37595,'sha256':SELECTION_SHA},readonly=True))
    assert selection['base']==BASE and selection['decision']=='ELIGIBLE_FOR_CONTRACT_REVIEW_ONLY'
    pairs=selection['accepted_source_pairs']; originals=selection['mandatory_originals']
    assert type(pairs) is type(originals) is list and len(pairs)==39 and len(originals)==42
    expected=[]
    for row in inventory['source_files']:
        rel=row['path']; expected.append({'key':SPECIAL.get(rel,'owned:'+rel),'path':str(CASE/rel),'bytes':row['bytes'],'sha256':row['sha256']})
    expected.append({'key':'owned:source-inventory.json','path':str(CASE/'source-inventory.json'),**seal(CASE/'source-inventory.json')})
    for row in pairs:
        keys(row,{'path','oid','disk','git','byte_equal'})
        path=(REPO/row['path']).resolve(strict=True); exact(path,row['disk'])
        expected.append({'key':'accepted:'+row['path'],'path':str(path),**row['disk']})
    for i,row in enumerate(originals):
        keys(row,{'path','bytes','sha256','original_mode','original_attributes'})
        path=absolute(row['path']); spec={'bytes':row['bytes'],'sha256':row['sha256']}
        exact(path,spec)
        assert path.stat().st_mode==row['original_mode'] and path.stat().st_file_attributes==row['original_attributes']
        expected.append({'key':f'mandatory:{i:02d}','path':str(path),**spec})
    installed=[
        ('manual',Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),18124110,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'),
        ('simlox-exe',Path(EXE),33196032,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'),
        ('python',Path(PYTHON),106448,'10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1'),
        ('dictionary',Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),78577,'11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'),
    ]
    for name,path,size,digest in installed:
        spec={'bytes':size,'sha256':digest}; exact(path,spec)
        expected.append({'key':'installed:'+name,'path':str(path),**spec})
    expected.extend(excluded_roles())
    integer(doc['owned_source_count'],len(owned_list())+1)
    integer(doc['source_count'],len(expected))
    assert len(expected)==len(owned_list())+232 and doc['source_files']==expected
    rolekeys=set(); paths={}
    for row in doc['source_files']:
        keys(row,{'key','path','bytes','sha256'})
        assert type(row['key']) is type(row['path']) is type(row['sha256']) is str
        assert type(row['bytes']) is int and row['bytes'] >= 0
        assert re.fullmatch(r'[0-9a-f]{64}',row['sha256'])
        key=row['key'].casefold(); assert key not in rolekeys; rolekeys.add(key)
        resolved=str(Path(row['path']).resolve(strict=True)).replace('/','\\').casefold()
        identity=(row['bytes'],row['sha256'])
        assert resolved not in paths or paths[resolved]==identity
        paths[resolved]=identity
    keys(doc['live_catalog_prelaunch_pin'],{'path','bytes','sha256'})
    catalog=REPO/'cases/simlox-air-support/publication-index-v1.json'
    assert doc['live_catalog_prelaunch_pin']['path']==str(catalog)
    current = strict_json(catalog.read_bytes())
    archive = strict_json(exact(CASE/'source-maps/catalog-local-503.json.bytes',
                                selection['catalog_local_crlf'],readonly=True))
    exact(CASE/'source-maps/catalog-git-503.json.bytes',selection['catalog_git_lf'],readonly=True)
    assert type(current) is type(archive) is dict and set(current)==set(archive)
    assert type(current['entries']) is list and len(current['entries'])>=503
    assert typed(current['entries'][:503],archive['entries'])
    for k in archive:
        if k not in ('entries','as_of'):
            assert typed(current[k],archive[k])
    assert len({x['publication_id'] for x in current['entries']})==len(current['entries'])
    # The live point-time pin was sealed at manifest creation; after later
    # catalog append, the typed first-503 prefix remains the acceptance guard.
    assert {'bytes':doc['live_catalog_prelaunch_pin']['bytes'],'sha256':doc['live_catalog_prelaunch_pin']['sha256']}==selection['catalog_local_crlf']
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
    assert proof['schema']=='e02-var02-pure-proof/v104' and proof['mode']==mode
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
    assert receipt['schema']=='e02-var02-ssh-preflight/v104' and receipt['run_id']==RUN_ID
    assert type(receipt['native_run_directory']) is str and receipt['native_run_directory']==str(RUN)
    assert receipt['manifest_sha256']==seal(CASE/'prelaunch-manifest.json')['sha256']
    assert receipt['source_map_sha256']==source_map_digest(source_map)
    assert receipt['source_hashes']==source_map and receipt['source_hashes_after_pure']==source_map
    for field,wanted in [('file_line_ascii_bytes',119),('file_line_ascii_max',199),('ssh_session',0),('ps_major',5),('wts_active_gui_count',1),('accepted_source_pair_count',39),('required_local_source_count',0),('mandatory_original_count',42),('archived_catalog_count',2),('converter_negative_original_count',0),('installed_executable_count',4),('catalog_prefix_entries',503)]: integer(receipt[field],wanted)
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
    assert body['schema']=='e02-var02-independent-prelaunch-go/v104' and body['decision']=='GO_PRELAUNCH'
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
    assert data and not data.startswith(b'\xef\xbb\xbf') and data.endswith(b'\r\n')
    assert data.count(b'\r\n')==data.count(b'\n')==15
    lines=data.decode('utf-8').split('\r\n')
    assert lines[-1]==''
    lines.pop()
    assert len(lines)==15
    expected=[
        'Performing simulation',
        'Input file: '+str(RUN/'model.sxi'),
        'Output file: '+str(RUN/'model.sxo'),
        'Simulating.','Converting input data ...',
        'File: '+str(RUN/'model.sxi').replace('\\','/'),
        'Form: Control',
        'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',
        'Input conversion completed. Errors: 0, Warnings: 1, Notes: 0',
        None,'Starting simulation...',None,'Saving results ...',None,None,
    ]
    for actual,predicted in zip(lines,expected,strict=True):
        if predicted is not None: assert actual==predicted,(actual,predicted)
    for index,label in [(9,'Input data conversion time'),(11,'Simulation time'),(13,'Result saving time'),(14,'Total execution time')]:
        match=re.fullmatch(re.escape(label)+r': ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) secs\.',lines[index])
        assert match and math.isfinite(float(match.group(1))) and float(match.group(1))>=0
    assert len(lines[1].encode('ascii'))==125 and len(lines[2].encode('ascii'))==126
    assert len(lines[5].encode('ascii'))==119 and len(lines[5].encode('ascii'))<=199
    return len(lines)


def checker_receipt(data:bytes,name:str,raw:Path):
    body=strict_json(data)
    common={'schema','passed','run_id','native_run_directory','input_sha256','export_sha256','native_calls','issues'}
    if name=='check_import_export':
        wanted=common|{'authored_tables','authored_rows','authored_cells','exported_tables','exported_rows','exported_cells'}
        schema='e02-var02-roundtrip-check/v104'
    else:
        assert name=='check_behavior'
        wanted=common|{'log_sha256','report_sha256','physical_log_lines','timed_log_lines','report_typed_cells','authored_cells','exported_cells','second_mission_cancel_hour','repair_complete_hour','aircraft_ready_hour','third_mission_success_hour'}
        schema='e02-var02-native-behavior-check/v104'
    keys(body,wanted)
    assert body['schema']==schema and body['run_id']==RUN_ID
    boolean(body['passed'],True)
    assert type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    assert body['input_sha256']==INPUT_SHA and body['export_sha256']==seal(raw/'roundtrip-raw.json')['sha256']
    integer(body['native_calls'],0); assert body['issues']==[]
    if name=='check_import_export':
        for field,wanted in [('authored_tables',31),('authored_rows',24),('authored_cells',274),('exported_tables',31),('exported_rows',35),('exported_cells',369)]: integer(body[field],wanted)
    else:
        assert body['log_sha256']==seal(raw/'model.log')['sha256'] and body['report_sha256']==seal(raw/'report-raw.json')['sha256']
        for field,wanted in [('physical_log_lines',123),('timed_log_lines',99),('report_typed_cells',4044),('authored_cells',274),('exported_cells',369)]: integer(body[field],wanted)
        for field,wanted in [('second_mission_cancel_hour',20.3333),('repair_complete_hour',20.9167),('aircraft_ready_hour',21.25),('third_mission_success_hour',34)]:
            assert type(body[field]) in (int,float) and body[field]==wanted
    return body


def receipt_json(data:bytes):
    return strict_json(data[3:] if data.startswith(b'\xef\xbb\xbf') else data)

def planned():
    def rf(name): return str(RUN/name)
    commands=[
        {'name':'import','program':EXE,'arguments':f'-silent -jimport "{rf("input.json")}" -save "{rf("model.sxi")}" -log "{rf("import.log")}" -close'},
        {'name':'export','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -jexport "{rf("roundtrip-raw.json")}" -log "{rf("export.log")}" -close'},
        {'name':'calc','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -threads 1 -calc -log "{rf("model-run.log")}" -close'},
        {'name':'jsonreport','program':EXE,'arguments':f'"{rf("model.sxo")}" -silent -jsonreport "{rf("report-raw.json")}" -log "{rf("report-export.log")}" -close'},
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
    assert invocation['schema']=='e02-var02-invocation/v104' and closure['schema']=='e02-var02-closure/v104'
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
    assert typed(preflight['gui'],invocation['gui'])
    commands,checkers=planned()
    assert invocation['planned_commands']==commands and invocation['planned_checkers']==checkers
    native_path=absolute(invocation['pure_proof_path'])
    assert native_path.parent.parent==CASE/'test-output'
    native_receipt={'pure_proof_directory':str(native_path.parent),'pure_proof_path':str(native_path),
        'pure_proof_sha256':invocation['pure_proof_sha256'],'manifest_sha256':approval['manifest_sha256'],
        'source_map_sha256':approval['source_map_sha256'],'source_hashes_after_pure':source_map,
        'pure_checks':invocation['pure_checks']}
    native_proof=pure_proof(native_receipt,source_map,'native')
    assert utc(native_proof['started_utc'])>=utc(pure_proof(preflight,source_map,'preflight')['completed_utc'])
    started=utc(invocation['created_utc'])
    assert started>=utc(native_proof['completed_utc'])
    assert closure['invocation_sha256']==seal(raw/'invocation.json')['sha256']
    assert closure['source_hashes_after']==source_map
    assert closure['error'] in (None,'') and closure['step_error'] in (None,'')
    raw_map=closure['raw']
    assert type(raw_map) is dict and len(raw_map)==23
    assert set(raw_map)==set('input.json model.sxi import.log import-stdout.txt import-stderr.txt roundtrip-raw.json export.log export-stdout.txt export-stderr.txt roundtrip-validation.json check_import_export-stderr.txt model.sxo model.log model-run.log calc-stdout.txt calc-stderr.txt report-raw.json report-export.log jsonreport-stdout.txt jsonreport-stderr.txt author-validation.json check_behavior-stderr.txt steps.json'.split())
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
    assert converter_bytes((raw/'model-run.log').read_bytes())==15
    actual_export=strict_json((raw/'roundtrip-raw.json').read_bytes())
    expected_export=strict_json(exact(CASE/'child-roundtrip-oracle.json',
                                      {'bytes':46241,'sha256':EXPORT_SHA},readonly=True))
    keys(expected_export,{'model'}); keys(actual_export,{'model'})
    keys(expected_export['model'],{'database_version','tables'}); keys(actual_export['model'],{'database_version','tables'})
    assert typed(expected_export['model']['database_version'],actual_export['model']['database_version'])
    assert compare_tables(expected_export['model']['tables'],actual_export['model']['tables'])==(31,35,369)
    assert physical_log((raw/'model.log').read_bytes())['timed_lines']==99
    assert report_cells(native_report_json((raw/'report-raw.json').read_bytes()))==4044
    checker_receipt((raw/'roundtrip-validation.json').read_bytes(),'check_import_export',raw)
    checker_receipt((raw/'author-validation.json').read_bytes(),'check_behavior',raw)
    return {'decision':'GO_BOUNDED','full_lines':123,'timed_lines':99,'report_cells':4044,
            'authored_cells':274,'export_cells':369,'raw_files':25}


def converter_fixture():
    parent=exact(PARENT_RUN/'run.log',{'bytes':947,'sha256':PARENT_CONVERTER_SHA}).decode('utf-8')
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
        parent_log=exact(PARENT_RUN/'model.log',{'bytes':10714,'sha256':PARENT_LOG_SHA})
        assert parent_log.endswith(b'\r\n') and parent_log.count(b'\r\n')==parent_log.count(b'\n')==141
        assert sum(x.startswith(b'Time:') for x in parent_log.splitlines())==120
        template=exact(CASE/'preserved-oracle/expected-log-template.bin',
                       {'bytes':9178,'sha256':TEMPLATE_SHA},readonly=True)
        assert template.count(b'{{FINITE_GT34}}')==1
        assert physical_log(template.replace(b'{{FINITE_GT34}}',b'35.5'))=={'physical_lines':123,'timed_lines':99}
        report_cells(strict_json(exact(CASE/'preserved-oracle/expected-report.json',
                                       {'bytes':100409,'sha256':REPORT_SHA},readonly=True)))
        assert converter_bytes(converter_fixture())==15
        return {'decision':'PASS_PURE_ORACLES','physical_lines':123,'report_cells':4044}
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
