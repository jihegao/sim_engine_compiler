"""Portable read-only delivery replay; frozen native checkers remain historical."""
import argparse,hashlib,json,os,platform,re,sys
from pathlib import Path,PureWindowsPath
from precision_contract_v2 import strict_json,validate
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent

def seal(path):
    raw=Path(path).read_bytes()
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def relative(value):
    # Binding paths were authored on Windows. Parse their separators independently
    # of the replay host; absolute provenance paths are handled separately below.
    path=PureWindowsPath(value)
    if path.drive or path.root or not path.parts or '..' in path.parts:
        raise ValueError('archive path outside component')
    return Path(*path.parts)

def exact(path,pin):
    if seal(path)!={k:pin[k] for k in ('bytes','sha256')}:
        raise ValueError('exact file binding differs: '+str(path))

def trusted(root,binding_sha):
    if re.fullmatch('[0-9a-f]{64}',binding_sha) is None:
        raise ValueError('external component binding SHA required')
    path=root/'component-binding-v2.json'
    if seal(path)['sha256']!=binding_sha:
        raise ValueError('external component binding SHA differs')
    binding=strict_json(path.read_bytes())
    if binding['schema']!='simlox-k02-dtim-component-binding/v2':
        raise ValueError('binding schema')
    for entry in binding['files']:
        exact(root/relative(entry['relative_path']),entry)
    contract=strict_json((root/'contract.json').read_bytes())
    method_path=root/'source-snapshots/approved-author-method-v2.json'
    exact(method_path,contract['method'])
    method=strict_json(method_path.read_bytes())
    exact(root/'native-input.json',contract['source'])
    exact(root/'native-input.json',method['planned_source'])
    oracle=root/'prospective-export-full-typed-model-v1.json'
    exact(oracle,contract['oracle']);exact(oracle,method['expected_export'])
    expected=strict_json(oracle.read_bytes())
    validate(expected,expected)
    return contract,expected

def validate_log_bytes(root,raw,kind,expected_path):
    if kind not in ('import','export') or not isinstance(raw,bytes):
        raise ValueError('explicit log kind and raw bytes required')
    if not isinstance(expected_path,str) or not expected_path or any(c in expected_path for c in '\r\n\x00'):
        raise ValueError('invalid bound path')
    raw.decode('ascii',errors='strict')
    template=(root/'source-snapshots'/('parent-'+kind+'.log')).read_bytes()
    template.decode('ascii',errors='strict')
    lines=template.split(b'\r\n')
    if len(lines)<3 or lines[-1]!=b'' or any(b'\r' in x or b'\n' in x or b'\x00' in x for x in lines[:-1]):
        raise ValueError('sealed template CRLF contract differs')
    prefix=b'Importing data from Json file: ' if kind=='import' else b'Exporting data to Json file: '
    body=b'\r\n'.join([prefix+expected_path.encode('ascii'),*lines[1:-2]])+b'\r\n'
    completion=b'Import' if kind=='import' else b'Export'
    if not raw.startswith(body) or re.fullmatch(completion+rb' completed! Time: (?:0|[1-9][0-9]*)\.[0-9]{2} secs\r\n',raw[len(body):]) is None:
        raise ValueError('complete log bytes/path/elapsed/CRLF differ')
    return dict(kind=kind,physical_lines=len(lines)-1,full_body_verified=True,log_bytes_verified=True,required_line_terminator='CRLF including final terminator',path_and_elapsed_only_variable=True)

def replay(root,index_sha,binding_sha):
    root=Path(root)
    index=root/'evidence-index.json'
    if seal(index)['sha256']!=index_sha:
        raise ValueError('external exact evidence-index binding differs')
    document=strict_json(index.read_bytes())
    for entry in document['artifacts']:
        exact(root/relative(entry['relative_path']),entry)
    contract,expected=trusted(root,binding_sha)
    physical=PureWindowsPath(contract['candidate']['physical_directory'])
    if not physical.is_absolute():raise ValueError('absolute Windows provenance required')
    run=root/'runs'/document['run_id']
    names={'input.json','model.sxi','roundtrip-raw.json','import.log','export.log','jimport_save-stdout.bin','jimport_save-stderr.bin','jexport-stdout.bin','jexport-stderr.bin'}
    for kind in ('original','recovered'):
        if {f.name for f in (run/kind).iterdir()}!=names:
            raise ValueError('complete archived raw set differs')
    for name in names:
        if seal(run/'original'/name)!=seal(run/'recovered'/name):
            raise ValueError('original/recovered bytes differ')
    results=[]
    for kind in ('original','recovered'):
        raw=run/kind
        exact(raw/'input.json',contract['source'])
        result=validate(strict_json((raw/'roundtrip-raw.json').read_bytes()),expected)
        result['logs']=[validate_log_bytes(root,(raw/'import.log').read_bytes(),'import',str(physical/'input.json')),validate_log_bytes(root,(raw/'export.log').read_bytes(),'export',str(physical/'roundtrip-raw.json'))]
        result.update(status='RAW_IDENTITY_AND_EXACT_LOG_BYTES_CHECK_ONLY',publication_GO=False,binding_sha256=binding_sha,source_sha256=contract['source']['sha256'])
        results.append(result)
    return dict(status='READONLY_ARCHIVED_RAW_REPLAY_ACCEPTED_V2',run_id=document['run_id'],host=dict(os_name=os.name,sys_platform=sys.platform,python=platform.python_version(),path_class=type(Path()).__name__),results=results,native_calls=0,model_reruns=0,OS_identity_or_readonly_seal_reproduced=False,publication_GO=False,whole_scope_complete=False)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence-index-sha',required=True)
    parser.add_argument('--binding-sha',required=True)
    args=parser.parse_args()
    print(json.dumps(replay(ROOT,args.evidence_index_sha,args.binding_sha)))
    return 0
if __name__=='__main__':raise SystemExit(main())
