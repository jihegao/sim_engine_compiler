"""Independent read-only replay of sealed I07.var01 reorder lead-time contrast."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "i07-var01-reorder-leadt-v100-ssh-20261005-01"
ARMS = ("control", "change")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, ok: bool) -> None:
    CHECKS.append((label, bool(ok)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check("run identities", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("closure clean", closure["error"] is None and outcome["error"] is None)
check("invocation SHA", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
check("SSH session zero", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("global native mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("eight ordered steps", [step["name"] for step in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step success GUI preserved {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None)

parent = CASES / "E15-var07-explicit-istoh-v1.0.1"
sources = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "parent_input": parent / "native-input-explicit-three.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": parent / "make_report_settings.py",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector": parent / "runs" / "report-settings" / "item-position-results.sxs",
    "control": CASE / "control-input.json",
    "change": CASE / "change-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("complete source set", set(sources) == set(closure["source_hashes_before"]))
for key, before in closure["source_hashes_before"].items():
    check(f"source stable {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    check(f"source SHA {key}", sources[key].is_file() and sha(sources[key]) == before)
pins = {
    "parent_input": contract["dependency"]["input_sha256"],
    "parent_signoff": contract["dependency"]["signoff_sha256"],
    "settings_builder": contract["report_selector"]["builder_sha256"],
    "default_settings": contract["report_selector"]["default_sha256"],
    "selector": contract["report_selector"]["selector_sha256"],
    "builder": contract["builder_sha256"],
    "manual": contract["manual"]["sha256"],
    "dictionary": contract["manual"]["dictionary_sha256"],
}
for key, expected in pins.items():
    check(f"contract pin {key}", expected == closure["source_hashes_before"][key])
check("22 raw seals", len(closure["raw"]) == 22)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", sha(path) == seal["sha256"])

models = {arm: tables(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
parent_model = tables(load(sources["parent_input"]), "model")
check("32 tables and 22 populated each", all(len(model) == 32 and sum(bool(rows(table)) for table in model.values()) == 22 for model in models.values()))
for arm, model in models.items():
    check(f"E15 parent derivation {arm}", {name for name in parent_model if parent_model[name] != model[name]} == {"ProblemDescription"} and set(model) - set(parent_model) == {"ChangesItemReorder"})
    check(f"parent ItemReorder lead one {arm}", rows(model["ItemReorder"])[0]["LEADT"] == 1)
    check(f"input contract pin {arm}", sha(CASE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
    check(f"run-local source copy {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
check("pair differs only description and change row", {name for name in models["control"] if models["control"][name] != models["change"][name]} == {"ProblemDescription", "ChangesItemReorder"})
control_change = rows(models["control"]["ChangesItemReorder"])
active_change = rows(models["change"]["ChangesItemReorder"])
check("control null placeholder", len(control_change) == 1 and all(value is None for value in control_change[0].values()))
check("source-frozen TIMEC5 LEADT3 only", active_change == [{"IID": "TEACH-DU-01", "STID": "DEPOT-01", "TIMEC": 5, "LEADT": 3, "DISCF": None, "LEADTD": None, "ROINT": None, "NOTE": None}])

reports: dict[str, dict] = {}
observed = {}
for arm, model in models.items():
    exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, table in model.items():
        authored = rows(table)
        if not authored:
            continue
        check(f"roundtrip table present {arm}/{name}", name in exported)
        if name not in exported:
            continue
        native = exported[name]
        check(f"roundtrip exact columns {arm}/{name}", [(c["name"], c["datatype"]) for c in table["columns"]] == [(c["name"], c["datatype"]) for c in native["columns"]])
        back = rows(native)
        check(f"roundtrip row count {arm}/{name}", len(authored) == len(back))
        for i, (a, b) in enumerate(zip(authored, back)):
            for field, value in a.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{i}/{field}", b.get(field) == value)
    check(f"null change cells/placeholder exported {arm}", rows(exported["ChangesItemReorder"]) == (control_change if arm == "control" else active_change))
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter zero errors {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
    check(f"only warning 108 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
    check(f"outcome complete {arm}", outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0] and outcome["warning_codes"][arm] == ["108"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
    starts = [(float(t), float(d)) for t, d in re.findall(r"Time: ([\d.]+) <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: ([\d.]+)", log)]
    completions = [(float(t), float(d)) for t, d in re.findall(r"Time: ([\d.]+) <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was ([\d.]+)", log)]
    arrival = 11 if arm == "control" else 13
    duration = 1 if arm == "control" else 3
    check(f"one reorder trigger h10 and expected lead {arm}", starts == [(10, duration)] and completions == [(arrival, duration)])
    check(f"depot demand h10 qty one {arm}", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in log)
    check(f"two physical reorder receipts {arm}", len(re.findall(rf"Time: {arrival} <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item", log)) == 2)
    aborts = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission aborted:", log)]
    success = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission success:", log)]
    check(f"one abort/two successes {arm}", len(aborts) == 1 and abs(aborts[0] - 9.8829) < 1e-4 and success == [22, 34])
    rt = tables(native_report(RUN / f"{arm}-report-raw.json"), "report")
    reports[arm] = rt
    expected_tables = {"ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults", "ItemResultsTotal", "StockTotalResults"}
    check(f"ten selected report tables {arm}", set(rt) == expected_tables)
    item = rows(rt["ItemResults"])
    check(f"selected depot item identity and 72 bins {arm}", len(item) == 72 and all(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01" and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(item)))
    check(f"depot nominal four and on-hand path {arm}", all(row["STSZ"] == 4 and row["STOHA"] == (3 if row["STINT"] < 10 else 2 if row["STINT"] < arrival else 4) for row in item))
    check(f"one reorder in item bins {arm}", sum(row["NRO"] or 0 for row in item) == 1 and next(row for row in item if row["STINT"] == 10)["NRO"] == 1)
    item_total = rows(rt["ItemResultsTotal"])
    check(f"one selected item total {arm}", len(item_total) == 1 and item_total[0]["IID"] == "TEACH-DU-01" and item_total[0]["STID"] == "DEPOT-01")
    check(f"36-hour mean depot on-hand {arm}", abs(item_total[0]["STOHA"] - sum(row["STOHA"] for row in item) / 72) < 1e-6)
    check(f"mission summary ratio and table outcomes {arm}", len(rows(rt["ResultSummary"])) == 1 and abs(rows(rt["ResultSummary"])[0]["MSUF"] - 2 / 3) < 1e-6 and len(rows(rt["FixedMissionResults"])) == 3)
    check(f"72 mission/system/stock bins {arm}", all(len(rows(rt[name])) == 72 for name in ("MissionResults", "SystemResults", "StockTotalResults")))
    stock_bins, system_bins = rows(rt["StockTotalResults"]), rows(rt["SystemResults"])
    check(f"one h10 stock demand and system failure {arm}", sum(row["NDF"] or 0 for row in stock_bins) == 1 and stock_bins[20]["NDF"] == 1 and sum(row["NFAIL"] or 0 for row in system_bins) == 1)
    check(f"no ordinary stock backorder {arm}", all((row["NBO"] or 0) == 0 for row in stock_bins))
    observed[arm] = {"reorder_start": starts, "reorder_completion": completions, "mission_abort": aborts, "mission_success": success, "depot_on_hand_10": item[20]["STOHA"], "depot_on_hand_11": item[22]["STOHA"], "depot_on_hand_13": item[26]["STOHA"], "mean_on_hand": item_total[0]["STOHA"]}

check("all non-item reports identical except description", all(reports["control"][name] == reports["change"][name] for name in reports["control"] if name not in ("ProblemDescription", "ItemResults", "ItemResultsTotal")))
failed = [name for name, passed in CHECKS if not passed]
verdict = {"schema": "simlox-i07-var01-independent-replay/v1", "run_id": RUN.name, "verdict": "GO_BOUNDED" if not failed else "NO_GO", "checks": len(CHECKS), "passed": len(CHECKS) - len(failed), "failed": failed, "observed": observed, "limits": "One fixed seed, one existing depot ItemReorder, one source-frozen TIMEC5 LEADT change and one observed h10 reorder. The event log records reorder durations and receipts but does not separately announce application of the h5 change. No LEADTD, outstanding-order mutation, concurrent tie or general reorder policy claim."}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in verdict.items() if k != "observed"}, indent=2))
if failed:
    raise SystemExit(1)
