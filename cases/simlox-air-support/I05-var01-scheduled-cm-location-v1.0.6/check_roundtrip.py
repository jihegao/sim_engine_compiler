"""Validate SIMLOX JSON import/export identity for I05.var01 v1.0.6."""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE_SHA256='57c85c325ed1ed72f96a6ef5b459a568c8d3ff34aab75248dedee2b023d193ed'
DESCRIPTION='D06 position A direct CM with one scheduled CMT update before the first repair'
def sha(path: Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def parse(path: Path)->dict:
    raw=path.read_bytes()
    text=raw.decode('utf-8-sig')
    # Normalize the SIMLOX writer's trailing commas only in this parse copy.
    text=re.sub(r',(?=\s*[}\]])','',text)
    return json.loads(text)
def populated(doc: dict)->dict[str,dict]:
    if not isinstance(doc,dict) or not isinstance(doc.get('model'),dict) or not isinstance(doc['model'].get('tables'),list):
        raise ValueError('model/tables root differs')
    result={}
    for table in doc['model']['tables']:
        name=table.get('name')
        if not isinstance(name,str) or name in result: raise ValueError('table name missing or duplicated')
        columns=table.get('columns'); instances=table.get('instances')
        if not isinstance(columns,list) or not isinstance(instances,list): raise ValueError(f'{name}: columns/instances missing')
        rows=[]
        for inst in instances:
            if not isinstance(inst,dict) or not isinstance(inst.get('rows'),list): raise ValueError(f'{name}: malformed instance')
            rows.extend(inst['rows'])
        for row in rows:
            if not isinstance(row,list) or len(row)!=len(columns): raise ValueError(f'{name}: nonrectangular row')
        if rows: result[name]={'columns':columns,'rows':rows}
    return result
def same_cell(actual,expected,datatype):
    if expected is None: return actual is None
    if datatype=='double':
        return (type(actual) in (int,float) and type(expected) in (int,float)
                and not isinstance(actual,bool) and not isinstance(expected,bool) and float(actual)==float(expected))
    if datatype=='integer': return type(actual) is int and type(expected) is int and actual==expected
    return type(actual) is type(expected) and actual==expected
def same_table(actual,expected,name):
    if actual['columns']!=expected['columns'] or len(actual['rows'])!=len(expected['rows']): return False
    datatypes=[column.get('datatype') for column in expected['columns']]
    if any(not isinstance(t,str) for t in datatypes): return False
    return all(len(a)==len(e) and all(same_cell(x,y,t) for x,y,t in zip(a,e,datatypes,strict=True))
               for a,e in zip(actual['rows'],expected['rows'],strict=True))
def validate(run:Path)->dict:
    issues=[]
    required=['input.json','roundtrip-raw.json','model.sxi','import.log','export.log']
    for name in required:
        p=run/name
        if not p.is_file() or p.stat().st_size<=4: issues.append(f'missing/empty {name}')
    if issues: return {'schema':'simlox-i05-var01-roundtrip/v106','passed':False,'differences':issues}
    if sha(run/'input.json')!=SOURCE_SHA256 or sha(HERE/'native-input.json')!=SOURCE_SHA256:
        issues.append('candidate source/copy byte hash differs')
    source=populated(parse(run/'input.json')); exported=populated(parse(run/'roundtrip-raw.json'))
    for name,table in source.items():
        if name not in exported or not same_table(exported[name],table,name):
            issues.append(f'authored table columns or rows changed/missing: {name}')
    if len(source)!=19: issues.append(f'expected 19 populated authored tables, found {len(source)}')
    if not set(source).issubset(exported): issues.append('one or more authored tables missing after export')
    change=source.get('ChangesCMLocation')
    if not change or [c.get('name') for c in change['columns']]!=['FMID','ID','STID','TIMEC','CMT','CMTD','NOTE']:
        issues.append('ChangesCMLocation columns differ')
    elif len(change['rows'])!=1 or change['rows'][0]!=['FM-POS-A','TEACH-AIR-01','BASE-01',5.0,1.5,None,None]:
        issues.append('ChangesCMLocation authored row differs')
    for filename,marker in [('import.log','Import completed!'),('export.log','Export completed!')]:
        if marker not in (run/filename).read_text(encoding='utf-8-sig',errors='replace'):
            issues.append(f'{filename} completion marker absent')
    return {'schema':'simlox-i05-var01-roundtrip/v106','passed':not issues,'differences':issues,
            'source_sha256':SOURCE_SHA256,'roundtrip_sha256':sha(run/'roundtrip-raw.json'),
            'sxi_sha256':sha(run/'model.sxi'),'authored_populated_tables':sorted(source),
            'native_added_populated_tables':sorted(set(exported)-set(source)),
            'scope':'source-bound JSON import/export identity only','behavior_status':'not_run','publication_state':'not_published'}
def main()->int:
    try: result=validate(Path(sys.argv[1]).resolve())
    except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
        result={'schema':'simlox-i05-var01-roundtrip/v106','passed':False,'differences':[f'{type(exc).__name__}: {exc}'],'publication_state':'not_published'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__': sys.exit(main())
