from pathlib import Path
import json,hashlib,copy,datetime
O=Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261009T221148Z/var09-method-review');C=Path.cwd()/'cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0';B=C.parent;P=Path('C:/Users/user/Documents/Codex/2026-09-29/simlox-c04-deadline/repo/cases/simlox-air-support/D01-system-direct-repair-v1.0.0/runs/d01-v100-ssh-20260929-01')
def pin(p):
 d=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}
def read(p):
 s=p.read_text(encoding='utf-8-sig');o=[];q=False;e=False
 for i,c in enumerate(s):
  if q:
   o.append(c)
   if e:e=False
   elif c=='\\':e=True
   elif c=='"':q=False
  elif c=='"':q=True;o.append(c)
  elif c==',':
   k=i+1
   while k<len(s) and s[k].isspace():k+=1
   if k>=len(s) or s[k] not in ']}':o.append(c)
  else:o.append(c)
 return json.loads(''.join(o))
def equal(a,b):
 if type(a)!=type(b):return False
 if type(a)==dict:return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
 if type(a)==list:return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
 return a==b
co=read(C/'contract.json');inp=read(C/'native-input.json');parent=read(B/'D01-system-direct-repair-v1.0.0/native-input.json');expected=copy.deepcopy(parent)
cols=[{'name':n,'datatype':t,**({'key':True} if k else {})} for n,t,k in [('SID','string',1),('STID','string',1),('TIMEC','double',1),('DIRPT','double',0),('SURPT','double',0),('DIRPF','double',0),('SURPF','double',0),('DIRPD','string',0),('SURPD','string',0),('NOTE','string',0)]]
ct={'name':'ChangesSystemRepair','columns':cols,'instances':[{'instance_name':'','rows':[['TEACH-AIR-01','BASE-01',5.0,1.5,0.0,1.0,1.0,None,None,None]]}]};assert equal(ct,co['delta']['table'])
next(t for t in expected['model']['tables'] if t['name']=='ProblemDescription')['instances'][0]['rows'][0][0]=co['candidate']['description'];expected['model']['tables'].append(ct);assert equal(inp,expected)
pr=read(P/'report-raw.json');proj=read(C/'parent-report-projection.json');assert equal(pr['report']['tables'],proj['tables']);assert proj['typed_cell_count']==4044
future=copy.deepcopy(pr['report']['tables']);system=next(t for t in future if t['name']=='SystemResults');rows=system['instances'][0]['rows'];columns=[x['name'] for x in system['columns']];si,ei=columns.index('STINT'),columns.index('ETINT');old=copy.deepcopy(rows)
for dst,src in [(21,20),(22,20),(23,21),(69,68),(70,68),(71,69)]:rows[dst]=copy.deepcopy(old[src]);rows[dst][si]=old[dst][si];rows[dst][ei]=old[dst][ei]
for r in rows:
 starts=[(a,b) for a,b in [(10,11.5),(34,35.5)] if r[si]<=a<r[ei]];r[columns.index('NSYDT')]=len(starts);r[columns.index('SYDT')]=sum(b-a for a,b in starts)/len(starts) if starts else None
changes=[{'row':i,'column':columns[k],'old':a,'new':b,'old_type':type(a).__name__,'new_type':type(b).__name__} for i,(r,s) in enumerate(zip(old,rows)) for k,(a,b) in enumerate(zip(r,s)) if not equal(a,b)];assert len(changes)==22
next(t for t in future if t['name']=='ProblemDescription')['instances'][0]['rows'][0][0]=co['candidate']['description']
lines=(P/'model.log').read_bytes().splitlines(keepends=True);assert len(lines)==128;sub=[]
for i,line in enumerate(lines):
 body=line.rstrip(b'\r\n');new=body
 if i+1 in [37,113]:new=body.replace(b', C, 0.5>,',b', C, 1.5>,')
 elif i+1 in [44,120]:new=body.replace(b'last for 0.5 hours',b'last for 1.5 hours')
 elif i+1 in [45,121]:new=body.replace(b'remaining time: 0.5',b'remaining time: 1.5')
 elif 46<=i+1<=52:new=body.replace(b'Time: 10.5',b'Time: 11.5',1)
 elif 122<=i+1<=128:new=body.replace(b'Time: 34.5',b'Time: 35.5',1)
 if new!=body:sub.append({'physical_line_1based':i+1,'parent':body.decode(),'child':new.decode()})
assert len(sub)==20
oracle=read(C/'event-oracle.json');assert equal(sub,[{k:x[k] for k in ['physical_line_1based','parent','child']} for x in oracle['line_substitutions']])
ro=read(C/'report-oracle.json');assert ro['parent_report_sha256']==pin(P/'report-raw.json')['sha256'];assert equal(ro['system_downtime_projection']['periods'],[{'start':10.0,'end':11.5},{'start':34.0,'end':35.5}]);assert ro['full_scope_count']==4044
controls={'distinct_float_int_rejected':not equal(1,1.0),'distinct_bool_int_rejected':not equal(True,1),'metadata_alias_rejected':not equal({'key':True},{'key':1})}
for label,row,col,val in [('stale_start',20,'SYDT',0.5),('fake_continuation',21,'NSYDT',1),('nonnull_continuation',22,'SYDT',0.5),('wrong_second_start',68,'NSYDT',0),('wrong_completion',23,'NREPT',0),('wrong_occupancy',21,'NSYRP',0)]:
 mutant=copy.deepcopy(future);rr=next(t for t in mutant if t['name']=='SystemResults')['instances'][0]['rows'];assert not equal(rr[row][columns.index(col)],val);rr[row][columns.index(col)]=val;controls[label]=not equal(mutant,future)
assert all(controls.values());assert sum(r[columns.index('NSYRP')]*(r[ei]-r[si]) for r in rows)==3;assert sum(r[columns.index('NSYDT')] for r in rows)==2;assert sum((r[columns.index('SYDT')] or 0)*r[columns.index('NSYDT')] for r in rows)==3
out={'schema':'independent-var09-method-diagnostic/v1','reviewer':'/root/var09_source_review','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'PRELIMINARY_PREDICTION_MATCH_NOT_GATE','author_files':[pin(p) for p in C.glob('*') if p.is_file()],'parent_raw':[pin(P/n) for n in ['model.log','report-raw.json']],'exact_model_delta':True,'source_report_projection_exact4044':True,'independent_event_substitutions':sub,'independent_typed_report_changes':changes,'own_negative_controls':controls,'source_gaps':['await final author file pins and distinct event negative-control fixes'],'native_calls':0,'author_reader_imported':False}
(O/'independent-prediction-v2.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({'output':pin(O/'independent-prediction-v2.json'),'checks':len(controls)},indent=2))
