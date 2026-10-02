"""Independent read-only H01.var02 simultaneous-fields replay; standard library only."""
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
PARENT = ROOT / "H01-var02-rate-no-consequence-v1.0.0/rate-input.json"
RUNS = {
    "control": CASE / "runs/h01-var02-mutual-control-v100-ssh-20261002-01",
    "simultaneous": CASE / "runs/h01-var02-mutual-simultaneous-v100-ssh-20261002-01",
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
ck("accepted rate parent hash", sha(PARENT) == contract["accepted_parent"]["sha256"])
ck("control byte-identical parent", (CASE / "control-input.json").read_bytes() == PARENT.read_bytes())
ck("control source hash", sha(CASE / "control-input.json") == contract["sources_sha256"]["control"])
ck("simultaneous source hash", sha(CASE / "simultaneous-input.json") == contract["sources_sha256"]["simultaneous"])
ck("exact diff hash", sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"])
for key, p in {
    "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
    "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
    "simlox_exe": INSTALL / "Simlox.exe",
}.items():
    ck(f"installed {key} fingerprint", sha(p) == contract["installed_source_sha256"][key])

source = {arm: tables(read(CASE / f"{arm}-input.json")) for arm in RUNS}
ck("same source table set", set(source["simultaneous"]) == set(source["control"]))
ck("changed tables only MissionDamage and PDESC", {k for k in source["control"]
   if source["control"][k] != source["simultaneous"][k]}
   == {"MissionDamage", "ProblemDescription"})
ck("rate control row", rows(source["control"]["MissionDamage"])
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 0, 3000000, None]])
ck("simultaneous child row", rows(source["simultaneous"]["MissionDamage"])
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 1, 3000000, None]])
ck("consequence unchanged at zero", rows(source["control"]["DamageItem"])
   == rows(source["simultaneous"]["DamageItem"])
   == [["BATTLE-HIT", "TEACH-AIR-01", "<ATTRITION>", 0, None, None, None]])
ck("exact diff lineage", diff["parent_sha256"] == sha(PARENT)
   and diff["child_sha256"] == sha(CASE / "simultaneous-input.json"))
