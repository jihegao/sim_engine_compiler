"""Independent, read-only native-stage replay of the D15 PMRF seed panel."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "d15-var01-pmrf-seed-panel-v101-ssh-20261004-01"
SELECTED = CASE / "runs" / "d15-var01-pmrf-seed-panel-v101-item-report-ssh-20261004-01"
PREV = CASES / "D15-var01-pmrf-scheduled-v1.0.0"
GEOMETRY = CASES / "D14-var01-monitored-item-pm-v1.0.1"
ARMS = [f"seed{seed}-{kind}" for seed in range(2, 7) for kind in ("certain", "fractional")]
OPPORTUNITIES = [24.0, 48.5, 73.0, 97.5]
EXPECTED_FRACTIONAL = {2: 2, 3: 4, 4: 2, 5: 3, 6: 2}
CHECKS: list[tuple[str, bool]] = []


def check(label: str, result: bool) -> None:
    CHECKS.append((label, bool(result)))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def table_map(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    fields = [col["name"] for col in table["columns"]]
    return [dict(zip(fields, row, strict=True)) for row in rows(table)]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check("closure SHA", digest(RUN / "closure.json") == "ab02b29de7bb7cfe4397aae19d34d95a3a31f31c2f0fe7fe692d398f8f768fc9")
check("run ID", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("native closure clean", closure["error"] is None and outcome["error"] is None)
check("invocation seal", digest(RUN / "invocation.json") == closure["invocation_sha256"])
check("SSH session zero", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("global native mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("40 ordered steps", [step["name"] for step in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step result {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None)
    check(f"GUI preserved {step['name']}", step["gui_preserved"] is True)

sources = {
    "contract": CASE / "contract.json",
    "base_certain": PREV / "certain-input.json",
    "base_fractional": PREV / "fractional-input.json",
    "diagnostic_closure": PREV / "runs" / "d15-var01-pmrf-v100-ssh-20261004-01" / "closure.json",
    "report_builder": CASE / "make_report_settings.py",
    "report_default": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "base01_selector": CASE / "runs" / "report-settings" / "base-01.sxs",
    "parent_input": GEOMETRY / "native-input-monitored.json",
    "parent_closure": GEOMETRY / "runs" / "d14-var01-monitored-v101-ssh-20261002-01" / "closure.json",
    "parent_signoff": GEOMETRY / "cli-scope-signoff-2026-10-02.md",
    "d03_signoff": CASES / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": CASE / "build.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for arm in ARMS:
    sources[arm] = CASE / f"{arm}-input.json"
check("source seal key set", set(sources) == set(closure["source_hashes_before"]))
for key, before in closure["source_hashes_before"].items():
    check(f"source before/after {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    check(f"source on disk {key}", sources[key].is_file() and digest(sources[key]) == before)
for arm in ARMS:
    check(f"contract input pin {arm}", contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
dependency = contract["dependency"]
for key, source_key in (("certain", "base_certain"), ("fractional", "base_fractional")):
    check(f"predecessor source {key}", dependency["source_inputs_sha256"][key] == closure["source_hashes_before"][source_key])
check("predecessor diagnostic", dependency["excluded_diagnostic_closure_sha256"] == closure["source_hashes_before"]["diagnostic_closure"])
check("accepted geometry", dependency["accepted_geometry_input_sha256"] == closure["source_hashes_before"]["parent_input"])
check("manual pin", contract["manual"]["sha256"] == closure["source_hashes_before"]["manual"])
check("102 raw seals", len(closure["raw"]) == 102)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", digest(path) == seal["sha256"])

model = {arm: table_map(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
baseline = {kind: table_map(load(PREV / f"{kind}-input.json"), "model") for kind in ("certain", "fractional")}
event_counts: dict[str, dict] = {}
for seed in range(2, 7):
    certain, fractional = f"seed{seed}-certain", f"seed{seed}-fractional"
    check(f"paired table sets seed{seed}", model[certain].keys() == model[fractional].keys())
    check(f"paired table delta seed{seed}", {name for name in model[certain] if model[certain][name] != model[fractional][name]} == {"ProblemDescription", "PMReplacement"})
    check(f"paired PMRF seed{seed}", records(model[certain]["PMReplacement"])[0]["PMRF"] == 1 and records(model[fractional]["PMReplacement"])[0]["PMRF"] == 0.5)
    for kind in ("certain", "fractional"):
        arm = f"seed{seed}-{kind}"
        check(f"baseline table set {arm}", model[arm].keys() == baseline[kind].keys())
        check(f"seed-only table delta {arm}", {name for name in model[arm] if model[arm][name] != baseline[kind][name]} == {"ProblemDescription", "Control"})
        check(f"seed value {arm}", records(model[arm]["Control"])[0]["RSEED"] == str(seed))
        base_control = records(baseline[kind]["Control"])[0]
        seed_control = records(model[arm]["Control"])[0]
        check(f"only RSEED control change {arm}", {key for key in base_control if base_control[key] != seed_control[key]} == {"RSEED"})
        check(f"local source copy {arm}", digest(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
        check(f"36 tables {arm}", len(model[arm]) == 36)
        check(f"20 populated tables {arm}", sum(bool(rows(t)) for t in model[arm].values()) == 20)
        exported = table_map(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
        for name, authored in model[arm].items():
            original = records(authored)
            if not original:
                continue
            check(f"roundtrip table {arm}/{name}", name in exported)
            if name not in exported:
                continue
            returned = records(exported[name])
            check(f"roundtrip row count {arm}/{name}", len(original) == len(returned))
            for index, (a, b) in enumerate(zip(original, returned)):
                for field, value in a.items():
                    if value is not None:
                        check(f"roundtrip cell {arm}/{name}/{index}/{field}", b.get(field) == value)
        converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
        check(f"converter success {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
        check(f"only warning 108 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
        check(f"outcome completed {arm}", outcome["arms"][arm] == "completed")
        check(f"outcome converter {arm}", outcome["converter_summaries"][arm] == [0, 1, 0] and outcome["warning_codes"][arm] == ["108"])
        check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 300000)
        log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
        starts = [float(x) for x in re.findall(r"Time: ([\d.]+)\s+system PM task \d+ on <TEACH-AIR-01,0> started", log)]
        completes = re.findall(r"Time: [\d.]+\s+system PM task \d+ on <TEACH-AIR-01,0> completed", log)
        demand = [float(x) for x in re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0>", log)]
        removed = re.findall(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-AIR-01,BASE-01,0> 1 PM tasks", log)
        received = re.findall(r"system PM task \d+ on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,(\d+)>", log)
        item_pm = re.findall(r"Time: [\d.]+\s+item PM task \d+ on <TEACH-LRU-01,0,(\d+)> started", log)
        returns = re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", log)
        withdrawals = re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", log)
        withdrawal_hours = [float(x) for x in re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item", log)]
        stock_return_hours = [float(x) for x in re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item", log)]
        item_pm_completion_hours = [float(x) for x in re.findall(r"Time: ([\d.]+)\s+item PM task \d+ on <TEACH-LRU-01,0,\d+> completed", log)]
        remove_starts = re.findall(r"remove subitem subtask \d+ seqno 0 within system PM task \d+ on <TEACH-AIR-01,0> started", log)
        fit_completions = re.findall(r"fit subitem subtask \d+ seqno 2 within system PM task \d+ on <TEACH-AIR-01,0> completed", log)
        check(f"four opportunities {arm}", starts == OPPORTUNITIES and len(completes) == 4)
        check(f"remove and fit at four PMs {arm}", len(remove_starts) == len(fit_completions) == 4)
        check(f"exchange event cardinality {arm}", len(demand) == len(removed) == len(received) == len(item_pm) == len(returns))
        check(f"exchange opportunity binding {arm}", all(t in OPPORTUNITIES for t in demand) and len(demand) == len(set(demand)))
        check(f"removed item PM and stock return {arm}", removed == item_pm == returns)
        check(f"physical replacement IDs {arm}", len(received) == len(set(received)))
        check(f"stock withdrawals match installed replacements {arm}", withdrawals == received)
        check(f"stock event time ordering {arm}", withdrawal_hours == demand and len(stock_return_hours) == len(demand) and all(a < b for a, b in zip(withdrawal_hours, stock_return_hours)))
        check(f"item overhaul completion matches return {arm}", item_pm_completion_hours == stock_return_hours)
        check(f"no terminal mission abort {arm}", "mission aborted:" not in log)
        expected = 4 if kind == "certain" else EXPECTED_FRACTIONAL[seed]
        check(f"exchange count {arm}", len(demand) == expected)
        report_tables = table_map(report(RUN / f"{arm}-report-raw.json"), "report")
        check(f"report table set {arm}", set(report_tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        system = records(report_tables["SystemResults"])
        stock = records(report_tables["StockTotalResults"])
        check(f"240 half-hour System bins {arm}", len(system) == 240 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(system)))
        check(f"240 half-hour Stock bins {arm}", len(stock) == 240 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(stock)))
        check(f"report PM count {arm}", sum(r["NPMS"] or 0 for r in system) == 4 and sum(r["NPMT"] or 0 for r in system) == 4)
        check(f"no report failures {arm}", sum(r["NFAIL"] or 0 for r in system) == 0)
        check(f"stock report demand and withdrawal count {arm}", sum(r["NDP"] or 0 for r in stock) == len(demand) and sum(r["NWT"] or 0 for r in stock) == len(withdrawals))
        event_counts[arm] = {"opportunities": starts, "demand_hours": demand, "return_hours": stock_return_hours, "removed_ids": removed, "replacement_ids": received, "exchanges": len(demand)}

selected_closure = load(SELECTED / "closure.json")
selected_invocation = load(SELECTED / "invocation.json")
selected_steps = load(SELECTED / "steps.json")
selected_outcome = load(SELECTED / "outcome.json")
check("selected report closure run", selected_closure["run_id"] == selected_invocation["run_id"] == SELECTED.name)
check("selected report source run", selected_closure["source_run_id"] == selected_invocation["source_run_id"] == RUN.name)
check("selected report native closure pin", selected_closure["source_closure_sha256"] == digest(RUN / "closure.json"))
check("selected report invocation seal", selected_closure["invocation_sha256"] == digest(SELECTED / "invocation.json"))
check("selected report clean", selected_closure["error"] is None and selected_outcome == {"status": "completed", "error": None})
check("selected report SSH0", selected_invocation["session_id"] == 0 and "sshd.exe" in selected_invocation["ssh_ancestor_names"])
check("selected report mutex", selected_invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("selected report protected GUI", selected_invocation["gui"] == invocation["gui"])
check("ten serial selected steps", [step["name"] for step in selected_steps] == [f"{arm}-base-01" for arm in ARMS])
for step in selected_steps:
    check(f"selected report step {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)
    check(f"selected report command {step['name']}", " -report -rpts " in step["arguments"] and " -rjexport " in step["arguments"] and " -close" in step["arguments"])
selected_sources = {
    "contract": CASE / "contract.json",
    "native_closure": RUN / "closure.json",
    "selector_base01": CASE / "runs" / "report-settings" / "base-01.sxs",
    "selector_builder": CASE / "make_report_settings.py",
    "default": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "report_runner": CASE / "run_item_reports_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for arm in ARMS:
    selected_sources[f"{arm}_sxo"] = RUN / f"{arm}.sxo"
check("selected source key set", set(selected_sources) == set(selected_closure["source_hashes_before"]))
for key, before in selected_closure["source_hashes_before"].items():
    check(f"selected source before/after {key}", before == selected_closure["source_hashes_after"][key] == selected_invocation["source_hashes_before"][key])
    check(f"selected source on disk {key}", selected_sources[key].is_file() and digest(selected_sources[key]) == before)
check("22 selected raw seals", len(selected_closure["raw"]) == 22)
for name, seal in selected_closure["raw"].items():
    path = SELECTED / name
    check(f"selected raw exists {name}", path.is_file())
    if path.is_file():
        check(f"selected raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"selected raw SHA {name}", digest(path) == seal["sha256"])
for arm in ARMS:
    selected = table_map(report(SELECTED / f"{arm}-base-01-item-report-raw.json"), "report")
    check(f"selected ItemResults present {arm}", "ItemResults" in selected and "ItemResultsTotal" in selected)
    check(f"selected report not default fallback {arm}", "ItemResults" not in table_map(report(RUN / f"{arm}-report-raw.json"), "report"))
    item = records(selected["ItemResults"])
    item_total = records(selected["ItemResultsTotal"])
    check(f"one selected BASE-01 item {arm}", len(item) == 240 and len(item_total) == 1 and all(row["IID"] == "TEACH-LRU-01" and row["STID"] == "BASE-01" for row in item) and item_total[0]["IID"] == "TEACH-LRU-01" and item_total[0]["STID"] == "BASE-01")
    check(f"selected half-hour bins {arm}", all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(item)))
    check(f"selected nominal stock/no backorder {arm}", all(row["STSZ"] == 1 and row["NBO"] == 0 and 0 <= row["STOHA"] <= 1.00005 for row in item))
    demands = event_counts[arm]["demand_hours"]
    returns = event_counts[arm]["return_hours"]
    demand_bins = [i for i, row in enumerate(item) if row["NDP"]]
    overhaul_bins = [i for i, row in enumerate(item) if row["NPM"]]
    check(f"selected demand bins {arm}", demand_bins == [int(t * 2) for t in demands] and all(item[i]["NDP"] == item[i]["NWT"] == 1 for i in demand_bins))
    check(f"selected overhaul bins {arm}", overhaul_bins == [int(t * 2) for t in returns] and all(item[i]["NPM"] == 1 for i in overhaul_bins))
    check(f"selected aggregate counts {arm}", sum(row["NDP"] or 0 for row in item) == sum(row["NWT"] or 0 for row in item) == sum(row["NPM"] or 0 for row in item) == len(demands) and item_total[0]["NDP"] == item_total[0]["NWT"] == item_total[0]["NPM"] == len(demands))
    check(f"selected backorder total zero {arm}", sum(row["NBO"] or 0 for row in item) == 0 and item_total[0]["NBO"] == 0)
    expected_stock = [1 - sum(max(0.0, min((i + 1) / 2, b) - max(i / 2, a)) for a, b in zip(demands, returns)) / 0.5 for i in range(240)]
    check(f"selected stock interval integral {arm}", all(abs(row["STOHA"] - expected_stock[i]) < 0.0001 for i, row in enumerate(item)))

check("fractional panel mixed", any(event_counts[f"seed{s}-fractional"]["exchanges"] < 4 for s in range(2, 7)))
check("certain panel all exchanges", all(event_counts[f"seed{s}-certain"]["exchanges"] == 4 for s in range(2, 7)))
failed = [label for label, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-d15-pmrf-seed-panel-independent-native-replay/v1",
    "run_id": RUN.name,
    "verdict": "GO_FULL_CONTRACT_BOUNDED" if not failed else "NO_GO_FULL_REPLAY",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "observed": event_counts,
    "selected_report_run_id": SELECTED.name,
    "selected_report_closure_sha256": digest(SELECTED / "closure.json"),
    "limits": "Five fixed seeds and four PM opportunities per arm. Selected BASE-01 item bins support local stock and backorder reconciliation. This panel is not a general PMRF probability estimate or evidence beyond the fixed modeled geometry and run settings.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in verdict.items() if k != "observed"}, indent=2))
if failed:
    raise SystemExit(1)
