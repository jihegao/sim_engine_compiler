"""Read-only replay of archived acceptance, never a native launch."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
def sha(p):
 b=Path(p).read_bytes();return len(b),hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence-index-sha',required=True);p.add_argument('--binding-sha',required=True);a=p.parse_args()
 index=ROOT/'evidence-index.json'
 if sha(index)[1]!=a.evidence_index_sha:raise ValueError('external exact evidence-index binding differs')
 j=json.loads(index.read_text(encoding='utf-8'))
 for f in j['artifacts']:
  rel=Path(f['relative_path'])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('archive path outside package')
  if sha(ROOT/rel)!=(f['bytes'],f['sha256']):raise ValueError('archive bytes differ: '+str(rel))
 from check_exchange_v2 import trusted,check_raw
 contract,_=trusted(ROOT,a.binding_sha)
 physical=Path(contract['candidate']['physical_directory'])
 run=ROOT/'runs'/j['run_id'];names={'input.json','model.sxi','roundtrip-raw.json','import.log','export.log','jimport_save-stdout.bin','jimport_save-stderr.bin','jexport-stdout.bin','jexport-stderr.bin'}
 for kind in ('original','recovered'):
  if {f.name for f in (run/kind).iterdir()}!=names:raise ValueError('complete archived raw set differs')
 for n in names:
  if sha(run/'original'/n)!=sha(run/'recovered'/n):raise ValueError('original/recovered bytes differ')
 results=[check_raw(ROOT,run/kind,a.binding_sha,str(physical/'input.json'),str(physical/'roundtrip-raw.json')) for kind in ('original','recovered')]
 print(json.dumps(dict(status='READONLY_ARCHIVED_RAW_REPLAY_ACCEPTED',run_id=j['run_id'],results=results,native_calls=0,model_reruns=0,OS_identity_or_readonly_seal_reproduced=False,publication_GO=False,whole_scope_complete=False)))
 return 0
if __name__=='__main__':raise SystemExit(main())
