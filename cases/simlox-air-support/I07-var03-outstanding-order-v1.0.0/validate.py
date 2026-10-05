"""Read-only author replay of one sealed pending-order LEADT change."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var03-outstanding-v100-ssh-20261005-01"
EARLY = ROOT / "I07-var01-reorder-lead-time-v1.0.0"
EARLY_RUN = EARLY / "runs/i07-var01-reorder-leadt-v100-ssh-20261005-01"
E15 = ROOT / "E15-var07-explicit-istoh-v1.0.1"
FAILED: list[str] = []
CHECKS = 0


def check(ok: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILED.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for inst in t["instances"] for row in inst["rows"]]


contract = load(HERE / "contract.json")
invocation = load(RUN / "invocation.json")
closure = load(RUN / "closure.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) ==
      ("I07", "I07.var03", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] ==
      invocation["source_hashes_before"], "source stable during run")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "roundtrip_checker": HERE / "check_roundtrip.py",
    "parent_input": EARLY / "change-input.json",
    "parent_signoff": EARLY / "cli-scope-signoff-2026-10-05.md",
    "parent_index": EARLY / "evidence-index.json",
    "parent_closure": EARLY_RUN / "closure.json",
    "e15_input": E15 / "native-input-explicit-three.json",
    "e15_signoff": E15 / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": E15 / "make_report_settings.py",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector": E15 / "runs/report-settings/item-position-results.sxs",
    "late": HERE / "late-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(paths) == set(closure["source_hashes_before"]), "complete source inventory")
for key, path in paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
for key, field in (("builder", "builder_sha256"), ("roundtrip_checker", "roundtrip_checker_sha256"),
                   ("late", "input_sha256"), ("manual", "manual_pdf_sha256"),
                   ("dictionary", "dictionary_sha256")):
    check(sha(paths[key]) == contract["source"][field], f"contract source {key}")
for key, field in (("parent_input", "input_sha256"), ("parent_signoff", "signoff_sha256"),
                   ("parent_index", "evidence_index_sha256"), ("parent_closure", "run_closure_sha256")):
    check(sha(paths[key]) == contract["parents"]["I07_var01"][field], f"I07 parent {key}")
for key, field in (("e15_input", "input_sha256"), ("e15_signoff", "signoff_sha256")):
    check(sha(paths[key]) == contract["parents"]["E15"][field], f"E15 parent {key}")
check(sha(paths["selector"]) == contract["report_selector"]["selector_sha256"], "selector pin")
check(len(closure["raw"]) == 13, "13 raw file seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
          f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
check([s["name"] for s in steps] == [f"late_{part}" for part in ("import", "export", "calc", "report")],
      "four serial stages")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"],
          f"stage {step['name']}")

source = load(HERE / "late-input.json")
parent = load(EARLY / "change-input.json")
check(sha(RUN / "late-input.json") == sha(HERE / "late-input.json"), "run source copy")
a, b = tables(parent), tables(source)
check(len(a) == len(b) == 32 and set(a) == set(b), "32 source tables")
check({name for name in a if a[name] != b[name]} == {"ProblemDescription", "ChangesItemReorder"},
      "only description and change table differ")
check(a["ChangesItemReorder"]["instances"][0]["rows"] ==
      [["TEACH-DU-01", "DEPOT-01", 5, 3, None, None, None, None]] and
      b["ChangesItemReorder"]["instances"][0]["rows"] ==
      [["TEACH-DU-01", "DEPOT-01", 10.5, 3, None, None, None, None]], "sole business delta TIMEC")
roundtrip = load(RUN / "late-roundtrip-check.json")
check(roundtrip["passed"] is True and roundtrip["authored_populated_tables"] == 22 and
      roundtrip["mismatches"] == [], "pre-calc exact roundtrip gate")
check(outcome["arms"] == {"late": "completed"} and outcome["converter_summaries"]["late"] == [0, 1, 0]
      and outcome["warning_codes"]["late"] == ["108"], "converter outcome")
runlog = (RUN / "late-run.log").read_text(encoding="utf-8-sig")
check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108"] and
      "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog, "exact native warning")
check((RUN / "late.sxo").stat().st_size > 1000, "valid SXO")

log = (RUN / "late.log").read_text(encoding="utf-8-sig", errors="replace")
early_log = (EARLY_RUN / "change.log").read_text(encoding="utf-8-sig", errors="replace")
check(sha(RUN / "late.log") == sha(EARLY_RUN / "control.log"), "late events byte-equal accepted control")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in log,
      "pending order started at h10 with original lead")
check("Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1" in log and
      "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in log,
      "pending order completes/delivers h11")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 3" in early_log and
      "Time: 13 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in early_log,
      "accepted early-change comparator h13")
check(log.count("reorder task") == 2 and log.count("Delivery with") == 1 and
      not re.search(r"Time: 10\.5 .*?(?:reorder task|Delivery with|Take replacement item|Put back replacement item)", log),
      "no extra order or h10.5 stock move")
snapshots = re.findall(r"^  Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:(.*)$",
                       log, re.MULTILINE)
expected_snapshots = [
    ("DEPOT-01", "3", "<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,"),
    ("BASE-01", "1", "<TEACH-DU-01,0,3>,"),
    ("BASE-01", "0", ""),
    ("DEPOT-01", "2", "<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,"),
    ("DEPOT-01", "3", "<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,5>,"),
    ("DEPOT-01", "4", "<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,5>,<TEACH-DU-01,0,6>,"),
    ("BASE-01", "1", "<TEACH-DU-01,0,0>,"),
]
check(snapshots == expected_snapshots, "complete stock snapshots and physical IDs")
report = load(RUN / "late-report-raw.json")
early_control = load(EARLY_RUN / "control-report-raw.json")
check({t["name"]: t for t in report["report"]["tables"] if t["name"] != "ProblemDescription"} ==
      {t["name"]: t for t in early_control["report"]["tables"] if t["name"] != "ProblemDescription"},
      "all accepted control report tables except description equal")
item = rows(report, "ItemResults")
check(len(item) == 72, "72 selected depot bins")
expected = [3] * 20 + [2] * 2 + [4] * 50
for i, (row, want) in enumerate(zip(item, expected)):
    check((row["IID"], row["STID"], row["STINT"], row["ETINT"]) ==
          ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2), f"item interval {i}")
    check(row["STSZ"] == 4 and row["STOHA"] == want and row["NBO"] == 0 and
          row["NRO"] == (1 if i == 20 else 0), f"stock bin {i}")
total = rows(report, "ItemResultsTotal")[0]
check(total["STSZ"] == 4 and total["NRO"] == 1 and
      abs(total["STOHA"] - sum(expected) / 72) < 1e-5, "item total")
fixed = rows(report, "FixedMissionResultsTotal")[0]
check(fixed["NMSTA"] == 3 and fixed["NMSUC"] == 2, "mission total")
check(rows(report, "SystemResults")[-1]["NSYRY"] == 1, "terminal ready")
check(len(rows(report, "StockTotalResults")) == 72 and
      all(r["NBO"] == 0 for r in rows(report, "StockTotalResults")), "aggregate stock no backorder")

result = {"schema": "simlox-i07-var03-author-replay/v1", "run_id": RUN.name,
          "closure_sha256": sha(RUN / "closure.json"), "passed": not FAILED,
          "checks": CHECKS, "checks_passed": CHECKS - len(FAILED), "failures": FAILED,
          "observed": {"new_run_order_start": 10, "new_run_delivery": 11,
                       "accepted_early_change_delivery": 13, "delivery_quantity": 2,
                       "new_run_terminal_depot_on_hand": 4},
          "limits": "One pending order, fixed seed, h10.5 change. No post-change new order; h10.5 application is not directly logged."}
dest = HERE / "review/author-validation-2026-10-05.json"
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"{'GO' if result['passed'] else 'NO-GO'} {result['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if result["passed"] else 1)
