"""Independent read-only replay of the E14 five-seed, two-SRU panel."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
NATIVE = CASE / "runs" / "e14-var01-02-two-sru-panel-v100-ssh-20261005-01"
SELECTED = CASE / "runs" / "e14-var01-02-two-sru-panel-v100-item-report-ssh-20261005-01"
PARENT = CASES / "G01-var01-lru-sru-v1.0.1"
ARMS = [f"seed{seed}-{kind}" for seed in range(2, 7) for kind in ("control", "extra")]
IIDS = ("TEACH-LRU-01", "TEACH-SRU-01", "TEACH-SRU-02")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, result: bool) -> None:
    CHECKS.append((label, bool(result)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def table_map(doc: dict, root: str) -> dict[str, dict]:
    return {table["name"]: table for table in doc[root]["tables"]}


def records(table: dict) -> list[dict]:
    fields = [col["name"] for col in table["columns"]]
    return [dict(zip(fields, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def event_list(log: str, pattern: str) -> list[tuple[float, str]]:
    return [(float(time), item) for time, item in re.findall(pattern, log)]


contract = load(CASE / "contract.json")
native_closure = load(NATIVE / "closure.json")
native_invocation = load(NATIVE / "invocation.json")
native_steps = load(NATIVE / "steps.json")
native_outcome = load(NATIVE / "outcome.json")
report_closure = load(SELECTED / "closure.json")
report_invocation = load(SELECTED / "invocation.json")
report_steps = load(SELECTED / "steps.json")
report_outcome = load(SELECTED / "outcome.json")
check("run IDs", contract["run_id"] == native_closure["run_id"] == native_invocation["run_id"] == NATIVE.name and contract["selected_report_run_id"] == report_closure["run_id"] == report_invocation["run_id"] == SELECTED.name)
check("native closure clean", native_closure["error"] is None and native_outcome["error"] is None)
check("selected closure clean", report_closure["error"] is None and report_outcome["error"] is None)
check("native invocation seal", sha(NATIVE / "invocation.json") == native_closure["invocation_sha256"])
check("report invocation seal", sha(SELECTED / "invocation.json") == report_closure["invocation_sha256"])
check("report binds sealed native run", report_closure["source_closure_sha256"] == sha(NATIVE / "closure.json"))
for label, invocation in (("native", native_invocation), ("report", report_invocation)):
    check(f"{label} SSH session zero", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
    check(f"{label} host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    check(f"{label} protected GUI", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("same protected GUI", native_invocation["gui"] == report_invocation["gui"])
check("40 native steps ordered", [step["name"] for step in native_steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
check("30 selected steps ordered", [step["name"] for step in report_steps] == [f"{arm}-{iid.lower()}" for arm in ARMS for iid in IIDS])
for step in native_steps + report_steps:
    check(f"step clean {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)
for step in report_steps:
    check(f"report-only command {step['name']}", " -report -rpts " in step["arguments"] and " -rjexport " in step["arguments"] and " -calc " not in step["arguments"])

native_sources = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "selector_builder": CASE / "make_report_settings.py",
    "parent_input": PARENT / "native-input.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-01.md",
    "default": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector_lru": CASE / "runs" / "report-settings" / "teach-lru-01.sxs",
    "selector_sru01": CASE / "runs" / "report-settings" / "teach-sru-01.sxs",
    "selector_sru02": CASE / "runs" / "report-settings" / "teach-sru-02.sxs",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for arm in ARMS:
    native_sources[arm] = CASE / f"{arm}-input.json"
report_sources = {
    "contract": CASE / "contract.json",
    "native_closure": NATIVE / "closure.json",
    "selector_builder": CASE / "make_report_settings.py",
    "default": native_sources["default"],
    "selector_lru": native_sources["selector_lru"],
    "selector_sru01": native_sources["selector_sru01"],
    "selector_sru02": native_sources["selector_sru02"],
    "exe": native_sources["exe"],
    "report_runner": CASE / "run_item_reports_ssh.ps1",
    "python": native_sources["python"],
}
for arm in ARMS:
    report_sources[f"{arm}_sxo"] = NATIVE / f"{arm}.sxo"
for label, closure, invocation, sources in (("native", native_closure, native_invocation, native_sources), ("report", report_closure, report_invocation, report_sources)):
    check(f"{label} source key set", set(sources) == set(closure["source_hashes_before"]))
    for key, before in closure["source_hashes_before"].items():
        check(f"{label} source before/after {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
        check(f"{label} source SHA {key}", sources[key].is_file() and sha(sources[key]) == before)
    expected_raw = 102 if label == "native" else 62
    check(f"{label} raw seal count", len(closure["raw"]) == expected_raw)
    run = NATIVE if label == "native" else SELECTED
    for name, seal in closure["raw"].items():
        path = run / name
        check(f"{label} raw exists {name}", path.is_file())
        if path.is_file():
            check(f"{label} raw size {name}", path.stat().st_size == seal["bytes"])
            check(f"{label} raw SHA {name}", sha(path) == seal["sha256"])
check("accepted parent input pin", contract["dependency"]["parent_input_sha256"] == native_closure["source_hashes_before"]["parent_input"])
check("accepted parent signoff pin", contract["dependency"]["parent_signoff_sha256"] == native_closure["source_hashes_before"]["parent_signoff"])
check("manual pin", contract["manual"]["sha256"] == native_closure["source_hashes_before"]["manual"])
check("default selector pin", contract["report_settings"]["installed_default_sha256"] == native_closure["source_hashes_before"]["default"])
for iid, key in (("TEACH-LRU-01", "selector_lru"), ("TEACH-SRU-01", "selector_sru01"), ("TEACH-SRU-02", "selector_sru02")):
    check(f"selected selector pin {iid}", contract["report_settings"]["item_selector_sha256"][iid] == native_closure["source_hashes_before"][key] == report_closure["source_hashes_before"][key])

models = {arm: table_map(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
for kind in ("control", "extra"):
    base = models[f"seed2-{kind}"]
    for seed in range(3, 7):
        arm = f"seed{seed}-{kind}"
        model = models[arm]
        check(f"seed-only table delta {arm}", {name for name in base if base[name] != model[name]} == {"ProblemDescription", "Control"})
        left, right = records(base["Control"])[0], records(model["Control"])[0]
        check(f"seed-only Control field {arm}", {key for key in left if left[key] != right[key]} == {"RSEED"})
observed: dict[str, dict] = {}
total_extra = 0
total_nff = 0
for seed in range(2, 7):
    control, extra = f"seed{seed}-control", f"seed{seed}-extra"
    check(f"pair tables seed{seed}", models[control].keys() == models[extra].keys())
    check(f"pair changed tables seed{seed}", {name for name in models[control] if models[control][name] != models[extra][name]} == {"ProblemDescription", "ItemStructure"})
    cstructure, estructure = records(models[control]["ItemStructure"]), records(models[extra]["ItemStructure"])
    check(f"paired changed business cells seed{seed}", {(i, k) for i, (a, b) in enumerate(zip(cstructure, estructure)) for k in a if a[k] != b[k]} == {(i, k) for i in (1, 2) for k in ("RRF", "NFFF")})
    check(f"paired RRF/NFFF seed{seed}", all(cstructure[i]["RRF"] == cstructure[i]["NFFF"] == 1 and estructure[i]["RRF"] == 4 and estructure[i]["NFFF"] == 2 for i in (1, 2)))
    for kind in ("control", "extra"):
        arm = f"seed{seed}-{kind}"
        model = models[arm]
        check(f"contract input SHA {arm}", contract["inputs_sha256"][arm] == native_closure["source_hashes_before"][arm])
        check(f"native input copy {arm}", sha(NATIVE / f"{arm}-input.json") == contract["inputs_sha256"][arm])
        check(f"source seed {arm}", records(model["Control"])[0]["RSEED"] == str(seed))
        check(f"31 authored tables {arm}", len(model) == 31)
        check(f"21 populated tables {arm}", sum(bool(records(t)) for t in model.values()) == 21)
        exported = table_map(load(NATIVE / f"{arm}-roundtrip-raw.json"), "model")
        for name, table in model.items():
            original = records(table)
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
        converter = (NATIVE / f"{arm}-run.log").read_text(encoding="latin-1")
        check(f"converter zero errors {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
        check(f"converter only warning 108 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
        check(f"usable SXO {arm}", (NATIVE / f"{arm}.sxo").stat().st_size > 300000)
        check(f"native outcome {arm}", native_outcome["arms"][arm] == "completed" and native_outcome["converter_summaries"][arm] == [0, 1, 0])
        log = (NATIVE / f"{arm}.log").read_text(encoding="latin-1")
        extras = re.findall(r"Time: ([\d.]+).*extra removal of subitem <(TEACH-SRU-0[12]),0,(\d+)>( No Fault!)?", log)
        extra_by_lru = re.findall(r"Time: ([\d.]+).*item SURP task \d+ on <TEACH-LRU-01,0,(\d+)> extra removal of subitem <(TEACH-SRU-0[12]),0,(\d+)>", log)
        failed_sru = re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>.*subitem failed: <(TEACH-SRU-0[12]),0,(\d+)>", log)
        check(f"extra-removal LRU binding {arm}", len(extras) == len(extra_by_lru))
        for _, lru_id, primary_iid, primary_id in failed_sru:
            times = [float(time) for time, subject, _, _ in extra_by_lru if subject == lru_id]
            primary = re.findall(rf"Time: ([\d.]+) <{primary_iid},0,BASE-01,0> Item demand arrives.*item requiring maintenance is <{primary_iid},0,{primary_id}>", log)
            check(f"chronological serial extra removals {arm}/{lru_id}", times == sorted(times) and len(times) == len(set(times)))
            if primary and times:
                check(f"extra before primary issue {arm}/{lru_id}", max(times) < float(primary[0]))
        nffs = [row for row in extras if row[3]]
        check(f"control has no extra removals {arm}", kind == "extra" or not extras)
        nff_starts = [(float(t), iid, ident) for t, iid, ident in re.findall(r"Time: ([\d.]+)\s+item NFF task \d+ on <(TEACH-SRU-0[12]),0,(\d+)> started", log)]
        nff_ends = [(float(t), iid, ident) for t, iid, ident in re.findall(r"Time: ([\d.]+)\s+item NFF task \d+ on <(TEACH-SRU-0[12]),0,(\d+)> completed", log)]
        check(f"NFF task correspondence {arm}", len(nffs) == len(nff_starts) and {(iid, ident) for _, iid, ident in nff_starts} == {(iid, ident) for _, iid, ident, flag in extras if flag})
        start_by_id = {(iid, ident): time for time, iid, ident in nff_starts}
        check(f"NFF quarter-hour completed path {arm}", len(nff_ends) <= len(nff_starts) and all((iid, ident) in start_by_id and abs(end - start_by_id[iid, ident] - 0.25) < 0.0002 for end, iid, ident in nff_ends))
        check(f"NFF quarter-hour planned path {arm}", len(re.findall(r"within item NFF task \d+ on <TEACH-SRU-0[12],0,\d+> starts performing, planned to last for 0.25 hours", log)) == len(nff_starts))
        dirp_starts = event_list(log, r"Time: ([\d.]+)\s+item DIRP task \d+ on <(TEACH-SRU-0[12]),0,\d+> started")
        dirp_ends = event_list(log, r"Time: ([\d.]+)\s+item DIRP task \d+ on <(TEACH-SRU-0[12]),0,\d+> completed")
        check(f"ordinary SRU one-hour path {arm}", len(dirp_starts) >= len(dirp_ends) and all(item == item2 and abs(end - start - 1.0) < 0.0002 for (start, item), (end, item2) in zip(dirp_starts, dirp_ends)))
        total_extra += len(extras)
        total_nff += len(nffs)
        default_path = NATIVE / f"{arm}-report-raw.json"
        default_raw = default_path.read_text(encoding="utf-8-sig")
        try:
            json.loads(default_raw)
            strict_default = True
        except json.JSONDecodeError:
            strict_default = False
        normalized_default = re.sub(r",\s*([}\]])", r"\1", default_raw)
        check(f"default JSON trailing-comma diagnostic {arm}", not strict_default and len(default_raw) - len(normalized_default) == 8)
        native_tables = table_map(json.loads(normalized_default), "report")
        check(f"native 72 System/Stock bins {arm}", all(name in native_tables and len(records(native_tables[name])) == 72 for name in ("SystemResults", "StockTotalResults")))
        check(f"no resource report {arm}", "ResourceResults" not in native_tables)
        mission_success = len(re.findall(r"mission success:", log))
        mission_abort = len(re.findall(r"mission aborted:", log))
        check(f"three physical mission outcomes {arm}", mission_success + mission_abort == 3)
        observed[arm] = {"extra_removals": len(extras), "nff": len(nffs), "nff_completed_by_h36": len(nff_ends), "mission_success": mission_success, "mission_abort": mission_abort, "items": {}}
        for iid in IIDS:
            key = iid.lower()
            selected_path = SELECTED / f"{arm}-{key}-item-report-raw.json"
            selected = table_map(load(selected_path), "report")
            check(f"ItemResults present {arm}/{iid}", "ItemResults" in selected and "ItemResultsTotal" in selected)
            if "ItemResults" not in selected:
                continue
            item = records(selected["ItemResults"])
            total = records(selected["ItemResultsTotal"])
            check(f"selected 72 rows {arm}/{iid}", len(item) == 72 and len(total) == 1)
            check(f"selector IID/STID {arm}/{iid}", all(row["IID"] == iid and row["STID"] == "BASE-01" for row in item) and total[0]["IID"] == iid and total[0]["STID"] == "BASE-01")
            check(f"half-hour selected bins {arm}/{iid}", all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(item)))
            initial = 1 if iid == "TEACH-LRU-01" else 4
            check(f"selected nominal stock {arm}/{iid}", all(row["STSZ"] == initial for row in item))
            demand = event_list(log, rf"Time: ([\d.]+) <({iid}),0,BASE-01,0> Item demand arrives")
            withdrawn = event_list(log, rf"Time: ([\d.]+) <({iid}),0,BASE-01,0> Take replacement item")
            returned = event_list(log, rf"Time: ([\d.]+) <({iid}),0,BASE-01,0> Put back replacement item")
            check(f"demand/withdrawal event pair {arm}/{iid}", demand == withdrawn)
            check(f"stock count bounds {arm}/{iid}", all(0 <= row["STOHA"] <= initial + 0.001 for row in item))
            check(f"report demand/withdrawal sums {arm}/{iid}", sum(row["NDF"] or 0 for row in item) == len(demand) and sum(row["NWT"] or 0 for row in item) == len(withdrawn))
            check(f"report repair-return sum {arm}/{iid}", sum(row["NRP"] or 0 for row in item) == len(returned))
            check(f"report no backorder {arm}/{iid}", sum(row["NBO"] or 0 for row in item) == 0)
            check(f"report total row counts {arm}/{iid}", total[0]["NDF"] == len(demand) and total[0]["NWT"] == len(withdrawn) and total[0]["NRP"] == len(returned))
            for field, events in (("NDF", demand), ("NWT", withdrawn), ("NRP", returned)):
                report_bins = [index for index, row in enumerate(item) for _ in range(row[field] or 0)]
                event_bins = sorted(int(time * 2) for time, _ in events if time < 36)
                check(f"selected {field} event bins {arm}/{iid}", report_bins == event_bins)
            timeline = sorted([(time, -1) for time, _ in withdrawn] + [(time, 1) for time, _ in returned])
            expected = []
            for index in range(72):
                lo, hi = index / 2, (index + 1) / 2
                level = initial + sum(delta for time, delta in timeline if time <= lo)
                cursor = lo
                integral = 0.0
                for time, delta in timeline:
                    if lo < time < hi:
                        integral += (time - cursor) * level
                        cursor = time
                        level += delta
                integral += (hi - cursor) * level
                expected.append(integral / 0.5)
            check(f"selected stock interval ledger {arm}/{iid}", all(abs(row["STOHA"] - expected[index]) < 0.001 for index, row in enumerate(item)))
            terminal_physical = initial - len(withdrawn) + len(returned)
            check(f"terminal physical stock balance {arm}/{iid}", 0 <= terminal_physical <= initial)
            observed[arm]["items"][iid] = {"demands": len(demand), "withdrawals": len(withdrawn), "stock_returns": len(returned), "terminal_physical_stock": terminal_physical, "terminal_stock_interval_average": item[-1]["STOHA"]}

for seed in range(2, 7):
    a, b = observed[f"seed{seed}-control"], observed[f"seed{seed}-extra"]
    check(f"paired outcomes enumerated seed{seed}", a["mission_success"] + a["mission_abort"] == b["mission_success"] + b["mission_abort"] == 3)
check("panel extra-removal witness", total_extra > 0)
check("panel NFF witness", total_nff > 0)
failed = [label for label, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-e14-two-sru-independent-replay/v1",
    "native_run_id": NATIVE.name,
    "selected_report_run_id": SELECTED.name,
    "verdict": "GO_BOUNDED" if not failed else "NO_GO_REPLAY",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "extra_removals": total_extra,
    "no_fault_found": total_nff,
    "observed": observed,
    "limits": "RRF and NFFF change together, so their separate causal effects are not isolated. Seed5 extra has a third NFF quarter-hour task started at h35.8124; it is still open at the h36 cutoff, so only two of that arm's three NFF tasks complete in-window. Five fixed seeds, one base, two SRU positions and h36. No maintenance-resource competition is modeled; no population probability or general routing claim.",
    "report_parser_status": "All 10 default -jsonreport files contain a trailing comma before report.tables closing bracket and require that one syntax normalization for inspection; all 30 selected -rjexport reports are strict JSON.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: val for key, val in verdict.items() if key != "observed"}, indent=2))
if failed:
    raise SystemExit(1)
