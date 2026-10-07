"""Read-only source, published Git, original failure and raw seal verification."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
CONTRACT=HERE/'contract.json'

def digest(b: bytes) -> dict:
    return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def resolve(value: str) -> Path:
    p=Path(value)
    return p if p.is_absolute() else (HERE/p).resolve()

def check(path: Path, record: dict) -> None:
    actual=digest(path.read_bytes())
    assert actual=={'bytes':record.get('bytes',record.get('size_bytes')),'sha256':record['sha256']},(path,actual,record)

def verify() -> dict:
    c=json.loads(CONTRACT.read_text(encoding='utf-8'))
    assert c['schema']=='simlox-c09-var02-lender-shortage-control-v011-contract/v1'
    assert c['case_id']=='C09' and c['decision']=='CONTRACT_ONLY_PENDING_INDEPENDENT_REVIEW'
    assert digest(CONTRACT.read_bytes())['sha256']=='2abc4d733557d97c0766c88599429cef756fcdf16315db56102076670c96632b'
    counts={'direct':0,'disk_git_pairs':0,'accepted_run_raw':0,'accepted_closures':0,'manifest_sources':0,'sole_raw':0,'failure_files':0}
    def walk(node):
        if isinstance(node,dict):
            if isinstance(node.get('path'),str):
                p=resolve(node['path'])
                if 'sha256' in node and ('bytes' in node or 'size_bytes' in node):
                    check(p,node);counts['direct']+=1
                if 'local_disk' in node and 'published_git' in node:
                    check(p,node['local_disk'])
                    blob=subprocess.check_output(['git','-C',str(REPO),'show',c['base_commit']+':'+p.relative_to(REPO).as_posix()])
                    assert digest(blob)==node['published_git'],p
                    counts['disk_git_pairs']+=1
                if 'raw' in node and 'closure' in node and 'invocation' in node and isinstance(node['raw'],(dict,list)):
                    closure=node['closure'];inv=node['invocation']
                    check(resolve(closure['path']) if 'path' in closure else p/'closure.json',closure)
                    check(resolve(inv['path']) if 'path' in inv else p/'invocation.json',inv)
                    counts['accepted_closures']+=1
                    pairs=node['raw'].items() if isinstance(node['raw'],dict) else enumerate(node['raw'])
                    for name,r in pairs:
                        check(resolve(r['path']) if 'path' in r else p/name,r)
                        counts['accepted_run_raw']+=1
            for v in node.values():walk(v)
        elif isinstance(node,list):
            for v in node:walk(v)
    walk(c)
    v=c['excluded_v102'];manifest=resolve(v['manifest']['path'])
    m=json.loads(manifest.read_text(encoding='utf-8-sig'))
    assert len(m['source_files'])==v['manifest_source_record_count']==256
    for x in m['source_files']:
        check(Path(x['path']),x);counts['manifest_sources']+=1
    run=resolve(v['ordinary_run']['closure']['path']).parent
    closure=json.loads((run/'closure.json').read_text(encoding='utf-8-sig'))
    assert closure['error']=='check_behavior rejected native result'
    assert closure['source_hashes_before']==closure['source_hashes_after']
    assert closure['source_hashes_before']=={x['key']:x['sha256'] for x in m['source_files']}
    assert closure['invocation_sha256']==digest((run/'invocation.json').read_bytes())['sha256']
    assert set(closure['raw'])==set(v['ordinary_run']['raw']) and len(closure['raw'])==13
    for name,r in closure['raw'].items():
        check(run/name,r);counts['sole_raw']+=1
    failure=json.loads((run/'failure-seal.json').read_text(encoding='utf-8-sig'))
    assert failure['error']==closure['error'] and failure['run_id']==closure['run_id']
    for name,r in failure['files'].items():
        check(run/name,r);counts['failure_files']+=1
    assert not (run.parent/v['unstarted_run_id']).exists()
    assert counts['sole_raw']==13 and counts['manifest_sources']==256
    return {'schema':'c09-var02-control-source-verification/v1','passed':True,'contract_sha256':digest(CONTRACT.read_bytes())['sha256'],'counts':counts}

if __name__=='__main__':
    try:r=verify()
    except Exception as exc:r={'schema':'c09-var02-control-source-verification/v1','passed':False,'error':f'{type(exc).__name__}: {exc}'}
    print(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True))
    sys.exit(0 if r['passed'] else 1)
