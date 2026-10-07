import json,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[1];p=r/'cases/simlox-air-support/E08-var04-current-future-peer-v0.1.1'
pins={'contract.json':(106416,'b95349ff646d5faaf2d754cce2624e39735bdf772865f294a93828140596bad3'),'README.md':(2039,'799861f3f59f742b34a175899b9a41cbee1539ea961d01b480b41389615e9dd3'),'.gitattributes':(8,'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da')}
for name,(size,sha) in pins.items():
 f=p/name;b=f.read_bytes();assert len(b)==size and hashlib.sha256(b).hexdigest()==sha;f.chmod(0o444)
out=r/'tmp/e08-var04-v011-contract-root-freeze-20261007.json';assert not out.exists();out.write_text(json.dumps({'decision':'CORRECTED_EXACT_CONTRACT_FROZEN','pins':pins,'excluded_v010_contract':'83af26abcceb0199fd9264c8807304cb0fad5dfd5cee9c2cb005b6a934a50707','native_calls':0,'issue18_unfinished':True},indent=2)+'\n',encoding='utf-8');out.chmod(0o444)
c=json.loads((p/'contract.json').read_bytes())
for k in ['ownership','report_reconstruction','provenance_and_limits']:print(k,json.dumps(c[k],indent=2,ensure_ascii=False))
