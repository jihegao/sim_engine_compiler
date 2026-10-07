from pathlib import Path
import sys,json,hashlib
r=Path(__file__).resolve().parents[1]; p=r/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2/review'
sys.path.insert(0,str(p))
import independent_replay as v
import independent_self_check as s
raw=s.synthetic_child_log(); v.child_physical(raw,v.Audit())
lines=raw.decode().splitlines()
mutants={}
changed=[x for x in lines if x.strip() not in ('no failures','no PMTasks')]
changed[-1:-1]=[x for x in lines if x.strip() in ('no failures','no PMTasks')]
mutants['orphan return continuations moved to terminal']='\n'.join(changed)+'\n'
changed=lines.copy(); n=next(i for i,x in enumerate(changed) if 'allocated to maintenance task' in x)
changed.insert(n+1,'  Free resources at: <BASE-01,0> P-CREW 2')
mutants['contradictory untimed free crew while booked']='\n'.join(changed)+'\n'
changed=lines.copy(); n=next(i for i,x in enumerate(changed) if 'Time: 8.0 ' in x)
changed.insert(n,'Time: 8.0 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>')
mutants['extra typed ready increase during preparation']='\n'.join(changed)+'\n'
out=[]
for label,changed in mutants.items():
 try: v.child_physical(changed.encode(),v.Audit()); result='ESCAPED'
 except (AssertionError,ValueError,TypeError,KeyError,IndexError) as e: result='REJECTED: '+str(e)
 out.append({'mutation':label,'result':result})
receipt={'schema':'i03-var02-root-independent-ledger-probes/v1','method_sha256':hashlib.sha256((p/'independent_replay.py').read_bytes()).hexdigest(),'synthetic_only':True,'new_native_runs':0,'results':out}
f=r/'tmp/i03-var02-independent-ledger-probes-20261007.json'; assert not f.exists(); f.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8'); print(json.dumps(receipt,indent=2))
