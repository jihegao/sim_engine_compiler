"""PURE, in-memory negatives for the independent I03.var08 reader."""
import copy
import importlib.util
import json
import math
import pathlib
import struct
import tempfile

HERE=pathlib.Path(__file__).resolve().parent
SOURCE=HERE/"independent_replay.py"
if not SOURCE.is_file():
    SOURCE=HERE/"i03-var08-independent-replay-draft-v1.py"
spec=importlib.util.spec_from_file_location("i03var08reviewer",SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c=m.parse_json(m.CONTRACT.read_bytes())
assert m.pure(c)["report_cells"]==5210
source=m.expected_source(c)
old_catalog=m.parse_json((m.PKG/"preserved-context/context-17.bytes").read_bytes())
append_catalog=copy.deepcopy(old_catalog)
new_entry=copy.deepcopy(old_catalog["entries"][-1]);new_entry["publication_id"]="I03.var08.synthetic_append_only"
append_catalog["entries"].append(new_entry)
assert m.validate_catalog_prefix(old_catalog,append_catalog)==495
export=copy.deepcopy(source)
for t in export["model"]["tables"]:
    if not t["instances"][0]["rows"]:
        t["instances"][0]["rows"]=[[None]*len(t["columns"])]
expected_log=m.expected_log()
assert m.verify_log(("\n".join(m.expected_log(7))+"\n").encode())==113
expected_report={"report":m.expected_report(c,True)}
rejected=[]


def reject(label, fn):
    try: fn()
    except (AssertionError,ValueError,KeyError,TypeError,UnicodeDecodeError): rejected.append(label)
    else: raise AssertionError("escaped mutation: "+label)


def source_mut(label, f):
    x=copy.deepcopy(source);f(x);reject(label,lambda:m.verify_source(c,x))


def export_mut(label, f):
    x=copy.deepcopy(export);f(x);reject(label,lambda:m.verify_export(source,x))


def report_mut(label, f):
    x=copy.deepcopy(expected_report);f(x);reject(label,lambda:m.verify_report(c,x))


def log_mut(label, f, bypass_literal=False):
    x=expected_log.copy();f(x)
    raw=("\n".join(x)+"\n").encode()
    if not bypass_literal:
        reject(label,lambda:m.verify_log(raw))
        return
    # Stand in for a hypothetical re-sealed expected transcript: the physical
    # ledger must still reject this semantic mutation beyond literal matching.
    saved=m.verify_log.__globals__["expected_log"]
    m.verify_log.__globals__["expected_log"]=lambda _id=0:x.copy()
    try: reject(label,lambda:m.verify_log(raw))
    finally:m.verify_log.__globals__["expected_log"]=saved


source_mut("PDESC",lambda x:x["model"]["tables"][0]["instances"][0]["rows"][0].__setitem__(0,"other"))
source_mut("transfer_key_bool_integer",lambda x:x["model"]["tables"][23]["columns"][0].__setitem__("key",1))
source_mut("TFQTY_bool",lambda x:x["model"]["tables"][23]["instances"][0]["rows"][0].__setitem__(4,True))
source_mut("TFDT_one",lambda x:x["model"]["tables"][23]["instances"][0]["rows"][0].__setitem__(5,1.0))
source_mut("transfer_table_duplicate",lambda x:x["model"]["tables"].append(copy.deepcopy(x["model"]["tables"][23])))
source_mut("table_reorder",lambda x:x["model"]["tables"].__setitem__(slice(22,24),list(reversed(x["model"]["tables"][22:24]))))
source_mut("database_version_bool",lambda x:x["model"].__setitem__("database_version",True))
export_mut("all_null_width",lambda x:x["model"]["tables"][5]["instances"][0]["rows"][0].pop())
export_mut("extra_export_row",lambda x:x["model"]["tables"][23]["instances"][0]["rows"].append(copy.deepcopy(x["model"]["tables"][23]["instances"][0]["rows"][0])))
export_mut("export_metadata_bool_integer",lambda x:x["model"]["tables"][23]["columns"][0].__setitem__("key",1))
export_mut("export_extra_metadata",lambda x:x["model"]["tables"][23].__setitem__("extra",0))
reject("JSON_duplicate_key",lambda:m.parse_json(b'{"a":1,"a":2}'))
reject("JSON_nonfinite_literal",lambda:m.parse_json(b'{"a":NaN}'))
reject("JSON_exponent_overflow",lambda:m.parse_json(b'{"a":{"b":1e999}}'))
parent_report_bytes=(m.ACCEPTED/"report-raw.json").read_bytes()
assert m.parse_json(parent_report_bytes,native=True)["report"]
reject("unexpected_native_trailing_comma",lambda:m.parse_json(parent_report_bytes.replace(b']',b',]',1),native=True))
reject("roundtrip_json_must_be_strict",lambda:m.parse_json(b'{"model":{"tables":[]},}'))
def catalog_mut(label,f):
    x=copy.deepcopy(append_catalog);f(x);reject(label,lambda:m.validate_catalog_prefix(old_catalog,x))
catalog_mut("catalog_metadata_bool",lambda x:x.__setitem__("as_of",True))
catalog_mut("catalog_prefix_changed",lambda x:x["entries"][0].__setitem__("new_native_runs",True))
catalog_mut("catalog_duplicate_publication_id",lambda x:x["entries"][-1].__setitem__("publication_id",x["entries"][-2]["publication_id"]))
catalog_mut("catalog_appended_id_bool",lambda x:x["entries"][-1].__setitem__("publication_id",True))

def replace_sub(x, old, new):
    matches=[i for i,s in enumerate(x) if old in s]
    assert len(matches)==1,(old,matches)
    x[matches[0]]=x[matches[0]].replace(old,new)

log_mut("transfer_qty_two",lambda x:replace_sub(x,"starts with 1 resources","starts with 2 resources"),True)
log_mut("transfer_arrival_duplicate",lambda x:x.insert(next(i for i,s in enumerate(x) if "resource transfer task 0 (OUT)  arrives" in s)+1,m.TRANSFER_LINES[-1]),True)
log_mut("transfer_arrival_missing",lambda x:x.pop(next(i for i,s in enumerate(x) if "resource transfer task 0 (OUT)  arrives" in s)),True)
log_mut("allocation_available_wrong",lambda x:replace_sub(x,"allocated to maintenance task: 1  available now: 1","allocated to maintenance task: 1  available now: 2"),True)
log_mut("deallocation_available_wrong",lambda x:replace_sub(x,"deallocated from  maintenance task: 1  available now: 1","deallocated from  maintenance task: 1  available now: 2"),True)
log_mut("shift_free_wrong",lambda x:x.__setitem__(next(i for i,s in enumerate(x) if s.startswith("Time: 26  resource shift 3 starting"))+1,"  Free resources at: <BASE-01,0> P-CREW 2"),True)
log_mut("extra_known_transfer_line",lambda x:x.insert(next(i for i,s in enumerate(x) if "resource transfer task 0 (OUT)  starts" in s),m.TRANSFER_LINES[2]))
log_mut("unknown_timed",lambda x:x.insert(next(i for i,s in enumerate(x) if s.startswith("Time: 25  resource shift 2 created")),"Time: 24.75  unknown event"))
log_mut("moved_transfer_arrival",lambda x:replace_sub(x,"Time: 24.75  resource transfer task 0 (OUT)  arrives","Time: 26  resource transfer task 0 (OUT)  arrives"))
log_mut("mission_changed",lambda x:replace_sub(x,"mission starting, duration: 1","mission starting, duration: 2"))
log_mut("MAXUT_diagnostic_changed",lambda x:replace_sub(x,"set time to max utilisation: 0","set time to max utilisation: 1"))
log_mut("mismatched_task_id",lambda x:replace_sub(x,"resource transfer task 0 (OUT)  arrives","resource transfer task 7 (OUT)  arrives"))
log_mut("terminal_ready_missing_semantic",lambda x:replace_sub(x,
    "Time: 29 <TEACH-AIR-01,1> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>",
    "Time: 29 <TEACH-AIR-01,1> Next random failure will occur 1e+010"),True)

def row(t,j):return next(x for x in expected_report["report"]["tables"] if x["name"]==t)["instances"][0]["rows"][j]
def mutate_row(x,t,j,k,value):
    z=next(y for y in x["report"]["tables"] if y["name"]==t)
    n=[v["name"] for v in z["columns"]].index(k)
    z["instances"][0]["rows"][j][n]=value

report_mut("resource_NR_half_bin",lambda x:mutate_row(x,"ResourceResults",49,"NR",1))
report_mut("resource_NRA_half_bin",lambda x:mutate_row(x,"ResourceResults",49,"NRA",2))
report_mut("system_NSYMP",lambda x:mutate_row(x,"SystemResults",47,"NSYMP",1))
report_mut("stock_PNB",lambda x:mutate_row(x,"StockTotalResults",0,"PNB",0))
report_mut("stock_null_to_zero",lambda x:mutate_row(x,"StockTotalResults",0,"ROS",0))
report_mut("NREP_bool",lambda x:mutate_row(x,"ResultSummary",0,"NREP",True))
report_mut("extra_report_row",lambda x:next(y for y in x["report"]["tables"] if y["name"]=="ResourceResults")["instances"][0]["rows"].append(copy.deepcopy(row("ResourceResults",0))))
report_mut("column_key_bool_integer",lambda x:next(y for y in x["report"]["tables"] if y["name"]=="ResourceResults")["columns"][0].__setitem__("key",1))
report_mut("report_extra_root",lambda x:x.__setitem__("extra",0))
report_mut("report_extra_table_metadata",lambda x:x["report"]["tables"][0].__setitem__("extra",0))
report_mut("report_extra_instance_metadata",lambda x:x["report"]["tables"][0]["instances"][0].__setitem__("extra",0))
report_mut("system_null_to_zero",lambda x:mutate_row(x,"SystemResults",0,"SYDT",0))
for col in ("NR","NRA","NRN","NRUM","NRW"):
    t=next(y for y in expected_report["report"]["tables"] if y["name"]=="ResourceResultsTotal")
    idx=[v["name"] for v in t["columns"]].index(col)
    val=t["instances"][0]["rows"][0][idx]
    def one_ulp(x,col=col,val=val):
        z=next(y for y in x["report"]["tables"] if y["name"]=="ResourceResultsTotal")
        i=[v["name"] for v in z["columns"]].index(col)
        u=struct.unpack("<I",struct.pack("<f",float(val)))[0]+1
        z["instances"][0]["rows"][0][i]=struct.unpack("<f",struct.pack("<I",u))[0]
    report_mut("total_"+col+"_plus_one_ULP",one_ulp)

with tempfile.TemporaryDirectory(prefix="i03-var08-pure-proof-") as scratch:
    proof_dir=pathlib.Path(scratch)
    source_map={"runner_script":"a"*64}
    manifest_raw=b"PURE_PROOF_FIXTURE_ONLY"
    proof={"schema":"i03-var08-idle-maxut-pure-proof/v1","mode":"preflight",
        "run_id":m.RUN_ID,"manifest_sha256":m.sha(manifest_raw),
        "source_map_sha256":m.source_map_sha(source_map),
        "started_utc":"2026-10-08T00:00:00+00:00",
        "completed_utc":"2026-10-08T00:00:12+00:00",
        "status":"passed","error":None,"checks":[],
        "source_hashes_after":source_map.copy()}
    for i,tool in enumerate(m.PROOF_TOOLS):
        stem=pathlib.Path(tool).stem
        stdout=proof_dir/f"{stem}-stdout.bin"
        stderr=proof_dir/f"{stem}-stderr.bin"
        stdout.write_bytes((f"PURE {tool}\n").encode())
        stderr.write_bytes(b"")
        proof["checks"].append({"tool":tool,"program":m.PYTHON,
            "arguments":f'-X utf8 -B "{m.PKG/tool}"',
            "started_utc":f"2026-10-08T00:00:{i*2:02d}+00:00",
            "completed_utc":f"2026-10-08T00:00:{i*2+1:02d}+00:00",
            "status":"completed","error":None,"child_pid":1000+i,
            "child_session_id":0,"exit_code":0,"capture_error":None,
            "stdout_path":str(stdout),"stderr_path":str(stderr),
            "stdout_bytes":stdout.stat().st_size,"stderr_bytes":0,
            "stdout_sha256":m.sha(stdout.read_bytes()),
            "stderr_sha256":m.sha(stderr.read_bytes())})
    proof_path=proof_dir/"pure-proof.json"
    def proof_call(obj):
        raw=json.dumps(obj,separators=(",",":")).encode()
        proof_path.write_bytes(raw)
        return m.verify_pure_proof(proof_path,"preflight",manifest_raw,source_map,m.sha(raw))
    assert proof_call(proof)["status"]=="passed"
    def proof_mut(label,f):
        obj=copy.deepcopy(proof);f(obj)
        reject(label,lambda:proof_call(obj))
    proof_mut("proof_exit_bool",lambda x:x["checks"][0].__setitem__("exit_code",True))
    proof_mut("proof_wrong_argv",lambda x:x["checks"][0].__setitem__("arguments",'-X utf8 -B "other.py"'))
    proof_mut("proof_wrong_tool",lambda x:x["checks"][0].__setitem__("tool","other.py"))
    proof_mut("proof_wrong_stream_path",lambda x:x["checks"][0].__setitem__("stdout_path",x["checks"][1]["stdout_path"]))
    proof_mut("proof_wrong_stream_size",lambda x:x["checks"][0].__setitem__("stdout_bytes",1))
    proof_mut("proof_wrong_stream_hash",lambda x:x["checks"][0].__setitem__("stdout_sha256","0"*64))
    proof_mut("proof_wrong_session",lambda x:x["checks"][0].__setitem__("child_session_id",1))
    proof_mut("proof_wrong_order",lambda x:x["checks"][1].__setitem__("started_utc","2026-10-07T23:59:00+00:00"))
    proof_mut("proof_after_source_drift",lambda x:x["source_hashes_after"].__setitem__("runner_script","b"*64))
    proof_mut("proof_native_mode",lambda x:x.__setitem__("mode","native"))
    proof_mut("proof_failed_status",lambda x:x.__setitem__("status","failed"))

gui={"pid":13340,"session_id":1,"start_unix_ms":1790590196826,"responding":True}
assert m.verify_gui(gui) is None
reject("preflight_gui_bool_session",lambda:m.verify_gui({**gui,"session_id":True}))
reject("invocation_gui_integer_responding",lambda:m.verify_gui({**gui,"responding":1}))
assert m.require_core_owned(set(m.CORE_OWNED)) is None
reject("coordinated_manifest_inventory_missing_capture_helper",
       lambda:m.require_core_owned(set(m.CORE_OWNED)-{"captured_process.ps1"}))
reject("coordinated_manifest_inventory_missing_context_copy",
       lambda:m.require_core_owned(set(m.CORE_OWNED)-{"preserved-context/context-17.bytes"}))
reject("coordinated_manifest_inventory_invented_owned",
       lambda:m.require_core_owned(set(m.CORE_OWNED)|{"invented-helper.py"}))

print(json.dumps({"mode":"PURE_SYNTHETIC_ONLY","report_cells":5210,"rejections":len(rejected),"labels":rejected},sort_keys=True))
