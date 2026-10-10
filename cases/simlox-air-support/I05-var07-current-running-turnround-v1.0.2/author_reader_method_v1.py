import json,copy,re,hashlib,datetime
from pathlib import Path
O=Path(__file__).resolve().parent

def read(n):return json.loads((O/n).read_bytes())
def strict(a,b,p='$'):
 if type(a)!=type(b):raise ValueError('type '+p)
 if isinstance(a,dict):
  if list(a)!=list(b):raise ValueError('keys/order '+p)
  for k in a:strict(a[k],b[k],p+'.'+k)
 elif isinstance(a,list):
  if len(a)!=len(b):raise ValueError('length '+p)
  for i,(x,y) in enumerate(zip(a,b)):strict(x,y,p+'['+str(i)+']')
 elif a!=b:raise ValueError('value '+p)
def ledger(raw):
 lines=raw.decode('ascii').splitlines();active={};periods=[]
 pattern=re.compile(r'Time: ([0-9.]+)  system (turnround|preparation) task ([0-9]+) on <TEACH-AIR-01,0> (started|completed)')
 for line in lines:
  m=pattern.fullmatch(line)
  if not m:continue
  clock=float(m[1]);key=(m[2],int(m[3]))
  if m[4]=='started':
   if key in active or any((p['kind'],p['task'])==key for p in periods):raise ValueError('duplicate activity start')
   active[key]=clock
  else:
   if key not in active:raise ValueError('completion without registered start')
   start=active.pop(key)
   if clock<=start:raise ValueError('nonpositive activity')
   periods.append({'kind':key[0],'task':key[1],'start':start,'end':clock,'hours':clock-start})
 if active:raise ValueError('unfinished activity at horizon')
 expected=[('preparation',0,20.5,21.0),('turnround',1,23.5,24.5),('preparation',2,24.5,25.0),('turnround',3,27.0,28.5)]
 if [(p['kind'],p['task'],p['start'],p['end']) for p in periods]!=expected:raise ValueError('activity identities/count/order/clocks')
 for task,sub,start,durn in [(1,2,23.5,'1'),(3,5,27.0,'1.5')]:
  line=f'Time: {start:g}  subtask {sub} seqno 0 within system turnround task {task} on <TEACH-AIR-01,0> starts performing, planned to last for {durn} hours'
  if lines.count(line)!=1:raise ValueError('captured duration')
 return periods
def validate(raw,report,model):
 expectedraw=(O/'expected-model-derived.log').read_bytes()
 if raw!=expectedraw:raise ValueError('full ordered115 physical event bytes')
 strict(report,read('expected-report-derived.json'));strict(model,read('expected-roundtrip-derived.json'))
 periods=ledger(raw);tables={t['name']:t for t in report['report']['tables']};sys=tables['SystemResults'];c={x['name']:i for i,x in enumerate(sys['columns'])};rows=sys['instances'][0]['rows']
 if len(rows)!=72 or len(tables['StockTotalResults']['instances'][0]['rows'])!=72:raise ValueError('full72+72 bins')
 integ=lambda key:sum(r[c[key]]*(r[c['ETINT']]-r[c['STINT']]) for r in rows)
 for key,kind,total in [('NSYMT','turnround',2.5),('NSYMP','preparation',1.0)]:
  activity=sum(p['hours'] for p in periods if p['kind']==kind)
  if integ(key)!=activity or activity!=total:raise ValueError('independent start ledger '+key)
 if integ('NSYMO')!=4:raise ValueError('mission ledger')
 if any(r[c['NSYDT']]!=0 or r[c['SYDT']] is not None for r in rows):raise ValueError('turnround is not maintenance')
 if rows[-1][c['NSYRY']]!=1:raise ValueError('terminal ready')
 cells=sum(len(r) for t in report['report']['tables'] for ins in t['instances'] for r in ins['rows'])
 if cells!=4044 or len(model['model']['tables'])!=33:raise ValueError('full report/table counts')
 return {'full_physical_log_lines':115,'full_typed_report_cells':cells,'full_export_tables':33,'system_stock_bins':[72,72],'start_registered_periods':periods,'turnround_hours':2.5,'preparation_hours':1.0,'mission_hours':4.0,'terminal_ready':1,'native_calls':0}
