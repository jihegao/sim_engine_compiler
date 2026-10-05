"""Repeat the accepted LEADT in the change row to isolate ROINT switch rejection."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'I07-var09-strategy-switch-v1.0.0/native-input.json'
PARENT=HERE.parent/'E15-var01-time-based-cycle-v1.0.0/native-input.json'
OLD_SHA='62317d269a873e75244f46595efaa0bcb558015d5c9734b776bdaa83ee40869b'
PARENT_SHA='d37bdc10592dff04e521d66276b49f9404dfea0511fac5ea73ef201b02b22b1f'
assert hashlib.sha256(OLD.read_bytes()).hexdigest()==OLD_SHA
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA
old=json.loads(OLD.read_text(encoding='utf-8-sig'));parent=json.loads(PARENT.read_text(encoding='utf-8-sig'))
tables={t['name']:t for t in old['model']['tables']};pt={t['name']:t for t in parent['model']['tables']}
assert len(tables)==32 and len(pt)==31
assert all(tables[n]==pt[n] for n in pt)
row=tables['ChangesItemReorder']['instances'][0]['rows'][0]
cols=[x['name'] for x in tables['ChangesItemReorder']['columns']]
assert cols==['IID','STID','TIMEC','LEADT','DISCF','LEADTD','ROINT','NOTE']
assert row==['TEACH-DU-01','DEPOT-01',5.0,None,None,None,0.0,None]
assert pt['ItemReorder']['instances'][0]['rows'][0][2]==1.0
row[3]=1.0
raw=(json.dumps(old,ensure_ascii=False,indent=2)+'\n').encode()
target=HERE/'native-input.json'
if target.exists():assert target.read_bytes()==raw,'frozen candidate differs'
else:target.write_bytes(raw)
print({'candidate_sha256':hashlib.sha256(raw).hexdigest(),'sole_correction':'ChangesItemReorder.LEADT null-to1.0'})