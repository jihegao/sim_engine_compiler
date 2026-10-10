import json,copy,re,sys,datetime
from pathlib import Path
O=Path(__file__).resolve().parent

def read(n):return json.loads((O/n).read_bytes())
def strict(a,b,p='$'):
 if type(a)!=type(b):raise ValueError('type '+p)
 if isinstance(a,dict):
  if a.keys()!=b.keys():raise ValueError('keys '+p)
  for k in a:strict(a[k],b[k],p+'.'+k)
 elif isinstance(a,list):
  if len(a)!=len(b):raise ValueError('length '+p)
  for i,(x,y) in enumerate(zip(a,b)):strict(x,y,p+'['+str(i)+']')
 elif a!=b:raise ValueError('value '+p)

def eventledger(raw):
 text=raw.decode('ascii');periods=[]
 for task,start,end in [(1,23.5,24),(3,26.75,27.75)]:
  starts=[];ends=[]
  for line in text.splitlines():
   m=re.match(r'Time: ([0-9.]+)  system turnround task '+str(task)+r' on <TEACH-AIR-01,0> (started|completed)$',line)
   if m:(starts if m[2]=='started' else ends).append(float(m[1]))
  if starts!=[start] or ends!=[end]:raise ValueError('main turnround clock/count')
  periods.append({'task':task,'start':start,'end':end,'duration':end-start,'start_bin':int(start*2)/2})
 for needle in [b'Time: 26.75  subtask 6 seqno 1',b'Time: 26.9167  subtask 6 seqno 1',b'Time: 26.9167  subtask 7 seqno 2',b'Time: 27.75  subtask 7 seqno 2']:
  if needle not in raw:raise ValueError('current/later identities')
 return periods

def validate(raw,report):
 e=read('event-oracle-method-draft.json');r=read('report-oracle-method-draft.json')
 if raw!=bytes.fromhex(e['prospective_raw_log_hex']):raise ValueError('entire ordered eventbytes')
 strict(report,r['full_prospective']);periods=eventledger(raw)
 t=report['report']['tables'][2];c={x['name']:i for i,x in enumerate(t['columns'])};rows=t['instances'][0]['rows']
 integ=lambda k:sum(x[c[k]]*(x[c['ETINT']]-x[c['STINT']]) for x in rows)
 if integ('NSYMT')!=1.5 or integ('NSYMP')!=1 or integ('NSYMO')!=4:raise ValueError('full activity hour ledger')
 if any(x[c['NSYDT']]!=0 or x[c['SYDT']] is not None for x in rows):raise ValueError('invented maintenance downtime')
 if rows[-1][c['NSYRY']]!=1:raise ValueError('terminal not ready')
 return {'physical_lines':len(raw.splitlines()),'typed_cells':4044,'turnround_periods':periods,'turnround_hours':integ('NSYMT'),'preparation_hours':integ('NSYMP'),'flight_hours':integ('NSYMO'),'maintenance_downtime_count':0,'terminal_ready':1}

def controls():
 e=read('event-oracle-method-draft.json');r=read('report-oracle-method-draft.json');raw=bytes.fromhex(e['prospective_raw_log_hex']);report=r['full_prospective'];positive=validate(raw,report);neg=[]
 def rejected(name,l,p):
  try:validate(l,p)
  except ValueError as exc:neg.append({'name':name,'rejected':True,'reason':str(exc)})
  else:raise AssertionError(name)
 for name,bad in [('parent unchanged',bytes.fromhex(e['parent_raw_log_hex'])),('current duration overwritten',raw.replace(b'planned to last for 0.166667 hours',b'planned to last for 0.333333 hours')),('future old duration',raw.replace(b'0.833333 hours',b'0.333333 hours')),('wrong future completion',raw.replace(b'Time: 27.75',b'Time: 27.25')),('earlier mission altered',raw.replace(b'Time: 24.75',b'Time: 24.8'))]:rejected(name,bad,copy.deepcopy(report))
 for name,fn in [('dropped column metadata',lambda p:p['report']['tables'][2]['columns'][0].pop('name')),('stock changed',lambda p:p['report']['tables'][3]['instances'][0]['rows'][0].__setitem__(-1,999)),('int changed float token',lambda p:p['report']['tables'][2]['instances'][0]['rows'][0].__setitem__(2,0.0)),('extra report bin',lambda p:p['report']['tables'][2]['instances'][0]['rows'].append(copy.deepcopy(p['report']['tables'][2]['instances'][0]['rows'][-1])))]:
  p=copy.deepcopy(report);fn(p);rejected(name,raw,p)
 direct=[]
 for name,bad in [('missing maincomplete',raw.replace(b'Time: 27.75  system turnround task 3',b'ignored task3')),('duplicate maincomplete',raw+b'Time: 27.75  system turnround task 3 on <TEACH-AIR-01,0> completed\r\n'),('old mainend',raw.replace(b'Time: 27.75  system turnround task 3',b'Time: 27.25  system turnround task 3'))]:
  try:eventledger(bad)
  except ValueError as exc:direct.append({'name':name,'rejected':True,'reason':str(exc)})
  else:raise AssertionError(name)
 return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'AUTHOR_SYNTHETIC_METHOD_CONTROLS_ONLY','positive':positive,'negatives':neg,'direct_event_ledger_negatives':direct,'native_calls':0,'formal_runID':None}
if __name__=='__main__':
 try:
  if sys.argv[1:]==['--self-check']:
   out=controls();checks={x['name']:x['rejected'] for x in out['negatives']+out['direct_event_ledger_negatives']};result={'decision':'GO_AUTHOR_METHOD_CONTROLS_ONLY','checks':checks,'checks_total':len(checks),'native_calls':0,'details':out}
  else:
   import argparse
   from check_model import parse
   parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=['child'],required=True);parser.add_argument('--model-log',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
   result={'decision':'GO_AUTHOR_RAW_REPLAY','full_typed_report_and_log_passed':True,'arm':'child','details':validate(Path(args.model_log).read_bytes(),parse(args.report))}
 except Exception as exc:
  print(json.dumps({'decision':'NO_GO_AUTHOR','error':type(exc).__name__+': '+str(exc)}));sys.exit(1)
 print(json.dumps(result))
