"""Exact native roundtrip of every authored populated table."""
from __future__ import annotations
import argparse,json
from pathlib import Path
def populated(path):
 d=json.loads(path.read_text(encoding='utf-8-sig'))
 return {t['name']:{'columns':[(c['name'],c['datatype']) for c in t['columns']],'rows':[row for instance in t['instances'] for row in instance['rows']]} for t in d['model']['tables'] if any(i['rows'] for i in t['instances'])}
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('exported',type=Path);p.add_argument('result',type=Path);a=p.parse_args()
src,native=populated(a.source),populated(a.exported)
bad=[name for name,value in src.items() if native.get(name)!=value]
result={'schema':'simlox-i07-var09-roundtrip/v1.0.1','passed':len(src)==22 and not bad,'authored_populated_tables':len(src),'native_export_populated_tables':len(native),'mismatches':bad}
a.result.write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)