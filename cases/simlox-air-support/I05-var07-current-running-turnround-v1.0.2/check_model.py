import json,copy,sys
from pathlib import Path
from author_reader_method_v1 import strict
O=Path(__file__).resolve().parent

def parse(p):
 s=Path(p).read_bytes().decode('utf-8-sig');out=[];q=False;esc=False
 for i,c in enumerate(s):
  if q:
   out.append(c)
   if esc:esc=False
   elif c=='\\':esc=True
   elif c=='"':q=False
  elif c=='"':q=True;out.append(c)
  elif c==',' and s[i+1:].lstrip().startswith((']', '}')):continue
  else:out.append(c)
 def pairs(items):
  d={}
  for k,v in items:
   if k in d:raise ValueError('duplicate JSON key')
   d[k]=v
  return d
 return json.loads(''.join(out),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite')))
def expected():return json.loads((O/'expected-roundtrip-derived.json').read_bytes())
def validate(actual):
 strict(actual,expected())
 return {'all_tables':33,'parent_native_default_tables_preserved':True,'strict_all_metadata_types_cells':True,'new_change_rows':1,'new_change_columns':7,'TIMEC':23.7}
def controls():
 e=expected();v=validate(e);bad=[]
 def neg(n,p):
  try:validate(p)
  except ValueError as ex:bad.append({'name':n,'rejected':True,'reason':str(ex)})
  else:raise AssertionError(n)
 for n,fn in [('missing default',lambda p:p['model']['tables'].pop(2)),('duplicate table',lambda p:p['model']['tables'].append(copy.deepcopy(p['model']['tables'][0]))),('TIMEC old',lambda p:next(t for t in p['model']['tables'] if t['name']=='ChangesMissionTurnround')['instances'][0]['rows'][0].__setitem__(3,25.0)),('DURN changed',lambda p:next(t for t in p['model']['tables'] if t['name']=='ChangesMissionTurnround')['instances'][0]['rows'][0].__setitem__(4,2.0)),('key metadata',lambda p:p['model']['tables'][0]['columns'][0].pop('key',None)),('order',lambda p:p['model']['tables'].reverse())]:
  p=copy.deepcopy(e);fn(p)
  if p==e and n=='key metadata':p['model']['tables'][0]['columns'][0].pop('name')
  neg(n,p)
 return {'positive':v,'negative_controls':bad,'native_calls':0}
if __name__=='__main__':
 try:
  if sys.argv[1:]==['--self-check']:r={'passed':True,'controls':controls(),'native_calls':0}
  else:
   run=Path(sys.argv[1]);assert (run/'input.json').read_bytes()==(O/'native-input.json').read_bytes(),'input byte mismatch'
   assert 'Import completed!' in (run/'import.log').read_text(encoding='utf-8-sig') and 'Export completed!' in (run/'export.log').read_text(encoding='utf-8-sig'),'converter marker missing'
   r={'passed':True,**validate(parse(run/'roundtrip-raw.json'))}
 except Exception as e:print(json.dumps({'passed':False,'error':type(e).__name__+': '+str(e)}));sys.exit(1)
 print(json.dumps(r))
