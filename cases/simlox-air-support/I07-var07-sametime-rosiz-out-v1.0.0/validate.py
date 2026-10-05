"""Read-only author replay of the sealed same-time ROSIZ/OUT matched pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var07-sametime-rosiz-out-v100-ssh-20261005-01"
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


def model_tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


contract, invocation, closure, outcome, steps = (
    load(p) for p in (HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json",
                     RUN / "outcome.json", RUN / "steps.json")
)
check((contract["case_id"], contract["variant_id"], contract["version"]) ==
      ("I07", "I07.var07", "1.0.0-candidate"), "contract identity")
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
for key in ("control", "change"):
    check(sha(sources[key]) == contract["source"]["inputs_sha256"][key], f"contract {key} pin")
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
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
check([step["name"] for step in steps] == [f"{arm}_{part}" for arm in ("control", "change")
                                         for part in ("import", "export", "calc", "report")], "eight serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"],
          f"step {step['name']}")

control, change = load(HERE / "control-input.json"), load(HERE / "change-input.json")
check(sha(RUN / "control-input.json") == sha(HERE / "control-input.json") and
      sha(RUN / "change-input.json") == sha(HERE / "change-input.json"), "run input copies")
ct, cht = model_tables(control), model_tables(change)
check(len(ct) == len(cht) == 33 and set(ct) == set(cht), "33 common tables")
check({key for key in ct if ct[key] != cht[key]} == {"ChangesStockAllocation"}, "single table delta")
check(ct["ChangesStockAllocation"]["instances"][0]["rows"] == [[None] * 6] and
      cht["ChangesStockAllocation"]["instances"][0]["rows"] ==
      [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]], "sole h5 ROSIZ value delta")
for arm in ("control", "change"):
    rt = load(RUN / f"{arm}-roundtrip-check.json")
    check(rt["passed"] is True and rt["authored_populated_tables"] == 23 and
          rt["native_export_populated_tables"] == 33 and rt["mismatches"] == [],
          f"{arm} 23-table roundtrip")
    check(outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0]
          and outcome["warning_codes"][arm] == ["108"], f"{arm} converter outcome")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108"] and
          "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog,
          f"{arm} exact native warning")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")

logs = {arm: (RUN / f"{arm}.log").read_text(encoding="utf-8-sig", errors="replace")
        for arm in ("control", "change")}
for arm, log in logs.items():
    check("Time: 5 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in log
          and "Time: 5  item transfer task 0 (OUT)  arrives with 1 items" in log,
          f"{arm} common OUT of physical ID0")
    check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,1> from stock" in log
          and "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,1>" in log,
          f"{arm} shared h10 base demand and h12 transport")
    check(log.count("item transfer task 0 (OUT)  arrives") == 1 and
          log.count("Take replacement item <TEACH-DU-01,0,0>") == 1,
          f"{arm} one OUT")
check(not re.search(r"Time: 5 .*reorder task", logs["control"]) and
      "Time: 5 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in logs["change"],
      "child-only same-time h5 order")
check("Time: 6 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives" in logs["change"]
      and "Time: 6 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,4>" in logs["change"],
      "h6 child delivery ID4, batch one observed")
check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in logs["control"]
      and "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 1 started, reorder time: 1" in logs["change"],
      "h10 subsequent orders")
check("Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in logs["control"]
      and "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives" in logs["change"],
      "h11 subsequent batches observed")
check([len(re.findall(r"reorder task \d+ started", logs[arm])) for arm in ("control", "change")] == [1, 2],
      "complete order counts")
expected_stock = {
    "control": [("DEPOT-01", 3, (0, 1, 2)), ("BASE-01", 1, (3,)),
                ("DEPOT-01", 2, (1, 2)), ("BASE-01", 0, ()),
                ("DEPOT-01", 1, (2,)), ("DEPOT-01", 2, (2, 5)),
                ("DEPOT-01", 3, (2, 5, 6)), ("BASE-01", 1, (1,))],
    "change": [("DEPOT-01", 3, (0, 1, 2)), ("BASE-01", 1, (3,)),
               ("DEPOT-01", 2, (1, 2)), ("DEPOT-01", 3, (1, 2, 4)),
               ("BASE-01", 0, ()), ("DEPOT-01", 2, (2, 4)),
               ("DEPOT-01", 3, (2, 4, 6)), ("BASE-01", 1, (1,))],
}
for arm, log in logs.items():
    found = []
    for station, level, items in re.findall(
        r"^  Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:(.*)$", log, re.M
    ):
        ids = tuple(int(x) for x in re.findall(r"<TEACH-DU-01,0,(\d+)>", items))
        found.append((station, int(level), ids))
        check(len(ids) == int(level), f"{arm} physical stock snapshot {len(found)} level")
    check(found == expected_stock[arm], f"{arm} full physical stock ledger")

for arm in ("control", "change"):
    report = load(RUN / f"{arm}-report-raw.json")
    item = rows(report, "ItemResults")
    check(len(item) == 72, f"{arm} 72 half-hour bins")
    onhand = ([3] * 10 + [2] * 10 + [1] * 2 + [3] * 50 if arm == "control"
              else [3] * 10 + [2] * 2 + [3] * 8 + [2] * 2 + [3] * 50)
    order_bins = {20} if arm == "control" else {10, 20}
    for i, (row, expected) in enumerate(zip(item, onhand)):
        check((row["IID"], row["STID"], row["STINT"], row["ETINT"]) ==
              ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2), f"{arm} interval {i}")
        check(row["STSZ"] == (4 if i < 10 else 3) and row["STOHA"] == expected and
              row["NBO"] == 0 and row["NRO"] == int(i in order_bins), f"{arm} stock bin {i}")
    total = rows(report, "ItemResultsTotal")[0]
    check(total["NRO"] == len(order_bins) and total["NBO"] == 0 and
          abs(total["STSZ"] - (10 * 4 + 62 * 3) / 72) < 1e-5 and
          abs(total["STOHA"] - sum(onhand) / 72) < 1e-5, f"{arm} item total")
    check(len(rows(report, "StockTotalResults")) == 72 and
          all(r["NBO"] == 0 for r in rows(report, "StockTotalResults")),
          f"{arm} aggregate no backorder")

control_report = load(RUN / "control-report-raw.json")
change_report = load(RUN / "change-report-raw.json")
shared_results = {"ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal",
                  "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"}
for name in sorted(shared_results):
    check(rows(control_report, name) == rows(change_report, name), f"paired {name} results")

result = {"schema": "simlox-i07-var07-author-replay/v1", "run_id": RUN.name,
          "closure_sha256": sha(RUN / "closure.json"), "passed": not FAIL,
          "checks": COUNT, "checks_passed": COUNT - len(FAIL), "failures": FAIL,
          "observed": {"h5_control_order": False, "h5_change_order": True,
                       "h6_change_delivery": 1, "h10_control_batch": 2,
                       "h10_change_batch": 1, "h11_deliveries": [2, 1],
                       "terminal_depot_on_hand": [3, 3]},
          "limits": "One fixed-seed same-time available-stock OUT and ROSIZ change; no GUI or wider tie ordering."}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"{'GO' if result['passed'] else 'NO-GO'} {result['checks_passed']}/{COUNT}")
for failure in FAIL:
    print(failure)
raise SystemExit(0 if result["passed"] else 1)
