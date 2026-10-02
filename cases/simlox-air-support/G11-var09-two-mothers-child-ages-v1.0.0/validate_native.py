"""Read-only author replay of the frozen two-mother child-age native pair."""
import hashlib
import json
import re
from pathlib import Path
from check_roundtrip import SHA, native_json, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: f"g11-var09-{arm}-v100-ssh-20261003-01" for arm in SHA}
PARENT = "473efed447d08808d565d08956b659574596be8e2a8457f451b4816bf50251ae"
PARENT_CLOSURE = "945ee70ce912810bb1bec897030815184648cdbb84326f0ccab038475660c8b9"
CONTRACT = "e1c15bab7395571bfbd220db72b3e755a5ee406fdd9209567bdfedaac87d7328"
DIFF = "6da9fdbf44583fc6ca27c5ec60d57d9d718f86785ae116cd091afb8bd74f658c"

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def vals(t, name):
    i = [c["name"] for c in t["columns"]].index(name)
    return [row[i] for inst in t["instances"] for row in inst["rows"]]

class Audit:
    def __init__(self): self.checks, self.errors = 0, []
    def need(self, condition, label):
        self.checks += 1
        if not condition: self.errors.append(label)

def arm_replay(arm, a):
    folder = HERE / "runs" / RUNS[arm]
    closure, invocation, steps = (read(folder / n) for n in ("closure.json", "invocation.json", "steps.json"))
    roundtrip = read(folder / "roundtrip-validation.json")
    a.need(closure["arm"] == arm and closure["run_id"] == RUNS[arm] and closure["error"] is None, f"{arm} closure identity")
    a.need(sha(folder / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
    a.need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH session")
    a.need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{arm} GUI guard")
    a.need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{arm} mutex")
    a.need(invocation["prelife_log_option_before"] == "NO" and closure["prelife_log_option_after"] == "NO", f"{arm} registry restore")
    a.need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} five steps")
    for s in steps: a.need(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"], f"{arm} step {s['name']}")
    for key, digest in {"input": SHA[arm], "parent": PARENT, "parent_closure": PARENT_CLOSURE, "contract": CONTRACT, "exact_diff": DIFF}.items():
        a.need(closure["source_hashes_before"].get(key) == digest, f"{arm} pinned {key}")
    for key, digest in closure["source_hashes_before"].items():
        a.need(closure["source_hashes_after"].get(key) == digest, f"{arm} unchanged {key}")
    a.need(len(closure["raw"]) == 13, f"{arm} raw count")
    for name, seal in closure["raw"].items():
        p = folder / name
        a.need(p.is_file() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"], f"{arm} raw {name}")
    before, after = populated(native_json(folder / "input.json")), populated(native_json(folder / "roundtrip-raw.json"))
    a.need(roundtrip["passed"] and not roundtrip["differences"] and len(before) == 23 and roundtrip["populated_tables"] == sorted(before), f"{arm} roundtrip verdict")
    for name, content in before.items(): a.need(after.get(name) == content, f"{arm} roundtrip {name}")
    runlog = (folder / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.need(re.findall(r"\(warning #(\d+)\)", runlog) == ["108"], f"{arm} warning gate")
    a.need("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and "(error #" not in runlog and "(notice #" not in runlog, f"{arm} conversion totals")
    prelife = (folder / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
    parsed = [(mid, label, float(age)) for mid, label, age in re.findall(r"\*\*(TEACH-AIR-01|POS-A|TEACH-LRU-01)\*\*([^*]+)\*\* Age\[CALHOURS\]:([0-9.]+)", prelife)]
    age_a, age_b = (20., 60.) if arm == "age20-then60" else (60., 20.)
    expected = [("TEACH-AIR-01", "SYS-A", 60.), ("POS-A", "POS-INH-A", 60.), ("TEACH-LRU-01", "LRU-A", age_a), ("TEACH-AIR-01", "SYS-B", 60.), ("POS-A", "POS-INH-B", 60.), ("TEACH-LRU-01", "LRU-B", age_b)]
    a.need(parsed == expected and "Prelifed Stock:" in prelife, f"{arm} two Prelife paths")
    event = (folder / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    first, second = (1, 0) if arm == "age20-then60" else (0, 1)
    def pairs(pattern): return [(float(t), int(i)) for t, i in re.findall(pattern, event)]
    for kind, phase, target in (("system", "started", [(40., first), (80., second)]), ("system", "completed", [(40.5, first), (80.5, second)]), ("item", "started", [(40.25, first), (80.25, second)]), ("item", "completed", [(41.25, first), (81.25, second)])):
        identifier = "TEACH-AIR-01" if kind == "system" else "TEACH-LRU-01,0"
        observed = pairs(r"Time: ([0-9.]+)  " + kind + r" PM task \d+ on <" + identifier + r",(\d+)> " + phase)
        a.need(observed == target, f"{arm} {kind} PM {phase}")
    removed = [int(i) for i in re.findall(r"Item demand arrives from pos [^\n]* item requiring maintenance is <TEACH-LRU-01,0,(\d+)>", event)]
    issued = [int(i) for i in re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", event)]
    returned = [int(i) for i in re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", event)]
    a.need(removed == [first, second] and issued == [2, first] and returned == [first, second], f"{arm} physical stock route")
    a.need(len(re.findall(r"PMID: LRU-CAL100", event)) == 2 and "PMID: SYS-CAL1000" not in event, f"{arm} PM attribution")
    a.need(not re.search(r"mission (started|success:|cancelled)", event, re.I) and "backorder" not in event.lower() and "(error #" not in event, f"{arm} event exclusions")
    report = {t["name"]: t for t in native_json(folder / "report-raw.json")["report"]["tables"]}
    a.need(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm} report tables")
    for field, target in {"NREP": 1, "RTIUP": 96, "MSTF": 0, "MSUF": 0}.items(): a.need(vals(report["ResultSummary"], field) == [target], f"{arm} summary {field}")
    for name in ("SystemResults", "StockTotalResults"):
        starts, ends = vals(report[name], "STINT"), vals(report[name], "ETINT")
        a.need(len(starts) == 192 and starts[0] == 0 and ends[-1] == 96 and all(e == s for e, s in zip(ends, starts[1:])), f"{arm} {name} bins")
    for field, target in {"NPMT": 2, "NPMS": 2, "NFAIL": 0, "NSYPM": 2}.items(): a.need(sum(x or 0 for x in vals(report["SystemResults"], field)) == target, f"{arm} system {field}")
    for field, target in {"NBO": 0, "NDP": 2, "NWT": 2}.items(): a.need(sum(x or 0 for x in vals(report["StockTotalResults"], field)) == target, f"{arm} stock {field}")
    a.need(vals(report["SystemResults"], "NSYRY")[-1] == 2 and vals(report["StockTotalResults"], "PNB")[-1] == 1, f"{arm} terminal ready/stock")
    return {"arm": arm, "run_id": RUNS[arm], "closure_sha256": sha(folder / "closure.json"), "prelife_log_sha256": sha(folder / "model_Prelife.log"), "event_log_sha256": sha(folder / "model.log"), "report_sha256": sha(folder / "report-raw.json"), "prelife_paths": parsed, "system_pm": [(40, first), (80, second)], "removed": removed, "issued": issued, "returned": returned}

def main():
    a = Audit()
    a.need(sha(HERE / "contract.json") == CONTRACT and sha(HERE / "exact-diff.json") == DIFF, "contract/diff pins")
    parent = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1"
    a.need(sha(parent / "native-input-inherited.json") == PARENT and sha(parent / "runs/g11-var04-inherited-v101-ssh-20261002-01/closure.json") == PARENT_CLOSURE, "accepted parent pins")
    docs = []
    for arm in RUNS:
        a.need(sha(HERE / f"native-input-{arm}.json") == SHA[arm], f"{arm} input SHA")
        docs.append(native_json(HERE / f"native-input-{arm}.json"))
    tables = [{t["name"]: t for t in doc["model"]["tables"]} for doc in docs]
    a.need({name for name in tables[0] if tables[0][name] != tables[1][name]} == {"ProblemDescription", "PrelifeData"}, "changed table set")
    ages = [vals(t["PrelifeData"], "AGE") for t in tables]
    a.need(len(ages[0]) == len(ages[1]) and [(x, y) for x, y in zip(*ages) if x != y] == [(20, 60), (60, 20)], "only two leaf AGE cells swapped")
    arms = [arm_replay(arm, a) for arm in RUNS]
    reports = [native_json(HERE / "runs" / RUNS[arm] / "report-raw.json")["report"]["tables"] for arm in RUNS]
    a.need([t for t in reports[0] if t["name"] != "ProblemDescription"] == [t for t in reports[1] if t["name"] != "ProblemDescription"], "aggregate reports equal")
    result = {"schema": "simlox-g11-var09-two-mothers-child-ages-author-replay/v1", "case_id": "G11", "variant_id": "G11.var09", "version": "1.0.0", "checks": a.checks, "passed_checks": a.checks-len(a.errors), "passed": not a.errors, "differences": a.errors, "arms": arms, "scope": "two same-type mothers, different installed leaf ages, first PM and stock route", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
