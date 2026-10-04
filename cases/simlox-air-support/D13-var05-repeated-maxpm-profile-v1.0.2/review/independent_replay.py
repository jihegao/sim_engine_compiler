"""Independent, read-only replay of the sealed D13.var05 direct-LIMIT run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "d13-repeated-maxpm-profile-v102-ssh-20261004-01"
CHECKS: list[tuple[str, bool]] = []


def check(label: str, condition: bool) -> None:
    CHECKS.append((label, bool(condition)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    # The native 2017 exporter emits a trailing comma after the last table.
    text = path.read_text(encoding="utf-8-sig")
    check(f"native report trailing-comma form {path.name}", bool(re.search(r",\s*]\s*}\s*}$", text)))
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(document: dict, top: str) -> dict[str, dict]:
    return {t["name"]: t for t in document[top]["tables"]}


def rows(table: dict) -> list[list]:
    return [r for instance in table["instances"] for r in instance["rows"]]


def keyed_rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for row in rows(table)]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")

check("contract run ID", contract["run_id"] == RUN.name)
check("closure run ID", closure["run_id"] == RUN.name)
check("closure has no error", closure["error"] is None)
check("outcome has no error", outcome["error"] is None)
check("invocation seal", sha(RUN / "invocation.json") == closure["invocation_sha256"])
check("session zero", invocation["session_id"] == 0)
check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"])
check("global serial mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("eight ordered native steps", [s["name"] for s in steps] == [f"{a}_{stage}" for a in ("flat", "nested") for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step completed {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None)
    check(f"GUI preserved {step['name']}", step["gui_preserved"] is True)

source_paths = {
    "contract": CASE / "contract.json",
    "flat": CASE / "flat-input.json",
    "nested": CASE / "nested-input.json",
    "parent_input": CASES / "D13-var03-dynamic-maxpm-v1.0.0" / "rise-input.json",
    "parent_closure": CASES / "D13-var03-dynamic-maxpm-v1.0.0" / "runs" / "d13-dynamic-maxpm-v100-ssh-20261004-01" / "closure.json",
    "parent_signoff": CASES / "D13-var03-dynamic-maxpm-v1.0.0" / "cli-scope-signoff-2026-10-04.md",
    "build.py": CASE / "build.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, expected in closure["source_hashes_before"].items():
    check(f"source unchanged in closure {key}", expected == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    if key in source_paths:
        check(f"source SHA {key}", sha(source_paths[key]) == expected)
check("contract flat SHA", closure["source_hashes_before"]["flat"] == contract["inputs_sha256"]["flat"])
check("contract repeated SHA", closure["source_hashes_before"]["nested"] == contract["inputs_sha256"]["nested"])
check("parent input SHA", closure["source_hashes_before"]["parent_input"] == contract["dependency"]["parent_input_sha256"])
check("parent closure SHA", closure["source_hashes_before"]["parent_closure"] == contract["dependency"]["parent_closure_sha256"])
check("parent signoff SHA", closure["source_hashes_before"]["parent_signoff"] == contract["dependency"]["parent_signoff_sha256"])
check("manual SHA", closure["source_hashes_before"]["manual"] == contract["manual"]["sha256"])
for version in ("v100", "v101"):
    path = CASES / ("D13-var05-repeated-maxpm-profile-v1.0.0" if version == "v100" else "D13-var05-repeated-maxpm-profile-v1.0.1") / "runs" / f"d13-repeated-maxpm-profile-{version}-ssh-20261004-01" / "closure.json"
    check(f"excluded {version} closure SHA", sha(path) == contract[f"excluded_diagnostic_{version}_closure_sha256"])

check("22 sealed raw files", len(closure["raw"]) == 22)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    check(f"raw length {name}", path.stat().st_size == seal["bytes"])
    check(f"raw SHA {name}", sha(path) == seal["sha256"])

input_docs = {arm: load(CASE / f"{arm}-input.json") for arm in ("flat", "nested")}
parent_doc = load(source_paths["parent_input"])
parent_tables = tables(parent_doc, "model")
arm_tables = {arm: tables(input_docs[arm], "model") for arm in input_docs}
for arm in ("flat", "nested"):
    check(f"run-local input copy {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
    source = arm_tables[arm]
    check(f"32 authored tables {arm}", len(source) == 32)
    check(f"19 populated tables {arm}", sum(bool(rows(t)) for t in source.values()) == 19)
    check(f"parent table names {arm}", source.keys() == parent_tables.keys())
    for name in source:
        if name not in ("ProblemDescription", "Unit", "MaxPMProfile"):
            check(f"parent table fixed {arm}/{name}", source[name] == parent_tables[name])
    exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, authored in source.items():
        if not rows(authored):
            continue
        check(f"roundtrip table {arm}/{name}", name in exported)
        if name not in exported:
            continue
        original = keyed_rows(authored)
        returned = keyed_rows(exported[name])
        check(f"roundtrip row count {arm}/{name}", len(original) == len(returned))
        for i, (before, after) in enumerate(zip(original, returned)):
            for field, value in before.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{i}/{field}", after.get(field) == value)
    calc = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter summary {arm}", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc)
    check(f"converter only expected warnings {arm}", re.findall(r"\(warning #(\d+)\)", calc) == ["108", "126"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    check(f"reported completed outcome {arm}", outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0])

flat = arm_tables["flat"]
repeat = arm_tables["nested"]
flat_unit = keyed_rows(flat["Unit"])[0]
repeat_unit = keyed_rows(repeat["Unit"])[0]
check("flat Unit profile", flat_unit["MAXPMP"] == "CAP-FLAT")
check("repeat Unit profile", repeat_unit["MAXPMP"] == "CAP-REPEAT")
check("Unit differs only profile", {k: v for k, v in flat_unit.items() if k != "MAXPMP"} == {k: v for k, v in repeat_unit.items() if k != "MAXPMP"})
check("flat nine LIMIT rows", len(rows(flat["MaxPMProfile"])) == 9)
check("repeat three direct LIMIT rows", len(rows(repeat["MaxPMProfile"])) == 3 and all(r["SPRID"] == "<LIMIT>" and r["PRID"] == "CAP-REPEAT" for r in keyed_rows(repeat["MaxPMProfile"])))
base_limits = [(0.0, 0.25, 0), (0.25, 0.75, 1), (0.75, 12.0, 2)]
expected_flat = [("CAP-FLAT", "<LIMIT>", start + offset, end + offset, 1, 0, cap) for offset in (0, 12, 24) for start, end, cap in base_limits]
expected_repeat = [("CAP-REPEAT", "<LIMIT>", start, end, 3, 12, cap) for start, end, cap in base_limits]
def core(table: dict) -> list[tuple]:
    return [tuple(r[k] for k in ("PRID", "SPRID", "STIM", "ETIM", "IQTY", "IINT", "MAXPM")) for r in keyed_rows(table)]
check("flat explicit schedule", core(flat["MaxPMProfile"]) == expected_flat)
check("direct LIMIT repeat schedule", core(repeat["MaxPMProfile"]) == expected_repeat)
expanded = sorted((start + cycle * 12, end + cycle * 12, cap) for start, end, cap in base_limits for cycle in range(3))
check("repeat expands to flat schedule", expanded == sorted((r["STIM"], r["ETIM"], r["MAXPM"]) for r in keyed_rows(flat["MaxPMProfile"])))

check("event log byte identity", (RUN / "flat.log").read_bytes() == (RUN / "nested.log").read_bytes())
log = (RUN / "flat.log").read_text(encoding="latin-1")
for aircraft, time in ((0, "24.25"), (1, "24.75")):
    check(f"physical PM work aircraft {aircraft}", bool(re.search(rf"Time: {time}\s+subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,{aircraft}> starts performing", log)))
    check(f"PM completion aircraft {aircraft}", bool(re.search(rf"system PM task \d+ on <TEACH-AIR-01,{aircraft}> completed", log)))
check("three mission successes", len(re.findall(r"mission success:", log)) == 3)
check("no failed or aborted mission", "mission failed:" not in log and "mission aborted:" not in log)
check("both ready after last mission", "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)

reports = {arm: tables(report(RUN / f"{arm}-report-raw.json"), "report") for arm in ("flat", "nested")}
check("same report table names", reports["flat"].keys() == reports["nested"].keys())
for name, table in reports["flat"].items():
    if name != "ProblemDescription":
        check(f"report equality {name}", table == reports["nested"][name])
for arm in ("flat", "nested"):
    t = reports[arm]
    check(f"one summary row {arm}", len(rows(t["ResultSummary"])) == 1)
    for name in ("SystemResults", "StockTotalResults"):
        samples = keyed_rows(t[name])
        check(f"72 bins {arm}/{name}", len(samples) == 72)
        for i, row in enumerate(samples):
            check(f"half-hour bin {arm}/{name}/{i}", row["STINT"] == i * 0.5 and row["ETINT"] == (i + 1) * 0.5)
    check(f"both ready in terminal bin {arm}", keyed_rows(t["SystemResults"])[-1]["NSYRY"] == 2)
    stock = keyed_rows(t["StockTotalResults"])
    check(f"no stock backorder {arm}", all(row["NBO"] == 0 for row in stock))

failed = [label for label, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-d13-var05-direct-limit-independent-replay/v1",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED" if not failed else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "event_log_sha256": sha(RUN / "flat.log"),
    "scope": "One seed, two aircraft, one PM and three repetitions of direct MaxPMProfile <LIMIT> rows; no subprofile-hierarchy claim.",
}
(CASE / "review" / "independent-verdict.json").write_text(
    json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(verdict, indent=2))
if failed:
    raise SystemExit(1)
