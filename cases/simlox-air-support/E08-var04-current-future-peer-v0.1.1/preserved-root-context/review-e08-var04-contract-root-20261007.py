import json,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[1];p=r/'cases/simlox-air-support/E08-var04-current-future-peer-v0.1.0'
pins={'contract.json':(102414,'83af26abcceb0199fd9264c8807304cb0fad5dfd5cee9c2cb005b6a934a50707'),'README.md':(1797,'0c7d06a3b219d291240cd2df826ac37863c1fba26440d8a1b7dac1705ef7eea2'),'.gitattributes':(8,'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da')}
for name,(size,sha) in pins.items():
 f=p/name;b=f.read_bytes();assert len(b)==size and hashlib.sha256(b).hexdigest()==sha;f.chmod(0o444)
out=r/'tmp/e08-var04-contract-root-freeze-20261007.json';assert not out.exists();out.write_text(json.dumps({'decision':'EXACT_CONTRACT_BYTES_FROZEN_FOR_INDEPENDENT_REVIEW','pins':pins,'issue18_unfinished':True,'native_calls':0},indent=2)+'\n',encoding='utf-8');out.chmod(0o444)
contract=json.loads((p/'contract.json').read_bytes());print('KEYS',list(contract))
for key,value in contract.items():
 if key not in {'accepted_evidence','source_references','raw_references','excluded_evidence','custody','dependencies','source_pins','raw_pins'}:
  s=json.dumps(value,indent=2,ensure_ascii=False)
  if len(s)<18000:print(key,s)
  else:print(key,'LENGTH',len(s),'TYPE',type(value).__name__,'KEYS',list(value) if isinstance(value,dict) else None)
print((p/'README.md').read_text())
