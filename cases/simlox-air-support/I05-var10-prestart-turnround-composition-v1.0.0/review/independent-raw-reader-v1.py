import runpy,pathlib,copy,json,re,datetime
J=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009t195400z/resume-20261010t032847z');g=runpy.run_path(str(J/'review-var10-part1-v2.py'));globals().update({k:v for k,v in g.items() if not k.startswith('__')})
parent=read(s['source']['path']);child=read(A/'candidate-input-method-draft.json');nt={'name':'ChangesTaskBreakDown','columns':[{'name':'TID','datatype':'string','key':True},{'name':'SEQ','datatype':'integer','key':True},{'name':'TIMEC','datatype':'double','key':True},{'name':'DURN','datatype':'double'},{'name':'DURND','datatype':'string'},{'name':'NOTE','datatype':'string'}],'instances':[{'instance_name':'','rows':[['TURN-STEPS',1,25,.25,None,None],['TURN-STEPS',2,25,.75,None,None]]}]};ex=copy.deepcopy(parent);ex['model']['tables'][0]['instances'][0]['rows'][0][0]=desc;ex['model']['tables'].append(nt);strict(child,ex);rt=read(raw['roundtrip-raw.json']);rt['model']['tables'][0]['instances'][0]['rows'][0][0]=desc;rt['model']['tables'].append(copy.deepcopy(nt));assert len(rt['model']['tables'])==33

def ledger(log):
 ll=log.decode('ascii').splitlines();periods=[]
 for task,a,b in [(1,23.5,24),(3,26.75,27.75)]:
  for action,t in [('started',a),('completed',b)]:
   hits=[float(z[1]) for x in ll if (z:=re.fullmatch(r'Time: ([0-9.]+)  system turnround task '+str(task)+r' on <TEACH-AIR-01,0> '+action,x))];assert hits==[t]
  periods.append({'task':task,'start':a,'end':b,'hours':b-a,'start_bin':int(a*2)/2})
 for sid,seq,a,b,d in [(6,1,26.75,27,.25),(7,2,27,27.75,.75)]:
  pref=f'subtask {sid} seqno {seq} within system turnround task 3 on <TEACH-AIR-01,0>'
  for t,msg in [(a,'started'),(a,f'starts performing, planned to last for {d} hours'),(b,'completed')]:assert ll.count(f'Time: {t:g}  {pref} {msg}')==1
 return periods
periods=ledger(newlog);integral=lambda k:sum(r[columns[k]]*(r[columns['ETINT']]-r[columns['STINT']]) for r in rows);assert integral('NSYMT')==sum(x['hours'] for x in periods)==1.5 and integral('NSYMP')==1 and integral('NSYMO')==4;assert all(r[columns['NSYDT']]==0 and r[columns['SYDT']] is None for r in rows);assert rows[-1][columns['NSYRY']]==1
bad=[]
def negative(n,fn):
 try:fn()
 except AssertionError:bad.append({'name':n,'rejected':True})
 else:raise AssertionError('negativeaccepted '+n)
def valid(log,r):assert log==newlog;strict(r,expected);ledger(log)
for n,l in [('oldparent',parentlog),('oldfirst',newlog.replace(b'last for 0.25 hours',b'last for 0.166667 hours')),('oldsecond',newlog.replace(b'last for 0.75 hours',b'last for 0.333333 hours')),('wrongstepclock',newlog.replace(b'Time: 27 ',b'Time: 26.9167 ')),('wrongmainend',newlog.replace(b'Time: 27.75',b'Time: 27.25')),('missing',b''.join(newlog.splitlines(keepends=True)[:-1])),('duplicate',newlog+newlog.splitlines(keepends=True)[0])]:negative(n,lambda l=l:valid(l,expected))
for n,fn in [('numeric-type',lambda p:p['report']['tables'][2]['instances'][0]['rows'][54].__setitem__(columns['NSYMT'],1.0)),('metadata',lambda p:p['report']['tables'][2]['columns'][0].pop('name')),('stock',lambda p:p['report']['tables'][3]['instances'][0]['rows'][0].__setitem__(-1,999))]:
 p=copy.deepcopy(expected);fn(p);negative(n,lambda p=p:valid(newlog,p))
