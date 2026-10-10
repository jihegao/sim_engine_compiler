import json,pathlib,hashlib,copy,re,datetime,math
W=pathlib.Path.cwd();J=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z');R=J/'resume-20261010T002248Z';O=R/'var02-raw-review';H=W/'cases/simlox-air-support/I05-var02-scheduled-damage-repair-v1.0.0';S=R/'var02-source-review'
def pin(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def load(p):return json.loads(pathlib.Path(p).read_bytes())
def parse(raw):
 text=raw.decode('utf-8-sig');out=[];q=False;esc=False
 for i,ch in enumerate(text):
  if q:
   out.append(ch)
   if esc:esc=False
   elif ch=='\\':esc=True
   elif ch=='"':q=False
  elif ch=='"':q=True;out.append(ch)
  elif ch==',':
   end=i+1
   while end<len(text) and text[end].isspace():end+=1
   if end==len(text) or text[end] not in ']}':out.append(ch)
  else:out.append(ch)
 return json.loads(''.join(out))
def strict(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(strict(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(strict(x,y) for x,y in zip(a,b))
 return a==b
selpath=R/'var02-author-method-selection-v100.json';assert pin(selpath)['sha256']=='aaf6c880a26c47c08eeef0a4693437c8f70b397333306f8db7cfc93385fc5240';sel=load(selpath)
for p in sel['source_files']+[sel['author_controls'],sel['independent_source_receipt'],sel['primary_manual_summary']]:assert pin(p['path'])==p
assert len(sel['source_files'])==11
# Fully read/parse selected sources; no author code imports/execution.
selected={pathlib.Path(p['path']).name:pathlib.Path(p['path']).read_bytes() for p in sel['source_files']}
for name,raw in selected.items():
 if name.endswith('.json'):json.loads(raw)
 else:raw.decode('utf-8-sig')
controls=load(sel['author_controls']['path']);assert [x['result']['checks_total'] for x in controls['checks']]==[74,13];assert all(x['exit_code']==0 and all(x['result']['checks'].values()) for x in controls['checks'])
source=load(sel['independent_source_receipt']['path']);hp=pathlib.Path(source['original_raw_12'][0]['path']).parent
for p in source['original_raw_12']+[source['closure_pin'],source['invocation_pin']]:assert pin(p['path'])==p
parent=load(source['source_pin']['path']);cand=json.loads(selected['native-input.json']);desc='I05.var02: hour5 scalar scheduled DamageRepair DIRPT1 to1.5 from accepted H02.var01'
cols=['DAMID','SID','STID','TIMEC','DIRPT','SURPT','DIRPF','SURPF','DIRPD','SURPD','NOTE'];dtypes=['string']*3+['double']*5+['string']*3
newtable={'name':'ChangesDamageRepair','columns':[dict(name=n,datatype=t,**({'key':True} if i<4 else {})) for i,(n,t) in enumerate(zip(cols,dtypes))],'instances':[{'instance_name':'','rows':[['BATTLE-LOSS','TEACH-AIR-01','BASE-01',5.0,1.5,0.0,1.0,1.0,None,None,None]]}]}
expect=copy.deepcopy(parent);next(t for t in expect['model']['tables'] if t['name']=='ProblemDescription')['instances'][0]['rows'][0][0]=desc;expect['model']['tables'].append(newtable);assert strict(cand,expect)
authored=[t for t in cand['model']['tables'] if any(i['rows'] for i in t['instances'])];assert len(authored)==18;assert sum(len(r) for t in authored for i in t['instances'] for r in i['rows'])==218
# Independent event derivation from parent tasks, not event oracle.
pl=(hp/'model.log').read_bytes();lines=pl.splitlines(keepends=True);assert len(lines)==137;cl=[];changes=[]
endmap={'10.2814':'10.7814','22.6446':'23.1446','33.393':'33.893'}
for num,raw in enumerate(lines,1):
 body=raw.rstrip(b'\r\n').decode('utf-8');new=body
 if re.fullmatch(r'   < system DIRP task [012] on <TEACH-AIR-01,0>, C, 1>,',body):new=body.replace(', C, 1>,',', C, 1.5>,')
 elif re.search(r'^Time: [\d.]+  direct repair subtask [012] seqno 0 within system DIRP task [012] on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$',body):new=body[:-len('1 hours')]+'1.5 hours'
 elif re.search(r'^Time: [\d.]+ <TEACH-AIR-01,BASE-01,0> System soon ready <TEACH-AIR-01,0>, estimated remaining time: 1$',body):new=body[:-1]+'1.5'
 else:
  for old,end in endmap.items():
   if body.startswith('Time: '+old+' '):new=body.replace('Time: '+old+' ','Time: '+end+' ',1);break
 if new!=body:changes.append(dict(physical_line_1based=num,parent=body,child=new))
 cl.append(new.encode()+raw[len(body.encode()):])
cl=b''.join(cl);assert len(changes)==30
E=json.loads(selected['event-oracle.json']);assert E['physical_lines']==137;assert [{k:x[k] for k in ['physical_line_1based','parent','child']} for x in E['line_substitutions']]==changes
# Independent full report already derived from primary sealed report by this reviewer. Re-read exact parent and recompute.
pr=parse((hp/'report-raw.json').read_bytes());ar=json.loads(selected['parent-report-projection.json'])['report'];assert strict(pr,ar)
cr=copy.deepcopy(pr);ts={t['name']:t for t in cr['report']['tables']};ts['ProblemDescription']['instances'][0]['rows'][0][0]=desc;t=ts['SystemResults'];names=[c['name'] for c in t['columns']];c={n:i for i,n in enumerate(names)};rows=t['instances'][0]['rows'];lookup={x[c['STINT']]:i for i,x in enumerate(rows)}
for start,done in [(9,10),(21.5,22.5),(32,33)]:
 rows[lookup[start]][c['SYDT']]=1.5;old=copy.deepcopy(rows[lookup[done]])
 for n,v in [('NSYRY',0),('NSYA',0),('NSYUA',1),('NSYRP',1),('NREPT',0)]:rows[lookup[done]][c[n]]=v
 for n in ['NSYRY','NSYA','NSYUA','NSYRP','NREPT']:rows[lookup[done+.5]][c[n]]=old[c[n]]
assert strict(cr,json.loads(selected['report-oracle.json'])['expected_report']);assert strict(pr['report']['tables'][1],cr['report']['tables'][1])
# Reusable private exact validator, all report metadata/types, full raw line endings, independent ledger.
def accept(log,report,child=True):return log==(cl if child else pl) and strict(report,cr if child else pr)
checks={'sealed_parent_positive':accept(pl,pr,False),'prospective_child_positive_not_native':accept(cl,cr),'parent_not_child':not accept(pl,pr),'child_not_parent':not accept(cl,cr,False)}
for x in changes:
 ls=cl.splitlines(keepends=True);i=x['physical_line_1based']-1;body=ls[i].rstrip(b'\r\n');ls[i]=x['parent'].encode()+ls[i][len(body):];checks['restore_event_'+str(i+1)]=not accept(b''.join(ls),cr)
rdeltas=[]
for ti,(a,b) in enumerate(zip(pr['report']['tables'],cr['report']['tables'])):
 for ii,(a1,b1) in enumerate(zip(a['instances'],b['instances'])):
  for ri,(r1,r2) in enumerate(zip(a1['rows'],b1['rows'])):
   for ci,(x,y) in enumerate(zip(r1,r2)):
    if not strict(x,y):
     rdeltas.append(dict(table=a['name'],row=ri,column=a['columns'][ci]['name'],old=x,new=y,old_type=type(x).__name__,new_type=type(y).__name__));m=copy.deepcopy(cr);m['report']['tables'][ti]['instances'][ii]['rows'][ri][ci]=x;checks[f'restore_report_{ti}_{ii}_{ri}_{ci}']=not accept(cl,m)
assert len(rdeltas)==34
for name,mutate in [('summary_ready_formula',lambda x:x['report']['tables'][1]['instances'][0]['rows'][0].__setitem__(3,0.7)),('summary_float_int_alias',lambda x:x['report']['tables'][1]['instances'][0]['rows'][0].__setitem__(3,1)),('metadata_bool_int_alias',lambda x:x['report']['tables'][2]['columns'][0].__setitem__('key',1)),('stock_extra_bool',lambda x:x['report']['tables'][3]['instances'][0]['rows'][0].__setitem__(2,False)),('fractional_completion_float_alias',lambda x:x['report']['tables'][2]['instances'][0]['rows'][20].__setitem__(4,0.0))]:
 m=copy.deepcopy(cr);mutate(m);checks[name]=not accept(cl,m)
checks['extra_event']=not accept(cl+b'extra\r\n',cr);checks['CRLF_drift']=not accept(cl.replace(b'\r\n',b'\n',1),cr);checks['private_comma_quote_safe']=parse(b'{"a":",] ,}","b":[1,],}')=={'a':',] ,}','b':[1]}
# Input exact negative controls, independent schema expectations.
for i,value in [(0,'WRONG'),(1,'WRONG'),(2,'WRONG'),(3,0.0),(3,True),(4,2.0),(5,1.0),(6,.5),(8,'<EXP>')]:
 m=copy.deepcopy(cand);m['model']['tables'][-1]['instances'][0]['rows'][0][i]=value;checks['input_'+str(i)+'_'+str(value)]=not strict(m,expect)
# Full parent-generated native tables metadata and rows expected exactly except numeric double token equivalence.
exp=parse((hp/'roundtrip-raw.json').read_bytes());assert len(exp['model']['tables'])==35;native=copy.deepcopy(exp);next(t for t in native['model']['tables'] if t['name']=='ProblemDescription')['instances'][0]['rows'][0][0]=desc;native['model']['tables'].append(newtable)
def export_ok(value):
 if value.keys()!=native.keys() or value['model'].keys()!=native['model'].keys():return False
 for k in native['model']:
  if k!='tables' and not strict(value['model'][k],native['model'][k]):return False
 a=value['model']['tables'];bm={t['name']:t for t in a}
 if len(a)!=len(bm) or set(bm)!={t['name'] for t in native['model']['tables']}:return False
 if [t['name'] for t in a if t['name']!='ChangesDamageRepair']!=[t['name'] for t in exp['model']['tables']]:return False
 for t in native['model']['tables']:
  u=bm[t['name']]
  if t.keys()!=u.keys() or not strict(t['columns'],u['columns']) or len(t['instances'])!=len(u['instances']):return False
  for i,j in zip(t['instances'],u['instances']):
   if i.keys()!=j.keys() or not strict(i['instance_name'],j['instance_name']) or len(i['rows'])!=len(j['rows']):return False
   for r,s in zip(i['rows'],j['rows']):
    if len(r)!=len(s):return False
    for col,x,y in zip(t['columns'],r,s):
     if col['datatype']=='double' and x is not None:
      if type(y) not in [int,float] or not math.isfinite(y) or x!=y:return False
     elif not strict(x,y):return False
 return True
checks['synthetic_export_positive_not_native']=export_ok(native)
for name in ['Tasks','TaskBreakDown','SystemRepair','DamageRepair']:
 m=copy.deepcopy(native);tt=next(t for t in m['model']['tables'] if t['name']==name);tt['instances'][0]['rows'][0][0]='WRONG';checks['native_default_or_parent_'+name]=not export_ok(m)
m=copy.deepcopy(native);m['model']['tables'][-1]['columns'][0]['key']=1;checks['native_new_metadata']=not export_ok(m)
m=copy.deepcopy(native);m['model']['tables'][-1]['instances'][0]['rows'][0][3]=True;checks['native_numeric_bool']=not export_ok(m)
assert all(checks.values()),[k for k,v in checks.items() if not v]
# Independently derive start-registered ledger from log, not author report ledger JSON.
text=cl.decode().replace('\r\n','\n');starts=re.findall(r'^Time: ([\d.]+)  system DIRP task ([012]) on <TEACH-AIR-01,0> started$',text,re.M);ends=re.findall(r'^Time: ([\d.]+)  system DIRP task ([012]) on <TEACH-AIR-01,0> completed$',text,re.M);assert len(starts)==len(ends)==3;ledger=[]
for (start,k),(end,k2) in zip(starts,ends):
 assert k==k2 and abs(float(end)-float(start)-1.5)<1e-4;row=rows[lookup[math.floor(float(start)*2)/2]];assert row[c['SYDT']]==1.5 and type(row[c['SYDT']])==float and row[c['NSYDT']]==1;ledger.append(dict(task=k,start=start,end=end,duration=1.5,registered_bin=row[c['STINT']]))
assert sum(r[c['NSYDT']] for r in rows)==3;assert sum((r[c['SYDT']] or 0)*r[c['NSYDT']] for r in rows)==4.5;occupancy=sum((r[c['ETINT']]-r[c['STINT']])*r[c['NSYRP']] for r in rows);assert abs(occupancy-4.5)<1e-6
# Actual closed evidence inspection only. Run this reader only on root's explicit closure notification.
fpath=H/'prelaunch-manifest-v100-run01.json';f=load(fpath);assert pin(fpath)['sha256']=='08839a3723d7b33b5a6bb0e9ca50540e17a936324ef5c6e16d2ba7e12a16832e';assert len(f['sources'])==85
original=pathlib.Path(f['native_run_directory']);recovered=pathlib.Path(f['recovered_run_directory']);closure=load(original/'closure.json');inv=load(original/'invocation.json');assert closure['error'] is None;assert closure['run_id']==inv['run_id']==f['run_id'];assert closure['invocation_sha256']==pin(original/'invocation.json')['sha256'];assert inv['prelaunch_manifest_sha256']==pin(fpath)['sha256']
sourcepins=[];wanted={x['key']:x['sha256'] for x in f['sources']};assert len(wanted)==85
for x in f['sources']:
 pp=pin(x['path']);assert pp['bytes']==x['bytes'] and pp['sha256']==x['sha256'];sourcepins.append(dict(key=x['key'],**pp))
assert closure['source_hashes_before']==closure['source_hashes_after']==inv['source_hashes_before']==wanted
assert inv['host_name']=='4700-3';sess=inv['session'];assert sess['ps_major']==5 and sess['session_id']==0 and sess['ssh_connection'] and sess['ssh_client'] and 'sshd.exe' in sess['ssh_ancestors'];assert inv['queue_mutex']=='Global\\SimloxIssue18NativeQueue';assert inv['gui']['session_id']==1 and inv['gui']['responding'] is True and inv['gui']['wts_active_line']
assert inv['input_sha256']==pin(H/'native-input.json')['sha256'];assert (original/'input.json').read_bytes()==(H/'native-input.json').read_bytes()
ap=H/'review/independent-prelaunch-go.json';approval=load(ap);assert inv['independent_prelaunch_approval_sha256']==pin(ap)['sha256'];pf=H/'review/preflight-ssh0-20261010T004136071Z.json';assert inv['preflight_sha256']==pin(pf)['sha256'];preflight=load(pf)
steps=closure['steps'];assert strict(steps,load(original/'steps.json'));assert [x['name'] for x in steps]==['import','export','check_import_export','calc','jsonreport','check_behavior'];native_steps=[x for x in steps if x['name'] in ['import','export','calc','jsonreport']];assert len({x['child_pid'] for x in native_steps})==4
for i,s in enumerate(steps):
 assert s['sequence']==i and s['status']=='completed' and s['exit_code']==0 and s['gui_preserved'] is True and s['error'] is None and s['started_utc']<s['completed_utc'];assert i==0 or steps[i-1]['completed_utc']<=s['started_utc']
 for mode in ['stdout','stderr']:
  pp=pin(s[mode+'_path']);assert pp['bytes']==s[mode+'_bytes'] and pp['sha256']==s[mode+'_sha256']
 assert s['stderr_bytes']==0
physical_files=sorted(p.name for p in original.iterdir() if p.is_file());recovered_files=sorted(p.name for p in recovered.iterdir() if p.is_file());assert set(recovered_files)==set(physical_files)|{'run-summary.json'};assert set(closure['raw'])==set(physical_files)-{'closure.json'};pairs=[]
for name in physical_files:
 p=original/name;q=recovered/name;px=pin(p);qx=pin(q);assert px['sha256']==qx['sha256'] and px['bytes']==qx['bytes'];assert p.stat().st_file_attributes&1 and q.stat().st_file_attributes&1
 if name!='closure.json':assert {'bytes':px['bytes'],'sha256':px['sha256']}==closure['raw'][name]
 pairs.append(dict(name=name,bytes=px['bytes'],sha256=px['sha256'],original_readonly=True,recovered_readonly=True))
assert len(physical_files)==25 and len(closure['raw'])==24
summary=load(recovered/'run-summary.json');assert summary['closure_sha256']==pin(original/'closure.json')['sha256'] and summary['invocation_sha256']==pin(original/'invocation.json')['sha256'] and summary['raw_file_count']==24
# Actual converter evidence: preserve parent warning semantics, inspect text and terminal CRLF.
rawrun=(original/'run.log').read_bytes();runlines=rawrun.splitlines();assert len(runlines)==19 and rawrun.endswith(b'\r\n') and rawrun.count(b'\r\n')==19;assert re.findall(rb'warning #(\d+)',rawrun)==[b'108',b'254',b'126'];assert b'Errors: 0, Warnings: 3, Notes: 0' in rawrun and b'Repair fraction (REPF) is ignored for system damages' in rawrun;assert closure['converter']['physical_lines']==19 and closure['converter']['errors']==0 and closure['converter']['warnings']==3
assert export_ok(parse((original/'roundtrip-raw.json').read_bytes()))
actual_log=(original/'model.log').read_bytes();actual_report=parse((original/'report-raw.json').read_bytes());assert accept(actual_log,actual_report);assert len(actual_log.splitlines())==137
actual_rows=actual_report['report']['tables'][2]['instances'][0]['rows'];assert sum(x[c['NDAM']] for x in actual_rows)==3 and sum(x[c['NREPT']] for x in actual_rows)==3;assert actual_rows[-1][c['NSYRY']]==1 and actual_rows[-1][c['NSYLA']]==0 and actual_rows[-1][c['NSYRP']]==0
st=actual_report['report']['tables'][3];sn=[x['name'] for x in st['columns']];stocktotals={n:sum(r[sn.index(n)] or 0 for i in st['instances'] for r in i['rows']) for n in ['NBO','NDD','NDR','NDP','NLD']};assert not any(stocktotals.values())
for x in f['sources']:assert pin(x['path'])['sha256']==x['sha256']
for x in pairs:
 for root in [original,recovered]:assert pin(root/x['name'])['sha256']==x['sha256'] and (root/x['name']).stat().st_file_attributes&1
result={'schema':'issue18-i05-var02-independent-raw-acceptance/v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/var02_source_review','decision':'GO_BOUNDED','reader_pin':pin(O/'independent-raw-reader-v2.py'),'reader_provenance':'Own signed method source expanded with independent actual closure/source/raw verification; no author reader import/execution','method_receipt_pin':pin(R/'var02-method-review/independent-method-go-v100.json'),'freeze_pin':pin(fpath),'sourcekeys_before_after_actual':85,'actual_source_pins':sourcepins,'run_id':f['run_id'],'native_attempts':1,'native_steps':native_steps,'native_calls_by_reviewer':0,'parent_reruns_by_reviewer':0,'session':sess,'protected_gui':inv['gui'],'prelaunch_approval_pin':pin(ap),'pure_preflight_pin':pin(pf),'closure_pin':pin(original/'closure.json'),'invocation_pin':pin(original/'invocation.json'),'original_recovered_pairs':pairs,'closure_raw_map_count':24,'recovered_summary_pin':pin(recovered/'run-summary.json'),'original_recovered_unchanged_after_replay':True,'allpairs_readonly':True,'authored_row_bearing_tables':18,'authored_cells':218,'original_parent_native_tables':35,'native_default_tables':18,'native_export_tables':36,'converter_physical_lines':19,'converter_errors':0,'converter_warnings':[108,254,126],'physical_event_lines':137,'event_changes':30,'all_other_event_bytes_and_endings_preserved':True,'report_cells':4044,'report_metadata_typed_exact':True,'System_rows':72,'Stock_rows':72,'report_changes_including_PDESC':34,'summary_all_typed_unchanged':True,'independent_ledger':ledger,'registered_periods':3,'registered_hours':4.5,'occupied_hours':occupancy,'endstate':{'ready':1,'lost':0,'inrepair':0},'stock_totals':stocktotals,'checks_total':len(checks),'checks':checks,'limits':['One scalar existingDamageRepairDIRPT scheduledpositivehour5 from fixedacceptedH02.var01 only','GUI-exclusivefunctionality/gatesexcluded,processprotectiononlysafety','No fraction/distribution/group/inprogress/sametime/otherRNG/wholevariant acceptance','No crossengine/performance/wholeIssue or wholeGoal completion proof','Publication/content/staged/remote/postmerge gates remain independent'],'overall_complete':False,'completion_denominator':None}
(O/'independent-raw-acceptance-v100.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'receipt':pin(O/'independent-raw-acceptance-v100.json'),'decision':'GO_BOUNDED','checks':len(checks),'native_by_reviewer':0}))