import hashlib,json,stat,subprocess
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1]
package=root/'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.0'
expected={'contract.json':(32311,'7bb562507914516fffc2d4f30d9a28ba05dbd4d6f4150c0d475a921fa14e10b9'),'README.md':(1244,'ba7e04b62c80346c5de42b664da772aacfc6436484498e7286e6f8262cd1644f'),'.gitattributes':(8,'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da')}
out=root/'tmp/b03-var01-root-contract-freeze-20261007.json'
assert not out.exists()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()=='6b806777edd4aa8951a2883004edcc54b0ea3042'
assert sorted(p.name for p in package.iterdir())==sorted(expected)
records=[]
for name,(size,sha) in expected.items():
 p=package/name;b=p.read_bytes();assert len(b)==size and hashlib.sha256(b).hexdigest()==sha,(name,len(b),hashlib.sha256(b).hexdigest())
 records.append({'path':p.relative_to(root).as_posix(),'bytes':size,'sha256':sha})
for name in expected:(package/name).chmod(stat.S_IREAD)
receipt={'decision':'ROOT_CONTRACT_FROZEN_AWAIT_INDEPENDENT_GO','utc':datetime.now(timezone.utc).isoformat(),'files':records,'author_files_exist_at_freeze':True,'methods_created':False,'new_native_runs':0,'selection_receipt':'tmp/b03-var01-root-owner-selection-20261007.json','overall_goal':'unfinished'}
out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');out.chmod(stat.S_IREAD)
print(json.dumps({'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(records)}))
