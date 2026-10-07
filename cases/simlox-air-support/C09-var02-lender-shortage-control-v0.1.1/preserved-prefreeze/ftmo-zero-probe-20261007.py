"""Root diagnostic of a prefreeze whole-bin comparator defect; no raw writes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[1]
case = repo / 'cases/simlox-air-support/C09-var02-lender-shortage-control-v0.1.1'
sys.path.insert(0, str(case))
from check_roundtrip import parse
from numeric_bounds import compare
from report_oracle import derive
from validate_native_cli import RUN, output_tables_doc, source_shape

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
expected, edges = derive(log, horizon=12, fleet=3, description=source_shape(), with_edges=True)
actual = output_tables_doc(parse(RUN / 'report-raw.json'))
baseline, count = compare(expected, actual, edges=edges, log=log)
assert not baseline and count == 1754
assert expected['SystemResults'][0]['FTMO'] == 0
mutated = deepcopy(actual)
mutated['SystemResults'][0]['FTMO'] = 1e-9
errors, count = compare(expected, mutated, edges=edges, log=log)
result = {'schema': 'c09-control-v011-root-prefreeze-numeric-probe/v1',
          'contract_sha256': hashlib.sha256((case / 'contract.json').read_bytes()).hexdigest(),
          'numeric_bounds_sha256': hashlib.sha256((case / 'numeric_bounds.py').read_bytes()).hexdigest(),
          'native_calls': 0, 'raw_changed': False, 'cells': count,
          'mutation': 'source-exact SystemResults[0].FTMO 0 to 1e-9',
          'expected': 'reject under frozen contract',
          'actual': 'REJECTED' if errors else 'ESCAPED', 'errors': errors,
          'disposition': 'NO_GO_AUTHOR_IMPLEMENTATION' if not errors else 'PASS_PROBE'}
path = repo / 'tmp/c09-control-v011-ftmo-zero-probe-20261007.json'
assert not path.exists(), 'Preserve original diagnostic; do not overwrite'
path.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps(result))
