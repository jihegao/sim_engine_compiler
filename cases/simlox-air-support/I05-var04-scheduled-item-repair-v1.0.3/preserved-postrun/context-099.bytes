"""Independent I05.var04 v103 source, prospective behavior, and custody reader.

No author or accepted-checker imports. No native, SSH, or Git mutation.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

METHOD = Path(__file__).resolve()
if METHOD.parent.name == 'tmp':
    REPO = METHOD.parent.parent
    CASE = REPO / 'cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.3'
elif METHOD.parent.name == 'review' and METHOD.parent.parent.name == 'I05-var04-scheduled-item-repair-v1.0.3':
    CASE = METHOD.parent.parent
    REPO = CASE.parents[2]
else:
    raise AssertionError('independent reader outside approved tmp or case review path')

RUN_ID = 'i05-var04-item-repair-v103-ssh-20261009-01'
RUN = REPO / 'tmp/i05-var04-native-v103-20261009-01'
RECOVERED = CASE / 'runs' / RUN_ID
PARENT = REPO / 'cases/simlox-air-support/E05-local-repair-reissue-v1.0.0'
PARENT_RUN = PARENT / 'runs/e05-v100-ssh-20260929-01'
BASE = '7998e59944a8e061db2b48041349602039f4dc10'
CONTRACT_SHA = '012f9873ec0c62ab55314641213ffa9283b7eb8237df9b0d9d65564bea11d8f3'
EXPORT_ORDER_SHA = 'bab7315e63c301eccd7e004d9946d2b4db291279f3d65ec65a3c4cd4e3fca7b7'
BUSINESS_CONTRACT_SHA = '8bc2b9e7f579bfcfd75c025a9d7ac74ba385a09f70b744771d7937513d41eaf9'
INPUT_SHA = 'f4157f818f9f7c00a18b01074fcde9d52ed81baa8f4d92d8e3c323f2bf2545c2'
PATTERN_SHA = '5cf823b0a1719a09e632fca16cbd6f1cc0798751dbe72e8ad29e25fb24cb7de3'
REPORT_RULES_SHA = '84661b8f0675f91226d86623588d8c46011a7b81f05a8276666f2778b711436b'
PARENT_INPUT_SHA = 'ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca'
PARENT_EXPORT_SHA = '896387a14791dd6f14ceec9acf6398beca981656fc0656019e7849df2af79b21'
PARENT_LOG_SHA = '3ed9e6a5fc2d66dd8eb5fa4f111bc3baa127dfbfc40aadac639ed55e7f8701f8'
PARENT_CONVERTER_SHA = '922d6c97cc6f45cca7f1a8a5eadd6254bf4e542b8f032c1a5273c8bd4d7f6f43'
SELECTION_SHA = '57d53ce82f61d7408c33ab9380e6b5cf4921e93846bb470d7b3fd61b19004b25'
EXE = r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
PYTHON = r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
TOOLS = ['build.py','source_gate.py','self_check.py','make_source_inventory.py','make_prelaunch_manifest.py']
STAGES = ['import','export','check_import_export','calc','jsonreport','check_behavior']
SPECIAL = {}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': sha(data)}


def exact(path: Path, spec: dict, readonly: bool = False) -> bytes:
    assert type(spec) is dict and set(spec) == {'bytes','sha256'}
    assert type(spec['bytes']) is int and spec['bytes'] >= 0
    assert type(spec['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',spec['sha256'])
    data = path.read_bytes()
    assert {'bytes': len(data), 'sha256': sha(data)} == spec, str(path)
    if readonly:
        assert not path.is_symlink() and not (path.stat().st_file_attributes & 0x400), str(path)
        assert path.stat().st_file_attributes & 1, str(path)
    return data


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        assert key not in obj, key
        obj[key] = value
    return obj


def reject_constant(value):
    raise AssertionError(('nonfinite JSON token', value))


def strict_json(data: bytes, *, allow_bom: bool = False):
    if allow_bom and data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    else:
        assert not data.startswith(b'\xef\xbb\xbf')
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)


def accepted_powershell_receipt_json(data:bytes):
    """Require one BOM on the two byte-pinned historical E05 PS receipts."""
    assert data.startswith(b'\xef\xbb\xbf') and not data.startswith(b'\xef\xbb\xbf\xef\xbb\xbf')
    return strict_json(data[3:])


def keys(value, wanted):
    assert type(value) is dict and set(value) == set(wanted), (set(value) ^ set(wanted))


def integer(value, wanted):
    assert type(value) is int and value == wanted, (value, wanted)


def boolean(value, wanted):
    assert type(value) is bool and value is wanted


def absolute(value):
    assert type(value) is str
    path = Path(value)
    assert path.is_absolute() and '..' not in path.parts
    return path


def utc(value):
    assert type(value) is str
    moment = datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    assert moment.tzinfo is not None and moment.utcoffset() == datetime.timedelta(0)
    return moment


def typed(expected, actual, datatype=None, tolerance=0.0):
    if expected is None or actual is None:
        return expected is None and actual is None
    if datatype == 'integer':
        return type(expected) is type(actual) is int and expected == actual
    if datatype == 'double':
        return (type(expected) in (int,float) and type(actual) in (int,float)
                and math.isfinite(expected) and math.isfinite(actual)
                and abs(expected-actual) <= tolerance)
    if datatype == 'string':
        return type(expected) is type(actual) is str and expected == actual
    if type(expected) is not type(actual):
        return False
    if type(expected) is dict:
        return set(expected) == set(actual) and all(typed(expected[k],actual[k]) for k in expected)
    if type(expected) is list:
        return len(expected) == len(actual) and all(typed(a,b) for a,b in zip(expected,actual,strict=True))
    return expected == actual


def compare_tables(expected, actual, tolerance=0.0):
    assert type(expected) is type(actual) is list and len(expected) == len(actual)
    rows = cells = 0
    for et, at in zip(expected, actual, strict=True):
        keys(et, {'name','columns','instances'}); keys(at, {'name','columns','instances'})
        assert et['name'] == at['name'] and type(et['name']) is str
        ec, ac = et['columns'], at['columns']
        assert type(ec) is type(ac) is list and len(ec) == len(ac)
        for x,y in zip(ec,ac,strict=True):
            assert type(x) is type(y) is dict and set(x) == set(y)
            assert set(x) in ({'name','datatype'}, {'name','datatype','key'})
            assert type(x['name']) is type(y['name']) is str
            assert type(x['datatype']) is type(y['datatype']) is str
            if 'key' in x:
                assert type(x['key']) is type(y['key']) is bool
            assert typed(x,y)
        ei, ai = et['instances'], at['instances']
        assert type(ei) is type(ai) is list and len(ei) == len(ai)
        for x,y in zip(ei,ai,strict=True):
            keys(x, {'instance_name','rows'}); keys(y, {'instance_name','rows'})
            assert typed(x['instance_name'],y['instance_name'])
            xr, yr = x['rows'], y['rows']
            assert type(xr) is type(yr) is list and len(xr) == len(yr)
            for a,b in zip(xr,yr,strict=True):
                assert type(a) is type(b) is list and len(a) == len(b) == len(ec)
                rows += 1
                for col, ev, av in zip(ec,a,b,strict=True):
                    assert typed(ev,av,col['datatype'],tolerance), (et['name'],col['name'],ev,av)
                    cells += 1
    return len(expected), rows, cells


NUMBER = r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e\+[0-9]+)?"
TOKEN = re.compile(r"\{([A-Za-z0-9_.]+)\}")


def exact_json(data: bytes):
    assert not data.startswith(b"\xef\xbb\xbf")
    def pairs(items):
        answer = {}
        for name, value in items:
            assert name not in answer, name
            answer[name] = value
        return answer
    def reject(word):
        raise AssertionError(("nonfinite JSON", word))
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject)


def exact_type(left, right) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(exact_type(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(exact_type(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def interval(word: str) -> tuple[float, float]:
    """The closed rounding interval implied by one displayed decimal token."""
    assert re.fullmatch(NUMBER, word), word
    center = float(word)
    assert math.isfinite(center)
    if "e+" in word:
        mantissa, exponent = word.split("e+", 1)
        unit = 10.0 ** (int(exponent) - len(mantissa.partition(".")[2]))
    else:
        unit = 10.0 ** -len(word.partition(".")[2])
    return center - unit / 2, center + unit / 2


def intersects(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return max(a[0], b[0]) <= min(a[1], b[1])


def shifted(a: tuple[float, float], delta: float) -> tuple[float, float]:
    return a[0] + delta, a[1] + delta


def parent_control_catalog(catalog: dict) -> dict:
    """Derive the accepted E05 duration literals without changing the child oracle."""
    assert type(catalog) is dict and catalog['schema']=='i05-var04-log-patterns/v101'
    lines=catalog['lines']
    assert type(lines) is list and len(lines)==222
    parent=copy.deepcopy(catalog)
    old='planned to last for 1.5 hours'
    new='planned to last for 1 hours'
    positions={66,137,209}
    for number in sorted(positions):
        source=lines[number-1]
        target=parent['lines'][number-1]
        assert source['line']==number and type(source['template']) is str
        assert source['template'].count(old)==1 and new not in source['template']
        target['template']=source['template'].replace(old,new)
    for number,(source,target) in enumerate(zip(lines,parent['lines'],strict=True),1):
        if number in positions:
            assert source.keys()==target.keys()
            for key in source:
                if key!='template':
                    assert typed(source[key],target[key])
        else:
            assert typed(source,target)
    return parent


def read_log(raw: bytes, catalog: dict, *, child: bool = True) -> dict:
    assert type(catalog) is dict and catalog['schema']=='i05-var04-log-patterns/v101'
    if not child:
        catalog=parent_control_catalog(catalog)
    assert not raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\r\n")
    assert raw.count(b"\r\n") == raw.count(b"\n") == 222
    physical = raw[:-2].decode("ascii").split("\r\n")
    assert len(physical) == 222
    assert catalog["physical_lines"] == 222 and catalog["timed_lines"] == 186
    assert type(catalog["lines"]) is list and len(catalog["lines"]) == 222
    bindings: dict[str, str] = {}
    last_time = -math.inf
    timed = 0
    for n, (line, rule) in enumerate(zip(physical, catalog["lines"], strict=True), 1):
        assert rule["line"] == n and type(rule["timed"]) is bool
        assert rule["timed"] == line.startswith("Time: ")
        if rule["timed"]:
            hit_time = re.match(r"Time: (" + NUMBER + r")\b", line)
            assert hit_time is not None, n
            observed = float(hit_time.group(1))
            assert math.isfinite(observed) and observed >= last_time, n
            last_time = observed
            timed += 1
        fragments: list[str] = []
        names: list[str] = []
        cursor = 0
        for token in TOKEN.finditer(rule["template"]):
            fragments.extend((re.escape(rule["template"][cursor:token.start()]), "(" + NUMBER + ")"))
            names.append(token.group(1))
            cursor = token.end()
        fragments.append(re.escape(rule["template"][cursor:]))
        match = re.fullmatch("".join(fragments), line)
        assert match is not None, (n, line)
        assert names == [b["symbol"] for b in rule["bindings"]], n
        for name, word in zip(names, match.groups(), strict=True):
            assert math.isfinite(float(word))
            if name in bindings:
                assert bindings[name] == word, (name, n)
            else:
                bindings[name] = word
    assert timed == 186 and len(bindings) == 24
    first = {"failure": "9.25527", "arrival": "9.75527", "item_start": "9.92193",
             "system_ready": "10.2553", "restock": "11.4219" if child else "10.9219"}
    assert all(bindings["cycle0." + name] == word for name, word in first.items())
    for cycle, mission_start in enumerate((8, 20, 32)):
        prefix = f"cycle{cycle}."
        failure = interval(bindings[prefix + "failure"])
        arrival = interval(bindings[prefix + "arrival"])
        start = interval(bindings[prefix + "item_start"])
        ready = interval(bindings[prefix + "system_ready"])
        returned = interval(bindings[prefix + "restock"])
        assert mission_start < failure[0] <= failure[1] < mission_start + 2
        if cycle == 1:
            assert failure[0] >= 21.5 and failure[1] < 22
            assert bindings[prefix + "arrival"] == "22"
            assert bindings[prefix + "system_ready"] == "22.5"
        if cycle == 2:
            assert failure[0] >= 32.5 and failure[1] < 33.5
        cap = (mission_start + 2, mission_start + 2)
        return_window = shifted(failure, .5) if failure[0] + .5 < mission_start + 2 else cap
        assert intersects(arrival, return_window), cycle
        arrival_for_math = cap if cycle == 1 else arrival
        assert intersects(start, shifted(arrival_for_math, 1/6)), cycle
        assert intersects(ready, shifted(arrival_for_math, .5)), cycle
        assert intersects(returned, shifted(start, 1.5 if child else 1.0)), cycle
        ready_for_math = (22.5, 22.5) if cycle == 1 else ready
        assert arrival_for_math[1] < start[1] < ready_for_math[1] < returned[1] < 36
        for kind in ("failure_complexity", "repair_complexity"):
            value = float(bindings[prefix + kind])
            assert 0 <= value <= 1
        assert float(bindings[prefix + "followup_clock"]) > float(bindings[prefix + "failure"])
        if cycle:
            assert interval(bindings[f"cycle{cycle-1}.restock"])[1] < arrival[0]
    return {"words": bindings, "child": child, "capped_second_return": True,
            "physical_lines": 222, "timed_lines": 186}


def bounds(point: str | int | float, observed: dict) -> tuple[float, float]:
    if type(point) in (int, float):
        return float(point), float(point)
    if point in ("cycle1.arrival", "cycle1.system_ready"):
        assert observed["capped_second_return"]
        word = observed["words"][point]
        assert word == ("22" if point.endswith("arrival") else "22.5")
        exact = 22.0 if point.endswith("arrival") else 22.5
        return exact, exact
    return interval(observed["words"][point])


def time_bin(point: str, observed: dict) -> int:
    low, high = bounds(point, observed)
    left, right = math.floor(2 * low), math.floor(2 * high)
    assert left == right and 0 <= left < 72, (point, low, high)
    return left


def occupancy(index: int, spans: list[tuple[object, object]], observed: dict) -> tuple[float, float]:
    left, right = index / 2, (index + 1) / 2
    lower = upper = 0.0
    for a, b in spans:
        a_lo, a_hi = bounds(a, observed)
        b_lo, b_hi = bounds(b, observed)
        lower += max(0.0, min(right, b_lo) - max(left, a_hi))
        upper += max(0.0, min(right, b_hi) - max(left, a_lo))
    return 2 * lower, 2 * upper


def float32_step(number: float) -> float:
    bits = struct.unpack("<I", struct.pack("<f", abs(number)))[0]
    this = struct.unpack("<f", struct.pack("<I", bits))[0]
    next_ = struct.unpack("<f", struct.pack("<I", bits + 1))[0]
    return next_ - this


def numeric(low: float, high: float) -> tuple:
    assert math.isfinite(low) and math.isfinite(high) and low <= high
    if low == high and low in (0.0, .5, 1.0, 36.0):
        return "exact_double", low, high
    pad = 2 * float32_step(max(abs(low), abs(high)))
    return "bounded_double", low - pad, high + pad


def expected_cell(table: str, index: int, column: str, observed: dict) -> tuple:
    cycles = range(3)
    if table == "ProblemDescription":
        assert index == 0 and column == "PDESC"
        return "string", "E05 local LRU repair, stock return and second issue"
    if table == "ResultSummary":
        assert index == 0
        if column == "NREP": return "integer", 1
        if column == "RTIUP": return numeric(36.0, 36.0)
        if column in ("MTMF", "STMF"):
            arrivals = [bounds(f"cycle{j}.arrival", observed) for j in cycles]
            starts = (8, 20, 32)
            return numeric(sum(a[0]-s for a,s in zip(arrivals, starts))/6,
                           sum(a[1]-s for a,s in zip(arrivals, starts))/6)
        if column == "MSTF": return numeric(1.0, 1.0)
        assert column in ("RTILW", "RSMTMF", "RSMSTF", "MSUF", "RSMSUF", "RSSTMF")
        return numeric(0.0, 0.0)
    if table == "SystemResults":
        assert 0 <= index < 72
        if column == "UNID": return "string", "Total over all Units"
        if column == "SID": return "string", "Total over all Systems"
        if column == "STINT": return numeric(index / 2, index / 2)
        if column == "ETINT": return numeric((index + 1) / 2, (index + 1) / 2)
        launched = [(s, f"cycle{j}.arrival") for j,s in enumerate((8,20,32))]
        mobilized = [(s, f"cycle{j}.arrival") for j,s in enumerate((7,19,31))]
        preparation = [(s,s+1) for s in (7,19,31)]
        unavailable = [(f"cycle{j}.arrival",f"cycle{j}.system_ready") for j in cycles]
        ready = [(0,7), ("cycle0.system_ready",19), ("cycle1.system_ready",31), ("cycle2.system_ready",36)]
        windows = {"NSYRY":ready,"NSYMA":mobilized,"NSYMO":launched,"NSYMR":preparation,
                   "NSYUA":unavailable,"FTMO":launched,"NSYRP":unavailable,"STACC":launched}
        if column in windows: return numeric(*occupancy(index, windows[column], observed))
        if column == "NSYA":
            low, high = occupancy(index, unavailable, observed)
            return numeric(1-high,1-low)
        if column in ("NFAIL","NREPT","NSYDT","SYDT"):
            suffix = "failure" if column == "NFAIL" else ("system_ready" if column == "NREPT" else "arrival")
            hits = sum(time_bin(f"cycle{j}.{suffix}", observed) == index for j in cycles)
            return numeric(.5,.5) if column == "SYDT" and hits else (("null",None) if column == "SYDT" else numeric(float(hits),float(hits)))
        assert column in ("NSYMC","NSYMP","NSYMT","NSYMS","NSYAL","NSYPM","NSYTP","NSYWR","NSYWI","NSYLA","NSYUH","NPMT","NDAM","NPMS","NROBT","NRCFG","STREQ","STF","STLOW","SYDTU","NSYSW","NPSTA","NPSUC")
        return numeric(0.0,0.0)
    if table == "StockTotalResults":
        assert 0 <= index < 72
        if column == "STINT": return numeric(index/2,index/2)
        if column == "ETINT": return numeric((index+1)/2,(index+1)/2)
        demand = sum(time_bin(f"cycle{j}.arrival", observed) == index for j in cycles)
        if column in ("NBOU","WTS"): return "null",None
        if column in ("ROS","ROST","WT","WTT"): return numeric(0.0,0.0) if demand else ("null",None)
        if column == "PNB": return numeric(1.0,1.0)
        if column in ("NDF","NWT"): return numeric(float(demand),float(demand))
        assert column in ("NBO","NDD","NDR","NDP","NLD")
        return numeric(0.0,0.0)
    raise AssertionError((table,index,column))


def read_native_report(raw: bytes):
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\n") == raw.count(b"\r\n")
    tail = b",\r\n      ]"
    assert raw.count(tail) == 1
    return exact_json(raw.replace(tail,b"\r\n      ]",1))


def check_report(raw: bytes, catalog: dict, observed: dict) -> int:
    assert type(catalog) is dict and catalog['schema']=='i05-var04-report-predicates/v101'
    report = read_native_report(raw)
    assert type(report) is dict and set(report) == {"report"}
    body = report["report"]
    assert type(body) is dict and set(body) == {"tables"}
    tables = body["tables"]
    assert type(tables) is list and len(tables) == 4
    expected_tables = catalog["tables"]
    assert type(expected_tables) is list and len(expected_tables) == 4
    expected_order = ["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"]
    assert [t["name"] for t in tables] == [m["name"] for m in expected_tables] == expected_order
    observed_cells = {}
    for table, meta in zip(tables, expected_tables, strict=True):
        assert type(table) is dict and set(table) == {"name","columns","instances"}
        assert type(table["columns"]) is list and exact_type(table["columns"], meta["columns"])
        assert type(table["instances"]) is list and len(table["instances"]) == 1
        instance = table["instances"][0]
        assert type(instance) is dict and set(instance) == {"instance_name","rows"}
        assert type(instance["instance_name"]) is str and instance["instance_name"] == meta["instance_name"]
        assert type(instance["rows"]) is list and len(instance["rows"]) == meta["rows"]
        for index, row in enumerate(instance["rows"]):
            assert type(row) is list and len(row) == len(table["columns"])
            for field, value in zip(table["columns"],row,strict=True):
                key = table["name"],index,field["name"]
                assert key not in observed_cells
                observed_cells[key] = field["datatype"],value
    assert len(observed_cells) == catalog["cell_count"] == len(catalog["predicates"]) == 4044
    for item in catalog["predicates"]:
        key = item["table"],item["row"],item["column"]
        dtype,value = observed_cells.pop(key)
        assert dtype == item["datatype"]
        target = expected_cell(*key, observed)
        if target[0] == "string": assert type(value) is str and value == target[1], key
        elif target[0] == "integer": assert type(value) is int and value == target[1], key
        elif target[0] == "null": assert value is None, key
        else:
            assert dtype == "double" and type(value) in (int,float) and math.isfinite(value)
            assert target[1] <= value <= target[2], (key,value,target)
    assert not observed_cells
    return 4044


SOURCE_LIST_SHA = 'a0527d9c2011fe3cc7e363c211f07332d61d1b455bde4e5977b765e2ca09e8dd'
MANIFEST_KEYS=set('schema run_id native_run_directory file_line_ascii_bytes file_line_ascii_max base_commit contract_sha256 execution_binding_sha256 input_sha256 source_inventory_sha256 runner_sha256 validator_sha256 independent_reader_sha256 source_count source_files owned_source_count accepted_source_pair_count required_local_source_count mandatory_original_count accepted_context_count historical_v100_role_count historical_v100_source_count historical_v101_role_count historical_v101_source_count historical_v102_role_count historical_v102_source_count archived_catalog_count converter_negative_original_count installed_source_count catalog_prefix_entries live_catalog_prelaunch_pin pure_tools stages native_commands pure_checkers new_native_runs_authorized_by_manifest independent_method_state'.split())
PREFLIGHT_KEYS=set('schema run_id native_run_directory run_dirs_absent file_line_ascii_bytes file_line_ascii_max native_run_path_ancestors_no_reparse ssh_session ps_major ssh_ancestors mutex_free wts_active_gui_count gui accepted_source_pair_count required_local_source_count mandatory_original_count accepted_context_count historical_v100_role_count historical_v100_source_count historical_v101_role_count historical_v101_source_count historical_v102_role_count historical_v102_source_count archived_catalog_count converter_negative_original_count installed_source_count catalog_prefix_entries manifest_sha256 source_map_sha256 source_hashes source_hashes_after_pure pure_proof_directory pure_proof_path pure_proof_sha256 pure_checks native_process_started'.split())
PROOF_KEYS=set('schema mode run_id native_run_directory manifest_sha256 source_map_sha256 started_utc completed_utc status error checks source_hashes_after'.split())
PURE_STEP_KEYS=set('tool program arguments started_utc completed_utc status error child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256'.split())
APPROVAL_KEYS=set('schema decision run_id native_run_directory manifest_sha256 runner_sha256 validator_sha256 contract_sha256 execution_binding_sha256 input_sha256 source_map_sha256 independent_reader_sha256 preflight_relative_path preflight_sha256'.split())
INVOCATION_KEYS=set('schema run_id created_utc original_run_dir native_run_directory input_sha256 contract_sha256 manifest_sha256 approval_sha256 approved_preflight_path approved_preflight_sha256 independent_reader_sha256 runner_script_sha256 session_id ssh_ancestors gui queue_mutex working_directory planned_commands planned_checkers source_hashes_before source_hashes_after_pure pure_proof_path pure_proof_sha256 pure_checks publication_state'.split())
CLOSURE_KEYS=set('schema run_id native_run_directory invocation_sha256 manifest_sha256 approval_sha256 approved_preflight_sha256 source_hashes_before source_hashes_after raw step_error error publication_state'.split())
STEP_KEYS=set('sequence name program arguments started_utc completed_utc child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256 converter_log_bytes converter_log_sha256 converter_log_validated gui_preserved status error'.split())

SELECTED = CASE/'source-maps/root-selection-record.json'
SELECTED_SPEC={'bytes':9645,'sha256':SELECTION_SHA}
OBSERVED_ATTRS=CASE/'source-maps/current-parent-raw-attributes.json'
OBSERVED_ATTRS_SPEC={'bytes':5859,'sha256':'cda6ef9f55c42fe16d4ae4e40c84ff3925936a4769855b7d813a87d7bcc7d19c'}
CONTEXT=[
    ('verdict',PARENT/'review/independent-native-review-2026-09-29.json',1577,'ad7801108647a3cb0790a0d93abf85f45c5613377b0dcfb7e6f58d0c59026936'),
    ('invocation',PARENT_RUN/'invocation.json',6819,'a5e5b85421c0d25d1779fad20da0eb7acbb98ea03a347591436157930704bbac'),
    ('closure',PARENT_RUN/'closure.json',5235,'e75836bcd99ba838d4ef247973794a2bf38fbddd4904d69337d631ba983d01ef'),
]
INSTALLED=[
    ('manual',Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),18124110,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'),
    ('dictionary',Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),78577,'11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'),
    ('simlox-exe',Path(EXE),33196032,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'),
    ('python',Path(PYTHON),106448,'10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1'),
]
LOCAL_CATALOG_SPEC={'bytes':549384,'sha256':'65856647dd310207447c4621511b9f42da43a9f25e625560d1f56d06762c6985'}
GIT_CATALOG_SPEC={'bytes':544581,'sha256':'0174772f37e670f1c8e99b65be5acca4870fc3e7dc7ffab24b1d3db73c4735d0'}
HISTORY=REPO/'tmp/i05-var04-source-preflight-failure-seal-v100-20261009.json'
HISTORY_SPEC={'bytes':20760,'sha256':'294086eda9e993d173ab0c00bed4e2e1a45ccff67b3f0884ef8175e566cef0a4'}
HISTORY_CAPTURE=REPO/'tmp/i05-var04-root-command-capture-v100-20261009.py'
HISTORY_CAPTURE_SPEC={'bytes':3610,'sha256':'09d86d3e88787bac53a2c10e89f9a60754bbff23253ecc9522f480cc215ea4a4'}
HISTORY_SPEC_PATH=REPO/'tmp/i05-var04-manifest-audit-spec-v100-20261009.json'
HISTORY_COMMAND_SPEC={'bytes':640,'sha256':'31f76205366b2fdcdc9dc0b4c815b31f20e50e155bd7f86b79a213b170736a2f'}
V101_HISTORY=REPO/'tmp/i05-var04-local-nogo-and-capacity-seal-v101-20261009.json'
V101_HISTORY_SPEC={'bytes':77133,'sha256':'b9fe71bab3374d6de647cdf02c824d6275e3280cbfb5eff8c2c3ebe87ac10800'}
V101_OLD_CASE=REPO/'cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.1'
V101_PROOF_LABELS=('build','independent-private','inventory-audit','inventory-generate',
                   'manifest-audit','manifest-generate','selfcheck','source-gate','source-promote')
V102_HISTORY=REPO/'tmp/i05-var04-excluded-native-failure-seal-v102-20261009.json'
V102_HISTORY_SPEC={'bytes':119310,'sha256':'2c8effe52fe4e869d98fe3218cced949d81a09e59f8507b3d2de2de44c1fe454'}
V102_OLD_CASE=REPO/'cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.2'


def recovery_binding():
    path=CASE/'preserved-design/recovery-binding-v103.json'
    doc=strict_json(exact(path,{'bytes':2227,'sha256':CONTRACT_SHA},readonly=True))
    keys(doc,{'schema','case_version','run_id','native_run_directory','construction_scope_note',
              'unchanged_business_contract_sha256','unchanged_candidate_input',
              'unchanged_log_patterns','unchanged_report_predicates',
              'excluded_v100_failure_seal','excluded_v101_failure_seal','excluded_v102_failure_seal',
              'excluded_v100_role_count','excluded_v101_role_count','excluded_v102_role_count',
              'excluded_v102_historical_file_count','authored_insertion_index',
              'export_insertion_index','export_order_provenance','export_serialization',
              'parent_control_duration_lines','parent_duration_literal','child_duration_literal',
              'synthetic_child_restock_substitutions','synthetic_child_duration_substitutions',
              'source_construction_only','native_calls_at_design'})
    assert doc['schema']=='i05-var04-recovery-binding/v103'
    assert doc['case_version']=='1.0.3' and doc['run_id']==RUN_ID
    assert type(doc['native_run_directory']) is str and doc['native_run_directory']==str(RUN)
    assert doc['unchanged_business_contract_sha256']==BUSINESS_CONTRACT_SHA
    assert doc['unchanged_candidate_input']=={'bytes':45095,'sha256':INPUT_SHA}
    assert doc['unchanged_log_patterns']=={'bytes':87444,'sha256':PATTERN_SHA}
    assert doc['unchanged_report_predicates']=={'bytes':1380881,'sha256':REPORT_RULES_SHA}
    assert doc['excluded_v100_failure_seal']==HISTORY_SPEC
    assert doc['excluded_v101_failure_seal']==V101_HISTORY_SPEC
    assert doc['excluded_v102_failure_seal']==V102_HISTORY_SPEC
    integer(doc['excluded_v100_role_count'],64)
    integer(doc['excluded_v101_role_count'],112)
    integer(doc['excluded_v102_role_count'],269)
    integer(doc['excluded_v102_historical_file_count'],268)
    integer(doc['authored_insertion_index'],12)
    integer(doc['export_insertion_index'],17)
    assert doc['export_order_provenance']=='observed in excluded v102 native import/export; not a general engine law or behavior acceptance'
    assert doc['export_serialization']=={'path':'preserved-design/export-serialization-v103.json',
                                         'bytes':1874,'sha256':EXPORT_ORDER_SHA}
    assert doc['parent_control_duration_lines']==[66,137,209]
    assert doc['parent_duration_literal']=='planned to last for 1 hours'
    assert doc['child_duration_literal']=='planned to last for 1.5 hours'
    integer(doc['synthetic_child_restock_substitutions'],15)
    integer(doc['synthetic_child_duration_substitutions'],3)
    boolean(doc['source_construction_only'],True)
    integer(doc['native_calls_at_design'],0)
    proposal=doc['construction_scope_note']
    assert proposal=={'path':'tmp/i05-var04-independent-v102-failure-scope-go-v103-construction-only-20261009.md',
                      'bytes':4231,'sha256':'5b8f8a722a7ebff9323d024e3d1d402a09993d40a3de35a2ed023ad514acc45c'}
    exact(REPO/proposal['path'],{'bytes':proposal['bytes'],'sha256':proposal['sha256']},readonly=True)
    exact(CASE/'preserved-design/contract.json',{'bytes':6921,'sha256':BUSINESS_CONTRACT_SHA},readonly=True)
    exact(CASE/'native-input.json',{'bytes':45095,'sha256':INPUT_SHA},readonly=True)
    exact(CASE/'preserved-oracle/log-patterns.json',{'bytes':87444,'sha256':PATTERN_SHA},readonly=True)
    exact(CASE/'preserved-oracle/report-predicates.json',{'bytes':1380881,'sha256':REPORT_RULES_SHA},readonly=True)
    return doc


def export_serialization():
    document=strict_json(exact(CASE/'preserved-design/export-serialization-v103.json',
                               {'bytes':1874,'sha256':EXPORT_ORDER_SHA},readonly=True))
    keys(document,{'schema','classification','observation_is_not_behavior_acceptance',
                   'excluded_v102_source','authored_insertion_index','export_insertion_index',
                   'export_predecessor','export_successor','accepted_e05_export_parent_sha256',
                   'superseded_source_delta_field','exact_export_table_names',
                   'export_topology','authored_topology',
                   'full_comparison','unknown_order_or_unrelated_edit','new_native_calls_at_design'})
    assert document['schema']=='i05-var04-export-serialization/v103'
    boolean(document['observation_is_not_behavior_acceptance'],True)
    assert document['excluded_v102_source']=='tmp/i05-var04-excluded-native-failure-seal-v102-20261009.json'
    integer(document['authored_insertion_index'],12)
    integer(document['export_insertion_index'],17)
    assert document['export_predecessor']=='Operations' and document['export_successor']=='Unit'
    assert document['accepted_e05_export_parent_sha256']==PARENT_EXPORT_SHA
    superseded=document['superseded_source_delta_field']
    assert superseded=={'path':'preserved-design/source-delta.json','bytes':5997,
                       'sha256':'eb0148601892353a2ebfb1cf43a1a76fc3ac746f2f4ed20d5fb4266d9990bcd8',
                       'field':'export_gate','old_export_insertion_index':12,
                       'new_export_insertion_index':17,
                       'scope':'export table order only; authored input index 12 and all business/log/report oracles unchanged'}
    old=strict_json(exact(CASE/superseded['path'],
                          {'bytes':superseded['bytes'],'sha256':superseded['sha256']},readonly=True))
    assert type(old) is dict and type(old['export_gate']) is str
    assert 'ChangesItemRepair table at index 12' in old['export_gate']
    for field,expected in [('export_topology',{'tables':32,'rows':36,'typed_cells':379}),
                           ('authored_topology',{'tables':32,'rows':25,'typed_cells':284})]:
        keys(document[field],expected)
        for key,wanted in expected.items():
            integer(document[field][key],wanted)
    assert document['unknown_order_or_unrelated_edit']=='NO_GO'
    integer(document['new_native_calls_at_design'],0)
    parent=strict_json(exact(PARENT_RUN/'roundtrip-raw.json',{'bytes':57986,'sha256':PARENT_EXPORT_SHA}))
    names=[table['name'] for table in parent['model']['tables']]
    assert len(names)==31 and names[16:18]==['Operations','Unit']
    expected=names.copy(); expected.insert(17,'ChangesItemRepair')
    assert document['exact_export_table_names']==expected
    return document


def historical_sources():
    original=exact(HISTORY,HISTORY_SPEC,readonly=True)
    assert exact(CASE/'source-maps/v100-failure-seal.json',HISTORY_SPEC,readonly=True)==original
    doc=strict_json(original)
    assert doc['schema']=='i05-var04-source-preflight-failure/v100'
    assert doc['decision']=='NO_GO_AS_FROZEN'
    integer(doc['actual_exit'],1)
    boolean(doc['manifest_promoted'],False)
    for field in ('ssh_preflight_calls','native_calls','accepted_checker_calls'): integer(doc[field],0)
    integer(doc['frozen_source_count'],54)
    assert type(doc['frozen_sources']) is list and len(doc['frozen_sources'])==54
    assert type(doc['auxiliary']) is list and len(doc['auxiliary'])==4
    rows=[{'key':'historical:failure-seal','path':str(HISTORY),**HISTORY_SPEC}]
    old=REPO/'cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.0'
    seen=set()
    for index,item in enumerate(doc['frozen_sources']):
        path=absolute(item['path']); no_reparse(path)
        assert path.resolve(strict=True).is_relative_to(old.resolve(strict=True))
        assert str(path).casefold() not in seen; seen.add(str(path).casefold())
        integer(item['attributes'],33)
        spec={'bytes':item['bytes'],'sha256':item['sha256']}
        exact(path,spec,readonly=True)
        integer(path.stat().st_file_attributes,33)
        rows.append({'key':f'historical:source:{index:02d}','path':str(path),**spec})
    for index,item in enumerate(doc['auxiliary']):
        path=absolute(item['path']); no_reparse(path)
        assert path.is_relative_to(REPO/'tmp')
        spec={'bytes':item['bytes'],'sha256':item['sha256']}
        exact(path,spec,readonly=True)
        integer(path.stat().st_file_attributes,33)
        rows.append({'key':f'historical:aux:{index:02d}','path':str(path),**spec})
    proof=doc['failed_proof']; proofpath=absolute(proof['path']); no_reparse(proofpath)
    proofspec={'bytes':proof['bytes'],'sha256':proof['sha256']}
    receipt=strict_json(exact(proofpath,proofspec,readonly=True))
    assert receipt['schema']=='i05-var04-root-command-proof/v100'
    boolean(receipt['native_dispatch'],False); integer(receipt['actual_exit'],1)
    assert typed(receipt['method_before'],receipt['method_after'])
    assert receipt['method_before']['capture']==HISTORY_CAPTURE_SPEC
    assert receipt['method_before']['spec']==HISTORY_COMMAND_SPEC
    assert receipt['method_before']['method']=={'bytes':55854,'sha256':'adc8f2843e94984c1ee38ccf7619f39048729d963324db241525304f325ed20c'}
    assert receipt['argv'][4]==str(old/'review/independent_reader.py')
    assert receipt['argv'][5]=='--manifest-candidate'
    rows.append({'key':'historical:proof:receipt','path':str(proofpath),**proofspec})
    for stream in ('stdout','stderr'):
        filename=stream+'.bin'; path=proofpath.parent/filename
        spec=receipt['streams'][filename]
        assert spec==proof[stream]
        exact(path,spec,readonly=True)
        integer(path.stat().st_file_attributes,33)
        rows.append({'key':'historical:proof:'+stream,'path':str(path),**spec})
    for name,path,spec in (('capture',HISTORY_CAPTURE,HISTORY_CAPTURE_SPEC),
                           ('spec',HISTORY_SPEC_PATH,HISTORY_COMMAND_SPEC)):
        exact(path,spec,readonly=True); integer(path.stat().st_file_attributes,33)
        rows.append({'key':'historical:method:'+name,'path':str(path),**spec})
    assert len(rows)==64
    return rows


def excluded_v101_sources():
    """Bind the v101 local NO_GO and every original byte it sealed."""
    original=exact(V101_HISTORY,V101_HISTORY_SPEC,readonly=True)
    assert exact(CASE/'source-maps/v101-failure-seal.json',V101_HISTORY_SPEC,readonly=True)==original
    integer(V101_HISTORY.stat().st_file_attributes,33)
    doc=strict_json(original)
    assert doc['schema']=='i05-var04-local-nogo-and-capacity/v101'
    assert doc['decision']=='NO_GO_AS_FROZEN'
    integer(doc['actual_exit'],1)
    for field in ('ssh_preflight_calls','native_calls','accepted_checker_calls'):
        integer(doc[field],0)
    integer(doc['frozen_source_count'],57)
    integer(doc['manifest_role_count'],160)
    assert type(doc['frozen_sources']) is list and len(doc['frozen_sources'])==57
    assert type(doc['original_command_proofs']) is list and len(doc['original_command_proofs'])==9
    assert type(doc['auxiliary']) is list and len(doc['auxiliary'])==26
    rows=[{'key':'excluded-v101:seal','path':str(V101_HISTORY),**V101_HISTORY_SPEC}]
    old_root=V101_OLD_CASE.resolve(strict=True)
    for index,item in enumerate(doc['frozen_sources']):
        path=absolute(item['path']); no_reparse(path)
        assert path.resolve(strict=True).is_relative_to(old_root)
        integer(item['attributes'],33)
        spec={'bytes':item['bytes'],'sha256':item['sha256']}
        exact(path,spec,readonly=True); integer(path.stat().st_file_attributes,33)
        rows.append({'key':f'excluded-v101:source:{index:02d}','path':str(path),**spec})
    for label,item in zip(V101_PROOF_LABELS,doc['original_command_proofs'],strict=True):
        assert item['label']==label
        receipt_item=item['receipt']; path=absolute(receipt_item['path']); no_reparse(path)
        assert path.is_relative_to(REPO/'tmp') and path.name=='receipt.json'
        spec={'bytes':receipt_item['bytes'],'sha256':receipt_item['sha256']}
        receipt=strict_json(exact(path,spec,readonly=True))
        integer(receipt_item['attributes'],33); integer(path.stat().st_file_attributes,33)
        assert receipt['schema']=='i05-var04-root-command-proof/v101'
        boolean(receipt['native_dispatch'],False)
        assert typed(receipt['method_before'],receipt['method_after'])
        expected_exit=1 if label=='independent-private' else 0
        integer(item['actual_exit'],expected_exit); integer(receipt['actual_exit'],expected_exit)
        rows.append({'key':f'excluded-v101:proof:{label}:receipt','path':str(path),**spec})
        for name,stream in zip(('stdout','stderr'),item['streams'],strict=True):
            stream_path=absolute(stream['path']); no_reparse(stream_path)
            assert stream_path==path.parent/(name+'.bin')
            stream_spec={'bytes':stream['bytes'],'sha256':stream['sha256']}
            assert typed(receipt['streams'][name+'.bin'],stream_spec)
            exact(stream_path,stream_spec,readonly=True)
            integer(stream['attributes'],33); integer(stream_path.stat().st_file_attributes,33)
            rows.append({'key':f'excluded-v101:proof:{label}:{name}',
                         'path':str(stream_path),**stream_spec})
    for index,item in enumerate(doc['auxiliary']):
        path=absolute(item['path']); no_reparse(path)
        assert path.is_relative_to(REPO/'tmp')
        spec={'bytes':item['bytes'],'sha256':item['sha256']}
        exact(path,spec,readonly=True)
        integer(item['attributes'],33); integer(path.stat().st_file_attributes,33)
        rows.append({'key':f'excluded-v101:aux:{index:02d}','path':str(path),**spec})
    method=doc['method']; path=absolute(method['path']); no_reparse(path)
    assert path.is_relative_to(REPO/'tmp')
    spec={'bytes':method['bytes'],'sha256':method['sha256']}
    exact(path,spec,readonly=True)
    integer(method['attributes'],33); integer(path.stat().st_file_attributes,33)
    rows.append({'key':'excluded-v101:method:seal','path':str(path),**spec})
    assert len(rows)==112 and len({r['key'].casefold() for r in rows})==112
    return rows


def excluded_v102_sources():
    """Bind every frozen file in the unsuccessful v102 native/export diagnosis."""
    original=exact(V102_HISTORY,V102_HISTORY_SPEC,readonly=True)
    assert exact(CASE/'source-maps/v102-failure-seal.json',V102_HISTORY_SPEC,readonly=True)==original
    document=strict_json(original)
    keys(document,{'schema','utc','decision','classification','frozen_source_count',
                   'canonical_file_count','source_role_count','static_freeze','failure_custody',
                   'original_command_proofs','historical_files','historical_file_count',
                   'historical_role_count','source_bytes_modes_attributes_stable','failed_stage',
                   'actual_exit','formal_native_dispatches','native_import_export_commands',
                   'converter_calls','simulation_calls','report_calls','accepted_checker_calls',
                   'native_retry_calls','publication_state','semantic_acceptance',
                   'original_goal_unfinished','recovery_condition','method'})
    assert document['schema']=='i05-var04-excluded-native-failure/v102'
    assert document['decision']=='NO_GO_AS_FROZEN' and document['publication_state']=='excluded'
    boolean(document['semantic_acceptance'],False)
    boolean(document['source_bytes_modes_attributes_stable'],True)
    assert document['failed_stage']=='check_import_export'
    for field,wanted in [('frozen_source_count',59),('canonical_file_count',89),
                         ('source_role_count',274),('historical_file_count',268),
                         ('historical_role_count',269),('actual_exit',1),
                         ('formal_native_dispatches',1),('native_import_export_commands',2),
                         ('converter_calls',0),('simulation_calls',0),('report_calls',0),
                         ('accepted_checker_calls',0),('native_retry_calls',0)]:
        integer(document[field],wanted)
    proofs=document['original_command_proofs']
    assert type(proofs) is list and len(proofs)==18
    assert sum(item['native_dispatch'] is True for item in proofs)==1
    history=document['historical_files']
    assert type(history) is list and len(history)==268
    assert len({item['path'].casefold() for item in history})==268
    rows=[{'key':'excluded-v102:seal','path':str(V102_HISTORY),**V102_HISTORY_SPEC}]
    oldroot=V102_OLD_CASE.resolve(strict=True)
    casecount=0
    for index,item in enumerate(history):
        keys(item,{'path','bytes','sha256','mode','attributes'})
        path=absolute(item['path']); no_reparse(path)
        assert path.is_relative_to(REPO)
        spec={'bytes':item['bytes'],'sha256':item['sha256']}
        exact(path,spec,readonly=True)
        integer(path.stat().st_mode,item['mode'])
        integer(path.stat().st_file_attributes,33)
        if path.is_relative_to(oldroot):
            casecount+=1
        rows.append({'key':f'excluded-v102:history:{index:03d}','path':str(path),**spec})
    integer(casecount,89)
    assert len(rows)==269 and len({r['key'].casefold() for r in rows})==269
    return rows


def no_reparse(path:Path):
    for part in [path,*path.parents]:
        if part.exists():
            assert not part.is_symlink() and not part.is_junction() and not (part.stat().st_file_attributes&0x400), part


def owned_list():
    body=(CASE/'source-list.json').read_bytes()
    assert sha(body)==SOURCE_LIST_SHA
    roster=strict_json(body)
    keys(roster,{'schema','files'})
    assert roster['schema']=='i05-var04-owned-source-list/v103'
    files=roster['files']
    assert type(files) is list and len(files)>=3
    assert all(type(x) is str and x==Path(x).as_posix() and not Path(x).is_absolute() and '..' not in Path(x).parts for x in files)
    assert len(files)==len(set(files))==len({x.casefold() for x in files})
    assert files.count('review/independent_reader.py')==files.count('review/independent_self_check.py')==files.count('review/independent-static-go-2026-10-09.md')==1
    return files


def source_inventory(candidate:Path|None=None):
    owned=owned_list()
    path=CASE/'source-inventory.json' if candidate is None else candidate
    no_reparse(path)
    assert path.stat().st_file_attributes&1
    document=strict_json(path.read_bytes())
    keys(document,{'schema','source_count','source_files'})
    assert document['schema']=='i05-var04-source-inventory/v103'
    integer(document['source_count'],len(owned))
    assert type(document['source_files']) is list and len(document['source_files'])==len(owned)
    for name,row in zip(owned,document['source_files'],strict=True):
        keys(row,{'path','bytes','sha256'})
        assert row['path']==name
        target=CASE/name
        no_reparse(target)
        exact(target,{'bytes':row['bytes'],'sha256':row['sha256']},readonly=True)
    return document


def accepted_sources():
    selected=strict_json(exact(SELECTED,SELECTED_SPEC,readonly=True))
    assert selected['decision']=='PASS_CANDIDATE_DEPENDENCY_BYTES_ONLY'
    assert selected['merge']==BASE and selected['catalog_count']==504
    integer(selected['native_calls'],0); integer(selected['accepted_checker_calls'],0)
    pairs=selected['source_pairs']
    originals=selected['accepted_parent_raw_seals']
    assert type(pairs) is type(originals) is list and len(pairs)==21 and len(originals)==12
    attrdoc=strict_json(exact(OBSERVED_ATTRS,OBSERVED_ATTRS_SPEC,readonly=True))
    attrs=attrdoc['rows']
    assert type(attrs) is list and len(attrs)==12
    roles=[]
    for row in pairs:
        rel=Path(row['path'])
        assert not rel.is_absolute() and '..' not in rel.parts
        path=(REPO/rel).resolve(strict=True)
        assert path.is_relative_to(REPO.resolve(strict=True))
        no_reparse(path)
        spec={'bytes':row['bytes'],'sha256':row['sha256']}
        exact(path,spec)
        roles.append({'key':'accepted:'+row['path'],'path':str(path),**spec})
    for index,(row,attrs_row) in enumerate(zip(originals,attrs,strict=True)):
        path=absolute(row['path'])
        no_reparse(path)
        spec={'bytes':row['bytes'],'sha256':row['sha256']}
        assert attrs_row['role']==f'E05:raw:{index:02d}'
        assert all(attrs_row[k]==row[k] for k in ('path','bytes','sha256'))
        exact(path,spec)
        stat=path.stat()
        integer(stat.st_mode,attrs_row['mode']); integer(stat.st_file_attributes,attrs_row['file_attributes'])
        roles.append({'key':f'mandatory:{index:02d}','path':str(path),**spec})
    verdict=strict_json(exact(CONTEXT[0][1],{'bytes':CONTEXT[0][2],'sha256':CONTEXT[0][3]}))
    assert verdict['schema']=='simlox-e05-independent-native-review/v1' and verdict['run_id']=='e05-v100-ssh-20260929-01'
    boolean(verdict['passed'],True)
    assert verdict['differences']==[] and verdict['raw_report_sha256']=='fcf9a124546e77fb96871b5bf4b5e111774c00616bfed69c19ad7f1b6c08b4bf'
    invoke=accepted_powershell_receipt_json(exact(CONTEXT[1][1],{'bytes':CONTEXT[1][2],'sha256':CONTEXT[1][3]}))
    close=accepted_powershell_receipt_json(exact(CONTEXT[2][1],{'bytes':CONTEXT[2][2],'sha256':CONTEXT[2][3]}))
    assert invoke['run_id']==close['run_id']==verdict['run_id']
    assert invoke['input_sha256']==PARENT_INPUT_SHA and close['error'] is None
    assert close['invocation_sha256']==CONTEXT[1][3]
    assert close['source_hashes_before']==close['source_hashes_after']
    for name,path,size,digest in CONTEXT:
        no_reparse(path)
        st=path.stat(); integer(st.st_mode,33206); integer(st.st_file_attributes,32)
        roles.append({'key':'accepted-context:'+name,'path':str(path),'bytes':size,'sha256':digest})
    for name,path,size,digest in INSTALLED:
        no_reparse(path)
        exact(path,{'bytes':size,'sha256':digest})
        roles.append({'key':'installed:'+name,'path':str(path),'bytes':size,'sha256':digest})
    assert len(roles)==40
    return roles


def manifest_document(candidate:Path|None=None):
    recovery_binding()
    export_serialization()
    inventory=source_inventory()
    path=CASE/'prelaunch-manifest.json' if candidate is None else candidate
    no_reparse(path)
    assert path.stat().st_file_attributes&1
    document=strict_json(path.read_bytes())
    keys(document,MANIFEST_KEYS)
    assert document['schema']=='i05-var04-prelaunch-manifest/v103'
    assert document['run_id']==RUN_ID and type(document['native_run_directory']) is str and document['native_run_directory']==str(RUN)
    converter_lines=['Input file: '+str(RUN/'model.sxi'),'Output file: '+str(RUN/'model.sxo'),'File: '+str(RUN/'model.sxi').replace('\\','/')]
    assert all(x.isascii() for x in converter_lines) and [len(x.encode('ascii')) for x in converter_lines]==[125,126,119]
    integer(document['file_line_ascii_bytes'],119); integer(document['file_line_ascii_max'],199)
    assert document['base_commit']==BASE and document['contract_sha256']==CONTRACT_SHA
    binding=strict_json(exact(CASE/'execution-contract.json',seal(CASE/'execution-contract.json'),readonly=True))
    assert binding['schema']=='i05-var04-execution-contract/v103'
    assert binding['logical_run_id']==RUN_ID and binding['native_run_directory']==str(RUN)
    assert binding['recovered_run_directory']==str(RECOVERED)
    assert binding['recovery_binding_sha256']==CONTRACT_SHA
    assert binding['export_serialization_sha256']==EXPORT_ORDER_SHA
    assert binding['prospective_contract_sha256']==BUSINESS_CONTRACT_SHA
    integer(binding['authored_insertion_index'],12)
    integer(binding['export_insertion_index'],17)
    assert binding['export_order_provenance']=='excluded v102 import/export observation; falsifiable representation hypothesis only'
    integer(binding['historical_v100_source_count'],54)
    integer(binding['historical_v100_role_count'],64)
    integer(binding['historical_v101_source_count'],57)
    integer(binding['historical_v101_role_count'],112)
    integer(binding['historical_v102_source_count'],59)
    integer(binding['historical_v102_role_count'],269)
    assert binding['native_authorization_state']=='SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL'
    fields={'execution_binding_sha256':'execution-contract.json','input_sha256':'native-input.json','source_inventory_sha256':'source-inventory.json','runner_sha256':'run_native_ssh.ps1','validator_sha256':'validate_native_cli.py','independent_reader_sha256':'review/independent_reader.py'}
    for field,rel in fields.items():
        assert document[field]==seal(CASE/rel)['sha256'],field
    assert document['input_sha256']==INPUT_SHA
    for field,wanted in [('accepted_source_pair_count',21),('required_local_source_count',0),('mandatory_original_count',12),('accepted_context_count',3),('historical_v100_role_count',64),('historical_v100_source_count',54),('historical_v101_role_count',112),('historical_v101_source_count',57),('historical_v102_role_count',269),('historical_v102_source_count',59),('archived_catalog_count',2),('converter_negative_original_count',0),('installed_source_count',4),('catalog_prefix_entries',504),('native_commands',4),('pure_checkers',2),('new_native_runs_authorized_by_manifest',0)]:
        integer(document[field],wanted)
    assert document['pure_tools']==TOOLS and document['stages']==STAGES
    assert document['independent_method_state']=='SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL'
    expected=[{'key':'owned:'+row['path'],'path':str(CASE/row['path']),'bytes':row['bytes'],'sha256':row['sha256']} for row in inventory['source_files']]
    expected.append({'key':'owned:source-inventory.json','path':str(CASE/'source-inventory.json'),**seal(CASE/'source-inventory.json')})
    expected.extend(accepted_sources())
    expected.extend(historical_sources())
    expected.extend(excluded_v101_sources())
    expected.extend(excluded_v102_sources())
    integer(document['owned_source_count'],len(owned_list())+1)
    integer(document['source_count'],len(expected))
    assert len(expected)==len(owned_list())+486 and typed(expected,document['source_files'])
    seen_keys=set(); seen_paths={}
    for row in document['source_files']:
        keys(row,{'key','path','bytes','sha256'})
        name=row['key'].casefold()
        assert name not in seen_keys; seen_keys.add(name)
        resolved=str(Path(row['path']).resolve(strict=True)).replace('/','\\').casefold()
        identity=row['bytes'],row['sha256']
        assert resolved not in seen_paths or seen_paths[resolved]==identity
        seen_paths[resolved]=identity
    keys(document['live_catalog_prelaunch_pin'],{'path','bytes','sha256'})
    catalog=REPO/'cases/simlox-air-support/publication-index-v1.json'
    assert document['live_catalog_prelaunch_pin']=={'path':str(catalog),**LOCAL_CATALOG_SPEC}
    current=strict_json(catalog.read_bytes())
    archive=strict_json(exact(CASE/'source-maps/catalog-local-504.json.bytes',LOCAL_CATALOG_SPEC,readonly=True))
    exact(CASE/'source-maps/catalog-git-504.json.bytes',GIT_CATALOG_SPEC,readonly=True)
    assert type(current) is type(archive) is dict and set(current)==set(archive)
    assert type(current['entries']) is list and len(current['entries'])>=504
    assert typed(current['entries'][:504],archive['entries'])
    for field in archive:
        if field not in ('entries','as_of'):
            assert typed(current[field],archive[field])
    assert len({entry['publication_id'] for entry in current['entries']})==len(current['entries'])
    return document,{row['key']:row['sha256'] for row in expected}


NEW_COLUMNS=[
    {'name':'IID','datatype':'string','key':True},
    {'name':'STID','datatype':'string','key':True},
    {'name':'TIMEC','datatype':'double','key':True},
    {'name':'DIRPT','datatype':'double'},
    {'name':'SURPT','datatype':'double'},
    {'name':'DIRPF','datatype':'double'},
    {'name':'SURPF','datatype':'double'},
    {'name':'DIRPD','datatype':'string'},
    {'name':'SURPD','datatype':'string'},
    {'name':'NOTE','datatype':'string'},
]
NEW_TABLE={'name':'ChangesItemRepair','columns':NEW_COLUMNS,
           'instances':[{'instance_name':'','rows':[['TEACH-LRU-01','BASE-01',5.0,1.5,0.0,1.0,1.0,None,None,None]]}]}


def source_oracles():
    serialization=export_serialization()
    parent_input=strict_json(exact(PARENT/'native-input.json',{'bytes':43690,'sha256':PARENT_INPUT_SHA}))
    parent_export=strict_json(exact(PARENT_RUN/'roundtrip-raw.json',{'bytes':57986,'sha256':PARENT_EXPORT_SHA}))
    child_input=strict_json(exact(CASE/'native-input.json',{'bytes':45095,'sha256':INPUT_SHA},readonly=True))
    keys(parent_input,{'model'}); keys(parent_export,{'model'}); keys(child_input,{'model'})
    for body in (parent_input,parent_export,child_input): keys(body['model'],{'database_version','tables'})
    assert typed(parent_input['model']['database_version'],child_input['model']['database_version'])
    authored=copy.deepcopy(parent_input)
    exported=copy.deepcopy(parent_export)
    for body,parent_count,child_count,insertion in ((authored,(31,24,274),(32,25,284),12),
                                                    (exported,(31,35,369),(32,36,379),17)):
        tables=body['model']['tables']
        assert type(tables) is list and len(tables)==parent_count[0]
        if insertion==12:
            assert tables[11]['name']=='ItemRepair' and tables[12]['name']=='ItemReorder'
        else:
            assert tables[16]['name']=='Operations' and tables[17]['name']=='Unit'
        assert not any(table['name']=='ChangesItemRepair' for table in tables)
        tables.insert(insertion,copy.deepcopy(NEW_TABLE))
        assert count_tables(tables)==child_count
        assert tables[insertion]['name']=='ChangesItemRepair'
    assert count_tables(parent_input['model']['tables'])==(31,24,274)
    assert count_tables(parent_export['model']['tables'])==(31,35,369)
    assert compare_tables(authored['model']['tables'],child_input['model']['tables'])==(32,25,284)
    assert [table['name'] for table in exported['model']['tables']]==serialization['exact_export_table_names']
    return authored,exported


def count_tables(tables):
    assert type(tables) is list
    rows=cells=0
    for table in tables:
        keys(table,{'name','columns','instances'})
        assert type(table['columns']) is type(table['instances']) is list
        for instance in table['instances']:
            keys(instance,{'instance_name','rows'})
            assert type(instance['rows']) is list
            for row in instance['rows']:
                assert type(row) is list and len(row)==len(table['columns'])
                rows+=1; cells+=len(row)
    return len(tables),rows,cells


def source_map_digest(source_map):
    return hashlib.sha256(json.dumps(source_map,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()

def pure_proof(receipt:dict,source_map:dict,mode:str):
    proof_dir=absolute(receipt['pure_proof_directory'])
    assert proof_dir.parent==CASE/'test-output'
    assert re.fullmatch(rf'{mode}-pure-[0-9]{{8}}T[0-9]{{13}}Z-[0-9a-f]{{8}}',proof_dir.name)
    proof_path=proof_dir/'pure-proof.json'
    assert receipt['pure_proof_path']==str(proof_path) and receipt['pure_proof_sha256']==seal(proof_path)['sha256']
    proof=receipt_json(proof_path.read_bytes()); keys(proof,PROOF_KEYS)
    assert proof['schema']=='i05-var04-pure-proof/v103' and proof['mode']==mode
    assert proof['run_id']==RUN_ID and type(proof['native_run_directory']) is str and proof['native_run_directory']==str(RUN)
    assert proof['status']=='passed' and proof['error'] is None
    assert proof['manifest_sha256']==receipt['manifest_sha256'] and proof['source_map_sha256']==receipt['source_map_sha256']
    assert proof['source_hashes_after']==source_map and receipt['source_hashes_after_pure']==source_map
    assert typed(proof['checks'],receipt['pure_checks']) and type(proof['checks']) is list and len(proof['checks'])==len(TOOLS)
    previous=utc(proof['started_utc'])
    for tool,step in zip(TOOLS,proof['checks'],strict=True):
        keys(step,PURE_STEP_KEYS)
        assert step['tool']==tool and step['program']==PYTHON
        assert step['arguments']==f'-X utf8 -B "{CASE/tool}"'
        assert step['status']=='completed' and step['error'] is None and step['capture_error'] is None
        integer(step['exit_code'],0); integer(step['child_session_id'],0); integer(step['stderr_bytes'],0)
        assert type(step['child_pid']) is int and step['child_pid']>0
        start,end=utc(step['started_utc']),utc(step['completed_utc'])
        assert previous<=start<=end; previous=end
        for stream in ('stdout','stderr'):
            expected=proof_dir/(Path(tool).stem+'-'+stream+'.bin')
            assert step[stream+'_path']==str(expected)
            exact(expected,{'bytes':step[stream+'_bytes'],'sha256':step[stream+'_sha256']})
    assert utc(proof['completed_utc'])>=previous
    return proof


def preflight_receipt(path:Path):
    manifest,source_map=manifest_document()
    receipt=receipt_json(path.read_bytes()); keys(receipt,PREFLIGHT_KEYS)
    assert receipt['schema']=='i05-var04-ssh-preflight/v103' and receipt['run_id']==RUN_ID
    assert type(receipt['native_run_directory']) is str and receipt['native_run_directory']==str(RUN)
    assert receipt['manifest_sha256']==seal(CASE/'prelaunch-manifest.json')['sha256']
    assert receipt['source_map_sha256']==source_map_digest(source_map)
    assert receipt['source_hashes']==source_map and receipt['source_hashes_after_pure']==source_map
    for field,wanted in [('file_line_ascii_bytes',119),('file_line_ascii_max',199),('ssh_session',0),('ps_major',5),('wts_active_gui_count',1),('accepted_source_pair_count',21),('required_local_source_count',0),('mandatory_original_count',12),('accepted_context_count',3),('historical_v100_role_count',64),('historical_v100_source_count',54),('historical_v101_role_count',112),('historical_v101_source_count',57),('historical_v102_role_count',269),('historical_v102_source_count',59),('archived_catalog_count',2),('converter_negative_original_count',0),('installed_source_count',4),('catalog_prefix_entries',504)]: integer(receipt[field],wanted)
    for field,wanted in [('run_dirs_absent',True),('native_run_path_ancestors_no_reparse',True),('mutex_free',True),('native_process_started',False)]: boolean(receipt[field],wanted)
    assert type(receipt['ssh_ancestors']) is list and 'sshd.exe' in receipt['ssh_ancestors']
    keys(receipt['gui'],{'pid','session_id','start_unix_ms','responding'})
    for field,wanted in [('pid',13340),('session_id',1),('start_unix_ms',1790590196826)]: integer(receipt['gui'][field],wanted)
    boolean(receipt['gui']['responding'],True)
    pure_proof(receipt,source_map,'preflight')
    assert path.parent==CASE/'review' and re.fullmatch(r'preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json',path.name)
    return receipt,source_map


def approval_document(path:Path):
    body=receipt_json(path.read_bytes()); keys(body,APPROVAL_KEYS)
    assert body['schema']=='i05-var04-independent-prelaunch-go/v103' and body['decision']=='GO_PRELAUNCH'
    assert body['run_id']==RUN_ID and type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    manifest,source_map=manifest_document()
    for field,wanted in [('manifest_sha256',seal(CASE/'prelaunch-manifest.json')['sha256']),('runner_sha256',manifest['runner_sha256']),('validator_sha256',manifest['validator_sha256']),('contract_sha256',CONTRACT_SHA),('execution_binding_sha256',manifest['execution_binding_sha256']),('input_sha256',INPUT_SHA),('source_map_sha256',source_map_digest(source_map)),('independent_reader_sha256',seal(CASE/'review/independent_reader.py')['sha256'])]:
        assert body[field]==wanted,field
    rel=body['preflight_relative_path'].replace('\\','/')
    assert re.fullmatch(r'review/preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json',rel)
    receipt_path=CASE/rel
    assert receipt_path.is_file() and receipt_path.resolve(strict=True).parent==(CASE/'review').resolve(strict=True)
    assert body['preflight_sha256']==seal(receipt_path)['sha256']
    return body,preflight_receipt(receipt_path)[0]

def converter_bytes(data:bytes)->int:
    assert data and not data.startswith(b'\xef\xbb\xbf') and data.endswith(b'\r\n')
    assert data.count(b'\r\n')==data.count(b'\n')==15
    lines=data.decode('utf-8').split('\r\n')
    assert lines[-1]==''
    lines.pop()
    assert len(lines)==15
    expected=[
        'Performing simulation',
        'Input file: '+str(RUN/'model.sxi'),
        'Output file: '+str(RUN/'model.sxo'),
        'Simulating.','Converting input data ...',
        'File: '+str(RUN/'model.sxi').replace('\\','/'),
        'Form: Control',
        'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',
        'Input conversion completed. Errors: 0, Warnings: 1, Notes: 0',
        None,'Starting simulation...',None,'Saving results ...',None,None,
    ]
    for actual,predicted in zip(lines,expected,strict=True):
        if predicted is not None: assert actual==predicted,(actual,predicted)
    for index,label in [(9,'Input data conversion time'),(11,'Simulation time'),(13,'Result saving time'),(14,'Total execution time')]:
        match=re.fullmatch(re.escape(label)+r': ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) secs\.',lines[index])
        assert match and math.isfinite(float(match.group(1))) and float(match.group(1))>=0
    assert len(lines[1].encode('ascii'))==125 and len(lines[2].encode('ascii'))==126
    assert len(lines[5].encode('ascii'))==119 and len(lines[5].encode('ascii'))<=199
    return len(lines)


def checker_receipt(data:bytes,name:str,raw:Path):
    body=strict_json(data)
    common={'schema','passed','run_id','native_run_directory','input_sha256','export_sha256','native_calls','issues'}
    if name=='check_import_export':
        wanted=common|{'authored_tables','authored_rows','authored_cells','exported_tables','exported_rows','exported_cells'}
        schema='i05-var04-roundtrip-check/v103'
    else:
        assert name=='check_behavior'
        wanted=common|{'log_sha256','report_sha256','physical_log_lines','timed_log_lines','report_typed_cells','authored_cells','exported_cells','complete_repair_cycles'}
        schema='i05-var04-native-behavior-check/v103'
    keys(body,wanted)
    assert body['schema']==schema and body['run_id']==RUN_ID
    boolean(body['passed'],True)
    assert type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
    assert body['input_sha256']==INPUT_SHA and body['export_sha256']==seal(raw/'roundtrip-raw.json')['sha256']
    integer(body['native_calls'],0); assert body['issues']==[]
    if name=='check_import_export':
        for field,wanted in [('authored_tables',32),('authored_rows',25),('authored_cells',284),('exported_tables',32),('exported_rows',36),('exported_cells',379)]: integer(body[field],wanted)
    else:
        assert body['log_sha256']==seal(raw/'model.log')['sha256'] and body['report_sha256']==seal(raw/'report-raw.json')['sha256']
        for field,wanted in [('physical_log_lines',222),('timed_log_lines',186),('report_typed_cells',4044),('authored_cells',284),('exported_cells',379),('complete_repair_cycles',3)]: integer(body[field],wanted)
    return body


def receipt_json(data:bytes):
    return strict_json(data[3:] if data.startswith(b'\xef\xbb\xbf') else data)

def planned():
    def rf(name): return str(RUN/name)
    commands=[
        {'name':'import','program':EXE,'arguments':f'-silent -jimport "{rf("input.json")}" -save "{rf("model.sxi")}" -log "{rf("import.log")}" -close'},
        {'name':'export','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -jexport "{rf("roundtrip-raw.json")}" -log "{rf("export.log")}" -close'},
        {'name':'calc','program':EXE,'arguments':f'"{rf("model.sxi")}" -silent -threads 1 -calc -log "{rf("model-run.log")}" -close'},
        {'name':'jsonreport','program':EXE,'arguments':f'"{rf("model.sxo")}" -silent -jsonreport "{rf("report-raw.json")}" -log "{rf("report-export.log")}" -close'},
    ]
    checkers=[
        {'name':'check_import_export','program':PYTHON,'arguments':f'-X utf8 -B "{CASE/"check_roundtrip.py"}" --run-dir "{RUN}"'},
        {'name':'check_behavior','program':PYTHON,'arguments':f'-X utf8 -B "{CASE/"validate_native_cli.py"}" --run-dir "{RUN}"'},
    ]
    return commands,checkers


def sealed_replay(raw:Path):
    assert raw.is_dir() and raw.resolve(strict=True)==RECOVERED.resolve(strict=True) and raw.resolve(strict=True)!=RUN.resolve(strict=True)
    manifest,source_map=manifest_document()
    approval,preflight=approval_document(CASE/'review/independent-prelaunch-go.json')
    invocation=receipt_json((raw/'invocation.json').read_bytes())
    closure=receipt_json((raw/'closure.json').read_bytes())
    keys(invocation,INVOCATION_KEYS); keys(closure,CLOSURE_KEYS)
    assert invocation['schema']=='i05-var04-invocation/v103' and closure['schema']=='i05-var04-closure/v103'
    for body in (invocation,closure):
        assert body['run_id']==RUN_ID and type(body['native_run_directory']) is str and body['native_run_directory']==str(RUN)
        assert body['manifest_sha256']==approval['manifest_sha256']
        assert body['approval_sha256']==seal(CASE/'review/independent-prelaunch-go.json')['sha256']
        assert body['approved_preflight_sha256']==approval['preflight_sha256']
        assert body['source_hashes_before']==source_map
    assert invocation['original_run_dir']==str(RUN)
    assert invocation['input_sha256']==INPUT_SHA and invocation['contract_sha256']==CONTRACT_SHA
    assert invocation['approved_preflight_path']==str(CASE/approval['preflight_relative_path'])
    assert invocation['independent_reader_sha256']==manifest['independent_reader_sha256']
    assert invocation['runner_script_sha256']==manifest['runner_sha256']
    assert invocation['source_hashes_after_pure']==source_map
    assert invocation['queue_mutex']==r'Global\SimloxIssue18NativeQueue'
    assert invocation['working_directory']==str(REPO)
    assert invocation['publication_state']==closure['publication_state']=='not_published'
    integer(invocation['session_id'],0)
    assert type(invocation['ssh_ancestors']) is list and 'sshd.exe' in invocation['ssh_ancestors']
    assert typed(preflight['gui'],invocation['gui'])
    commands,checkers=planned()
    assert invocation['planned_commands']==commands and invocation['planned_checkers']==checkers
    native_path=absolute(invocation['pure_proof_path'])
    assert native_path.parent.parent==CASE/'test-output'
    native_receipt={'pure_proof_directory':str(native_path.parent),'pure_proof_path':str(native_path),
        'pure_proof_sha256':invocation['pure_proof_sha256'],'manifest_sha256':approval['manifest_sha256'],
        'source_map_sha256':approval['source_map_sha256'],'source_hashes_after_pure':source_map,
        'pure_checks':invocation['pure_checks']}
    native_proof=pure_proof(native_receipt,source_map,'native')
    assert utc(native_proof['started_utc'])>=utc(pure_proof(preflight,source_map,'preflight')['completed_utc'])
    started=utc(invocation['created_utc'])
    assert started>=utc(native_proof['completed_utc'])
    assert closure['invocation_sha256']==seal(raw/'invocation.json')['sha256']
    assert closure['source_hashes_after']==source_map
    assert closure['error'] in (None,'') and closure['step_error'] in (None,'')
    raw_map=closure['raw']
    assert type(raw_map) is dict and len(raw_map)==23
    assert set(raw_map)==set('input.json model.sxi import.log import-stdout.txt import-stderr.txt roundtrip-raw.json export.log export-stdout.txt export-stderr.txt roundtrip-validation.json check_import_export-stderr.txt model.sxo model.log model-run.log calc-stdout.txt calc-stderr.txt report-raw.json report-export.log jsonreport-stdout.txt jsonreport-stderr.txt author-validation.json check_behavior-stderr.txt steps.json'.split())
    assert {p.name for p in raw.iterdir() if p.is_file()}==set(raw_map)|{'invocation.json','closure.json'}
    for name,spec in raw_map.items():
        assert type(name) is str and '/' not in name and '\\' not in name and name not in ('invocation.json','closure.json')
        path=raw/name
        assert not path.is_symlink() and not (path.stat().st_file_attributes&0x400)
        exact(path,spec,readonly=True)
    for special in ('invocation.json','closure.json'):
        path=raw/special
        assert not path.is_symlink() and not (path.stat().st_file_attributes&0x400)
        exact(path,seal(path),readonly=True)
    steps=receipt_json((raw/'steps.json').read_bytes())
    assert type(steps) is list and len(steps)==6 and [step['name'] for step in steps]==STAGES
    previous=started
    for index,step in enumerate(steps):
        keys(step,STEP_KEYS)
        integer(step['sequence'],index); integer(step['exit_code'],0); integer(step['child_session_id'],0)
        assert type(step['child_pid']) is int and step['child_pid']>0
        assert step['capture_error'] is None and step['error'] is None and step['status']=='completed'
        boolean(step['gui_preserved'],True); boolean(step['converter_log_validated'],index==3)
        start,end=utc(step['started_utc']),utc(step['completed_utc'])
        assert previous<=start<=end; previous=end
        command=(checkers[0] if index==2 else checkers[1] if index==5 else commands[0 if index==0 else 1 if index==1 else 2 if index==3 else 3])
        keys(command,{'name','program','arguments'})
        assert all(step[field]==command[field] for field in ('name','program','arguments'))
        stdout='roundtrip-validation.json' if index==2 else 'author-validation.json' if index==5 else step['name']+'-stdout.txt'
        stderr=step['name']+'-stderr.txt'
        for stream,filename in [('stdout',stdout),('stderr',stderr)]:
            assert step[stream+'_path']==str(RUN/filename)
            exact(raw/filename,{'bytes':step[stream+'_bytes'],'sha256':step[stream+'_sha256']},readonly=True)
        integer(step['stderr_bytes'],0)
        if index==3:
            exact(raw/'model-run.log',{'bytes':step['converter_log_bytes'],'sha256':step['converter_log_sha256']},readonly=True)
        else:
            assert step['converter_log_bytes'] is None and step['converter_log_sha256'] is None
    assert seal(raw/'input.json')['sha256']==INPUT_SHA
    assert converter_bytes((raw/'model-run.log').read_bytes())==15
    authored,expected_export=source_oracles()
    actual_export=strict_json((raw/'roundtrip-raw.json').read_bytes())
    actual_input=strict_json((raw/'input.json').read_bytes())
    keys(expected_export,{'model'}); keys(actual_export,{'model'}); keys(actual_input,{'model'})
    keys(expected_export['model'],{'database_version','tables'}); keys(actual_export['model'],{'database_version','tables'})
    assert typed(expected_export['model']['database_version'],actual_export['model']['database_version'])
    assert compare_tables(authored['model']['tables'],actual_input['model']['tables'])==(32,25,284)
    assert compare_tables(expected_export['model']['tables'],actual_export['model']['tables'])==(32,36,379)
    patterns=strict_json(exact(CASE/'preserved-oracle/log-patterns.json',{'bytes':87444,'sha256':PATTERN_SHA},readonly=True))
    reports=strict_json(exact(CASE/'preserved-oracle/report-predicates.json',{'bytes':1380881,'sha256':REPORT_RULES_SHA},readonly=True))
    observed=read_log((raw/'model.log').read_bytes(),patterns)
    assert check_report((raw/'report-raw.json').read_bytes(),reports,observed)==4044
    checker_receipt((raw/'roundtrip-validation.json').read_bytes(),'check_import_export',raw)
    checker_receipt((raw/'author-validation.json').read_bytes(),'check_behavior',raw)
    return {'decision':'GO_BOUNDED','full_lines':222,'timed_lines':186,'report_cells':4044,
            'authored_cells':284,'export_cells':379,'raw_files':25}


def converter_fixture():
    parent=exact(PARENT_RUN/'run.log',{'bytes':929,'sha256':PARENT_CONVERTER_SHA}).decode('utf-8')
    old=str(PARENT_RUN); new=str(RUN)
    assert parent.count(old)==2 and parent.count(old.replace('\\','/'))==1
    return parent.replace(old,new).replace(old.replace('\\','/'),new.replace('\\','/')).encode('utf-8')


def main():
    if len(sys.argv)==3 and sys.argv[1] in ('--inventory-candidate','--manifest-candidate'):
        candidate=absolute(sys.argv[2])
        assert candidate.is_file() and not candidate.is_relative_to(CASE) and candidate.stat().st_file_attributes&1
        if sys.argv[1]=='--inventory-candidate':
            doc=source_inventory(candidate)
            return {'decision':'PASS_INVENTORY_CANDIDATE','source_count':doc['source_count'],'candidate_sha256':seal(candidate)['sha256']}
        doc,_=manifest_document(candidate)
        return {'decision':'PASS_MANIFEST_CANDIDATE','source_count':doc['source_count'],'candidate_sha256':seal(candidate)['sha256']}
    if len(sys.argv)==2 and sys.argv[1]=='--pure':
        source_oracles()
        parent_log=exact(PARENT_RUN/'model.log',{'bytes':18758,'sha256':PARENT_LOG_SHA})
        patterns=strict_json(exact(CASE/'preserved-oracle/log-patterns.json',{'bytes':87444,'sha256':PATTERN_SHA},readonly=True))
        reports=strict_json(exact(CASE/'preserved-oracle/report-predicates.json',{'bytes':1380881,'sha256':REPORT_RULES_SHA},readonly=True))
        observed=read_log(parent_log,patterns,child=False)
        assert check_report(exact(PARENT_RUN/'report-raw.json',{'bytes':104356,'sha256':'fcf9a124546e77fb96871b5bf4b5e111774c00616bfed69c19ad7f1b6c08b4bf'}),reports,observed)==4044
        assert converter_bytes(converter_fixture())==15
        return {'decision':'PASS_PURE_ORACLES','physical_lines':222,'report_cells':4044}
    if len(sys.argv)==2 and sys.argv[1]=='--preflight':
        receipts=list((CASE/'review').glob('preflight-ssh0-*.json'))
        assert len(receipts)==1
        preflight_receipt(receipts[0])
        return {'decision':'PASS_ACTUAL_ZERO_NATIVE_PREFLIGHT'}
    if len(sys.argv)==3 and sys.argv[1]=='--evidence-dir':
        return sealed_replay(absolute(sys.argv[2]))
    raise AssertionError('Use --inventory-candidate, --manifest-candidate, --pure, --preflight, or --evidence-dir')


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True))
