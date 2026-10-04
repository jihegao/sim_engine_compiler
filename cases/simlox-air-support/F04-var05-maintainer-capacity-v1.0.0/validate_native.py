"""Author replay for the bounded F04.var05 maintainer-capacity contrast."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F04-var01-deterministic-43day-v1.0.1" / "runs" / (
    "f04-var01-repeat-a-v101-ssh-20261004-01")
RUN = HERE / "runs" / "f04-var05-maintainer-capacity-v100-ssh-20261004-01"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log",
       "export.log", "model.sxo", "run.log", "model.log", "report-raw.json",
       "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> tuple[dict, bool]:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        out: list[str] = []
        quoted = escaped = False
        n = len(raw)
        for i, char in enumerate(raw):
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
            elif char == ",":
                j = i + 1
                while j < n and raw[j].isspace():
                    j += 1
                if j >= n or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out)), True


def rows(report: dict, name: str) -> list[dict]:
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    table = found[0]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(m.group(1)) for m in re.finditer(
        r"^Time: ([\d.]+) " + pattern, log, re.M)]


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo)) / (hi - lo)


def resource_spans(log: str) -> list[tuple[float, float]]:
    pattern = re.compile(
        r"^Time: ([\d.]+)  <(P-CREW|P-MAINT) at <(BASE-0[12]),0>> "
        r"(allocated to|deallocated from)\s+maintenance task: 1  available now: (\d+)$")
    capacities = {("BASE-01", "P-MAINT"): 2, ("BASE-01", "P-CREW"): 1,
                  ("BASE-02", "P-MAINT"): 1, ("BASE-02", "P-CREW"): 1}
    current = {key: 0 for key in capacities}
    opened: dict[tuple[str, str], list[float]] = {key: [] for key in capacities}
    spans = []
    for line in log.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        time = float(match.group(1))
        key = (match.group(3), match.group(2))
        if match.group(4) == "allocated to":
            current[key] += 1
            opened[key].append(time)
        else:
            assert opened[key], key
            start = opened[key].pop(0)
            spans.append((start, time))
            current[key] -= 1
        assert 0 <= current[key] <= capacities[key]
        assert capacities[key] - current[key] == int(match.group(5)), (key, line)
    for key, pending in opened.items():
        spans.extend((start, 1032.0) for start in pending)
    assert sum(current.values()) == sum(map(len, opened.values()))
    return spans


def resource_queues(log: str) -> list[tuple[float, float]]:
    spans = []
    pending: dict[tuple[str, str, str], float] = {}
    now = None
    task = None
    for line in log.splitlines():
        tick = re.match(r"^Time: ([\d.]+)", line)
        if tick:
            now = float(tick.group(1))
        test_task = re.match(r"^Time: [\d.]+  (.+?) resource availability test", line)
        if test_task:
            task = test_task.group(1)
        test = re.search(r"<(?P<rid>P-CREW|P-MAINT) at <(?P<station>BASE-0[12]),0>> request for: 1 (?P<state>failed|OK)", line)
        if not test:
            continue
        assert now is not None and task is not None
        key = (test.group("station"), test.group("rid"), task)
        if test.group("state") == "failed":
            pending.setdefault(key, now)
        elif key in pending:
            spans.append((pending.pop(key), now))
    assert not pending
    return spans


def main() -> None:
    contract = read(HERE / "contract.json")
    assert contract["version"] == "1.0.0-candidate"
    assert sha(HERE / "native-input.json") == contract["input_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    assert sha(PARENT / "closure.json") == contract["accepted_parent"]["closure_sha256"]
    assert sha(PARENT / "report-raw.json") == contract["accepted_parent"]["default_report_sha256"]
    assert sha(PARENT / "model.log") == contract["accepted_parent"]["event_log_sha256"]
    closure, invocation = read(RUN / "closure.json"), read(RUN / "invocation.json")
    assert closure["error"] is None and closure["run_id"] == RUN.name
    assert closure["invocation_sha256"] == sha(RUN / "invocation.json")
    assert set(closure["raw"]) == RAW
    for name, seal in closure["raw"].items():
        path = RUN / name
        assert (path.stat().st_size, sha(path)) == (seal["bytes"], seal["sha256"]), name
    sources = closure["source_hashes_before"]
    assert sources == closure["source_hashes_after"] == invocation["source_hashes_before"]
    assert sources["native_input"] == contract["input_sha256"] == sha(RUN / "input.json")
    assert sources["contract"] == sha(HERE / "contract.json")
    assert sources["exact_diff"] == contract["exact_diff_sha256"]
    assert sources["accepted_parent"] == contract["accepted_parent"]["input_sha256"]
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
        assert sources[name] == sha(HERE / name), name
    assert invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert invocation["gui"]["pid"] == 13340
    steps = read(RUN / "steps.json")
    assert [s["name"] for s in steps] == [
        "import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps)
    assert all(s.get("gui_preserved") for s in steps[:4])
    roundtrip = read(RUN / "roundtrip-validation.json")
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == 30
    assert roundtrip["source_sha256"] == contract["input_sha256"]
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog
    assert re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "2053", "2053"]

    parent_log = (PARENT / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    child_log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    assert times(parent_log, r" subtask 12 .*<TEACH-AIR-01,0> books resources") == [25.0]
    assert times(child_log, r" subtask 12 .*<TEACH-AIR-01,0> books resources") == [24.5]
    assert times(parent_log, r" system PM task 12 on <TEACH-AIR-01,0> completed") == [26.0]
    assert times(child_log, r" system PM task 12 on <TEACH-AIR-01,0> completed") == [25.5]
    assert times(child_log, r" <P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0")[0] == 24.5
    for mtype in ("BASE2-MISSION", "RISK-MISSION", "BASIC-MISSION"):
        for event in ("mission starting", "mission success:"):
            parent = times(parent_log, rf"<{mtype},[^>]+> {event}")
            child = times(child_log, rf"<{mtype},[^>]+> {event}")
            assert len(parent) == len(child) == 21 and parent == child
    assert not re.search(
        r"critical random failure added|Item demand arrives|Backorder added|mission cancelled|mission abort",
        child_log, re.I)
    pm_starts = times(child_log, r" system PM task \d+ on <TEACH-AIR-01,\d+> started")
    pm_ends = times(child_log, r" system PM task \d+ on <TEACH-AIR-01,\d+> completed")
    assert (len(pm_starts), len(pm_ends)) == (324, 323)

    parent_report, parent_fixed = native_json(PARENT / "report-raw.json")
    child_report, child_fixed = native_json(RUN / "report-raw.json")
    assert parent_fixed and child_fixed
    assert rows(parent_report, "ResultSummary") == rows(child_report, "ResultSummary")
    parent_system = rows(parent_report, "SystemResults")
    system = rows(child_report, "SystemResults")
    parent_stock = rows(parent_report, "StockTotalResults")
    stock = rows(child_report, "StockTotalResults")
    parent_resource = rows(parent_report, "ResourceResults")
    resource = rows(child_report, "ResourceResults")
    assert stock == parent_stock
    assert all(len(x) == 2064 for x in (
        parent_system, system, stock, parent_resource, resource))
    assert all((row["STINT"], row["ETINT"]) == (i * .5, (i + 1) * .5)
               for collection in (system, stock, resource)
               for i, row in enumerate(collection))
    spans, queues = resource_spans(child_log), resource_queues(child_log)
    for i, (sy, st, res) in enumerate(zip(system, stock, resource)):
        lo, hi = i * .5, (i + 1) * .5
        booked = sum(overlap(a, b, lo, hi) for a, b in spans)
        waiting = sum(overlap(a, b, lo, hi) for a, b in queues)
        assert abs(sy["NSYRY"] + sy["NSYMA"] + sy["NSYUA"] - 8) < 1e-4, i
        assert st["NBO"] == 0, i
        assert res["NR"] == 5 and abs(res["NRUM"] - booked) < 1e-2, i
        assert abs(res["NRW"] - waiting) < 5e-3, i
    integral = lambda data, key: sum(.5 * row[key] for row in data)
    parent_queue = integral(parent_resource, "NRW")
    child_queue = integral(resource, "NRW")
    assert abs(parent_queue - 27.24975824356079) < .01
    assert abs(child_queue - 21.0) < .01 and child_queue < parent_queue
    assert abs(integral(resource, "NRUM") - sum(b - a for a, b in spans)) < .01
    assert abs(child_queue - sum(b - a for a, b in queues)) < .01
    assert abs(integral(system, "STACC") - 210) < .01
    assert abs(integral(system, "NSYPM") - 324) < .01
    assert (system[-1]["NSYRY"], system[-1]["NSYPM"],
            resource[-1]["NRUM"], resource[-1]["NRW"]) == (7, 1, 1, 0)

    result = {
        "schema": "simlox-f04-maintainer-capacity-author-validation/v1",
        "decision": "GO_BOUNDED", "run_id": RUN.name,
        "closure_sha256": sha(RUN / "closure.json"),
        "accepted_raw_files_verified": len(closure["raw"]),
        "first_wave_aircraft_0_pm_completion_parent_child": [26.0, 25.5],
        "parent_child_resource_queue_hours": [parent_queue, child_queue],
        "parent_child_total_resource_capacity": [4, 5],
        "mission_starts_and_successes_each_type": 21,
        "pm_starts_completions": [len(pm_starts), len(pm_ends)],
        "system_stock_resource_bins_reconciled": 2064,
        "system_operating_hours": integral(system, "STACC"),
        "terminal_ready_pm": [system[-1]["NSYRY"], system[-1]["NSYPM"]],
        "native_report_trailing_comma_corrected_for_parse": child_fixed,
        "scope_limit": contract["limitations"],
    }
    path = HERE / "author-native-validation-2026-10-04.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(json.dumps({"decision": result["decision"],
                      "validation_sha256": hashlib.sha256(raw).hexdigest(),
                      "closure_sha256": result["closure_sha256"],
                      "queue_hours": result["parent_child_resource_queue_hours"]}))


if __name__ == "__main__":
    main()
