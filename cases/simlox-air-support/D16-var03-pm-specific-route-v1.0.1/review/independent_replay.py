"""Independent, read-only replay of the D16.var03 sealed CLI pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "d16-var03-pm-route-v101-ssh-20261005-01"
PARENT = CASES / "D12-var04-remote-critical-v1.0.1"
PARENT_RUN = PARENT / "runs" / "d12-var04-remote-critical-v101-ssh-20261004-01"
DIAGNOSTIC = CASES / "D16-var03-pm-specific-route-v1.0.0" / "runs" / "d16-var03-pm-route-v100-ssh-20261005-01" / "closure.json"
ARMS = ("default", "pm_specific")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, ok: bool) -> None:
    CHECKS.append((label, bool(ok)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict, root: str) -> dict:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check("run identities", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("closure and outcome clean", closure["error"] is None and outcome["error"] is None)
check("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
check("SSH session zero", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("eight ordered steps", [s["name"] for s in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step successful and GUI preserved {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)

source_paths = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "parent_input": PARENT / "remote-input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
    "diagnostic_closure": DIAGNOSTIC,
    "default": CASE / "default-input.json",
    "pm_specific": CASE / "pm_specific-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("source key set", set(source_paths) == set(closure["source_hashes_before"]))
for key, before in closure["source_hashes_before"].items():
    check(f"source stable {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    check(f"source seal {key}", source_paths[key].is_file() and sha(source_paths[key]) == before)
for key, expected in (("parent_input", contract["dependency"]["input_sha256"]), ("parent_closure", contract["dependency"]["closure_sha256"]), ("parent_signoff", contract["dependency"]["signoff_sha256"]), ("builder", contract["builder_sha256"]), ("manual", contract["manual"]["sha256"]), ("dictionary", contract["manual"]["dictionary_sha256"])):
    check(f"contract pin {key}", expected == closure["source_hashes_before"][key])
check("excluded diagnostic closure pin", contract["excluded_diagnostic_closure_sha256"] == closure["source_hashes_before"]["diagnostic_closure"])
check("raw seal count", len(closure["raw"]) == 22)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", sha(path) == seal["sha256"])

model = {arm: tables(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
parent_model = tables(load(PARENT / "remote-input.json"), "model")
check("common 32 table geometry", all(len(model[a]) == 32 for a in ARMS))
check("paired changed tables", {name for name in model["default"] if model["default"][name] != model["pm_specific"][name]} == {"ProblemDescription", "PMStationStructure"})
check("parent to default changed tables", {name for name in parent_model if name in model["default"] and parent_model[name] != model["default"][name]} == {"ProblemDescription"} and set(model["default"]) - set(parent_model) == {"PMStationStructure"})
check("default PM route null placeholder", len(rows(model["default"]["PMStationStructure"])) == 1 and all(value is None for value in rows(model["default"]["PMStationStructure"])[0].values()))
check("specific CAL24 route", rows(model["pm_specific"]["PMStationStructure"]) == [{"PMID": "CAL24", "ID": "TEACH-AIR-01", "STID": "BASE-01", "MSTID": "BASE-02", "TFRMS": 1.0, "TTOMS": 1.0, "CFRMS": None, "CTOMS": None, "DFRAC": 1.0, "OPOL": "SLOW", "PFRMS": None, "PTOMS": None, "NOTE": None}])
check("generic quarter-hour link common", rows(model["default"]["StationStructure"]) == rows(model["pm_specific"]["StationStructure"]) and rows(model["default"]["StationStructure"])[0]["TFRMS"] == rows(model["default"]["StationStructure"])[0]["TTOMS"] == 0.25)
check("parent event baseline byte identical", sha(RUN / "default.log") == sha(PARENT_RUN / "remote.log"))

observed = {}
for arm in ARMS:
    check(f"input contract SHA {arm}", sha(CASE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
    check(f"run-local input SHA {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
    exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    check(f"24 authored populated tables {arm}", sum(bool(rows(table)) for table in model[arm].values()) == 24)
    authored_route = model[arm]["PMStationStructure"]
    exported_route = exported["PMStationStructure"]
    check(f"exact PMStationStructure columns {arm}", [(c["name"], c["datatype"]) for c in authored_route["columns"]] == [(c["name"], c["datatype"]) for c in exported_route["columns"]])
    check(f"exact PMStationStructure row count {arm}", len(rows(authored_route)) == len(rows(exported_route)))
    check(f"exact PMStationStructure cells {arm}", rows(authored_route) == rows(exported_route))
    for name, authored in model[arm].items():
        original = rows(authored)
        if not original:
            continue
        check(f"roundtrip table present {arm}/{name}", name in exported)
        if name not in exported:
            continue
        returned = exported[name]
        authored_columns = {c["name"]: c["datatype"] for c in authored["columns"]}
        native_columns = {c["name"]: c["datatype"] for c in returned["columns"]}
        check(f"roundtrip exact populated columns {arm}/{name}", [(c["name"], c["datatype"]) for c in authored["columns"]] == [(c["name"], c["datatype"]) for c in returned["columns"]])
        extra = set(native_columns) - set(authored_columns)
        if extra:
            check(f"native-only columns null {arm}/{name}", all(all(row.get(field) is None for field in extra) for row in rows(returned)))
        back = rows(returned)
        check(f"roundtrip row count {arm}/{name}", len(original) == len(back))
        for i, (a, b) in enumerate(zip(original, back)):
            for field, value in a.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{i}/{field}", b.get(field) == value)
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"zero-error converter {arm}", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter)
    check(f"classified warnings {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108", "126"])
    check(f"outcome complete {arm}", outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"])
    check(f"nonempty native output {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
    legs = [(float(t), float(hours)) for t, hours in re.findall(r"Time: ([\d.]+)  transport task \d+ starts with 1 items/systems, transport time: ([\d.]+)", log)]
    arrivals = [float(t) for t in re.findall(r"Time: ([\d.]+)  transport task \d+ arrives with 1 items/systems", log)]
    departure = 0.25 if arm == "default" else 1.0
    check(f"four physical travel legs {arm}", len(legs) == len(arrivals) == 4 and [x[0] for x in legs] == [24, 24, 25.25 if arm == "default" else 26, 25.25 if arm == "default" else 26] and all(x[1] == departure for x in legs))
    check(f"arrival times {arm}", arrivals == ([24.25, 24.25, 25.5, 25.5] if arm == "default" else [25, 25, 27, 27]))
    tasks = [(float(t), int(task), int(aircraft), action) for t, task, aircraft, action in re.findall(r"Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,(\d+)> (started|completed)", log)]
    cal_start = 24.25 if arm == "default" else 25
    cal_end = cal_start + 1
    big_start = 25.5 if arm == "default" else 27
    big_end = big_start + 1
    expected = [(cal_start, 0, 1, "started"), (cal_start, 1, 0, "started"), (cal_end, 0, 1, "completed"), (cal_end, 1, 0, "completed"), (big_start, 2, 1, "started"), (big_start, 3, 0, "started"), (big_end, 2, 1, "completed"), (big_end, 3, 0, "completed")]
    check(f"CAL24 and BIG24P75 timing for both aircraft {arm}", tasks == expected and len(re.findall(r"PMID: CAL24", log)) == len(re.findall(r"PMID: BIG24P75", log)) == 2)
    check(f"one mission succeeds and no abort/cancel {arm}", len(re.findall(r"mission success:", log)) == 1 and "mission aborted:" not in log and "mission cancelled:" not in log)
    rt = tables(report(RUN / f"{arm}-report-raw.json"), "report")
    check(f"six default report tables {arm}", set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
    sys, stock, resource = (rows(rt[name]) for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
    check(f"60 half-hour report bins {arm}", all(len(group) == 60 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(group)) for group in (sys, stock, resource)))
    check(f"four PM completions in report {arm}", sum(row["NPMT"] or 0 for row in sys) == 4)
    check(f"PM work hours in system/resource bins {arm}", abs(sum((row["NSYPM"] or 0) * 0.5 for row in sys) - 4) < 1e-3 and abs(sum((row["NRUM"] or 0) * 0.5 for row in resource) - 4) < 1e-3)
    check(f"physical transport occupancy integral {arm}", abs(sum((row["NSYTP"] or 0) * 0.5 for row in sys) - 4 * departure) < 1e-3)
    check(f"mission summary and zero failures {arm}", len(rows(rt["ResultSummary"])) == 1 and rows(rt["ResultSummary"])[0]["MSUF"] == 1 and sum(row["NFAIL"] or 0 for row in sys) == 0)
    check(f"stock ledger zero backorder and demand {arm}", all(all((row[field] or 0) == 0 for field in ("NBO", "NBOU", "NDF", "NDD", "NDR")) for row in stock))
    check(f"two aircraft terminal ready {arm}", sys[-1]["NSYRY"] == 2 and all(f"<TEACH-AIR-01,{i}> nbr ready increased at unit:" in log for i in (0, 1)))
    observed[arm] = {"travel_hours_per_leg": departure, "leg_starts": legs, "leg_arrivals": arrivals, "cal24_start": cal_start, "cal24_completion": cal_end, "big24p75_start": big_start, "big24p75_completion": big_end, "transport_aircraft_hours": sum((row["NSYTP"] or 0) * 0.5 for row in sys), "pm_work_hours": sum((row["NSYPM"] or 0) * 0.5 for row in sys), "terminal_ready": sys[-1]["NSYRY"]}

failures = [label for label, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-d16-var03-independent-replay/v1",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failures),
    "failed": failures,
    "observed": observed,
    "reason": "The exporter-compatible 13-column PMStationStructure and default null placeholder roundtrip exactly. Two aircraft use quarter-hour versus one-hour travel legs while CAL24 work remains one hour at BASE-02, with PM/resource/system/stock reports reconciled. The v1.0.0 roundtrip failure remains excluded.",
    "limits": "One fixed seed, two aircraft, a single CAL24 system PM route and deterministic quarter-hour versus one-hour travel. BIG24P75 follows CAL24 on return; this does not isolate preemption. No CM-specific route or general policy claim.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in verdict.items() if k != "observed"}, indent=2))
if failures:
    raise SystemExit(1)
