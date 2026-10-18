import pathlib,json,hashlib,struct,math,copy,re,datetime
P=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z')
K=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-09/i05-var08-pm-location/cases/simlox-air-support/K02-var01-json-dtim-precision-v1.0.4')
D=pathlib.Path(__file__).parent; MH='750bb491b1ec359a40b8d278facc4c7a5b380cc675b6f9bada9ac0c840189f42'; R='k02-json-dtim-v104-ssh-20261018-01'; pins={}
def pin(p):
 p=pathlib.Path(p); b=p.read_bytes(); return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def tracked(p):
 q=pin(p);pins[q['path']]=q;return q
def pairs(xs):
 d={}
 for k,v in xs:
  assert k not in d,('duplicate',k); d[k]=v
 return d
def read(p):
 tracked(p);return json.loads(pathlib.Path(p).read_bytes(),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def exact(q):
 a=tracked(q['path']);assert a=={k:q[k] for k in ('path','bytes','sha256')},q;return a
def save(p,x):
 with pathlib.Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
 return pin(p)
utc=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
m=read(K/'selected-manifest-v12.json');assert tracked(K/'selected-manifest-v12.json')['sha256']==MH
gate=read(K/'review/independent-native-go-v12.json');assert tracked(K/'review/independent-native-go-v12.json')['sha256']=='4587945487deb355570dfd88417f45c91aa42c29241054bbccc9b6b706fcc7a4'
for key in ('preflight','preflight_transport','benign_acceptance','actual_preflight_acceptance','accepted_static','authority'):exact(gate[key])
op=K/'review/native-20261018T100756773Z.json';o=read(op);assert tracked(op)['sha256']=='de1d673a866b4926c6d39454ad4431d0a6f6ccc70e5ffc600829199207f3037c'
r=o['result'];assert o['mode']=='native' and o['run_id']==R and o['manifest_sha256']==MH
assert o['independent_gate_sha256']==tracked(K/'review/independent-native-go-v12.json')['sha256']
assert r['RunId']==R and r['Mode']=='native' and not r['Failed'] and r['Failure'] is None and not r['UnknownChild'] and not r['QueueOwned']
for k in ('OriginalSealed','RecoveryVerified','RawBehaviorAccepted','QueueReleaseAttempted','QueueReleasedActual'):assert r[k] is True,k
assert r['NativeSimloxCalls']==2 and r['SimulationCalls']==0 and r['ParentReruns']==0
assert len(r['Children'])==2 and [x['Stage'] for x in r['Children']]==['jimport_save','jexport']
expected=[(75512,134367916936811739,21176),(71576,134367917279832012,2464)]
for c,e in zip(r['Children'],expected):
 assert (c['Pid'],c['Creation'],c['Tid'])==e and c['Session']==0 and c['ResumeCount']==1 and c['ExitCode']==0
 for k in ('CreateAttempted','CreateReturned','Created','ResumeAttempted','ResumeReturned','Signaled','IdentityBeforeResume','IdentityAfterSignal','ExitCodeObserved'):assert c[k] is True,(c['Stage'],k)
 assert c['Failure'] is None and c['WaitError'] is None and c['Application']==m['exe']['path'] and c['ImagePath']==m['exe']['path']
 assert '-calc' not in c['Command'].lower()
assert len(r['Handles'])==99 and len({h['Generation'] for h in r['Handles']})==99
assert all(h['ClosedActual'] and h['CloseAttempted'] and not h['CloseUnknown'] for h in r['Handles'])
# Successful BOOL/NT returns, not stale last-error fields 183/203, classify success.
tp=K/'review/transport-native-1ec82c784a0d4b15aad4b994d2295fdf';tr=read(tp/'transport-receipt.json')
assert tr['mode']=='native' and tr['run_id']==R and tr['manifest_sha256']==MH and tr['exit_code']==0 and tr['error'] is None and tr['source_stability_error'] is None and tr['native_approved'] is True
assert tr['review_sha256']==o['independent_gate_sha256']
for n in ('stdout','stderr'):
 q=tracked(tp/(n+'.bin'));assert {k:q[k] for k in ('bytes','sha256')}==tr['streams'][n]
assert (tp/'stderr.bin').read_bytes()==b'' and pathlib.Path((tp/'stdout.bin').read_text(encoding='utf-8-sig').strip())==op
gp=K/'review/guardian-native-v12-20261018T100700Z.json';g=read(gp)
assert tracked(gp)['sha256']==o['guardian_sha256']==tr['guardian_sha256']=='6a852e9ee9b0b72b9f558cdd99c1d580ca6e83afa488f8debeec2c7251bb3a13'
assert g['decision']=='GO_STANDALONE_SAFETY_ONLY' and g['terminal'] and g['mode']=='native' and g['manifest_sha256']==MH and g['run_id']==R and g['gui']==m['gui']
assert g['native_queue_free'] and g['executor_mutex_held'] and any('user' in s and ' 1 ' in s and 'Active' in s for s in g['wts'])
assert len(o['independent_suspended_identity'])==2
querypins=[]
qfiles=list((K/'review').glob('query-identity-'+R+'-*.json'));assert len(qfiles)==4
for qp in qfiles:
 q=read(qp);z=q['query'];child=next(c for c in r['Children'] if c['Pid']==q['pid'])
 assert q['site'] in ('Identity','Safety') and q['session']==0 and q['creation_filetime_decimal']==str(child['Creation']) and q['parent_pid']==55396
 assert z['RequestedPid']==z['ReturnedPid']==child['Pid'] and z['Access']==4096 and z['CreationFiletime']==str(child['Creation'])
 assert z['Image']==z['ExpectedImage']==m['exe']['path'] and all(z[k] for k in ('OpenReturned','TimesReturned','ImageReturned','CloseAttempted','ClosedActual'))
 assert q['cim_path_nullable'] is None and q['process_path_nullable'] is None
 querypins.append(tracked(qp))
assert sorted(read(p)['call_ordinal'] for p in qfiles)==[1,2,3,4]
for row,c in zip(o['independent_suspended_identity'],r['Children']):
 assert row['pid']==c['Pid'] and row['creation_filetime']==c['Creation'] and row['observed_before_resume'] and row['path']==m['exe']['path']
trace=K/('review/selected-owner-'+R+'.log');tracked(trace)
assert trace.read_text(encoding='utf-8-sig').splitlines()==r['Events']
ev=r['Events'];assert not any('NO_GO' in e or 'OWNERSHIP_HELD' in e for e in ev)
def event(s):
 ix=[i for i,e in enumerate(ev) if s in e];assert len(ix)==1,(s,ix);return ix[0]
for stage,gens in [('jimport_save',[20,21,22]),('jexport',[28,29,30])]:
 sig=event('ORIGINAL_H_SIGNALED '+stage+' exit=0');assert event('FROZEN_CREATE_SUSPENDED '+stage+' ')<event('IDENTITY_BEFORE_RESUME '+stage+' ')<sig
 for gen in gens:
  h=next(h for h in r['Handles'] if h['Generation']==gen)
  assert sig<event('CLOSED_ACTUAL '+h['Role']+' '+str(gen))<event('ORIGINAL_SEALED 9')
assert event('ORIGINAL_H_SIGNALED jimport_save exit=0')<event('FROZEN_CREATE_SUSPENDED jexport ')
assert event('ORIGINAL_SEALED 9')<event('EXACT_RECOVERY_VERIFIED')<event('RAW_BEHAVIOR_VALIDATOR_RETURNED')
ct=read(K/'contract.json');assert ct['candidate']==m['targets']['native'] or all(ct['candidate'][k]==m['targets']['native'][k] for k in ('run_id','physical_directory','recovered_directory'))
for key in ('method','source','oracle'):exact(ct[key])
method=read(ct['method']['path']);exact(method['planned_source']);exact(method['expected_export'])
binding=read(K/'component-binding-v2.json');assert tracked(K/'component-binding-v2.json')['sha256']==m['component_binding_sha256']
for q in binding['files']:
 rel=pathlib.Path(q['relative_path']);assert not rel.is_absolute() and '..' not in rel.parts
 actual=tracked(K/rel);assert {k:actual[k] for k in ('bytes','sha256')}=={k:q[k] for k in ('bytes','sha256')}
for q in m['sources']:exact(q)
for key in ('exe','python','ssh','git','powershell','compiler','runner_binary','independent_process_query','live_index','live_catalog'):exact(m[key])
expectednames={'export.log','import.log','input.json','jexport-stderr.bin','jexport-stdout.bin','jimport_save-stderr.bin','jimport_save-stdout.bin','model.sxi','roundtrip-raw.json'}
assert len(r['Originals'])==len(r['Recovered'])==9
raw=[]; modelresults=[]
def metadata(a,b,path='root'):
 assert type(a) is type(b),('metadata type',path)
 if isinstance(a,dict):
  assert a.keys()==b.keys(),('keys',path)
  for k in a:metadata(a[k],b[k],path+'/'+k)
 elif isinstance(a,list):
  assert len(a)==len(b),('length',path)
  for i,(x,y) in enumerate(zip(a,b)):metadata(x,y,path+'/'+str(i))
 else:assert a==b,('metadata',path,a,b)
def bits(x):
 assert type(x) in (int,float) and math.isfinite(x);return struct.pack('>d',float(x)).hex()
oracle=read(ct['oracle']['path'])
for side,key in [('Originals','physical_directory'),('Recovered','recovered_directory')]:
 root=pathlib.Path(ct['candidate'][key]);assert {p.name for p in root.iterdir()}==expectednames
 assert {q['Name'] for q in r[side]}==expectednames
 for q in r[side]:
  f=pathlib.Path(q['Path']);assert f==root/q['Name'];p=tracked(f)
  assert p['bytes']==q['Bytes'] and p['sha256']==q['Sha'] and q['Attributes']==33 and f.stat().st_file_attributes==33
  raw.append(p)
 assert (root/'input.json').read_bytes()==pathlib.Path(ct['source']['path']).read_bytes()
 assert (root/'model.sxi').stat().st_size>4
 for n in expectednames:
  if n.endswith('.bin'):assert (root/n).read_bytes()==b''
 actual=read(root/'roundtrip-raw.json');a=copy.deepcopy(actual);e=copy.deepcopy(oracle);cells=0;dtypes={}
 assert len(a['model']['tables'])==len(e['model']['tables'])==31
 for t,u in zip(a['model']['tables'],e['model']['tables']):
  assert len(t['instances'])==len(u['instances'])
  for ins,ref in zip(t['instances'],u['instances']):
   rows=ins.pop('rows');want=ref.pop('rows');assert len(rows)==len(want)
   for row,rr in zip(rows,want):
    assert len(row)==len(rr)==len(u['columns'])
    for x,y,col in zip(row,rr,u['columns']):
     dt=col['datatype'];dtypes[dt]=dtypes.get(dt,0)+1
     if y is None:assert x is None
     elif dt=='double':assert bits(x)==bits(y)
     elif dt=='integer':assert type(x) is type(y) is int and x==y
     elif dt=='string':assert type(x) is type(y) is str and x==y
     else:raise ValueError(dt)
     cells+=1
 metadata(a,e);assert cells==381
 table=next(t for t in actual['model']['tables'] if t['name']=='OperationProfile');cols=[c['name'] for c in table['columns']]
 assert len(table['instances'])==1 and table['instances'][0]['instance_name']=='' and len(table['instances'][0]['rows'])==1
 row=table['instances'][0]['rows'][0];assert [row[cols.index(c)] for c in ('PRID','SPRID','STIM')]==['BASIC-SCHEDULE','BASIC-MISSION',8]
 assert table['columns'][cols.index('DTIM')]['datatype']=='double' and bits(row[cols.index('DTIM')])=='3fbf9add3746f65e'
 logs=[]
 for kind,pathpart,completion in [('import','input.json','Import'),('export','roundtrip-raw.json','Export')]:
  log=root/(kind+'.log');template=K/('source-snapshots/parent-'+kind+'.log');tracked(template)
  lines=log.read_bytes().decode('ascii').splitlines();base=template.read_bytes().decode('ascii').splitlines()
  prefix='Importing data from Json file: ' if kind=='import' else 'Exporting data to Json file: '
  assert len(lines)==len(base) and lines[:-1]==[prefix+str(pathlib.Path(ct['candidate']['physical_directory'])/pathpart),*base[1:-1]]
  assert re.fullmatch(completion+r' completed! Time: (?:0|[1-9][0-9]*)\.[0-9]{2} secs',lines[-1])
  logs.append(dict(kind=kind,physical_lines=len(lines),complete_body_equal=True,only_elapsed_variable=True))
 modelresults.append(dict(side=side,cells=cells,tables=31,instances=sum(len(t['instances']) for t in actual['model']['tables']),datatype_cells=dtypes,all_metadata_exact=True,nulls_exact=True,double_binary64_exact=True,target_binary64='3fbf9add3746f65e',logs=logs))
for a,b in zip(sorted(r['Originals'],key=lambda x:x['Name']),sorted(r['Recovered'],key=lambda x:x['Name'])):
 assert a['Name']==b['Name'] and pathlib.Path(a['Path']).read_bytes()==pathlib.Path(b['Path']).read_bytes()
 assert (a['Volume'],a['Id'])!=(b['Volume'],b['Id'])
assert len({(q['Volume'],q['Id']) for q in r['Originals']+r['Recovered']})==18
author=read(P/'author-k02-v104-native01-fullraw-acceptance-v1.json');assert tracked(P/'author-k02-v104-native01-fullraw-acceptance-v1.json')['sha256']=='2109775fa4035a4d686fe40436ebd94cafed6e77f0fd5b3e6b8b0e551708c376'
for q in pins.values():assert pin(q['path'])==q
decision='GO_BOUNDED_K02_V104_NATIVE01_FULL_ORIGINAL_RAW_EXCHANGE_ACCEPTED'
result=dict(schema='issue18-independent-k02-native01-actual/v1',utc=utc(),terminal=True,completed=True,decision=decision,run_id=R,manifest_sha256=MH,owning_result=tracked(op),transport=tracked(tp/'transport-receipt.json'),guardian=tracked(gp),native_stages=['jimport_save','jexport'],actual_native_calls=2,calc_calls=0,parent_reruns=0,actual_children=r['Children'],complete_typed_models=modelresults,original_recovered_raw=raw,independent_queries=querypins,handles_all99_closed_actual=True,queue_released_actual=True,unknown_child=False,signal_before_writer_close_before_seal_and_recovery=True,bounded_publication_eligible=True,publication_GO=False,publication_eligibility='Eligible for assembly and independent exact staged/publication review for this fixed precision exchange only. No publication, merge, remote/head/tree or whole-K02 acceptance is conferred.',scope='Authored JSON import-save/export preserves full prospective 381 typed cells and DTIM binary64 target; no calculation, model timing/event/RNG, mission behavior, GUI, performance or general JSON/whole variant claim.',historical_failures='v103 sealed failure and probe04/probe05 failures remain immutable and excluded from this successful run; no reruns or retroacceptance.',last_error_qualification='CreateError/ResumeError183 and successful query last-error203 are retained literal observations, not failed BOOL/NT-return classifications.',source_raw_oracle_unchanged=True,review_tool_qualifications=['8542f1 large display truncated; no complete-source claim from display. Independent reader fully parsed complete original/recovered files, event trace, prospective oracle and bindings.'],new_reviewer_failures=[],reviewer_execution=dict(native=0,model=0,SSH=0,Git=0,process_operations=0,mutex_operations=0,old_validator_main=0),whole_issue_complete=False,denominator=None)
ap=save(D/'actual-native-raw-acceptance-v1.json',result)
report='K02 v1.0.4 native01: independent full original raw acceptance\n\nBoth native stages naturally exited 0. All nine original files and nine recovered files match byte-for-byte, are readonly, have distinct recorded file identities and no extras. Both full documents match the prospective oracle: 31 tables, 33 instances, 381 typed cells and exact DTIM binary64 3fbf9add3746f65e. Complete import/export logs match the frozen physical-path templates except elapsed time.\n\nBoth children passed independent retained-query identity before Resume and original-H identity after signal. All 99 owning handles closed, writer closes followed original-H signals, sealing preceded exact recovery and queue-last release completed. No calc, retry, parent rerun or unknown child.\n\nEligible only for assembly and exact staged/publication review of this fixed precision-exchange evidence. Publication/remote/merge binding, whole K02 and whole Issue remain open. v103 and failed probes stay preserved. No simulation, GUI, crossengine or performance acceptance.\n'
with (D/'report.txt').open('x',encoding='utf-8',newline='\n') as f:f.write(report)
terminal=dict(schema='issue18-independent-k02-native01-terminal/v1',utc=utc(),terminal=True,completed=True,decision=decision,run_id=R,manifest_sha256=MH,actual_raw_acceptance=ap,bounded_publication_eligible=True,publication_GO=False,source_pins=list(pins.values()),independent_artifacts=[pin(__file__),ap,pin(D/'report.txt')],source_raw_oracle_unchanged=True,no_execution=result['reviewer_execution'],new_failures=[],qualifications=result['review_tool_qualifications'],remaining_holds=['Independent exact assembled/staged publication review','Exact remote/head/actual commit-and-tree postmerge evidence before publication completion','Whole K02 and Issue completion not inferred from fixed JSON precision exchange','Crossengine UNVERIFIED_SEPARATE_STATUS_NOT_NATIVE_GATE; GUI OUT_NOT_PASS; CI waiver NOT_PASS'],whole_issue_complete=False,denominator=None)
tpin=save(D/'terminal-receipt-v1.json',terminal)
for q in terminal['source_pins']+terminal['independent_artifacts']:assert pin(q['path'])==q
print(json.dumps(dict(terminal=tpin,acceptance=ap,pins_verified=len(pins),publication_eligible=True,publication_GO=False),indent=2))
