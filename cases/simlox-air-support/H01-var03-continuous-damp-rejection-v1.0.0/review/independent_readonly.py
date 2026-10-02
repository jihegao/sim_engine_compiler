"""Independent read-only H01.var03 replay; standard library only."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
REVIEW = CASE / "review"
OUT = REVIEW / "independent-readonly-2026-10-02.json"
ROOT = CASE.parent
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
PARENT = ROOT / "A05-continuous-baseline-v1.0.1/native-continuous.json"
RUNS = {
    "control": CASE / "runs/h01-var03-control-v100-ssh-20261002-01",
    "damp": CASE / "runs/h01-var03-damp-v100-ssh-20261002-01",
}
fails: list[str] = []
checks = 0


def ck(label, condition):
    global checks
    checks += 1
    if not condition:
        fails.append(label)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p, native=False):
    s = p.read_text(encoding="utf-8-sig")
    if native:
        s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def tables(x):
    return {t["name"]: t for t in x.get("model", x.get("report"))["tables"]}


def cols(t):
    return [c["name"] for c in t["columns"]]


def rows(t):
    return [r for inst in t["instances"] for r in inst["rows"]]


def recs(t):
    return [dict(zip(cols(t), r)) for r in rows(t)]


def close(a, b, tol=1e-7):
    return isinstance(a, (int, float)) and math.isclose(a, b, rel_tol=0, abs_tol=tol)


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
ck("accepted A05 parent hash", sha(PARENT) == contract["accepted_parent"]["sha256"])
ck("control byte-identical parent", (CASE / "control-input.json").read_bytes() == PARENT.read_bytes())
ck("control source hash", sha(CASE / "control-input.json") == contract["sources_sha256"]["control"])
ck("DAMP source hash", sha(CASE / "damp-input.json") == contract["sources_sha256"]["damp"])
ck("exact diff hash", sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"])
for key, p in {
    "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
    "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
    "simlox_exe": INSTALL / "Simlox.exe",
}.items():
    ck(f"installed {key} fingerprint", sha(p) == contract["installed_source_sha256"][key])

source = {arm: tables(read(CASE / f"{arm}-input.json")) for arm in RUNS}
ck("DAMP adds only three tables", set(source["damp"]) - set(source["control"])
   == {"DamageType", "MissionDamage", "DamageItem"})
ck("DAMP removes no tables", set(source["control"]) <= set(source["damp"]))
ck("existing table delta only PDESC", {k for k in source["control"]
   if source["control"][k] != source["damp"][k]} == {"ProblemDescription"})
ck("DAMP row", rows(source["damp"]["MissionDamage"])
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 1, None, None]])
ck("attrition consequence row", rows(source["damp"]["DamageItem"])
   == [["BATTLE-LOSS", "TEACH-AIR-01", "<ATTRITION>", 1, None, None, None]])
mission_type = recs(source["damp"]["MissionType"])[0]
ck("mission remains CONTINUOUS", mission_type["MPAT"] == "CONTINUOUS"
   and mission_type["TFOUT"] is None and mission_type["TFRET"] is None)
ck("exact diff lineage", diff["parent_sha256"] == sha(PARENT)
   and diff["control_sha256"] == sha(CASE / "control-input.json")
   and diff["damp_sha256"] == sha(CASE / "damp-input.json"))
ck("exact diff tables", diff["added_tables"] == {k: source["damp"][k]
   for k in ("DamageItem", "DamageType", "MissionDamage")}
   and not diff["removed_tables"]
   and diff["changed_tables"] == {"ProblemDescription": {
       "before": source["control"]["ProblemDescription"],
       "after": source["damp"]["ProblemDescription"]}}
   and diff["unchanged_table_count"] == len(source["control"]) - 1)

observed = {}
for arm, run in RUNS.items():
    inv = read(run / "invocation.json")
    cl = read(run / "closure.json")
    steps = read(run / "steps.json")
    ck(f"{arm} run identity", inv["run_id"] == cl["run_id"] == run.name)
    ck(f"{arm} sealed invocation", cl["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{arm} run/source input", inv["input_sha256"] == sha(CASE / f"{arm}-input.json")
       == sha(run / "input.json"))
    ck(f"{arm} parent seal", inv["parent_sha256"] == sha(PARENT))
    ck(f"{arm} session-zero SSH", inv["execution_mode"] == "ssh_cli_v1"
       and inv["session_id"] == 0 and inv["ssh_connection_present"]
       and "sshd.exe" in [s.lower() for s in inv["ssh_ancestor_names"]])
    ck(f"{arm} GUI and queue", inv["gui"]["pid"] == 13340
       and inv["gui"]["session_id"] == 1
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    expected_steps = (["import", "export", "calc", "jsonreport", "check_import_export"]
                      if arm == "control" else ["import", "export", "calc", "check_import_export"])
    ck(f"{arm} ordered steps", [s["name"] for s in steps] == expected_steps)
    for s in steps:
        ck(f"{arm} step {s['name']} outcome", s["exit_code"] == 0
           and s["gui_preserved"] and not s["error"]
           and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed")
           and s["started_utc"] <= s["completed_utc"])
    ck(f"{arm} command binding", all(s["arguments"] == p["arguments"]
       for s, p in zip(steps[:3], inv["planned_commands"])))
    if arm == "control":
        ck("control report command binding", steps[3]["arguments"] == inv["planned_report"]["arguments"])
    ck(f"{arm} check command binding", steps[-1]["arguments"] == inv["planned_check"]["arguments"])
    ck(f"{arm} source before-after", cl["source_hashes_before"] == cl["source_hashes_after"]
       == inv["source_hashes_before"])
    paths = {
        "input": CASE / f"{arm}-input.json", "parent": PARENT,
        "contract": CASE / "contract.json",
        "manual": INSTALL / "UserDoc/SIMLOX.pdf",
        "dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
        "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
        "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "python": Path(inv["planned_check"]["executable"]),
        "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": INSTALL / "Simlox.exe",
    }
    for key, p in paths.items():
        ck(f"{arm} source seal {key}", sha(p) == cl["source_hashes_before"][key])
    expected_raw = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log",
                    "export.log", "model.sxo", "run.log", "roundtrip-validation.json", "steps.json"}
    if arm == "control":
        expected_raw |= {"model.log", "report-raw.json", "report-export.log"}
    ck(f"{arm} raw file set", set(cl["raw"]) == expected_raw)
    for name, meta in cl["raw"].items():
        data = (run / name).read_bytes()
        ck(f"{arm} raw seal {name}", len(data) == meta["bytes"]
           and hashlib.sha256(data).hexdigest() == meta["sha256"])
    rt = tables(read(run / "roundtrip-raw.json", native=True))
    populated = [k for k, t in source[arm].items() if rows(t)]
    ck(f"{arm} authored row table count", len(populated) == (13 if arm == "control" else 16))
    for name in populated:
        ck(f"{arm} exact roundtrip {name}", name in rt
           and cols(source[arm][name]) == cols(rt[name])
           and rows(source[arm][name]) == rows(rt[name]))
    calc = (run / "run.log").read_text(encoding="utf-8-sig")
    ck(f"{arm} warnings 108 and 126", "warning #108" in calc and "warning #126" in calc)
    ck(f"{arm} no other warnings", set(re.findall(r"warning #(\d+)", calc)) == {"108", "126"})
    ck(f"{arm} nonempty SXI", (run / "model.sxi").stat().st_size > 1000)
    if arm == "damp":
        ck("DAMP relevant #252 diagnostic", "Form: MissionDamage" in calc
           and "rec 1: (error #252) DAMP is not allowed for continuous or extendable type of missions" in calc)
        ck("DAMP one converter error", "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in calc
           and re.findall(r"error #(\d+)", calc) == ["252"])
        ck("DAMP invalid four-byte SXO", (run / "model.sxo").stat().st_size == 4)
        ck("DAMP no event/report artifacts", not (run / "model.log").exists()
           and not (run / "report-raw.json").exists()
           and not (run / "report-export.log").exists())
        ck("DAMP no simulation start", "Starting simulation" not in calc)
        observed[arm] = {"run_id": run.name, "converter_error": 252,
                         "converter_errors": 1, "sxo_bytes": 4, "has_report": False}
        continue
    ck("control converter zero errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc
       and not re.search(r"error #\d+", calc))
    ck("control valid SXO/report", (run / "model.sxo").stat().st_size > 1000
       and (run / "report-raw.json").stat().st_size > 1000)
    event = (run / "model.log").read_text(encoding="utf-8-sig")
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    for idx in (0, 1):
        ck(f"control aircraft {idx} allocated", f"Time: 7 {mid} mission allocates system: <TEACH-AIR-01,{idx}>" in event)
        ck(f"control aircraft {idx} returned ready", f"Time: 12 <TEACH-AIR-01,{idx}> nbr ready increased at unit:" in event)
    for hour, phrase in ((7, "mission activated, systems requested: 2"),
                         (8, "mission starting, duration: 4"),
                         (12, "mission success:"), (12, "mission completed:")):
        ck(f"control {phrase}", f"Time: {hour} {mid} {phrase}" in event)
    ck("control no damage/abort", "Damage " not in event and "mission aborted" not in event)
    rep = tables(read(run / "report-raw.json", native=True))
    ck("control report tables", {"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rep))
    sys = recs(rep["SystemResults"])
    stock = recs(rep["StockTotalResults"])
    summary = recs(rep["ResultSummary"])
    ck("control 32+32 report bins", len(sys) == len(stock) == 32 and len(summary) == 1)
    for i, (s, st) in enumerate(zip(sys, stock)):
        a, b = i / 2, (i + 1) / 2
        ck(f"control system bin {i} identity/time", s["UNID"] == "Total over all Units"
           and s["SID"] == "Total over all Systems"
           and close(s["STINT"], a) and close(s["ETINT"], b))
        ck(f"control stock bin {i} time", close(st["STINT"], a) and close(st["ETINT"], b))
        exp = {k: 0 for k in s if k not in ("UNID", "SID", "STINT", "ETINT")}
        exp.update(NSYRY=2 if a < 7 or a >= 12 else 0,
                   NSYMA=2 if 7 <= a < 12 else 0,
                   NSYMR=2 if 7 <= a < 8 else 0,
                   NSYMO=2 if 8 <= a < 12 else 0,
                   NSYA=2, FTMO=1 if 8 <= a < 12 else 0,
                   STACC=2 if 8 <= a < 12 else 0, SYDT=None)
        for k, value in exp.items():
            ck(f"control system {i} {k}", s[k] is None if value is None else close(s[k], value))
        stock_exp = {k: 0 for k in st if k not in ("STINT", "ETINT")}
        stock_exp["PNB"] = 1
        for k in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            stock_exp[k] = None
        for k, value in stock_exp.items():
            ck(f"control stock {i} {k}", st[k] is None if value is None else close(st[k], value))
    ck("control 8 aircraft flight hours", close(sum(s["NSYMO"] * .5 for s in sys), 8))
    ck("control terminal two ready", close(sys[-1]["NSYRY"], 2) and close(sys[-1]["NSYA"], 2))
    sm = summary[0]
    ck("control summary", sm == {"NREP": 1, "RTILW": 0, "RTIUP": 16,
       "MTMF": 1, "RSMTMF": 0, "MSTF": 0, "RSMSTF": 0, "MSUF": 0,
       "RSMSUF": 0, "STMF": 1, "RSSTMF": 0})
    observed[arm] = {"run_id": run.name, "converter_errors": 0,
                     "sxo_bytes": (run / "model.sxo").stat().st_size,
                     "system_bins": len(sys), "stock_bins": len(stock),
                     "aircraft_flight_hours": sum(s["NSYMO"] * .5 for s in sys)}

result = {
    "schema": "independent-h01-var03-readonly-review/v1",
    "passed": not fails, "verdict": "GO" if not fails else "NO-GO",
    "checks_passed": checks - len(fails), "checks_total": checks, "failures": fails,
    "observed": observed,
    "scope": "GO applies only to this installed converter rejecting DAMP=1 on the unchanged CONTINUOUS mission with exact error #252, alongside a valid unchanged continuous control.",
    "limits": [
        "The four-byte child SXO and absent event/report artifacts provide no child damage or attrition behavior evidence.",
        "DAMRT, intermediate DAMP, other missions, GUI visual operation and other engine versions are untested.",
        "A calc exit code of zero in the child is not a successful conversion or simulation.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if fails:
    print("\n".join(fails[:30]))
raise SystemExit(0 if not fails else 1)
