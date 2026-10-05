"""Read-only author replay for one later-demand first batch above new ROSIZ."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var06-large-first-batch-v100-ssh-20261005-01"
E15 = ROOT / "E15-var07-explicit-istoh-v1.0.1"
I02 = ROOT / "I02-var02-out-transfer-v1.0.0"
I07 = ROOT / "I07-var02-rosiz-v1.0.1"
FAIL: list[str] = []
COUNT = 0


def check(ok: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not ok:
        FAIL.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


contract, invocation, closure, outcome, steps = (
    load(p) for p in (HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json",
                     RUN / "outcome.json", RUN / "steps.json")
)
check((contract["case_id"], contract["variant_id"], contract["version"]) ==
      ("I07", "I07.var06", "1.0.0-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] ==
      invocation["source_hashes_before"], "source stability")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
sources = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "roundtrip_checker": HERE / "check_roundtrip.py",
    "parent_input": E15 / "native-input-explicit-three.json",
    "parent_signoff": E15 / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": E15 / "make_report_settings.py",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector": E15 / "runs/report-settings/item-position-results.sxs",
    "i02_input": I02 / "native-input.json",
    "i02_signoff": I02 / "cli-scope-signoff-2026-10-02.md",
    "i02_index": I02 / "evidence-index.json",
    "i07_signoff": I07 / "cli-scope-signoff-2026-10-05.md",
    "i07_index": I07 / "evidence-index.json",
    "control": HERE / "control-input.json", "change": HERE / "change-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(sources) == set(closure["source_hashes_before"]), "complete source inventory")
for key, path in sources.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
for key, field in (("builder", "builder_sha256"), ("roundtrip_checker", "roundtrip_checker_sha256"),
                   ("manual", "manual_pdf_sha256"), ("dictionary", "dictionary_sha256"),
                   ("exe", "simlox_exe_sha256")):
    check(sha(sources[key]) == contract["source"][field], f"contract source {key}")
for arm in ("control", "change"):
    check(sha(sources[arm]) == contract["source"]["inputs_sha256"][arm], f"contract {arm} pin")
for key, parent, field in (("parent_input", "E15", "input_sha256"),
                           ("parent_signoff", "E15", "signoff_sha256"),
                           ("i02_input", "I02_OUT", "input_sha256"),
                           ("i02_signoff", "I02_OUT", "signoff_sha256"),
                           ("i02_index", "I02_OUT", "evidence_index_sha256"),
                           ("i07_signoff", "I07_var02", "signoff_sha256"),
                           ("i07_index", "I07_var02", "evidence_index_sha256")):
    check(sha(sources[key]) == contract["prerequisites"][parent][field], f"parent {key}")
check(sha(sources["selector"]) == contract["report_selector"]["selector_sha256"], "selector pin")
check(len(closure["raw"]) == 24, "24 raw file seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
          f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
check([s["name"] for s in steps] == [f"{arm}_{part}" for arm in ("control", "change")
                                     for part in ("import", "export", "calc", "report")], "eight serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"],
          f"step {step['name']}")

parent, control, change = (load(p) for p in (sources["parent_input"], sources["control"],
                                       sources["change"]))
pt, ct, cht = tables(parent), tables(control), tables(change)
check(len(pt) == 31 and len(ct) == len(cht) == 32 and set(ct) == set(cht) ==
      set(pt) | {"ChangesStockAllocation"}, "source table inventory")
check({key for key in ct if ct[key] != cht[key]} == {"ChangesStockAllocation"}, "single paired table delta")
check({key for key in pt if pt[key] != ct[key]} == {"ProblemDescription", "StockAllocation"},
      "parent common adaptation")
check(pt["StockAllocation"]["instances"][0]["rows"][1][3:7] == [4, 2, None, 3]
      and ct["StockAllocation"]["instances"][0]["rows"][1][3:7] == [4, 3, None, 3],
      "common initial nominal/on-hand/ROSIZ")
check(ct["ChangesStockAllocation"]["instances"][0]["rows"] == [[None] * 6] and
      cht["ChangesStockAllocation"]["instances"][0]["rows"] ==
      [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]], "sole h5 changed row")
for arm in ("control", "change"):
    check(sha(RUN / f"{arm}-input.json") == sha(sources[arm]), f"{arm} run input copy")
    rt = load(RUN / f"{arm}-roundtrip-check.json")
    check(rt["passed"] is True and rt["authored_populated_tables"] == 22 and
          rt["native_export_populated_tables"] == 32 and rt["mismatches"] == [],
          f"{arm} exact pre-calc roundtrip")
    check(outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0]
          and outcome["warning_codes"][arm] == ["108"], f"{arm} converter outcome")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108"] and
          "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog,
          f"{arm} exact native warning")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} valid SXO")

logs = {arm: (RUN / f"{arm}.log").read_text(encoding="utf-8-sig", errors="replace")
        for arm in ("control", "change")}
for arm, log in logs.items():
    check(not re.search(r"^Time: (?:0|[1-9](?:\.\d+)?) .*reorder task", log, re.M),
          f"{arm} no pre-demand order")
    check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in log
          and "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in log,
          f"{arm} common h10 demand and h12 base receipt")
    check("item transfer task" not in log and "OUT-transfer" not in log, f"{arm} no transfer")
check("reorder task" not in logs["control"] and "Delivery with" not in logs["control"],
      "control no order or purchase delivery")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in logs["change"]
      and "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1" in logs["change"]
      and "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in logs["change"],
      "child h10 two-unit first order and h11 delivery")
check(len(re.findall(r"reorder task \d+ started", logs["change"])) == 1 and
      len(re.findall(r"Delivery with \d+ item", logs["change"])) == 1,
      "child exactly one order/delivery")
expected = {
    "control": [("DEPOT-01", 3, (0, 1, 2)), ("BASE-01", 1, (3,)),
                ("BASE-01", 0, ()), ("DEPOT-01", 2, (1, 2)), ("BASE-01", 1, (0,))],
    "change": [("DEPOT-01", 3, (0, 1, 2)), ("BASE-01", 1, (3,)),
               ("BASE-01", 0, ()), ("DEPOT-01", 2, (1, 2)),
               ("DEPOT-01", 3, (1, 2, 5)), ("DEPOT-01", 4, (1, 2, 5, 6)),
               ("BASE-01", 1, (0,))],
}
for arm, log in logs.items():
    actual = []
    for station, level, items in re.findall(
        r"^  Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:(.*)$", log, re.M
    ):
        ids = tuple(int(x) for x in re.findall(r"<TEACH-DU-01,0,(\d+)>", items))
        actual.append((station, int(level), ids))
        check(len(ids) == int(level), f"{arm} snapshot {len(actual)} level")
    check(actual == expected[arm], f"{arm} all physical stock snapshots")

reports = {arm: load(RUN / f"{arm}-report-raw.json") for arm in ("control", "change")}
for arm, report in reports.items():
    item = rows(report, "ItemResults")
    check(len(item) == 72, f"{arm} 72 selected bins")
    onhand = [3] * 20 + ([2] * 52 if arm == "control" else [2] * 2 + [4] * 50)
    for i, (row, want) in enumerate(zip(item, onhand)):
        check((row["IID"], row["STID"], row["STINT"], row["ETINT"]) ==
              ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2), f"{arm} bin interval {i}")
        check(row["STSZ"] == 4 and row["STOHA"] == want and row["NBO"] == 0 and
              row["NRO"] == int(arm == "change" and i == 20), f"{arm} stock bin {i}")
    total = rows(report, "ItemResultsTotal")[0]
    check(total["STSZ"] == 4 and total["NRO"] == int(arm == "change") and
          total["NBO"] == 0 and abs(total["STOHA"] - sum(onhand) / 72) < 1e-5,
          f"{arm} item total")
    check(len(rows(report, "StockTotalResults")) == 72 and
          all(r["NBO"] == 0 for r in rows(report, "StockTotalResults")),
          f"{arm} aggregate no backorder")
for name in ("ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal",
             "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"):
    check(rows(reports["control"], name) == rows(reports["change"], name), f"paired {name}")

result = {"schema": "simlox-i07-var06-author-replay/v1", "run_id": RUN.name,
          "closure_sha256": sha(RUN / "closure.json"), "passed": not FAIL,
          "checks": COUNT, "checks_passed": COUNT - len(FAIL), "failures": FAIL,
          "observed": {"h5_order_both": False, "h10_control_order": False,
                       "h10_child_first_batch": 2, "h11_child_delivery_ids": [5, 6],
                       "h12_base_receipt_id": 0, "terminal_depot_on_hand": [2, 4]},
          "limits": "One fixed-seed later demand and one stock-based DU; no general batch or event ordering law."}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"{'GO' if result['passed'] else 'NO-GO'} {result['checks_passed']}/{COUNT}")
for failure in FAIL:
    print(failure)
raise SystemExit(0 if result["passed"] else 1)
