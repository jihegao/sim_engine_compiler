"""Read-only author replay of the frozen I06 reliability-factor panel."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
CONTRACT = json.loads((CASE / "contract.json").read_text(encoding="utf-8"))
RUN = CASE / "runs" / CONTRACT["run_id"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> tuple[dict, int]:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw), 0
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        removed = 0
        for index, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[index + 1:].lstrip().startswith(("]", "}")):
                removed += 1
            else:
                out.append(char)
        return json.loads("".join(out)), removed


def populated(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            assert table["name"] not in result
            result[table["name"]] = ([(column["name"], column["datatype"]) for column in table["columns"]], rows)
    return result


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    return [c["name"] for c in matches[0]["columns"]], [row for instance in matches[0]["instances"] for row in instance["rows"]]


def main() -> dict:
    checks, failures, observed = 0, [], {}

    def check(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    closure = read(RUN / "closure.json")
    invocation = read(RUN / "invocation.json")
    check(closure["error"] is None, "closure error")
    check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    check(closure["source_hashes_before"] == closure["source_hashes_after"], "source drift")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 ancestor")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
    check(len(closure["raw"]) == 122, "raw file count")
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
    steps = read(RUN / "steps.json")
    check(len(steps) == 48, "guarded step count")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

    for kind in CONTRACT["kinds"]:
        for seed in CONTRACT["seeds"]:
            for arm in CONTRACT["arms"]:
                name = f"{kind}-seed{seed}-{arm}"
                source = CASE / f"{name}-input.json"
                check(sha(source) == CONTRACT["inputs_sha256"][name], f"{name} source pin")
                check(sha(RUN / f"{name}-input.json") == sha(source), f"{name} copied source")
                authored = populated(read(source))
                exported = populated(read(RUN / f"{name}-roundtrip-raw.json"))
                check(all(exported.get(key) == value for key, value in authored.items()), f"{name} exact populated roundtrip")
                run_log = (RUN / f"{name}-run.log").read_text(encoding="utf-8-sig", errors="replace")
                check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in run_log, f"{name} converter")
                check(re.findall(r"\(warning #(\d+)\)", run_log) == ["108"], f"{name} warning code")
                report, removed = native_report(RUN / f"{name}-report-raw.json")
                check(removed == 1, f"{name} one default JSON trailing comma")
                columns, system = rows(report, "SystemResults")
                check(len(system) == (120 if kind == "item" else 72), f"{name} report bins")
                event_text = (RUN / f"{name}.log").read_text(encoding="utf-8-sig", errors="replace")
                pattern = "critical random failure added" if kind == "item" else "critical CM failure mode added"
                failure_times = [float(value) for value in re.findall(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> " + pattern, event_text, re.M)]
                report_count = sum(row[columns.index("NFAIL")] or 0 for row in system)
                check(report_count == len(failure_times), f"{name} report/event failures")
                h9 = re.findall(r"^Time: 9 <TEACH-AIR-01,0> Next random failure will occur ([0-9.e+]+)", event_text, re.M)
                h24 = re.findall(r"^Time: 24 <TEACH-AIR-01,0> Next random failure will occur ([0-9.e+]+)", event_text, re.M)
                check(len(h9) >= 2 and len(h24) >= 1, f"{name} h9/h24 rescheduling")
                active_at_h24 = bool(re.search(r"^Time: 23 <BASIC-MISSION,[^\n]+> mission starting, duration: 2", event_text, re.M)) and not bool(re.search(r"^Time: 23(?:\.[0-9]+)? <BASIC-MISSION,[^\n]+> mission (?:aborted|cancelled):", event_text, re.M))
                finite_h24 = any(float(value) < 1e9 for value in h24)
                mission_success = len(re.findall(r"^Time: [0-9.]+ <BASIC-MISSION,[^\n]+> mission success:", event_text, re.M))
                mission_abort = len(re.findall(r"^Time: [0-9.]+ <BASIC-MISSION,[^\n]+> mission aborted:", event_text, re.M))
                mission_cancel = len(re.findall(r"^Time: [0-9.]+ <BASIC-MISSION,[^\n]+> mission cancelled:", event_text, re.M))
                check(mission_success + mission_abort + mission_cancel == 3, f"{name} mission outcome count")
                observed[name] = {
                    "failure_times": failure_times,
                    "failures_h9_h24": [time for time in failure_times if 9 <= time < 24],
                    "next_failure_at_h9": h9,
                    "next_failure_at_h24": h24,
                    "mission_active_at_h24": active_at_h24,
                    "finite_h24_reschedule": finite_h24,
                    "report_nfail": report_count,
                    "mission_success": mission_success,
                    "mission_abort": mission_abort,
                    "mission_cancel": mission_cancel,
                    "terminal_ready_interval_average": system[-1][columns.index("NSYRY")],
                }
            control = observed[f"{kind}-seed{seed}-control"]
            factor4 = observed[f"{kind}-seed{seed}-factor4"]
            check(control["next_failure_at_h9"] != factor4["next_failure_at_h9"], f"{kind} seed{seed} h9 schedule contrast")
        check(any(observed[f"{kind}-seed{seed}-control"]["failures_h9_h24"] != observed[f"{kind}-seed{seed}-factor4"]["failures_h9_h24"] for seed in CONTRACT["seeds"]), f"{kind} physical h9-h24 witness")
    check(any(all(observed[f"item-seed{seed}-{arm}"]["mission_active_at_h24"] and observed[f"item-seed{seed}-{arm}"]["finite_h24_reschedule"] for arm in CONTRACT["arms"]) for seed in CONTRACT["seeds"]), "item paired finite h24 reschedule during mission exposure")
    return {"schema": "simlox-i06-author-validation/v1", "passed": not failures,
            "checks": checks, "failures": failures, "observed": observed,
            "closure_sha256": sha(RUN / "closure.json"),
            "note": "At least one item pair shows finite h24 failure rescheduling during a mission. The native log does not print the applied factor value; the scheduled factor semantics are from the pinned manual and imported source.",
            "publication_state": "not_published"}


if __name__ == "__main__":
    result = main()
    output = CASE / "review" / "author-validation-2026-10-05.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "checks", "failures", "closure_sha256", "note")}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
