"""Independent read-only replay of the excluded D15.var01 seed-1 PMRF pair."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "d15-var01-pmrf-v100-ssh-20261004-01"
ARMS = ("certain", "fractional")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, value: bool) -> None:
    CHECKS.append((label, bool(value)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def table_map(doc: dict, top: str) -> dict[str, dict]:
    return {table["name"]: table for table in doc[top]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row, strict=True)) for row in rows(table)]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check("contract run ID", contract["run_id"] == RUN.name)
check("closure run ID", closure["run_id"] == RUN.name)
check("closure error null", closure["error"] is None)
check("outcome error null", outcome["error"] is None)
check("invocation seal", sha(RUN / "invocation.json") == closure["invocation_sha256"])
check("session zero", invocation["session_id"] == 0)
check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"])
check("host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("eight ordered steps", [step["name"] for step in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step completed {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None)
    check(f"GUI preserved {step['name']}", step["gui_preserved"] is True)

parent = CASES / "D14-var01-monitored-item-pm-v1.0.1"
sources = {
    "contract": CASE / "contract.json",
    "certain": CASE / "certain-input.json",
    "fractional": CASE / "fractional-input.json",
    "report_builder": CASE / "make_report_settings.py",
    "report_default": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "base01_selector": CASE / "runs" / "report-settings" / "base-01.sxs",
    "parent_input": parent / "native-input-monitored.json",
    "parent_closure": parent / "runs" / "d14-var01-monitored-v101-ssh-20261002-01" / "closure.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-10-02.md",
    "d03_signoff": CASES / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": CASE / "build.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for name, before in closure["source_hashes_before"].items():
    check(f"source before/after {name}", before == closure["source_hashes_after"][name] == invocation["source_hashes_before"][name])
    if name in sources:
        check(f"source SHA {name}", sha(sources[name]) == before)
for arm in ARMS:
    check(f"contract input SHA {arm}", contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
for name in ("parent_input", "parent_closure", "parent_signoff"):
    check(f"geometry parent SHA {name}", contract["dependency"][f"geometry_{name.removeprefix('parent_')}_sha256"] == closure["source_hashes_before"][name])
check("D03 prerequisite SHA", contract["dependency"]["catalog_parent_signoff_sha256"] == closure["source_hashes_before"]["d03_signoff"])
check("manual SHA", contract["manual"]["sha256"] == closure["source_hashes_before"]["manual"])
check("report default SHA", contract["report_settings"]["installed_default_sha256"] == closure["source_hashes_before"]["report_default"])
check("report selector SHA", contract["report_settings"]["base01_selector_sha256"] == closure["source_hashes_before"]["base01_selector"])

check("22 sealed raw files", len(closure["raw"]) == 22)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    check(f"raw bytes {name}", path.stat().st_size == seal["bytes"])
    check(f"raw SHA {name}", sha(path) == seal["sha256"])

models = {arm: table_map(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
check("identical table set", models["certain"].keys() == models["fractional"].keys())
check("source pair only description and PMReplacement", {name for name in models["certain"] if models["certain"][name] != models["fractional"][name]} == {"ProblemDescription", "PMReplacement"})
for arm, expected_pmrf in (("certain", 1), ("fractional", 0.5)):
    model = models[arm]
    check(f"36 authored tables {arm}", len(model) == 36)
    check(f"20 populated tables {arm}", sum(bool(rows(table)) for table in model.values()) == 20)
    check(f"run-local input copy {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
    replacement = records(model["PMReplacement"])
    check(f"one scheduled PM replacement {arm}", len(replacement) == 1 and replacement[0]["SCHED"] == "Y" and replacement[0]["PMRQ"] == 1 and replacement[0]["OPID"] is None and replacement[0]["PMRF"] == expected_pmrf)
    peer = records(models["fractional" if arm == "certain" else "certain"]["PMReplacement"])[0]
    check(f"replacement differs only PMRF {arm}", {k: v for k, v in replacement[0].items() if k != "PMRF"} == {k: v for k, v in peer.items() if k != "PMRF"})
    exported = table_map(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, table in model.items():
        original = records(table)
        if not original:
            continue
        check(f"roundtrip table {arm}/{name}", name in exported)
        if name not in exported:
            continue
        returned = records(exported[name])
        check(f"roundtrip rows {arm}/{name}", len(original) == len(returned))
        for index, (a, b) in enumerate(zip(original, returned)):
            for field, value in a.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{index}/{field}", b.get(field) == value)
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter zero errors {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
    check(f"converter only #108 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 300000)
    check(f"outcome completed {arm}", outcome[arm] == "completed")

check("event log byte parity", (RUN / "certain.log").read_bytes() == (RUN / "fractional.log").read_bytes())
logs = {arm: (RUN / f"{arm}.log").read_text(encoding="latin-1") for arm in ARMS}
opportunities = (24.0, 48.5, 73.0, 97.5)
for arm, log in logs.items():
    start_times = [float(value) for value in re.findall(r"Time: ([0-9.]+)\s+system PM task \d+ on <TEACH-AIR-01,0> started", log)]
    demand_times = [float(value) for value in re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0>", log)]
    removed_ids = re.findall(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-AIR-01,BASE-01,0> 1 PM tasks", log)
    replacements = re.findall(r"system PM task \d+ on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,(\d+)>", log)
    item_pm_starts = re.findall(r"^Time: [0-9.]+  item PM task \d+ on <TEACH-LRU-01,0,(\d+)> started", log, re.MULTILINE)
    completions = re.findall(r"^Time: [0-9.]+  system PM task \d+ on <TEACH-AIR-01,0> completed", log, re.MULTILINE)
    check(f"four PM opportunities {arm}", start_times == list(opportunities))
    check(f"four scheduled item demands {arm}", demand_times == list(opportunities))
    check(f"four distinct removed LRUs {arm}", removed_ids == ["1", "2", "3", "4"])
    check(f"four replacement LRUs {arm}", replacements == ["0", "1", "2", "3"])
    check(f"four local item PM starts {arm}", item_pm_starts == ["1", "2", "3", "4"])
    check(f"four system PM completions {arm}", len(completions) == 4)
    for time in opportunities:
        check(f"demand at PM start {arm}/{time}", f"Time: {time:g} <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in log)
    check(f"no terminal mission abort {arm}", "mission aborted:" not in log)

reports = {arm: table_map(native_report(RUN / f"{arm}-report-raw.json"), "report") for arm in ARMS}
check("same report tables", reports["certain"].keys() == reports["fractional"].keys())
for name, table in reports["certain"].items():
    if name != "ProblemDescription":
        check(f"non-description report equality {name}", table == reports["fractional"][name])
for arm in ARMS:
    check(f"240 System bins {arm}", len(rows(reports[arm]["SystemResults"])) == 240)
    check(f"240 StockTotal bins {arm}", len(rows(reports[arm]["StockTotalResults"])) == 240)
    for name in ("SystemResults", "StockTotalResults"):
        for index, sample in enumerate(records(reports[arm][name])):
            check(f"half-hour bin {arm}/{name}/{index}", sample["STINT"] == index / 2 and sample["ETINT"] == (index + 1) / 2)

failed = [label for label, passed in CHECKS if not passed]
event_parity = not failed
verdict = {
    "schema": "simlox-d15-v100-independent-diagnostic-replay/v1",
    "run_id": RUN.name,
    "verdict": "NO_GO_FULL_CONTRACT" if event_parity else "NO_GO_REPLAY",
    "diagnostic_replay": "GO" if event_parity else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "observed_pm_start_hours": list(opportunities),
    "observed_exchange_counts": {"certain": 4, "fractional": 4},
    "reason": "The fixed-seed fractional arm has four exchanges and zero no-exchange opportunities, failing the predeclared mixed fractional gate; selected item report export is also not yet sealed.",
    "event_log_sha256": sha(RUN / "certain.log"),
    "scope": "One seed and four scheduled system PM opportunities; this does not estimate PMRF probability or establish a mixed draw.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps(verdict, indent=2))
if failed:
    raise SystemExit(1)
