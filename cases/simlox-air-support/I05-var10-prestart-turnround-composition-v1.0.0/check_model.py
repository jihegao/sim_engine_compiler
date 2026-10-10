import json,copy,hashlib,datetime,sys
from pathlib import Path
O=Path(__file__).resolve().parent
P=Path(r'C:/Users/user/Documents/Codex/2026-09-29/simlox-c04-deadline/repo/cases/simlox-air-support/B04-var05-turnround-breakdown-v0.1.0/runs/b04-var05-turnbreak-v010-ssh-20261006-01')
def parse(path):
 text=Path(path).read_bytes().decode('utf-8-sig');out=[];quoted=False;escaped=False
 for i,ch in enumerate(text):
  if quoted:
   out.append(ch)
   if escaped:escaped=False
   elif ch=='\\':escaped=True
   elif ch=='"':quoted=False
  elif ch=='"':quoted=True;out.append(ch)
  elif ch==',' and text[i+1:].lstrip().startswith((']', '}')):continue
  else:out.append(ch)
 return json.loads(''.join(out))
def strict(a,b):
 if type(a)!=type(b):raise ValueError('numeric/container type changed')
 if isinstance(a,dict):
  if a.keys()!=b.keys():raise ValueError('metadata keys changed')
  for k in a:strict(a[k],b[k])
 elif isinstance(a,list):
  if len(a)!=len(b):raise ValueError('list length changed')
  for x,y in zip(a,b):strict(x,y)
 elif a!=b:raise ValueError('exact value changed')
def expected():
 parent=parse(P/'roundtrip-raw.json');candidate=parse(O/'native-input.json');by={t['name']:t for t in candidate['model']['tables']}
 out=copy.deepcopy(parent)
 for t in out['model']['tables']:
  if t['name']=='ProblemDescription':t['instances'][0]['rows'][0][0]=by['ProblemDescription']['instances'][0]['rows'][0][0]
 out['model']['tables'].append(copy.deepcopy(by['ChangesTaskBreakDown']))
 return out

def validate(actual):
 e=expected();a=copy.deepcopy(actual);et=e['model'].pop('tables');at=a['model'].pop('tables');strict(a,e)
 if len(at)!=len(et):raise ValueError('must preserve every nativeparent table plusnew1')
 names=[t['name'] for t in at];en=[t['name'] for t in et]
 if len(set(names))!=len(et) or set(names)!=set(en):raise ValueError('missing/duplicate/extra table')
 if [n for n in names if n!='ChangesTaskBreakDown']!=en[:-1]:raise ValueError('parent relative table order changed')
 by={t['name']:t for t in at}
 for t in et:strict(by[t['name']],t)
 return {'all_tables':len(et),'parent_native_default_tables_preserved':True,'new_change_rows':2,'new_change_columns':6,'new_table_insertion_position':'unobserved allowed; parent relative order exact','strict_all_metadata_types_cells':True}

def controls():
 e=expected();positive=validate(e);tests=[]
 def neg(name,p):
  try:validate(p)
  except ValueError as exc:tests.append({'name':name,'rejected':True,'reason':str(exc)})
  else:raise AssertionError('negative accepted '+name)
 for name,fn in [('missing native default',lambda p:p['model']['tables'].pop(2)),('extra table',lambda p:p['model']['tables'].append(copy.deepcopy(p['model']['tables'][0]))),('missing change row',lambda p:p['model']['tables'][-1]['instances'][0]['rows'].pop()),('change TID invalid',lambda p:p['model']['tables'][-1]['instances'][0]['rows'][0].__setitem__(0,'UNKNOWN')),('change duration altered',lambda p:p['model']['tables'][-1]['instances'][0]['rows'][1].__setitem__(3,1.5)),('key metadata dropped',lambda p:p['model']['tables'][-1]['columns'][0].pop('key')),('native numeric type changed',lambda p:p['model']['tables'][-1]['instances'][0]['rows'][0].__setitem__(1,1.0))]:
  p=copy.deepcopy(e);fn(p);neg(name,p)
 p=copy.deepcopy(e);p['model']['tables'][0],p['model']['tables'][1]=p['model']['tables'][1],p['model']['tables'][0];neg('parent table order',p)
 return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'SYNTHETIC_MODEL_CHECKER_ONLY','native_calls':0,'unobserved_export_precision':True,'positive':positive,'negatives':tests}
if __name__=='__main__':
 try:
  if sys.argv[1:]==['--self-check']:result={'passed':True,'native_calls':0,'controls':controls()}
  else:
   run=Path(sys.argv[1]);source=(O/'native-input.json').read_bytes()
   if (run/'input.json').read_bytes()!=source:raise ValueError('copied input differs')
   if 'Import completed!' not in (run/'import.log').read_text(encoding='utf-8-sig') or 'Export completed!' not in (run/'export.log').read_text(encoding='utf-8-sig'):raise ValueError('import/export markers missing')
   result={'passed':True,**validate(parse(run/'roundtrip-raw.json'))}
 except Exception as exc:
  print(json.dumps({'passed':False,'error':type(exc).__name__+': '+str(exc)}));sys.exit(1)
 print(json.dumps(result))