for n,l in [('startmissing',newlog.replace(b'Time: 26.75  system turnround task 3',b'ignored')),('endduplicate',newlog+b'Time: 27.75  system turnround task 3 on <TEACH-AIR-01,0> completed\r\n'),('durwrong',newlog.replace(b'last for 0.75 hours',b'last for 0.5 hours'))]:negative(n,lambda l=l:ledger(l))
p=copy.deepcopy(rt);p['model']['tables'].pop(2);negative('native-defaultmissing',lambda:strict(p,rt));p=copy.deepcopy(rt);p['model']['tables'][-1]['instances'][0]['rows'][0][1]=1.0;negative('SEQtypefloat',lambda:strict(p,rt))
for x in m['files']:assert pin(x['path'])['sha256']==x['sha256']
W=pathlib.Path.cwd();C=W/'cases/simlox-air-support/I05-var10-prestart-turnround-composition-v1.0.0';N=W/'tmp/i05-var10-prestart-native-v100-20261010-01';R=C/'runs/i05-var10-turnround-prestart-v100-ssh-20261010-01';D=J/'var10-raw-review'
cl=read(R/'closure.json');inv=read(R/'invocation.json');steps=read(R/'steps.json');manifest=read(C/'prelaunch-manifest-v100-run01.json');sources={x['key']:x['sha256'] for x in manifest['sources']};assert len(sources)==98 and cl['source_hashes_before']==cl['source_hashes_after']==inv['source_hashes_before']==sources
for x in manifest['sources']:assert pin(x['path'])['bytes']==x['bytes'] and pin(x['path'])['sha256']==x['sha256']
assert cl['error'] is None and cl['roundtrip_check_passed'] and cl['behavior_check_passed'];assert cl['invocation_sha256']==pin(N/'invocation.json')['sha256'];assert set(cl['raw'])=={p.name for p in N.iterdir() if p.is_file()}-{'closure.json'} and len(cl['raw'])==24
pairs=[]
for p in N.iterdir():
 if not p.is_file():continue
 q=R/p.name;assert p.read_bytes()==q.read_bytes() and (p.stat().st_file_attributes&1) and (q.stat().st_file_attributes&1);pairs.append({'original':pin(p),'recovered':pin(q),'readonly_both':True})
assert len(pairs)==25 and set(p.name for p in R.iterdir())==set(p.name for p in N.iterdir())|{'run-summary.json'}
for n,se in cl['raw'].items():assert pin(N/n)['bytes']==se['bytes'] and pin(N/n)['sha256']==se['sha256']
assert (N/'input.json').read_bytes()==(C/'native-input.json').read_bytes();assert (N/'model.log').read_bytes()==newlog;strict(read(N/'report-raw.json'),expected);ledger((N/'model.log').read_bytes())
a=read(N/'roundtrip-raw.json');aa=copy.deepcopy(a);ee=copy.deepcopy(rt);at=aa['model'].pop('tables');et=ee['model'].pop('tables');strict(aa,ee);en=[t['name'] for t in et];names=[t['name'] for t in at];assert len(names)==len(set(names))==33 and set(names)==set(en) and [n for n in names if n!='ChangesTaskBreakDown']==en[:-1]
by={t['name']:t for t in at}
for t in et:strict(by[t['name']],t)
assert inv['host_name']=='4700-3' and inv['session']['session_id']==0 and inv['session']['ps_major']==5 and inv['session']['session_name'] in [None,''] and inv['session']['ssh_connection'] and 'sshd.exe' in inv['session']['ssh_ancestors'];assert inv['queue_mutex']=='Global\\SimloxIssue18NativeQueue' and inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and inv['gui']['start_unix_ms']==1790590196826 and inv['gui']['responding'] and re.search(r'\b1\s+(Active|运行中)\b',inv['gui']['wts_active_line'])
assert [x['name'] for x in steps]==['import','export','check_import_export','calc','jsonreport','check_behavior'];strict(steps,cl['steps'])
for x in steps:
 assert x['status']=='completed' and x['exit_code']==0 and x['error'] is None and x['gui_preserved'] is True
 assert datetime.datetime.fromisoformat(x['started_utc'].replace('Z','+00:00'))<datetime.datetime.fromisoformat(x['completed_utc'].replace('Z','+00:00'))
 for k in ['stdout','stderr']:assert pin(x[k+'_path'])['bytes']==x[k+'_bytes'] and pin(x[k+'_path'])['sha256']==x[k+'_sha256']
 assert x['stderr_bytes']==0
