"""Read-only author replay of the sealed I07.var10 diagnostic and report extension."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I07-var10-nonreorder-base-v1.0.0"
RUN = HERE / "runs/i07-var10-report-only-v101-ssh-20261005-01"
OLD = PARENT / "runs/i07-var10-nonreorder-base-v100-ssh-20261005-01"
checks = 0
failures: list[str] = []


def check(value: bool, label: str) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path, pin: dict) -> bool:
    return path.is_file() and path.stat().st_size == pin["bytes"] and digest(path) == pin["sha256"]


contract, closure, invocation, outcome, steps = (
    obj(path) for path in (HERE / "contract.json", RUN / "closure.json",
                     RUN / "invocation.json", RUN / "outcome.json", RUN / "steps.json")
)
old_index, old_closure, old_contract = (
    obj(path) for path in (PARENT / "evidence-index.json", OLD / "closure.json", PARENT / "contract.json")
)
check(contract["version"] == "1.0.1-candidate" and contract["run_id"] == RUN.name,
      "extension identity")
check(closure["run_id"] == RUN.name and closure["parent_run_id"] == OLD.name,
      "closure lineage")
check(closure["error"] is None and outcome["error"] is None, "report run successful")
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source stability")
check(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(digest(OLD / "closure.json") == closure["parent_closure_sha256"], "old closure seal")
for name, pin in closure["raw"].items():
    check(seal(RUN / name, pin), f"new raw seal {name}")
check(set(closure["raw"]) == {"child-report-export.log", "child-report-raw.json", "steps.json", "outcome.json"},
      "one report-only raw set")
check(old_index["publication_state"] == "excluded_diagnostic", "old exclusion")
check(old_index["run"]["closure"]["sha256"] == digest(OLD / "closure.json"), "old index closure")
check(old_closure["error"] == "change unreviewed converter diagnostic", "old frozen gate")
check(len(old_closure["raw"]) == len(old_index["run"]["raw"]) == 22, "22 original seals")
for name, pin in old_closure["raw"].items():
    check(pin == old_index["run"]["raw"].get(name) and seal(OLD / name, pin), f"old raw seal {name}")
check(digest(PARENT / "evidence-index.json") == contract["diagnostic_parent"]["evidence_index_sha256"],
      "old diagnostic index pin")
check(digest(PARENT / "contract.json") == contract["diagnostic_parent"]["contract_sha256"],
      "old contract pin")
check(digest(OLD / "change.sxo") == contract["diagnostic_parent"]["child_sxo_sha256"],
      "old child SXO pin")
check(digest(OLD / "control.sxo") == contract["diagnostic_parent"]["control_sxo_sha256"],
      "old control SXO pin")
check(digest(OLD / "control-report-raw.json") == contract["diagnostic_parent"]["control_report_sha256"],
      "old control report pin")
check(old_closure["source_hashes_before"] == old_closure["source_hashes_after"], "old source stability")
check(old_contract["prerequisites"]["E15"]["package"] == "E15-var07-explicit-istoh-v1.0.1",
      "accepted E15 parent")
check(old_contract["prerequisites"]["I02_OUT"]["package"] == "I02-var02-out-transfer-v1.0.0",
      "accepted I02 parent")
for arm in ("control", "change"):
    imported = obj(OLD / f"{arm}-input.json")
    roundtrip = obj(OLD / f"{arm}-roundtrip-raw.json")
    check(len(imported["model"]["tables"]) >= 22, f"{arm} model tables")
    check(obj(OLD / f"{arm}-roundtrip-check.json")["passed"], f"{arm} exact roundtrip")
    check(roundtrip["model"]["tables"], f"{arm} exported tables")

control = obj(PARENT / "control-input.json")
child = obj(PARENT / "change-input.json")
ct = {t["name"]: t for t in control["model"]["tables"]}
dt = {t["name"]: t for t in child["model"]["tables"]}
check(set(ct) == set(dt), "same model tables")
check([name for name in ct if ct[name] != dt[name]] == ["ChangesStockAllocation"], "sole changed table")
check(ct["ChangesStockAllocation"]["instances"][0]["rows"] == [[None] * 6], "null control row")
check(dt["ChangesStockAllocation"]["instances"][0]["rows"] ==
      [["AIR_BASIC", "TEACH-DU-01", "BASE-01", 5, 1, None]], "exact child row")

check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 ancestry")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "native mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
      "protected GUI")
check(len(steps) == 1 and steps[0]["name"] == "child_report_only" and
      steps[0]["status"] == "completed" and steps[0]["exit_code"] == 0 and
      steps[0]["gui_preserved"], "single completed report step")
args = steps[0]["arguments"]
check(all(s in args for s in (" -report", " -rpts", " -rjexport", "change.sxo")), "report arguments")
check(not any(re.search(rf"(?:^|\s){re.escape(s)}(?:\s|$)", args) for s in
              ("-calc", "-jimport", "-jexport", "-save")), "no calculation/import/model write")
check("Export completed!" in (RUN / "child-report-export.log").read_text(errors="replace"),
      "native report completion")

warning = (OLD / "change-run.log").read_text(errors="replace")
check("No reorder data defined. ROSIZ ignored. TEACH-DU-01 / BASE-01" in warning,
      "exact native warning #172 text")
check(obj(OLD / "outcome.json")["warning_codes"] ==
      {"control": ["108"], "change": ["108", "172"]}, "exact diagnostic warning codes")
control_log = (OLD / "control.log").read_bytes()
child_log = (OLD / "change.log").read_bytes()
check(control_log == child_log and digest(OLD / "control.log") ==
      contract["diagnostic_parent"]["paired_log_sha256"], "byte-identical event ledgers")
log = control_log.decode("utf-8", errors="replace")
check("Time: 5 <TEACH-DU-01,0,DEPOT-01,0> reorder task" not in log, "no h5 order")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started" in log,
      "shared h10 depot reorder")
check("Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in log,
      "shared two-item delivery")
for physical_id in (5, 6):
    check(f"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,{physical_id}>"
          in log, f"new physical item {physical_id}")
check("Take replacement item <TEACH-DU-01,0,3> from stock" in log and
      "Take replacement item <TEACH-DU-01,0,0> from stock" in log,
      "base and depot physical issues")
check("Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in log,
      "base receives depot item")
snapshots = re.findall(r"Stock at: <TEACH-DU-01,0,(BASE-01|DEPOT-01),0> Level: (\d+) Items:([^\r\n]*)",
                       log)
check(len(snapshots) == 7, "all seven native stock snapshots present")
for station, level, item_list in snapshots:
    ids = re.findall(r"<TEACH-DU-01,0,\d+>", item_list)
    check(int(level) == len(ids) == len(set(ids)), f"physical stock snapshot {station}/{level}")

new_report = RUN / "child-report-raw.json"
old_report = OLD / "control-report-raw.json"
check(new_report.read_bytes() == old_report.read_bytes(), "all report bytes equal")
doc = obj(new_report)
tables = {t["name"]: t for t in doc["report"]["tables"]}
check(len(tables) == 10, "all ten selected report tables")
item = tables["ItemResults"]
names = [c["name"] for c in item["columns"]]
rows = [dict(zip(names, row)) for inst in item["instances"] for row in inst["rows"]]
check(len(rows) == 72 and all(r["IID"] == "TEACH-DU-01" and r["STID"] == "DEPOT-01" for r in rows),
      "all 72 selected depot bins")
for row in rows:
    start = row["STINT"]
    expected = 3 if start < 10 else 2 if start < 11 else 4
    check(row["STSZ"] == 4 and row["STOHA"] == expected and row["NBO"] == 0 and
          row["NRO"] == (1 if start == 10 else 0), f"depot bin {start}")

result = {"schema": "simlox-i07-var10-author-replay/v1", "run_id": RUN.name,
          "diagnostic_closure_sha256": digest(OLD / "closure.json"),
          "report_closure_sha256": digest(RUN / "closure.json"),
          "passed": not failures, "checks": checks, "checks_passed": checks - len(failures),
          "failures": failures,
          "observed": {"warning_172": True, "report_byte_equal": new_report.read_bytes() == old_report.read_bytes(),
                       "selected_depot_bins": len(rows), "stock_snapshots": len(snapshots)},
          "limits": contract["limits"]}
target = HERE / "review/author-validation-2026-10-05.json"
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}, indent=2))
if failures:
    raise SystemExit(1)
