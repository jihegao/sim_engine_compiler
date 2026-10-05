"""Freeze one forbidden time-to-stock scheduled reorder strategy change."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'E15-var01-time-based-cycle-v1.0.0/native-input.json'
PIN='d37bdc10592dff04e521d66276b49f9404dfea0511fac5ea73ef201b02b22b1f'
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PIN
source=json.loads(PARENT.read_text(encoding='utf-8-sig'))
tables=source['model']['tables'];by_name={t['name']:t for t in tables}
assert len(tables)==len(by_name)==31 and 'ChangesItemReorder' not in by_name
assert by_name['ItemReorder']['instances'][0]['rows']==[['TEACH-DU-01','DEPOT-01',1.0,None,None,16.0,None,None,None,None,None]]
fields=[('IID','string'),('STID','string'),('TIMEC','double'),('LEADT','double'),('DISCF','double'),('LEADTD','string'),('ROINT','double'),('NOTE','string')]
change={'name':'ChangesItemReorder','columns':[{'name':n,'datatype':kind,**({'key':True} if n in ('IID','STID','TIMEC') else {})} for n,kind in fields], 'instances':[{'instance_name':'','rows':[['TEACH-DU-01','DEPOT-01',5.0,None,None,None,0.0,None]]}]}
tables.insert(tables.index(by_name['ItemReorder'])+1,change)
raw=(json.dumps(source,ensure_ascii=False,indent=2)+'\n').encode()
target=HERE/'native-input.json'
if target.exists():assert target.read_bytes()==raw,'frozen candidate differs'
else:target.write_bytes(raw)
print({'parent_sha256':PIN,'candidate_sha256':hashlib.sha256(raw).hexdigest(),'tables':len(tables)})