ck("exact diff objects", diff["changed_tables"] == {k: {
   "before": source["control"][k], "after": source["simultaneous"][k]}
   for k in ("MissionDamage", "ProblemDescription")}
   and diff["mission_damage_changed_fields"] == ["DAMP"]
   and diff["unchanged_table_count"] == len(source["control"]) - 2)

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
    ck(f"{arm} authored row table count", len(populated) == 16)
    for name in populated:
        ck(f"{arm} exact roundtrip {name}", name in rt
           and cols(source[arm][name]) == cols(rt[name])
           and rows(source[arm][name]) == rows(rt[name]))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{arm} warnings 108 and 126", "warning #108" in calc and "warning #126" in calc)
    ck(f"{arm} no other warnings", set(re.findall(r"warning #(\d+)", calc)) == {"108", "126"})
    ck(f"{arm} nonempty SXI", (run / "model.sxi").stat().st_size > 1000)
    if arm == "simultaneous":
        ck("simultaneous relevant #253 diagnostic", "Form: MissionDamage" in calc
           and "rec 1: (error #253) DAMP and DAMRT cannot both be used for a certain MTID-DAMID combination" in calc)
        ck("simultaneous one converter error", "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in calc
           and re.findall(r"error #(\d+)", calc) == ["253"])
        ck("simultaneous invalid four-byte SXO", (run / "model.sxo").stat().st_size == 4)
        ck("simultaneous no event/report artifacts", not (run / "model.log").exists()
           and not (run / "report-raw.json").exists()
           and not (run / "report-export.log").exists())
        ck("simultaneous no simulation start", "Starting simulation" not in calc)
        observed[arm] = {"run_id": run.name, "converter_error": 253,
                         "converter_errors": 1, "sxo_bytes": 4, "has_report": False}
        continue
    ck("control converter zero errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc
       and not re.search(r"error #\d+", calc))
    ck("control valid SXO/report", (run / "model.sxo").stat().st_size > 1000
       and (run / "report-raw.json").stat().st_size > 1000)
    event = (run / "model.log").read_text(encoding="utf-8-sig")
    for idx, start in enumerate((8, 20, 32)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{idx}>"
        for hour, phrase in ((start - 1, "mission activated, systems requested: 1"),
                             (start, "mission starting, duration: 2"),
                             (start + 2, "mission success:"),
                             (start + 2, "mission completed:")):
            ck(f"control mission {idx} {phrase}", f"Time: {hour} {mid} {phrase}" in event)
        ck(f"control mission {idx} aircraft", f"Time: {start-1} {mid} mission allocates system: <TEACH-AIR-01,0>" in event)
        ck(f"control mission {idx} return ready", f"Time: {start+2} <TEACH-AIR-01,0> nbr ready increased at unit:" in event)
    times = [float(t) for t in re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured", event)]
    expected_times = [8.18829, 9.0828, 9.32945, 9.62341, 9.95328,
                      21.4989, 21.6238, 33.0466, 33.4931, 33.8743]
    ck("control exact ten rate hits", times == expected_times)
    ck("control hits strictly in three missions", all(any(start < t < start + 2 for start in (8, 20, 32)) for t in times))
    ck("control no attrition/abort", "subject to attrition" not in event and "mission aborted" not in event)
    rep = tables(read(run / "report-raw.json", native=True))
    ck("control report tables", {"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rep))
    sys = recs(rep["SystemResults"])
    stock = recs(rep["StockTotalResults"])
    summary = recs(rep["ResultSummary"])
    ck("control 72+72 report bins", len(sys) == len(stock) == 72 and len(summary) == 1)
    for i, (s, st) in enumerate(zip(sys, stock)):
        a, b = i / 2, (i + 1) / 2
        ck(f"control system bin {i} identity/time", s["UNID"] == "Total over all Units"
           and s["SID"] == "Total over all Systems"
           and close(s["STINT"], a) and close(s["ETINT"], b))
        ck(f"control stock bin {i} time", close(st["STINT"], a) and close(st["ETINT"], b))
        exp = {k: 0 for k in s if k not in ("UNID", "SID", "STINT", "ETINT")}
        active = any(start <= a < start + 3 for start in (7, 19, 31))
        flight = any(start <= a < start + 2 for start in (8, 20, 32))
        preflight = any(start <= a < start + 1 for start in (7, 19, 31))
        exp.update(NSYRY=0 if active else 1, NSYMA=1 if active else 0,
                   NSYMR=1 if preflight else 0, NSYMO=1 if flight else 0,
                   NSYA=1, FTMO=1 if flight else 0,
                   STACC=1 if flight else 0,
                   NDAM=sum(a <= t < b for t in times), SYDT=None)
        for k, value in exp.items():
            ck(f"control system {i} {k}", s[k] is None if value is None else close(s[k], value))
        stock_exp = {k: 0 for k in st if k not in ("STINT", "ETINT")}
        stock_exp["PNB"] = 1
        for k in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            stock_exp[k] = None
        for k, value in stock_exp.items():
            ck(f"control stock {i} {k}", st[k] is None if value is None else close(st[k], value))
    ck("control six aircraft flight hours", close(sum(s["NSYMO"] * .5 for s in sys), 6))
    ck("control ten NDAM counts", sum(s["NDAM"] for s in sys) == 10)
    ck("control terminal one ready", close(sys[-1]["NSYRY"], 1) and close(sys[-1]["NSYA"], 1))
    sm = summary[0]
    ck("control summary", sm == {"NREP": 1, "RTILW": 0, "RTIUP": 36,
       "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0, "MSUF": 1,
       "RSMSUF": 0, "STMF": 1, "RSSTMF": 0})
    observed[arm] = {"run_id": run.name, "converter_errors": 0,
                     "sxo_bytes": (run / "model.sxo").stat().st_size,
                     "system_bins": len(sys), "stock_bins": len(stock),
                     "aircraft_flight_hours": sum(s["NSYMO"] * .5 for s in sys),
                     "hit_times": times}

result = {
    "schema": "independent-h01-var02-simultaneous-readonly-review/v1",
    "passed": not fails, "verdict": "GO" if not fails else "NO-GO",
    "checks_passed": checks - len(fails), "checks_total": checks, "failures": fails,
    "observed": observed,
    "scope": "GO applies only to this installed converter rejecting simultaneous DAMP=1 and DAMRT=3000000 for the same mission-damage key with exact error #253, alongside a valid unchanged rate control.",
    "limits": [
        "The four-byte child SXO and absent event/report artifacts provide no child damage or attrition behavior evidence.",
        "Other positive field combinations, mission models, GUI visual operation and other engine versions are untested.",
        "A calc exit code of zero in the child is not a successful conversion or simulation.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if fails:
    print("\n".join(fails[:30]))
raise SystemExit(0 if not fails else 1)
