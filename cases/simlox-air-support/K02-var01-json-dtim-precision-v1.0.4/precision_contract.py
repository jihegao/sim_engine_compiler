"""Pure prospective JSON exchange checker; never starts SIMLOX or writes sources."""
import copy,json,math,struct
TARGET=0.12345678901234567
def strict_json(raw):
 def pairs(items):
  result={}
  for k,v in items:
   if k in result: raise ValueError('duplicate JSON key '+k)
   result[k]=v
  return result
 def invalid(x):raise ValueError('nonfinite JSON constant '+x)
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
def delta(doc):
 d=copy.deepcopy(doc); ts=[t for t in d['model']['tables'] if t['name']=='OperationProfile']; assert len(ts)==1
 t=ts[0];cs=[x['name'] for x in t['columns']];assert t['columns'][cs.index('DTIM')]['datatype']=='double'
 assert len(t['instances'])==1 and t['instances'][0]['instance_name']==''
 rows=t['instances'][0]['rows'];assert len(rows)==1
 row=rows[0]; assert [row[cs.index(k)] for k in ['PRID','SPRID','STIM']]==['BASIC-SCHEDULE','BASIC-MISSION',8]
 assert row[cs.index('DTIM')]==0.3333333333333333
 row[cs.index('DTIM')]=TARGET
 return d
def bits(x):
 if type(x) not in (int,float) or not math.isfinite(x): raise ValueError('not finite numeric cell')
 return struct.pack('>d',float(x)).hex()
def metadata(x,y,path):
 if type(x) is not type(y):raise ValueError('metadata type '+path)
 if isinstance(x,dict):
  if set(x)!=set(y):raise ValueError('metadata keys '+path)
  for k in x: metadata(x[k],y[k],path+'/'+k)
 elif isinstance(x,list):
  if len(x)!=len(y):raise ValueError('metadata length '+path)
  for i,(a,b) in enumerate(zip(x,y)):metadata(a,b,path+'/'+str(i))
 elif x!=y:raise ValueError('metadata value '+path)
def validate(actual,expected):
 a=copy.deepcopy(actual);e=copy.deepcopy(expected);cells=0
 ats=a['model']['tables'];ets=e['model']['tables']
 if len(ats)!=len(ets):raise ValueError('table count')
 for ti,(t,u) in enumerate(zip(ats,ets)):
  if len(t['instances'])!=len(u['instances']):raise ValueError('instance count')
  for ii,(inst,ref) in enumerate(zip(t['instances'],u['instances'])):
   rows=inst.pop('rows');wanted=ref.pop('rows')
   if len(rows)!=len(wanted):raise ValueError('row count')
   for ri,(row,erow) in enumerate(zip(rows,wanted)):
    if len(row)!=len(erow) or len(row)!=len(u['columns']):raise ValueError('column count')
    for ci,(x,y) in enumerate(zip(row,erow)):
     dtype=u['columns'][ci]['datatype'];path=f'{ti}/{ii}/{ri}/{ci}'
     if y is None:
      if x is not None:raise ValueError('null cell '+path)
     elif dtype=='double':
      if bits(x)!=bits(y):raise ValueError('binary64 cell '+path)
     elif dtype=='integer':
      if type(x) is not int or type(y) is not int or x!=y:raise ValueError('integer cell '+path)
     elif dtype=='string':
      if type(x) is not str or type(y) is not str or x!=y:raise ValueError('string cell '+path)
     else:raise ValueError('unsupported datatype '+dtype)
     cells+=1
 metadata(a,e,'root')
 if cells!=381:raise ValueError('full cell count')
 return dict(cells=cells,tables=len(ats),instances=sum(len(t['instances']) for t in ats),target_binary64=bits(TARGET),native_calls=0)
