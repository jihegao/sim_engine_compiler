import hashlib,json,stat,subprocess
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];pkg=root/'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.1'
expected={'contract.json':(38324,'3c487385f4a160b7994b9533deaacba8c4a91de6cdf032812316bb6a2ca287c8'),'README.md':(1313,'9a593fe0707e61223b19bc7093d9a50034dd81b3b2da0a17a5ec53ba0d26958d'),'.gitattributes':(8,'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da')}
c=json.loads((pkg/'contract.json').read_bytes())
for rec in c['excluded_v010']['files']:
 b=(root/rec['original_path']).read_bytes();assert len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['sha256'];assert (pkg/rec['inert_copy_path']).read_bytes()==b
 expected[rec['inert_copy_path']]=(rec['bytes'],rec['sha256'])
out=root/'tmp/b03-var01-v011-root-contract-freeze-20261007.json';assert not out.exists()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==c['base_commit']
assert sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob('*') if p.is_file())==sorted(expected)
records=[]
for name,(size,sha) in expected.items():
 p=pkg/name;b=p.read_bytes();assert len(b)==size and hashlib.sha256(b).hexdigest()==sha
 records.append({'path':p.relative_to(root).as_posix(),'bytes':size,'sha256':sha})
for name in expected:(pkg/name).chmod(stat.S_IREAD)
receipt={'decision':'ROOT_V011_CONTRACT_FROZEN_AWAIT_INDEPENDENT_GO','utc':datetime.now(timezone.utc).isoformat(),'files':records,'author_files_exist_at_freeze':True,'methods_created':False,'new_native_runs':0,'original_v010_no_go_preserved':True,'overall_goal':'unfinished'}
out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');out.chmod(stat.S_IREAD)
print(json.dumps({'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(records)}))
