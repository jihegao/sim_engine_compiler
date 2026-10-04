"""Read-only author replay of the sealed I07.var02 ROSIZ pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var02-rosiz-v101-ssh-20261005-01"
ARMS = ("control", "change")
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


def populated(doc: dict) -> dict:
    return {
        t["name"]: {"columns": [(c["name"], c["datatype"]) for c in t["columns"]],
                    "rows": [row for inst in t["instances"] for row in inst["rows"]]}
        for t in doc["model"]["tables"] if any(inst["rows"] for inst in t["instances"])
    }


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) ==
      ("I07", "I07.var02", "1.0.1-candidate"), "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] ==
      invocation["source_hashes_before"], "stable source")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")

parent = ROOT / "E15-var07-explicit-istoh-v1.0.1"
paths = {
    "contract": HERE / "contract.json", "builder": HERE / "build.py",
    "parent_input": parent / "native-input-default.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": parent / "make_report_settings.py",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector": parent / "runs/report-settings/item-position-results.sxs",
    **{arm: HERE / f"{arm}-input.json" for arm in ARMS},
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(sha(paths["parent_input"]) == contract["prerequisites"]["E15"]["input_sha256"], "E15 input pin")
check(sha(paths["parent_signoff"]) == contract["prerequisites"]["E15"]["signoff_sha256"], "E15 signoff pin")
check(sha(paths["builder"]) == contract["frozen_source"]["builder_sha256"], "builder contract pin")
for arm in ARMS:
    check(sha(paths[arm]) == contract["frozen_source"]["inputs_sha256"][arm], f"{arm} input contract pin")
check(sha(paths["selector"]) == contract["report_selector"]["selector_sha256"], "selected report pin")
check(sha(paths["manual"]) == contract["source"]["manual_pdf_sha256"], "manual pin")
check(sha(paths["dictionary"]) == contract["source"]["dictionary_sha256"], "dictionary pin")
check(sha(paths["exe"]) == contract["environment"]["simlox_exe_sha256"], "executable pin")
for prerequisite, package, signoff in (
    ("E02", "E02-zero-stock-local-backorder-v1.0.0", "cli-scope-signoff-2026-09-29.md"),
    ("I02_IN", "I02-var01-in-transfer-v1.0.2", "cli-scope-signoff-2026-10-02.md"),
    ("I02_BETWEEN", "I02-var03-between-transfer-v1.0.0", "cli-scope-signoff-2026-10-02.md"),
):
    base = ROOT / package
    pin = contract["prerequisites"][prerequisite]
    check(sha(base / "native-input.json") == pin["input_sha256"], f"{prerequisite} input pin")
    check(sha(base / signoff) == pin["signoff_sha256"], f"{prerequisite} signoff pin")
check(len(closure["raw"]) == 22, "22 raw seals")
for name, seal in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and
          sha(path) == seal["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([step["name"] for step in steps] ==
      [f"{arm}_{part}" for arm in ARMS for part in ("import", "export", "calc", "report")],
      "eight serial steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"],
          f"step {step['name']}")

authored = {arm: load(HERE / f"{arm}-input.json") for arm in ARMS}
control_tables = authored["control"]["model"]["tables"]
change_tables = authored["change"]["model"]["tables"]
check(len(control_tables) == len(change_tables) == 32 and
      [t["name"] for t in control_tables] == [t["name"] for t in change_tables], "32 matched tables")
check([a["name"] for a, b in zip(control_tables, change_tables) if a != b] ==
      ["ChangesStockAllocation"], "sole paired table delta")
for arm, expected in (("control", [[None] * 6]),
                      ("change", [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5, 1, None]])):
    table = next(t for t in authored[arm]["model"]["tables"] if t["name"] == "ChangesStockAllocation")
    check(table["instances"][0]["rows"] == expected, f"{arm} scheduled row")

reports = {}
observed = {}
for arm in ARMS:
    check(sha(HERE / f"{arm}-input.json") == sha(RUN / f"{arm}-input.json"), f"{arm} run input")
    source = populated(authored[arm])
    exported = populated(load(RUN / f"{arm}-roundtrip-raw.json"))
    check(len(source) == 22 and all(exported.get(name) == table for name, table in source.items()),
          f"{arm} exact 22-table roundtrip")
    check(outcome["arms"][arm] == "completed" and
          outcome["converter_summaries"][arm] == [0, 1, 0] and
          outcome["warning_codes"][arm] == ["108"], f"{arm} converter summary")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(runlog.count("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0") == 1 and
          re.findall(r"\(warning #(\d+)\)", runlog) == ["108"], f"{arm} exact warning")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} valid SXO")
    report = load(RUN / f"{arm}-report-raw.json")
    reports[arm] = report
    item = rows(report, "ItemResults")
    check(len(item) == 72 and all((r["IID"], r["STID"], r["STINT"], r["ETINT"]) ==
          ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2) for i, r in enumerate(item)),
          f"{arm} 72 selected depot bins")
    expected = [4] * 20 + ([3] * 52 if arm == "control" else [3] * 2 + [4] * 50)
    for i, (row, want) in enumerate(zip(item, expected)):
        check(row["STSZ"] == 4 and row["STOHA"] == want and row["NBO"] == 0,
              f"{arm} stock bin {i}")
        check(row["NRO"] == (1 if arm == "change" and i == 20 else 0), f"{arm} order bin {i}")
    total = rows(report, "ItemResultsTotal")[0]
    check(total["STSZ"] == 4 and abs(total["STOHA"] - sum(expected) / 72) < 1e-5 and
          total["NRO"] == (0 if arm == "control" else 1), f"{arm} item total")
    check(rows(report, "SystemResults")[-1]["NSYRY"] == 1, f"{arm} terminal system ready")
    fixed = rows(report, "FixedMissionResultsTotal")[0]
    check(fixed["NMSTA"] == 3 and fixed["NMSUC"] == 2, f"{arm} mission totals")
    check(rows(report, "ResultSummary")[0]["NREP"] == 1, f"{arm} one repetition")

    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig", errors="replace")
    depot = "<TEACH-DU-01,0,DEPOT-01,0>"
    base = "<TEACH-DU-01,0,BASE-01,0>"
    check(not re.search(r"Time: 5(?:\.\d+)? .*?(?:reorder task|Delivery with|Take replacement item|Put back replacement item)", log),
          f"{arm} no immediate h5 order/stock move")
    check(len(re.findall(r"Time: 10 " + re.escape(depot) + r" Take replacement item <TEACH-DU-01,0,0>", log)) == 1,
          f"{arm} h10 depot physical ID 0 issue")
    check(len(re.findall(r"Time: 12 " + re.escape(base) + r" Put back replacement item <TEACH-DU-01,0,0>", log)) == 1,
          f"{arm} h12 base physical ID 0 arrival")
    starts = re.findall(r"Time: (\d+(?:\.\d+)?) " + re.escape(depot) +
                        r" reorder task (\d+) started, reorder time: (\d+(?:\.\d+)?)", log)
    completes = re.findall(r"Time: (\d+(?:\.\d+)?) " + re.escape(depot) +
                           r" reorder task (\d+) completed, total time was (\d+(?:\.\d+)?)", log)
    deliveries = re.findall(r"Time: (\d+(?:\.\d+)?) " + re.escape(depot) +
                            r" Delivery with (\d+) item\(s\) arrives", log)
    arrivals = re.findall(r"Time: (\d+(?:\.\d+)?) " + re.escape(depot) +
                          r" Replacement item arrives <TEACH-DU-01,0,(\d+)>", log)
    returns = re.findall(r"Time: (\d+(?:\.\d+)?) " + re.escape(depot) +
                         r" Put back replacement item <TEACH-DU-01,0,(\d+)> to stock", log)
    if arm == "control":
        check((starts, completes, deliveries, arrivals, returns) == ([], [], [], [], []),
              "control no reorder or replenishment")
    else:
        check(starts == [("10", "0", "1")] and completes == [("11", "0", "1")] and
              deliveries == [("11", "1")] and arrivals == [("11", "6")] and
              returns == [("11", "6")], "change complete one-unit reorder ledger")
    check(log.count("reorder task") == (0 if arm == "control" else 2), f"{arm} no other reorder")
    check(log.count("Delivery with") == (0 if arm == "control" else 1), f"{arm} no other delivery")
    snapshots = re.findall(r"^  Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:(.*)$",
                           log, re.MULTILINE)
    expected_snapshots = [
        ("DEPOT-01", "4", "<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,"),
        ("BASE-01", "1", "<TEACH-DU-01,0,4>,"),
        ("BASE-01", "0", ""),
        ("DEPOT-01", "3", "<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,"),
    ]
    if arm == "change":
        expected_snapshots.append(
            ("DEPOT-01", "4", "<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,6>,"))
    expected_snapshots.append(("BASE-01", "1", "<TEACH-DU-01,0,0>,"))
    check(snapshots == expected_snapshots, f"{arm} complete physical stock snapshot sequence")
    check(len(re.findall(r" Take replacement item <TEACH-DU-01,0,\d+> from stock", log)) == 2 and
          len(re.findall(r" Put back replacement item <TEACH-DU-01,0,\d+> to stock", log)) ==
          (1 if arm == "control" else 2), f"{arm} complete physical stock movement count")
    check(len(rows(report, "StockTotalResults")) == 72 and
          all(r["NBO"] == 0 for r in rows(report, "StockTotalResults")),
          f"{arm} aggregate stock no backorder")
    observed[arm] = {"h10_depot_issue_physical_id": 0, "orders_started": starts,
                     "orders_completed": completes, "deliveries": deliveries,
                     "depot_arrival_physical_ids": [int(id_) for _, id_ in arrivals],
                     "depot_on_hand_first_bin": item[0]["STOHA"],
                     "depot_on_hand_terminal": item[-1]["STOHA"],
                     "item_NRO": total["NRO"]}

for name in ("ResultSummary", "SystemResults", "StockTotalResults", "MissionResults",
             "FixedMissionResultsTotal"):
    check(rows(reports["control"], name) == rows(reports["change"], name),
          f"paired {name} equality")
check(observed["control"]["depot_on_hand_terminal"] == 3 and
      observed["change"]["depot_on_hand_terminal"] == 4,
      "child-only replenishment terminal contrast")

verdict = {"schema": "simlox-i07-var02-author-replay/v1", "run_id": RUN.name,
           "closure_sha256": sha(RUN / "closure.json"), "passed": not FAILED,
           "checks": CHECKS, "checks_passed": CHECKS - len(FAILED), "failures": FAILED,
           "observed": observed,
           "limits": "One fixed seed, stock-based DU depot, ROSIZ2-to-1 at h5, one h10 demand. No multiple orders, other stocks, GUI or cross-engine claim."}
dest = HERE / "review/author-validation-2026-10-05.json"
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"{'GO' if verdict['passed'] else 'NO-GO'} {verdict['checks_passed']}/{CHECKS}")
for failure in FAILED:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)
