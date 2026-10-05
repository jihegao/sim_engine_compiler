"""Read-only author replay for the exact #168 warning and selected report."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD_CASE = ROOT / "E15-var10-rosiz-upper-bound-v1.0.0"
OLD = OLD_CASE / "runs/e15-var10-rosiz-over-limit-v100-ssh-20261005-01"
RUN = HERE / "runs/e15-var10-warning-report-v101-ssh-20261005-01"
E15 = ROOT / "E15-var07-explicit-istoh-v1.0.1"
PARENT = E15 / "runs/e15-var07-explicit-three-v101-ssh-20261002-01"
PARENT_REPORT = E15 / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json"
checks = 0
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sealed(path: Path, pin: dict) -> bool:
    return path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"]


contract, closure, invocation, outcome, steps = (load(p) for p in
    (HERE / "contract.json", RUN / "closure.json", RUN / "invocation.json",
     RUN / "outcome.json", RUN / "steps.json"))
old_index, old_closure, old_outcome = (load(p) for p in
    (OLD_CASE / "evidence-index.json", OLD / "closure.json", OLD / "outcome.json"))
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "extension run identity")
check(closure["parent_run_id"] == OLD.name and closure["parent_closure_sha256"] == sha(OLD / "closure.json"),
      "diagnostic lineage")
check(closure["error"] is None and outcome["error"] is None and outcome["status"] == "completed",
      "report-only completion")
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source stability")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "new invocation seal")
check(len(closure["raw"]) == 4, "four new raw files")
for name, pin in closure["raw"].items():
    check(sealed(RUN / name, pin), f"new raw seal {name}")
check(old_index["publication_state"] == "excluded_diagnostic", "old exclusion preserved")
check(old_closure["error"] == "expected converter error absent" and not old_closure["expected_negative"],
      "original frozen gate failed")
check(old_closure["source_hashes_before"] == old_closure["source_hashes_after"], "original source stability")
check(len(old_closure["raw"]) == 11 and old_index["run"]["raw"] == old_closure["raw"],
      "11 original indexed seals")
for name, pin in old_closure["raw"].items():
    check(sealed(OLD / name, pin), f"original raw seal {name}")
check(sha(OLD_CASE / "evidence-index.json") == contract["diagnostic_parent"]["evidence_index_sha256"],
      "old diagnostic index pin")
check(sha(OLD / "closure.json") == contract["diagnostic_parent"]["closure_sha256"],
      "old closure pin")
check(sha(OLD / "model.sxo") == contract["diagnostic_parent"]["sxo_sha256"], "sealed SXO pin")
check(sha(OLD / "model.log") == contract["diagnostic_parent"]["event_log_sha256"],
      "sealed event log pin")
check(sha(PARENT / "model.log") == contract["accepted_parent"]["event_log_sha256"],
      "accepted parent event pin")
check(sha(PARENT_REPORT) == contract["accepted_parent"]["selected_report_sha256"],
      "accepted selected report pin")
check(old_outcome["converter_summary"] == [0, 2, 0] and old_outcome["error_codes"] == [],
      "warning rather than converter rejection")
calc = (OLD / "run.log").read_text(errors="replace")
check("(warning #108)" in calc and
      "(warning #168) Reorder size too large (ROSIZ > STSIZ+1): TEACH-DU-01" in calc,
      "exact warning #168")
check(load(OLD / "roundtrip-check.json")["passed"] and
      load(OLD / "roundtrip-check.json")["authored_populated_tables"] == 21,
      "exact 21-table roundtrip")

parent_model = load(E15 / "native-input-explicit-three.json")
child_model = load(OLD_CASE / "native-input.json")
pt = {t["name"]: t for t in parent_model["model"]["tables"]}
ct = {t["name"]: t for t in child_model["model"]["tables"]}
check(set(pt) == set(ct) and [n for n in pt if pt[n] != ct[n]] == ["StockAllocation"],
      "sole changed model table")
pr = pt["StockAllocation"]["instances"][0]["rows"]
cr = ct["StockAllocation"]["instances"][0]["rows"]
check(pr[0] == cr[0] and pr[1][:4] == cr[1][:4] and pr[1][5:] == cr[1][5:] and
      (pr[1][4], cr[1][4], cr[1][3]) == (2, 6, 4), "sole ROSIZ2-to-6 depot delta")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
      invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "SSH0 serial ownership")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
      invocation["gui"]["start_utc"] == "2026-09-28T10:09:56.8261381Z", "protected GUI identity")
check(len(steps) == 1 and steps[0]["name"] == "selected_report_only" and
      steps[0]["status"] == "completed" and steps[0]["exit_code"] == 0 and
      steps[0]["gui_preserved"], "single guarded report step")
args = steps[0]["arguments"]
check(all(x in args for x in ("model.sxo", " -report", " -rpts", " -rjexport")) and
      not any(re.search(rf"(?:^|\s){re.escape(x)}(?:\s|$)", args) for x in
              ("-calc", "-jimport", "-jexport", "-save")), "report-only arguments")
check("Export completed!" in (RUN / "report-export.log").read_text(errors="replace"),
      "native report completed")

log = (OLD / "model.log").read_text(errors="replace")
accepted_log = (PARENT / "model.log").read_text(errors="replace")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started" not in log and
      "Delivery with 2 item(s) arrives" not in log, "candidate no reorder or delivery")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started" in accepted_log and
      "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in accepted_log,
      "accepted parent reorder contrast")
check("Take replacement item <TEACH-DU-01,0,3> from stock" in log and
      "Take replacement item <TEACH-DU-01,0,0> from stock" in log and
      "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in log,
      "physical base/depot issue and h12 receipt")
snapshots = re.findall(r"Stock at: <TEACH-DU-01,0,(BASE-01|DEPOT-01),0> Level: (\d+) Items:([^\r\n]*)", log)
check(len(snapshots) == 5, "all five physical stock snapshots")
for station, level, items in snapshots:
    ids = re.findall(r"<TEACH-DU-01,0,\d+>", items)
    check(int(level) == len(ids) == len(set(ids)), f"physical stock IDs {station}/{level}")
check(snapshots[0][0:2] == ("DEPOT-01", "3") and snapshots[0][2].count("<TEACH-DU-01") == 3 and
      snapshots[3][0:2] == ("DEPOT-01", "2"), "depot opening and post-demand stock")

report = load(RUN / "selected-report-raw.json")
parent_report = load(PARENT_REPORT)
t = {x["name"]: x for x in report["report"]["tables"]}
p = {x["name"]: x for x in parent_report["report"]["tables"]}
check(len(t) == len(p) == 10 and set(t) == set(p), "ten selected tables")
check({name for name in t if t[name] != p[name]} == {"ItemResults", "ItemResultsTotal"},
      "only item result tables differ")
names = [x["name"] for x in t["ItemResults"]["columns"]]
rows = [dict(zip(names, row)) for inst in t["ItemResults"]["instances"] for row in inst["rows"]]
parent_rows = [dict(zip(names, row)) for inst in p["ItemResults"]["instances"] for row in inst["rows"]]
check(len(rows) == len(parent_rows) == 72, "all 72 half-hour depot bins")
for row, parent_row in zip(rows, parent_rows):
    hour = row["STINT"]
    check(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01" and
          row["STSZ"] == 4 and row["STOHA"] == (3 if hour < 10 else 2) and
          row["NRO"] == 0 and row["NBO"] == 0, f"candidate depot bin {hour}")
    check(parent_row["STOHA"] == (3 if hour < 10 else 2 if hour < 11 else 4) and
          parent_row["NRO"] == (1 if hour == 10 else 0), f"accepted depot bin {hour}")
check(t["ResultSummary"] == p["ResultSummary"] and t["SystemResults"] == p["SystemResults"] and
      t["MissionResults"] == p["MissionResults"] and t["StockTotalResults"] == p["StockTotalResults"],
      "mission/system/aggregate stock reports equal")
check(log.count("mission success:") == 2 and log.count("mission aborted:") == 1 and
      "Time: 34 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
      "mission outcomes and terminal readiness")

result = {"schema": "simlox-e15-var10-warning-author-replay/v1", "run_id": RUN.name,
          "diagnostic_closure_sha256": sha(OLD / "closure.json"),
          "report_closure_sha256": sha(RUN / "closure.json"), "passed": not failures,
          "checks": checks, "checks_passed": checks - len(failures), "failures": failures,
          "observed": {"converter": [0, 2, 0], "warning": "168", "selected_depot_bins": len(rows),
                       "physical_stock_snapshots": len(snapshots), "report_sha256": sha(RUN / "selected-report-raw.json")},
          "limits": contract["limits"]}
target = HERE / "review/author-validation-2026-10-05.json"
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}, indent=2))
if failures:
    raise SystemExit(1)
