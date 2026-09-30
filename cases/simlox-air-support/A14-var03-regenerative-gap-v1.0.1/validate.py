"""Source-bound author replay for A14.var03 v1.0.1; never invokes SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build import build, PARENT, PARENT_SHA, TURNROUND_DONOR, TURNROUND_DONOR_SHA, DEPENDENCE_DONOR, DEPENDENCE_DONOR_SHA, VARIANTS
from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {v: HERE / "runs" / f"a14-var03-{v}-v101-20261001-01" for v in VARIANTS}
INPUT_SHA = {
    "regenerative-control": "08bae91cb7508b50f38d724165fb1306677da989eec1a847392b32d80bcd760e",
    "regenerative-zero": "ffcc14b83d28dab4f917e339c07172c1e4bd098f76f371a2cfd4979514839fb7",
    "regenerative-tolerant": "41d9346c23bd2efbc9ef9411a5ca99c95190c7ddb11d77cab69fba0318e20250",
    "fixed-control": "0f8c2452c47add9fb8fd1f76dce2fac2919a4e80584c6a054ba3534cf5f27fad",
    "fixed-tolerant": "21af387dd7f45c88bad3baaa621ae1385f6e9489e2e46220e8b429ec8ce44875",
}
DIFF_SHA = "e5e35e277b360778a36b1212f9076add6a2e755bce8e19b511d8684773b1432b"
EXPECTED_HOURS = {
    "regenerative-control": (12.25, 0.0, 1.0),
    "regenerative-zero": (11.75, 0.5, 1.0),
    "regenerative-tolerant": (12.25, 0.0, 1.0),
    "fixed-control": (10.25, 0.0, 0.5),
    "fixed-tolerant": (8.0, 0.0, 0.5),
}
EXPECTED_FACTORS = {
    "regenerative-control": (0.9607843160629272, 0.7313432693481445, 0, 0),
    "regenerative-zero": (0.9215686321258545, 0.7014925479888916, 0, 0),
    "regenerative-tolerant": (0.9607843160629272, 0.7313432693481445, 0, 0),
    "fixed-control": (1.0, 1.0, 1, 1),
    "fixed-tolerant": (0.7804877758026123, 0.7804877758026123, 1, 1),
}
checks = 0


def yes(ok: bool, label: str) -> None:
    global checks
    if not ok:
        raise AssertionError(label)
    checks += 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(report: dict, name: str) -> list[dict]:
    tabs = [t for t in report["report"]["tables"] if t["name"] == name]
    yes(len(tabs) == 1, f"unique report table {name}")
    t = tabs[0]
    cols = [c["name"] for c in t["columns"]]
    result = []
    for instance in t["instances"]:
        for row in instance["rows"]:
            yes(len(row) == len(cols), f"rectangular {name}")
            result.append(dict(zip(cols, row, strict=True)))
    return result


def overlap(start: float, end: float, low: float, high: float) -> float:
    return max(0.0, min(end, high) - max(start, low))


def source() -> None:
    contract = read(HERE / "contract.json")
    yes(contract["case_id"] == "A14" and contract["variant_id"] == "A14.var03" and contract["case_version"] == "1.0.1-candidate", "contract identity")
    yes(contract["inputs_sha256"] == INPUT_SHA and contract["exact_diff_sha256"] == DIFF_SHA, "contract sources")
    for path, expected in ((PARENT, PARENT_SHA), (TURNROUND_DONOR, TURNROUND_DONOR_SHA), (DEPENDENCE_DONOR, DEPENDENCE_DONOR_SHA), (HERE / "exact-diff.json", DIFF_SHA)):
        yes(sha(path) == expected, f"source hash {path.name}")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["installed_manual_sha256"], "manual fingerprint")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")) == contract["source"]["installed_executable_sha256"], "executable fingerprint")
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        yes(sha(path) == INPUT_SHA[variant], f"source {variant} hash")
        yes(parse_native(path) == build(variant), f"source {variant} build")


def assert_events(variant: str, events: str) -> None:
    starts = re.findall(r"^Time: ([0-9.]+) <(SUPPORT|EXECUTE),TEACH-UNIT,[^>]+> mission starting,", events, re.MULTILINE)
    if variant.startswith("regenerative"):
        yes(starts.count(("8", "SUPPORT")) == 1 and starts.count(("12.5", "SUPPORT")) == 1, f"{variant} support launches")
        yes(events.count("<SUPPORT,TEACH-UNIT,0,0,0> mission success:") == 1 and events.count("<SUPPORT,TEACH-UNIT,0,1,1> mission success:") == 1, f"{variant} two support successes")
        yes("Time: 12 <TEACH-AIR-01,0> turnround started" in events and "Time: 12.5 <TEACH-AIR-01,0> turnround ended" in events, f"{variant} gap turnaround")
        yes("Time: 14.5 <SUPPORT,TEACH-UNIT,0,1,1> mission completed:" in events and "Time: 15 <TEACH-AIR-01,0> turnround ended" in events, f"{variant} support terminal")
    else:
        yes(starts.count(("8", "SUPPORT")) == 1 and sum(m == "SUPPORT" for _, m in starts) == 1, f"{variant} fixed support launch")
        yes("Time: 12 <SUPPORT,TEACH-UNIT,0,0,0> mission completed:" in events and "Time: 12.5 <TEACH-AIR-01,0> turnround ended" in events, f"{variant} fixed support return")
    yes(starts.count(("8", "EXECUTE")) == 1, f"{variant} execute launch")
    yes("failure occurred" not in events.lower(), f"{variant} no failure")
    execute_lines = [line for line in events.splitlines() if "<EXECUTE,TEACH-UNIT" in line]
    suspended = [line for line in execute_lines if "mission suspended:" in line]
    resumed = [line for line in execute_lines if "mission resumed:" in line]
    if variant == "regenerative-zero":
        yes(len(suspended) == len(resumed) == 1 and suspended[0].startswith("Time: 12 ") and resumed[0].startswith("Time: 12.5 "), "zero tolerance suspension interval")
    elif variant == "fixed-tolerant":
        yes(len(suspended) == len(resumed) == 1 and suspended[0].startswith("Time: 8 ") and resumed[0].startswith("Time: 8 "), "fixed initial zero-duration transition")
    else:
        yes(not suspended and not resumed, f"{variant} no execute suspension")
    if variant == "fixed-tolerant":
        yes("Time: 12 <EXECUTE,TEACH-UNIT,0,0,1> mission aborted:" in events, "fixed predecessor abort")
        yes("Time: 14.25 <EXECUTE" not in events, "fixed no planned success")
    else:
        yes("Time: 14.25 <EXECUTE,TEACH-UNIT" in events and "mission success:" in "\n".join(line for line in execute_lines if line.startswith("Time: 14.25 ")), f"{variant} execute success")
        yes(not any("mission aborted:" in line for line in execute_lines), f"{variant} no execute abort")


def run(variant: str) -> dict:
    path = RUNS[variant]
    closure, invocation, steps = (read(path / name) for name in ("closure.json", "invocation.json", "steps.json"))
    yes(closure["error"] is None and closure["run_id"] == path.name, f"{variant} closed")
    yes(closure["invocation_sha256"] == sha(path / "invocation.json"), f"{variant} invocation seal")
    yes(closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant} source stable")
    pinned = closure["source_hashes_before"]
    for key, file in (("contract", "contract.json"), ("builder", "build.py"), ("exact_diff", "exact-diff.json"), ("diff_checker", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        yes(pinned[key] == sha(HERE / file), f"{variant} sealed {key}")
    yes((pinned["input"], pinned["parent"], pinned["donor_turnround"], pinned["donor_dependence"]) == (INPUT_SHA[variant], PARENT_SHA, TURNROUND_DONOR_SHA, DEPENDENCE_DONOR_SHA), f"{variant} lineage")
    yes(invocation["case_id"] == "A14" and invocation["variant_id"] == "A14.var03" and invocation["variant"] == variant and invocation["case_version"] == "1.0.1-candidate", f"{variant} invocation identity")
    yes(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} SSH provenance")
    yes(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} GUI and queue")
    yes([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} steps")
    yes(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} step results")
    for name, item in closure["raw"].items():
        yes((path / name).stat().st_size == item["bytes"] and sha(path / name) == item["sha256"], f"{variant} raw {name}")
    yes(sha(path / "input.json") == INPUT_SHA[variant], f"{variant} input copy")
    roundtrip = read(path / "roundtrip-validation.json")
    expected_count = 14 if variant.endswith("control") else 15
    yes(roundtrip["passed"] and not roundtrip["differences"] and len(roundtrip["populated_tables"]) == expected_count, f"{variant} roundtrip result")
    src, exported = (populated(parse_native(path / n)) for n in ("input.json", "roundtrip-raw.json"))
    yes(all(exported.get(name) == data for name, data in src.items()), f"{variant} exact business roundtrip")
    calc_log = (path / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    yes("Input conversion completed. Errors: 0, Warnings: 2" in calc_log and "error #" not in calc_log.lower(), f"{variant} conversion")
    yes((path / "model.sxo").stat().st_size > 1000, f"{variant} valid SXO size")
    events = (path / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    assert_events(variant, events)
    report = parse_native(path / "report-raw.json")
    summary, = report_rows(report, "ResultSummary")
    yes((summary["NREP"], summary["RTILW"], summary["RTIUP"]) == (1, 0, 16), f"{variant} report range")
    mtmf, stmf, mstf, msuf = EXPECTED_FACTORS[variant]
    yes(abs(summary["MTMF"] - mtmf) < 1e-6 and abs(summary["STMF"] - stmf) < 1e-6 and summary["MSTF"] == mstf and summary["MSUF"] == msuf, f"{variant} summary factors")
    systems, stocks = report_rows(report, "SystemResults"), report_rows(report, "StockTotalResults")
    yes(len(systems) == len(stocks) == 32, f"{variant} 32 bins")
    operating = [(8, 12)] + ([(12.5, 14.5)] if variant.startswith("regenerative") else [])
    if variant == "regenerative-zero":
        operating += [(8, 12), (12.5, 14.25)]
    else:
        operating += [(8, 12 if variant == "fixed-tolerant" else 14.25)]
    suspended = [(12, 12.5)] if variant == "regenerative-zero" else []
    turnround = [(12, 12.5)] + ([(14.5, 15)] if variant.startswith("regenerative") else [])
    for i, (system, stock) in enumerate(zip(systems, stocks, strict=True)):
        low, high = i / 2, (i + 1) / 2
        yes((system["STINT"], system["ETINT"], stock["STINT"], stock["ETINT"]) == (low, high, low, high), f"{variant} bin {i} alignment")
        for field, intervals in (("NSYMO", operating), ("NSYMS", suspended), ("NSYMT", turnround)):
            expected = sum(overlap(a, b, low, high) for a, b in intervals) / 0.5
            yes(abs(system[field] - expected) < 1e-6, f"{variant} bin {i} {field}")
        yes(system["NSYA"] == 2 and abs(system["NSYRY"] + system["NSYMA"] - 2) < 1e-6, f"{variant} bin {i} fleet conservation")
        yes(all(system[k] == 0 for k in ("NREPT", "NPMT", "NFAIL", "NDAM", "NSYRP", "NSYPM", "NROBT", "NRCFG")), f"{variant} bin {i} no failure/repair/PM")
        yes(all(stock[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} bin {i} no stock demand")
    hours = tuple(sum(row[k] * 0.5 for row in systems) for k in ("NSYMO", "NSYMS", "NSYMT"))
    yes(all(abs(a - b) < 1e-6 for a, b in zip(hours, EXPECTED_HOURS[variant], strict=True)), f"{variant} integrated hours")
    yes(systems[-1]["NSYRY"] == 2 and systems[-1]["NSYMA"] == 0, f"{variant} terminal ready")
    return {"run_id": path.name, "closure_sha256": sha(path / "closure.json"), "model_log_sha256": sha(path / "model.log"), "report_sha256": sha(path / "report-raw.json"), "hours": {"operating": hours[0], "suspended": hours[1], "turnround": hours[2]}}


def main() -> None:
    source()
    runs = {variant: run(variant) for variant in VARIANTS}
    result = {"schema": "simlox-a14-var03-v101-author-replay/v1", "passed": True, "checks": checks, "decision": "bounded_go_pending_independent_review", "runs": runs, "limits": ["One fixed-seed installed-version gap and fixed-predecessor contrast.", "No broader DTTOL law, GUI visual observation or cross-engine parity."]}
    output = HERE / "author-replay.json"
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": True, "checks": checks, "runs": {v: x["closure_sha256"] for v, x in runs.items()}}))


if __name__ == "__main__":
    main()
