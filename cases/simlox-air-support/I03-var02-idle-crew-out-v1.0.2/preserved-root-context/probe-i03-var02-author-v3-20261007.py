from pathlib import Path
import hashlib, json, sys

repo = Path(__file__).resolve().parents[1]
review = repo / 'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2/review'
sys.path.insert(0, str(review))
import independent_replay_v3 as v
import independent_self_check_v3 as s

sys.path.insert(0,str(review.parent))
import event_ledger as author
author_before=hashlib.sha256((review.parent/'event_ledger.py').read_bytes()).hexdigest()
def author_gate(raw,a):
    return author.child_timeline(author.parse_log(raw.decode('utf-8-sig')))


expected = {'independent_replay_v3.py':'e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e', 'independent_self_check_v3.py':'46b09155540c59de9369b26f4f6258d4c079e6cb75710dbd841bd075a35d73ae'}
def hashes():
    return {name:hashlib.sha256((review/name).read_bytes()).hexdigest() for name in expected}
assert hashes() == expected
raw=s.synthetic_child_log(); a=v.Audit(); author_gate(raw,a)
lines=raw.decode().splitlines(); mutants={}
def index(fragment):
    return next(i for i,x in enumerate(lines) if fragment in x)
def record(label, changed):
    assert changed != lines
    mutants[label]=('\n'.join(changed)+'\n').encode()
changed=[x for x in lines if x.strip() not in ('no failures','no PMTasks')]
changed[-1:-1]=[x for x in lines if x.strip() in ('no failures','no PMTasks')]
record('orphan return continuations at terminal',changed)
changed=lines.copy(); changed.insert(index('allocated to maintenance task')+1,'  Free resources at: <BASE-01,0> P-CREW 2')
record('contradictory free crew while booked',changed)
changed=lines.copy(); changed.insert(index('Time: 8.0 '),'Time: 8.0 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>')
record('extra ready increase during preparation',changed)
for fragment in ('Start of day no 0','Start of day no 1','resource shift 0 created','resource shift 0 starting','resource shift 0 ended','Free resources at:','systems ready: 2','System soon ready','turnround started','turnround ended','System ready <','Repair task priority list:','nbr ready decreased','Missions and tasks using resources at:','< subtask 0 seqno 1','Tasks waiting for resources at: <BASE-01,0> 1'):
    n=index(fragment)
    changed=lines.copy(); del changed[n]; record('delete '+fragment,changed)
    changed=lines.copy(); changed.insert(n+1,changed[n]); record('duplicate '+fragment,changed)
for label, fragment, old, new in (
    ('wrong booked quantity','< subtask 0 seqno 1',', C, 1, 0.5>',', C, 2, 0.5>'),
    ('wrong return diagnostic aircraft','System ready <TEACH-AIR-01,0>','System ready <TEACH-AIR-01,0>','System ready <TEACH-AIR-01,1>'),
    ('wrong opening resource station','Free resources at:','<BASE-01,0>','<BASE-01,1>')):
    changed=lines.copy(); n=index(fragment); assert old in changed[n]; changed[n]=changed[n].replace(old,new); record(label,changed)
for label, moving, target in (
    ('turnround starts after ending','<TEACH-AIR-01,0> turnround started','<TEACH-AIR-01,0> turnround ended'),
    ('soon ready after turnround ending','System soon ready <TEACH-AIR-01,0>','<TEACH-AIR-01,0> turnround ended')):
    changed=lines.copy(); n=index(moving); line=changed.pop(n); dest=next(i for i,x in enumerate(changed) if target in x); changed.insert(dest+1,line); record(label,changed)
results=[]
for label, mutation in mutants.items():
    try:
        author_gate(mutation,v.Audit()); result='ESCAPED'
    except (AssertionError,ValueError,TypeError,KeyError,IndexError) as exc:
        result='REJECTED'; error=str(exc)
    results.append({'mutation':label,'sha256':hashlib.sha256(mutation).hexdigest(),'result':result,**({'error':error} if result=='REJECTED' else {})})
assert hashes()==expected
assert author_before==hashlib.sha256((review.parent/'event_ledger.py').read_bytes()).hexdigest()
receipt={'schema':'i03-var02-root-author-v3-root-probes/v1','synthetic_only':True,'new_native_runs':0,'method_hashes':expected,'author_gate_sha256':author_before,'clean_checks':a.checks,'results':results,'escapes':[x['mutation'] for x in results if x['result']=='ESCAPED']}
out=repo/'tmp/i03-var02-author-v3-root-probes-20261007.json'
assert not out.exists(); out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({"checks":a.checks,"mutations":len(results),"escapes":receipt["escapes"]}))
