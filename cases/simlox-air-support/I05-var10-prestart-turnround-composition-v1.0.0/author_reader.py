import json,copy,re,pathlib,datetime,sys
O=pathlib.Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_bytes())
def strict(a,b,p='$'):
 if type(a)!=type(b):raise ValueError('type '+p)
 if isinstance(a,dict):
  if a.keys()!=b.keys():raise ValueError('keys '+p)
  for k in a:strict(a[k],b[k],p+'.'+k)
 elif isinstance(a,list):
  if len(a)!=len(b):raise ValueError('length '+p)
  for i,(x,y)in enumerate(zip(a,b)):strict(x,y,p+'['+str(i)+']')
 elif a!=b:raise ValueError('value '+p)
def ledger(raw):
 lines=raw.decode('ascii').splitlines();periods=[]
 for task,start,end in [(1,23.5,24),(3,26.75,27.75)]:
  starts=[];ends=[]
  for l in lines:
   m=re.fullmatch(r'Time: ([0-9.]+)  system turnround task '+str(task)+r' on <TEACH-AIR-01,0> (started|completed)',l)
   if m:(starts if m[2]=='started'else ends).append(float(m[1]))
  if starts!=[start]or ends!=[end]:raise ValueError('mainledger identities/count/clocks')
  periods.append({'task':task,'start':start,'end':end,'hours':end-start,'start_bin':int(start*2)/2})
 for sid,seq,start,end,duration in [(6,1,26.75,27,0.25),(7,2,27,27.75,0.75)]:
  prefix=f'subtask {sid} seqno {seq} within system turnround task 3 on <TEACH-AIR-01,0>'
  for t,action in [(start,'started'),(start,f'starts performing, planned to last for {duration} hours'),(end,'completed')]:
   if lines.count(f'Time: {t:g}  {prefix} {action}')!=1:raise ValueError('subledger start/duration/end')
 return periods
def validate(raw,report):
 e=read('event-oracle-method-draft.json');r=read('report-oracle-method-draft.json')
 if raw!=bytes.fromhex(e['prospective_raw_log_hex']):raise ValueError('fullordered eventbytes')
 strict(report,r['full_prospective']);periods=ledger(raw);t=report['report']['tables'][2];c={x['name']:i for i,x in enumerate(t['columns'])};rows=t['instances'][0]['rows'];integ=lambda k:sum(z[c[k]]*(z[c['ETINT']]-z[c['STINT']])for z in rows)
 if integ('NSYMT')!=sum(z['hours']for z in periods)or integ('NSYMT')!=1.5:raise ValueError('independent mainactivityledger')
 if integ('NSYMP')!=1 or integ('NSYMO')!=4:raise ValueError('unrelated preparation/missionledger')
 if any(z[c['NSYDT']]!=0 or z[c['SYDT']]is not None for z in rows):raise ValueError('maintenance invented')
 if rows[-1][c['NSYRY']]!=1:raise ValueError('endstate')
 return {'physical_lines':len(raw.splitlines()),'all_recursive_typed_cells':4044,'start_registered_turnround_periods':periods,'hours':1.5,'terminal_ready':1,'native_calls':0}
def controls():
 raw=bytes.fromhex(read('event-oracle-method-draft.json')['prospective_raw_log_hex']);report=read('report-oracle-method-draft.json')['full_prospective'];positive=validate(raw,report);bad=[]
 def neg(n,l,p):
  try:validate(l,p)
  except ValueError as e:bad.append({'name':n,'rejected':True,'reason':str(e)})
  else:raise AssertionError(n)
 for n,l in [('unchangedparent',bytes.fromhex(read('event-oracle-method-draft.json')['parent_raw_log_hex'])),('oldfirstduration',raw.replace(b'last for 0.25 hours',b'last for 0.166667 hours')),('oldlaterduration',raw.replace(b'last for 0.75 hours',b'last for 0.333333 hours')),('wrongstepclock',raw.replace(b'Time: 27  subtask',b'Time: 26.9167  subtask')),('oldmainend',raw.replace(b'Time: 27.75',b'Time: 27.25')),('firstturnroundchanged',raw.replace(b'Time: 24  system turnround',b'Time: 24.5  system turnround')),('missingevent',b'\r\n'.join(raw.split(b'\r\n')[:-2])),('duplicateevent',raw+raw.splitlines(keepends=True)[106])]:neg(n,l,copy.deepcopy(report))
 for n,fn in [('dropcolumnmetadata',lambda p:p['report']['tables'][2]['columns'][0].pop('name')),('stockvalue',lambda p:p['report']['tables'][3]['instances'][0]['rows'][0].__setitem__(-1,999)),('numerictype',lambda p:p['report']['tables'][2]['instances'][0]['rows'][54].__setitem__(9,1.0)),('extrabin',lambda p:p['report']['tables'][2]['instances'][0]['rows'].append(copy.deepcopy(p['report']['tables'][2]['instances'][0]['rows'][-1])))]:
  p=copy.deepcopy(report);fn(p);neg(n,raw,p)
 direct=[]
 for n,l in [('missingmainstart',raw.replace(b'Time: 26.75  system turnround task 3',b'ignoredtask3')),('duplicatemaincomplete',raw+b'Time: 27.75  system turnround task 3 on <TEACH-AIR-01,0> completed\r\n'),('wrongperformingduration',raw.replace(b'last for 0.75 hours',b'last for 0.5 hours'))]:
  try:ledger(l)
  except ValueError as e:direct.append({'name':n,'rejected':True,'reason':str(e)})
  else:raise AssertionError(n)
 return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'SYNTHETIC_AUTHOR_METHOD_CONTROLS_ONLY','positive':positive,'negatives':bad,'directledgernegatives':direct,'formal_runID':None,'native_calls':0}
if __name__=='__main__':
 try:
  if sys.argv[1:]==['--self-check']:
   out=controls();checks={x['name']:x['rejected'] for x in out['negatives']+out['directledgernegatives']};result={'decision':'GO_AUTHOR_METHOD_CONTROLS_ONLY','checks':checks,'checks_total':len(checks),'native_calls':0,'details':out}
  else:
   import argparse
   from check_model import parse
   parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=['child'],required=True);parser.add_argument('--model-log',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
   result={'decision':'GO_AUTHOR_RAW_REPLAY','full_typed_report_and_log_passed':True,'arm':'child','details':validate(pathlib.Path(args.model_log).read_bytes(),parse(args.report))}
 except Exception as exc:
  print(json.dumps({'decision':'NO_GO_AUTHOR','error':type(exc).__name__+': '+str(exc)}));sys.exit(1)
 print(json.dumps(result))
