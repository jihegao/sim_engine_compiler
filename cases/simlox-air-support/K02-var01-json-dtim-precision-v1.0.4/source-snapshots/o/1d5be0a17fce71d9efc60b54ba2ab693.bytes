"""Externally hash-bound read-only exchange checker; never grants publication GO."""
import argparse,hashlib,io,json,re,unittest
from pathlib import Path
from precision_contract_v2 import strict_json,validate
from exchange_logs import validate_log
ROOT=Path(__file__).resolve().parent
def seal(path):
    raw=Path(path).read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def exact(path,pin):
    observed=seal(path)
    if observed!={k:pin[k] for k in ('bytes','sha256')}:raise ValueError('exact file binding differs: '+str(path))
    return observed
def trusted(root,expected_binding_sha):
    root=Path(root)
    if not re.fullmatch('[0-9a-f]{64}',expected_binding_sha):raise ValueError('external expected binding SHA required')
    path=root/'component-binding-v2.json'
    if seal(path)['sha256']!=expected_binding_sha:raise ValueError('external component binding SHA differs')
    binding=strict_json(path.read_bytes())
    if binding['schema']!='simlox-k02-dtim-component-binding/v2':raise ValueError('binding schema')
    for entry in binding['files']:
        rel=Path(entry['relative_path'])
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('binding path outside component')
        exact(root/rel,entry)
    contract=strict_json((root/'contract.json').read_bytes())
    method_path=root/'source-snapshots/approved-author-method-v2.json'
    exact(method_path,contract['method'])
    method=strict_json(method_path.read_bytes())
    exact(root/'native-input.json',contract['source'])
    exact(root/'native-input.json',method['planned_source'])
    oracle_path=root/'prospective-export-full-typed-model-v1.json'
    exact(oracle_path,contract['oracle']);exact(oracle_path,method['expected_export'])
    expected=strict_json(oracle_path.read_bytes())
    validate(expected,expected)
    return contract,expected
def check_raw(root,raw_dir,expected_binding_sha,input_path,output_path):
    contract,expected=trusted(root,expected_binding_sha)
    physical=Path(contract['candidate']['physical_directory'])
    if input_path!=str(physical/'input.json') or output_path!=str(physical/'roundtrip-raw.json'):
        raise ValueError('log paths do not bind original physical provenance')
    raw_dir=Path(raw_dir)
    exact(raw_dir/'input.json',contract['source'])
    result=validate(strict_json((raw_dir/'roundtrip-raw.json').read_bytes()),expected)
    result['logs']=[validate_log((raw_dir/'import.log').read_bytes(),'import',input_path),validate_log((raw_dir/'export.log').read_bytes(),'export',output_path)]
    result.update(status='RAW_IDENTITY_CHECK_ONLY',publication_GO=False,binding_sha256=expected_binding_sha,source_sha256=contract['source']['sha256'])
    return result
def self_check():
    loader=unittest.TestLoader();suite=unittest.TestSuite()
    for module in ('test_precision_contract','test_exchange_logs','test_exchange_binding_v2'):suite.addTests(loader.loadTestsFromName(module))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    return dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),diagnostics=stream.getvalue(),native_calls=0)
def main():
    p=argparse.ArgumentParser();p.add_argument('--self-check',action='store_true');p.add_argument('--raw-directory',type=Path);p.add_argument('--binding-sha');p.add_argument('--input-path');p.add_argument('--output-path');a=p.parse_args()
    if a.self_check:
        if any((a.raw_directory,a.binding_sha,a.input_path,a.output_path)):p.error('self-check has no raw arguments')
        r=self_check();print(json.dumps(r));return 0 if r['status']=='PASS' else 1
    if not all((a.raw_directory,a.binding_sha,a.input_path,a.output_path)):p.error('all externally bound raw arguments required')
    print(json.dumps(check_raw(ROOT,a.raw_directory,a.binding_sha,a.input_path,a.output_path)));return 0
if __name__=='__main__':raise SystemExit(main())
