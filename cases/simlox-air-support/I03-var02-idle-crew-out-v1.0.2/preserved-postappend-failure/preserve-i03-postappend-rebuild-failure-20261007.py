from pathlib import Path
import subprocess,json,hashlib,stat
r=Path(__file__).resolve().parents[1];p=r/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
out=r/'tmp/i03-v102-postappend-index-failure-20261007-01';assert not out.exists();out.mkdir()
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
records={}
for name,method in [('replay','review/independent_replay_v3.py'),('builder','make_evidence_index.py')]:
    result=subprocess.run([str(Path(__import__('sys').executable)),'-X','utf8','-B',str(p/method)],cwd=r,capture_output=True)
    for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:
        f=out/(name+'-'+stream+'.bin');f.write_bytes(data)
    records[name]={'method':method,'method_pin':pin((p/method).read_bytes()),'exit_code':result.returncode,'streams':{s:pin(b) for s,b in [('stdout',result.stdout),('stderr',result.stderr)]}}
assert records['replay']['exit_code']==0 and records['builder']['exit_code']==1
assert (out/'replay-stderr.bin').read_bytes()==b''
old=json.loads((p/'review/independent-postrun-verdict-v3.json').read_bytes());new=json.loads((out/'replay-stdout.bin').read_bytes())
assert type(old['checks']) is int and old['checks']==14996 and type(new['checks']) is int and new['checks']==14995
assert {k:v for k,v in old.items() if k!='checks'}=={k:v for k,v in new.items() if k!='checks'}
catalog=(r/'cases/simlox-air-support/publication-index-v1.json').read_bytes();assert len(json.loads(catalog)['entries'])==491
(out/'unpublished-catalog491.bytes').write_bytes(catalog)
doc={'schema':'i03-postappend-index-rebuild-failure/v1','decision':'NO_GO_PUBLICATION_REPRO_ORIGINALS_PRESERVED','native_calls':0,'accepted_native_reruns':0,'original_native_verdict_checks':14996,'postappend_frozen_replay_checks':14995,'other_verdict_fields_exact':True,'cause':'Frozen replay skips one prepublication catalog-exact check at >490 entries; original builder strict full-verdict comparison rejects count change. Mandatory catalog prefix/metadata/archive/baseGit gates remain.','records':records,'original_index':pin((p/'evidence-index.json').read_bytes()),'unpublished_catalog491':pin(catalog),'original_failure_tool_output_format':'Initial failure observed as decoded exec tool text; this separate read-only reproduction preserves original subprocess stdout/stderr bytes.'}
(out/'failure-receipt.json').write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8')
for f in out.iterdir():f.chmod(f.stat().st_mode&~stat.S_IWRITE)
Path(__file__).chmod(Path(__file__).stat().st_mode&~stat.S_IWRITE)
print(json.dumps({'failure_receipt':pin((out/'failure-receipt.json').read_bytes()),'native_calls':0,'other_verdict_fields_exact':True,'index':doc['original_index']},indent=2))