def controls():
 raw=(O/'expected-model-derived.log').read_bytes();report=read('expected-report-derived.json');model=read('expected-roundtrip-derived.json');positive=validate(raw,report,model);bad=[]
 def neg(name,l,p,m):
  try:validate(l,p,m)
  except ValueError as e:bad.append({'name':name,'rejected':True,'reason':str(e)})
  else:raise AssertionError('negative accepted '+name)
 for name,mut in [('runningdurationchanged',raw.replace(b'last for 1 hours',b'last for 1.5 hours',1)),('runningendchanged',raw.replace(b'Time: 24.5  system turnround task 1',b'Time: 25  system turnround task 1')),('laterdurationold',raw.replace(b'last for 1.5 hours',b'last for 1 hours')),('laterendold',raw.replace(b'Time: 28.5',b'Time: 28')),('newchangemarker',raw+b'Time: 23.7  changed\r\n'),('missingevent',b''.join(raw.splitlines(keepends=True)[:-1])),('duplicatedevent',raw+raw.splitlines(keepends=True)[41]),('RNGmessagechanged',raw.replace(b'1e+010',b'1e+009',1))]:neg(name,mut,copy.deepcopy(report),copy.deepcopy(model))
 for name,fn in [('reportmetadata',lambda p:p['report'].pop('tables')),('reporttype',lambda p:p['report']['tables'][2]['instances'][0]['rows'][0].__setitem__(0,'0')),('reportstockvalue',lambda p:p['report']['tables'][3]['instances'][0]['rows'][0].__setitem__(-1,999)),('missingbin',lambda p:p['report']['tables'][2]['instances'][0]['rows'].pop()),('columnmetadata',lambda p:p['report']['tables'][2]['columns'][0].pop('name'))]:
  p=copy.deepcopy(report);fn(p);neg(name,raw,p,copy.deepcopy(model))
 for name,fn in [('missingnativedefaulttable',lambda p:p['model']['tables'].pop(1)),('exportTIMECold',lambda p:next(t for t in p['model']['tables'] if t['name']=='ChangesMissionTurnround')['instances'][0]['rows'][0].__setitem__(3,25.0)),('exportdurationchanged',lambda p:next(t for t in p['model']['tables'] if t['name']=='ChangesMissionTurnround')['instances'][0]['rows'][0].__setitem__(4,2.0)),('exportmetadata',lambda p:p['model']['tables'][0]['columns'][0].pop('name')),('tableorder',lambda p:p['model']['tables'].reverse())]:
  p=copy.deepcopy(model);fn(p);neg(name,raw,copy.deepcopy(report),p)
 direct=[]
 for name,l in [('missingmainstart',raw.replace(b'Time: 23.5  system turnround task 1 on <TEACH-AIR-01,0> started',b'ignored')),('duplicatestart',raw+raw.splitlines(keepends=True)[41]),('missingcomplete',raw.replace(b'Time: 24.5  system turnround task 1 on <TEACH-AIR-01,0> completed',b'ignored')),('wrongduration',raw.replace(b'last for 1.5 hours',b'last for 1 hours'))]:
  try:ledger(l)
  except ValueError as e:direct.append({'name':name,'rejected':True,'reason':str(e)})
  else:raise AssertionError('ledger negative accepted '+name)
 return {'schema':'issue18-var07-current-main-author-method-controls/v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'GO_AUTHOR_METHOD_CONTROLS_ONLY','positive':positive,'full_comparator_negatives':bad,'direct_start_ledger_negatives':direct,'checks_total':len(bad)+len(direct),'formal_version':None,'new_runID':None,'native_calls':0,'not_simulation_conformance':True}
if __name__=='__main__':print(json.dumps(controls(),indent=2))