conv=cl['converter'];assert conv['sha256']==pin(N/'run.log')['sha256'] and conv['physical_lines']==17 and conv['errors']==0 and conv['warnings']==2 and conv['notes']==0 and conv['warning_codes']==['108','126'] and conv['terminal_crlf'] is True
T=C/'review/transport-native-20261010T083908082658Z-5afbe074';tr=read(T/'transport-receipt.json');assert tr['mode']=='native' and tr['native_approved'] is True and tr['exit_code']==0 and tr['error'] is None and tr['source_stability_error'] is None and tr['source_hashes_after']==sources and (T/'ssh-stderr.bin').read_bytes()==b''
G=J/'var10-native-standalone-guardian.json';guardian=read(G);assert datetime.datetime.fromisoformat(guardian['utc'].replace('Z','+00:00'))<datetime.datetime.fromisoformat(tr['started_utc']);assert guardian['native_calls']==0 and guardian['native_queue_free'] and guardian['executor_mutex_held'] and guardian['other_native_runner_contenders']==[]
for key,filename in [('contract_sha256','contract.json'),('method_manifest_sha256','method-source-manifest.json'),('prelaunch_manifest_sha256','prelaunch-manifest-v100-run01.json'),('independent_prelaunch_approval_sha256','review/independent-prelaunch-go.json'),('input_sha256','native-input.json')]:assert inv[key]==pin(C/filename)['sha256']
pre=read(C/'review/independent-prelaunch-go.json');assert pre['decision']=='GO_PRELAUNCH' and inv['preflight_sha256']==pre['preflight_sha256']
for x in manifest['sources']:assert pin(x['path'])['sha256']==x['sha256']
r={'schema':'issue18-independent-fullraw-behavior/v1','decision':'GO_RAW_BEHAVIOR_RESTRICTED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/var13_method_gap_review','scope':'I05.var10 prestart scalarTURN-STEPS composition .25/.75 at25 on originalB04 only','run_id':manifest['run_id'],'source_roles':98,'source_hashes_before_after_current':sources,'manifest':pin(C/'prelaunch-manifest-v100-run01.json'),'closure':pin(N/'closure.json'),'invocation':pin(N/'invocation.json'),'transport':pin(T/'transport-receipt.json'),'guardian':pin(G),'original_recovered_pairs':pairs,'full_log_lines':125,'exact_substitutions':16,'report_typed_cells':4044,'metadata_full_exact':True,'report_changes':7,'System_bins':72,'Stock_bins':72,'native_roundtrip_tables':33,'default_tables_unchanged':True,'startregistered_periods':periods,'hours':{'turnround':1.5,'prep':1,'flight':4},'NSYDT':0,'SYDT':None,'ready_terminal':1,'independent_controls':bad,'four_natural_exit0_native_stages':[x for x in steps if x['name'] in ['import','export','calc','jsonreport']],'reader_pin':pin(D/'independent-fullraw-reader-v1.py'),'derivation_reader_dependencies':[pin(J/'review-var10-part1-v2.py')],'independence':'Own original-parent derivation and own strict fulltyped/log/model/ledger checker; no author reader import or observed oracle edits','review_native_calls':0,'parent_reruns':0,'whole_var10':False,'publication_GO':False,'crossengine':False,'performance':False,'whole_issue_complete':False,'completion_denominator':None,'GUI':'featurevalidation excluded; recorded stage safety only','commands_finished':True,'no_inflight_writes_after_receipt':True}

convbytes=(N/'run.log').read_bytes();text=convbytes.decode('utf-8-sig');assert text.endswith('\r\n') and not re.search(r'(?<!\r)\n',text);vl=text[:-2].split('\r\n');assert len(vl)==17
fixed={0:'Performing simulation',1:'Input file: '+str(N/'model.sxi'),2:'Output file: '+str(N/'model.sxo'),3:'Simulating.',4:'Converting input data ...',5:'File: '+str(N/'model.sxi').replace('\\','/'),6:'Form: Control',7:'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',8:'Form: System',9:'rec 1: (warning #126) This system contains no items: TEACH-AIR-01',10:'Input conversion completed. Errors: 0, Warnings: 2, Notes: 0',12:'Starting simulation...',14:'Saving results ...'}
for k,v in fixed.items():assert vl[k]==v
for k,v in {11:'Input data conversion time',13:'Simulation time',15:'Result saving time',16:'Total execution time'}.items():assert re.fullmatch(re.escape(v)+r': [0-9]+(?:\.[0-9]+)? secs\.',vl[k])
safety=read(D/'fresh-raw-review-safety.json');assert safety['host']=='4700-3' and safety['NativeQueue_obtainable'] is True and safety['GUI']['pid']==13340 and safety['GUI']['responding'] is True and safety['completed_physical_recovered_present'] is True
for x in manifest['sources']:assert pin(x['path'])['sha256']==x['sha256']
r['reader_pin']=pin(pathlib.Path(__file__));r['fresh_review_safety']=pin(D/'fresh-raw-review-safety.json');r['own_actual_converter_full_17grammar_passed']=True;r['reader_is_readonly']=True;r['supersedes_provisional_receipt']='v1 provisional before freshpostraw safety; all raw findings retained, v2 final adds own actualconverter grammar and fresh review safety'
print(json.dumps(r,ensure_ascii=False))

