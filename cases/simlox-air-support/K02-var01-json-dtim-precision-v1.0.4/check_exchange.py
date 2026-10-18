"""Read-only exchange validator. This cannot start a native process or grant GO."""
import argparse,hashlib,io,json,unittest
from pathlib import Path
from precision_contract import strict_json,validate
from exchange_logs import validate_log
ROOT=Path(__file__).resolve().parent
def self_check():
    suite=unittest.TestSuite()
    loader=unittest.TestLoader()
    for module in ('test_precision_contract','test_exchange_logs'):
        suite.addTests(loader.loadTestsFromName(module))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    return dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),diagnostics=stream.getvalue(),native_calls=0)
def main():
    p=argparse.ArgumentParser();p.add_argument('--self-check',action='store_true');p.add_argument('--raw-directory',type=Path);p.add_argument('--input-path');p.add_argument('--output-path');a=p.parse_args()
    if a.self_check:
        if any((a.raw_directory,a.input_path,a.output_path)):p.error('self-check has no raw arguments')
        result=self_check();print(json.dumps(result));return 0 if result['status']=='PASS' else 1
    if not all((a.raw_directory,a.input_path,a.output_path)):p.error('all bound raw arguments required')
    contract=strict_json((ROOT/'contract.json').read_bytes())
    source=(ROOT/'native-input.json').read_bytes()
    if hashlib.sha256(source).hexdigest()!=contract['source']['sha256']:raise ValueError('candidate source hash differs')
    # Original evidence must be provided; no output receipt is rewritten here.
    expected=strict_json((ROOT/'prospective-export-full-typed-model-v1.json').read_bytes())
    actual=strict_json((a.raw_directory/'roundtrip-raw.json').read_bytes())
    result=validate(actual,expected)
    result['logs']=[validate_log((a.raw_directory/'import.log').read_bytes(),'import',a.input_path),validate_log((a.raw_directory/'export.log').read_bytes(),'export',a.output_path)]
    result['status']='RAW_IDENTITY_CHECK_ONLY';result['publication_GO']=False
    print(json.dumps(result));return 0
if __name__=='__main__':raise SystemExit(main())
