import json, hashlib
from pathlib import Path
here=Path(__file__).resolve().parent
base=here/'source-maps/publication-index-v1-before-v108.json.bytes'
entry=json.loads((here/'publication-entry.json').read_text(encoding='utf-8-sig'))
raw=base.read_bytes(); idx=json.loads(raw.decode('utf-8'))
if any(e.get('publication_id')==entry['publication_id'] for e in idx['entries']): raise SystemExit('duplicate publication id')
if idx.get('entry_publication_state')!='reusable_published': raise SystemExit('unexpected canonical entry state')
idx['entries'].append(entry)
out=here/'review/publication-index-candidate-v108.json'
out.write_text(json.dumps(idx,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'CANDIDATE_CREATED','base_bytes':len(raw),'base_sha256':hashlib.sha256(raw).hexdigest(),'base_entries':len(idx['entries'])-1,'candidate_bytes':out.stat().st_size,'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'candidate_entries':len(idx['entries']),'entry_id':entry['publication_id']},sort_keys=True))
