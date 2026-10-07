"""Build an exact-byte source/raw index for the bounded retrospective control.

Never overwrites an existing, different index. The root publication catalog is
owned separately. No native call or accepted-run mutation occurs here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from verify_sources import verify as verify_sources

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
INDEX=HERE/'evidence-index.json'
VERSIONS=('C09-var02-lender-shortage-v1.0.0','C09-var02-lender-shortage-v1.0.1',
          'C09-var02-lender-shortage-v1.0.2','C09-var02-lender-shortage-control-v0.1.0')
EXPECTED_INDEPENDENT={
 'review/independent_replay.py':'adb694578c32cdffaeafc59b73c2225ad59114cd061362e76404f59e95143319',
 'review/independent-verdict.json':'5ebe43374a550d330dc8d70316f0f0761e026cb660037f1ef05a0b822c446651',
 'review/independent-postrun-review-2026-10-07.md':'9261bd9bfbfc7a59d956901826bf16002807eebca66135f62b3226e01b5f184a',
 'review/independent-contract-go-2026-10-07.md':'95742d1f230d33a0a520063a5983561819bc0d3d5a55b4258023e92caa100aad',
}

def digest(path:Path)->dict:
    raw=path.read_bytes()
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def relative(path:Path)->str:return Path(os.path.relpath(path,HERE)).as_posix()

def record(path:Path)->dict:return {'path':relative(path),**digest(path)}

def publishable(path:Path)->bool:
    rel=relative(path)
    parts=path.parts
    if any(x in {'runs','__pycache__','.git'} for x in parts) or path.suffix=='.pyc':return False
    if path.name=='evidence-index.json':return False
    if rel.startswith('review/independent-publication-') or rel.startswith('review/independent-staged-') or rel.startswith('review/independent-remote-') or rel.startswith('review/independent-content-'):return False
    return True

def accepted_source_refs(node:object)->list[dict]:
    result={}
    def walk(x):
        if isinstance(x,dict):
            if isinstance(x.get('path'),str) and 'local_disk' in x and 'published_git' in x:
                path=(HERE/x['path']).resolve()
                assert digest(path)==x['local_disk'],path
                result[relative(path)]={'path':relative(path),'local_disk':x['local_disk'],
                                        'published_git':x['published_git']}
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(node)
    return [result[k] for k in sorted(result)]

def accepted_raw_records(node:object)->list[dict]:
    records={}
    def walk(x):
        if isinstance(x,dict):
            if {'path','raw','closure','invocation'}<=set(x) and isinstance(x['raw'],(dict,list)):
                run=(HERE/x['path']).resolve()
                entries=x['raw'].items() if isinstance(x['raw'],dict) else enumerate(x['raw'])
                for name,pin in entries:
                    path=(HERE/pin['path']).resolve() if 'path' in pin else run/name
                    expected={'bytes':pin.get('bytes',pin.get('size_bytes')),'sha256':pin['sha256']}
                    assert digest(path)==expected,path
                    records[relative(path)]={'path':relative(path),**expected}
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(node)
    return [records[k] for k in sorted(records)]

def check_gates()->tuple[dict,dict,dict,dict]:
    c=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    assert c['case_id']=='C09' and c['classification_id']=='C09.var02.lender-shortage-control.retrospective'
    assert digest(HERE/'contract.json')['sha256']=='2abc4d733557d97c0766c88599429cef756fcdf16315db56102076670c96632b'
    assert c['excluded_v010']['independent_no_go']['sha256']=='45a6ae2112ab84e17b69f8768e7f37ae921aeb34a9b0a987e932d0a62e1cb231'
    verify_sources()
    author=json.loads((HERE/'author-validation.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'self-check.json').read_text(encoding='utf-8'))
    reviewer=json.loads((HERE/'review'/'independent-verdict.json').read_text(encoding='utf-8'))
    assert author['decision']==reviewer['decision']=='GO_BOUNDED_RETROSPECTIVE_CONTROL'
    assert author['full_report_cells_checked']==reviewer['full_report_cells_compared']==1754
    assert author['original_pair_decision']=='NO_GO_PROSPECTIVE_PAIR'
    assert author['positive_pair_accepted'] is False and author['shortage_arm']=='not_started_not_tested'
    assert checks['passed'] and checks['rejected_count']==23 and checks['accepted_count']==2
    assert reviewer['original_prospective_pair']=='NO_GO_PROSPECTIVE_PAIR'
    assert reviewer['shortage_run_absent'] and reviewer['tamper_rejections']==26
    for path,expected in EXPECTED_INDEPENDENT.items():assert digest(HERE/path)['sha256']==expected,path
    entry=json.loads((HERE/'publication-entry-v1.json').read_text(encoding='utf-8'))
    assert entry['publication_id']=='C09.var02.lender_wait_control.readonly.0.1.1'
    assert entry['positive_pair_accepted'] is False and entry['new_native_runs']==0
    assert entry['shortage_arm']=='not_started_not_tested' and entry['case_id']=='C09'
    custody=json.loads((HERE/'raw-custody-map.json').read_text(encoding='utf-8'))
    assert custody['accepted_dependency_run_count']==9 and custody['accepted_dependency_raw_count']==117
    assert custody['sole_failed_ordinary']['raw_count']==13 and custody['new_native_runs']==0
    for run in custody['accepted_dependencies']+[custody['sole_failed_ordinary']]:
        for key in ('closure','invocation')+ (('failure_seal',) if 'failure_seal' in run else ()):
            item=run[key]
            assert digest((HERE/item['path']).resolve())=={'bytes':item['bytes'],'sha256':item['sha256']}
        for item in run['raw']:
            assert digest((HERE/item['path']).resolve())=={'bytes':item['bytes'],'sha256':item['sha256']}
    return c,author,checks,reviewer

def build()->dict:
    c,author,checks,reviewer=check_gates()
    paths=set()
    for dirname in VERSIONS+(HERE.name,):
        package=BASE/dirname
        assert package.is_dir(),package
        paths.update(p for p in package.rglob('*') if p.is_file() and publishable(p))
    source=[record(p) for p in sorted(paths,key=relative)]
    assert len({x['path'] for x in source})==len(source)
    raw=accepted_raw_records(c['accepted_lineage'])
    # The sole failed original ordinary run is an additional, separately
    # classified raw lineage. Its thirteen seals are never Git sources.
    for x in c['excluded_v102']['ordinary_run']['raw'].values():
        path=(HERE/x['path']).resolve()
        assert digest(path)=={'bytes':x['bytes'],'sha256':x['sha256']}
        raw.append(record(path))
    raw=sorted({x['path']:x for x in raw}.values(),key=lambda x:x['path'])
    assert len(raw)==130,(len(raw),'117 accepted + 13 sole')
    custody=json.loads((HERE/'raw-custody-map.json').read_text(encoding='utf-8'))
    custody_raw={x['path']:x for run in custody['accepted_dependencies']+[custody['sole_failed_ordinary']] for x in run['raw']}
    assert {x['path']:x for x in raw}==custody_raw
    return {'schema':'simlox-air-support-evidence-index/v1',
            'case_id':'C09','variant_id':'C09.var02','version':'0.1.1',
            'classification':'retrospective_source_bound_lender_wait_control',
            'publication_state':'content_ready_pending_root_catalog',
            'original_pair_decision':'NO_GO_PROSPECTIVE_PAIR',
            'positive_pair_accepted':False,'shortage_arm':'not_started_not_tested',
            'new_native_runs':0,'contract_sha256':digest(HERE/'contract.json')['sha256'],
            'author_verdict_sha256':digest(HERE/'author-validation.json')['sha256'],
            'independent_verdict_sha256':digest(HERE/'review'/'independent-verdict.json')['sha256'],
            'author_report_cells':author['full_report_cells_checked'],
            'independent_report_cells':reviewer['full_report_cells_compared'],
            'author_tamper_rejections':checks['rejected_count'],
            'independent_tamper_rejections':reviewer['tamper_rejections'],
            'source_count':len(source),'source_files':source,
            'accepted_source_base_commit':c['base_commit'],
            'accepted_source_refs':accepted_source_refs(c['accepted_lineage']),
            'raw_count':len(raw),'raw_files':raw,
            'sole_run':{k:c['excluded_v102']['ordinary_run'][k] for k in ('run_id','closure','failure_seal','invocation')},
            'accepted_parent_raw_count':117,'sole_run_raw_count':13,
            'raw_location_policy':'ignored local sealed original run directories; no raw is published as Git source',
            'scope':'One sealed ordinary control with HOME lender P-MECH wait; TTRSS=TTRS=.5; no conditional-duration contrast.'}

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');a=parser.parse_args()
    obj=build();raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    if a.write:
        if INDEX.exists():assert INDEX.read_bytes()==raw,'existing index differs: preserve it before revision'
        else:INDEX.write_bytes(raw)
    elif INDEX.exists():assert INDEX.read_bytes()==raw,'index no longer matches source bytes'
    print(json.dumps({'passed':True,'source_count':obj['source_count'],'raw_count':obj['raw_count'],
                      'index_bytes':len(raw),'index_sha256':hashlib.sha256(raw).hexdigest(),
                      'written':a.write},sort_keys=True))
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print(json.dumps({'passed':False,'error':f'{type(exc).__name__}: {exc}'},sort_keys=True))
        sys.exit(1)
