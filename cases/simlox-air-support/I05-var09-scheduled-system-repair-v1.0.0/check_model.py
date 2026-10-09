"""Restricted authored-input and roundtrip contract. No simulation or native calls."""
import copy,json,hashlib,math,pathlib,sys
HERE=pathlib.Path(__file__).resolve().parent
CONTRACT=json.loads((HERE/'contract.json').read_bytes())
PINS=json.loads((HERE/'parent-evidence-pins.json').read_bytes())
from author_reader import typed_structure_equal,remove_exporter_trailing_commas

def expected():
 p=PINS['d01_source'];raw=pathlib.Path(p['path']).read_bytes()
 if len(raw)!=p['bytes'] or hashlib.sha256(raw).hexdigest()!=p['sha256']:raise ValueError('parent source pin differs')
 d=json.loads(raw)
 for t in d['model']['tables']:
  if t['name']=='ProblemDescription':t['instances'][0]['rows'][0][0]=CONTRACT['candidate']['description']
 d['model']['tables'].append(CONTRACT['delta']['table'])
 return d

def authored(doc):
 if not isinstance(doc,dict) or not isinstance(doc.get('model'),dict):raise ValueError('invalid model root')
 tables=doc['model'].get('tables');out={};seen=set()
 if not isinstance(tables,list):raise ValueError('missing tables')
 for t in tables:
  name=t.get('name')
  if type(name) is not str or name in seen:raise ValueError('missing or duplicated table')
  seen.add(name);cols=t['columns'];instances=t['instances'];rows=[]
  if not isinstance(cols,list) or not isinstance(instances,list):raise ValueError('invalid table topology')
  names=[c['name'] for c in cols]
  if len(set(names))!=len(names):raise ValueError('duplicate column')
  for inst in instances:
   if inst.get('instance_name')!='' or type(inst.get('rows')) is not list:raise ValueError('unsupported instance')
   for row in inst['rows']:
    if type(row) is not list or len(row)!=len(cols):raise ValueError('wrong row width')
    for cell,col in zip(row,cols,strict=True):
     if cell is None:continue
     datatype=col['datatype']
     if datatype=='double':
      if type(cell) not in (int,float) or not math.isfinite(cell):raise ValueError('invalid finite double')
     elif datatype=='integer':
      if type(cell) is not int:raise ValueError('invalid integer')
     elif datatype=='string':
      if type(cell) is not str:raise ValueError('invalid string')
     else:raise ValueError('unsupported datatype')
    rows.append(row)
  if rows:out[name]={'columns':cols,'rows':rows}
 return out

def validate_source(doc):
 authored(doc)
 if not typed_structure_equal(doc,expected()):raise ValueError('outside exact restricted profile; unknown/missing/different field or unsupported behavior')
 if len(authored(doc))!=15:raise ValueError('row-bearing count differs')
 return True

def check_export(source,exported):
 validate_source(source);a=authored(source);b=authored(exported)
 if not set(a).issubset(b):raise ValueError('authored table missing')
 for name,t in a.items():
  u=b[name]
  if not typed_structure_equal(t['columns'],u['columns']) or len(t['rows'])!=len(u['rows']):raise ValueError('columns/rows differ: '+name)
  for x,y in zip(t['rows'],u['rows'],strict=True):
   for orig,actual,col in zip(x,y,t['columns'],strict=True):
    if col['datatype']=='double' and orig is not None:
     if type(actual) not in (int,float) or not math.isfinite(actual) or actual!=orig:raise ValueError('numeric cell differs: '+name)
    elif not typed_structure_equal(actual,orig):raise ValueError('typed cell differs: '+name)
 return {'row_bearing_authored_tables':len(a),'native_added_row_bearing_tables':sorted(set(b)-set(a)),'double_token_normalization':'finite int/float only on declared model double columns; report remains strictly typed'}

def self_check():
 base=expected();checks={'exact_source_positive':validate_source(base),'synthetic_export_positive':bool(check_export(base,copy.deepcopy(base)))}
 def mutate(name,fn):
  d=copy.deepcopy(base);fn(d)
  try:validate_source(d)
  except (ValueError,KeyError,TypeError):checks[name]=True
  else:checks[name]=False
 def row(d):return next(t for t in d['model']['tables'] if t['name']=='ChangesSystemRepair')['instances'][0]['rows'][0]
 for name,index,val in [('missing_target',0,'NO-SYSTEM'),('group_target',1,'GROUP-X'),('nonpositive_time',2,0),('bool_time',2,True),('nonfinite_time',2,float('nan')),('fraction_change',5,0.5),('distribution_change',7,'DIST-X'),('inprogress_time',2,10.1),('changed_duration',3,2.0)]:mutate(name,lambda d,i=index,v=val:row(d).__setitem__(i,v))
 mutate('duplicate_change_key',lambda d:d['model']['tables'][-1]['instances'][0]['rows'].append(copy.deepcopy(row(d))))
 mutate('missing_column',lambda d:d['model']['tables'][-1]['columns'].pop())
 mutate('unknown_table',lambda d:d['model']['tables'].append({'name':'Unknown','columns':[],'instances':[]}))
 mutate('parent_rule_drift',lambda d:next(t for t in d['model']['tables'] if t['name']=='SystemRepair')['instances'][0]['rows'][0].__setitem__(2,9))
 quoted=b'{"x":"literal ,] and ,}","a":[1,],}'
 checks['normalizer_preserves_quoted_commas']=json.loads(remove_exporter_trailing_commas(quoted))=={'x':'literal ,] and ,}','a':[1]}
 if not all(checks.values()):raise AssertionError(checks)
 return {'decision':'GO_AUTHOR_MODEL_CONTROLS_ONLY','checks':checks,'checks_total':len(checks),'native_calls':0}

def main():
 if sys.argv[1:]==['--self-check']:return self_check()
 if len(sys.argv)!=2:raise ValueError('requires --self-check or native run directory')
 r=pathlib.Path(sys.argv[1]);source=json.loads((r/'input.json').read_bytes())
 if (r/'input.json').read_bytes()!=(HERE/'native-input.json').read_bytes():raise ValueError('source/copy byte mismatch')
 for name,marker in [('import.log','Import completed!'),('export.log','Export completed!')]:
  if marker not in (r/name).read_text(encoding='utf-8-sig'):raise ValueError('missing completion marker')
 if (r/'model.sxi').stat().st_size<=4:raise ValueError('empty native input')
 out=check_export(source,json.loads(remove_exporter_trailing_commas((r/'roundtrip-raw.json').read_bytes())))
 return {'passed':True,'scope':'source-bound import/export only; not behavior acceptance',**out}
if __name__=='__main__':
 try:print(json.dumps(main(),sort_keys=True))
 except (ValueError,OSError,KeyError,TypeError,IndexError,AssertionError) as exc:print(json.dumps({'passed':False,'error':str(exc)}));sys.exit(1)