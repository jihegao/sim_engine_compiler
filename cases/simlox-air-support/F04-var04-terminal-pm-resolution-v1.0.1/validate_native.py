"""Author replay for the bounded F04.var04 terminal-PM continuation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F04-var01-deterministic-43day-v1.0.1" / "runs" / (
    "f04-var01-repeat-a-v101-ssh-20261004-01")
EXCLUDED = HERE.parent / "F04-var04-terminal-pm-resolution-v1.0.0" / "runs" / (
    "f04-var04-terminal-pm-v100-ssh-20261004-01")
RUN = HERE / "runs" / "f04-var04-terminal-pm-v101-ssh-20261004-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> tuple[dict, bool]:
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


def report_rows(report: dict, name: str) -> list[dict]:
    tables = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(tables) == 1
    table = tables[0]
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row))
            for instance in table["instances"] for row in instance["rows"]]


def assert_raw(run: Path, expected_sha: str) -> dict:
    assert sha(run / "closure.json") == expected_sha
    closure = read(run / "closure.json")
    assert closure["error"] is None and closure["run_id"] == run.name
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    for name, seal in closure["raw"].items():
        path = run / name
        assert (path.stat().st_size, sha(path)) == (seal["bytes"], seal["sha256"]), name
    return closure


def events_before_cutoff(path: Path) -> bytes:
    lines = path.read_bytes().splitlines(keepends=True)
    assert lines[0].startswith(b"SIMLOX LOG FILE")
    return b"".join(lines[2:]).split(b"Time: 1032 ")[0]


def main() -> None:
    contract = read(HERE / "contract.json")
    assert contract["version"] == "1.0.1-candidate"
    assert sha(HERE / "native-input.json") == contract["input_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    parent = assert_raw(PARENT, contract["accepted_parent"]["closure_sha256"])
    excluded = assert_raw(EXCLUDED, contract["excluded_diagnostic"]["closure_sha256"])
    closure = assert_raw(RUN, sha(RUN / "closure.json"))
    assert len(closure["raw"]) == len(excluded["raw"]) == 12
    assert sha(PARENT / "report-raw.json") == contract["accepted_parent"]["default_report_sha256"]
    assert sha(PARENT / "model.log") == contract["accepted_parent"]["event_log_sha256"]
    source = closure["source_hashes_before"]
    assert source == closure["source_hashes_after"] == read(RUN / "invocation.json")["source_hashes_before"]
    assert source["native_input"] == contract["input_sha256"] == sha(RUN / "input.json")
    assert source["contract"] == sha(HERE / "contract.json")
    assert source["exact_diff"] == contract["exact_diff_sha256"]
    assert source["accepted_parent"] == contract["accepted_parent"]["input_sha256"]
    assert source["accepted_parent_closure"] == contract["accepted_parent"]["closure_sha256"]
    assert source["excluded_diagnostic_closure"] == contract["excluded_diagnostic"]["closure_sha256"]
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
        assert source[name] == sha(HERE / name), name
    invocation = read(RUN / "invocation.json")
    assert invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["gui"]["pid"] == 13340
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    steps = read(RUN / "steps.json")
    assert [x["name"] for x in steps] == [
        "import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(x["status"] == "completed" and x["exit_code"] == 0 for x in steps)
    assert all(x.get("gui_preserved") for x in steps[:4])
    roundtrip = read(RUN / "roundtrip-validation.json")
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == 30
    assert roundtrip["source_sha256"] == contract["input_sha256"]
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog
    assert re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "2053", "2053"]

    parent_log, child_log = PARENT / "model.log", RUN / "model.log"
    assert events_before_cutoff(parent_log) == events_before_cutoff(child_log)
    ptxt = parent_log.read_text(encoding="utf-8-sig", errors="replace")
    ctxt = child_log.read_text(encoding="utf-8-sig", errors="replace")
    task = "system PM task 533 on <TEACH-AIR-01,6>"
    assert ptxt.count("Time: 1031  " + task + " started") == 1
    assert ctxt.count("Time: 1031  " + task + " started") == 1
    assert "Time: 1032  " + task + " completed" not in ptxt
    assert ctxt.count("Time: 1032  " + task + " completed") == 1
    assert ctxt.count("Time: 1032  <P-MAINT at <BASE-02,0>> deallocated from  maintenance task: 1") == 1
    assert "Time: 1032 <TEACH-AIR-01,BASE-02,0> System ready <TEACH-AIR-01,6>" in ctxt
    assert "Time: 1032.5  resource shift 2 ended" in ctxt
    pm_starts = lambda log: len(re.findall(r"Time: [0-9.]+  system PM task \d+ on .* started", log))
    pm_completions = lambda log: len(re.findall(r"Time: [0-9.]+  system PM task \d+ on .* completed", log))
    assert (pm_starts(ptxt), pm_completions(ptxt)) == (324, 323)
    assert (pm_starts(ctxt), pm_completions(ctxt)) == (324, 324)

    pd, pfix = native_report(PARENT / "report-raw.json")
    cd, cfix = native_report(RUN / "report-raw.json")
    ed, efix = native_report(EXCLUDED / "report-raw.json")
    assert pfix and cfix and efix
    assert {t["name"] for t in pd["report"]["tables"]} == {
        t["name"] for t in cd["report"]["tables"]}
    ps, cs = report_rows(pd, "ResultSummary")[0], report_rows(cd, "ResultSummary")[0]
    assert ps["RTIUP"] == 1032 and cs["RTIUP"] == 1032.5
    assert {k: v for k, v in ps.items() if k != "RTIUP"} == {
        k: v for k, v in cs.items() if k != "RTIUP"}
    for name in ("StockTotalResults", "ResourceResults"):
        p, c = report_rows(pd, name), report_rows(cd, name)
        assert len(p) == 2064 and len(c) == 2065
        assert c[:2064] == p
        assert (c[-1]["STINT"], c[-1]["ETINT"]) == (1032, 1032.5)
    p, c = report_rows(pd, "SystemResults"), report_rows(cd, "SystemResults")
    assert len(p) == 2064 and len(c) == 2065
    changed = [(i, sorted(key for key in row if row[key] != c[i][key]))
               for i, row in enumerate(p) if row != c[i]]
    assert changed == [(2062, ["NSYDT", "SYDT"])]
    assert (p[2062]["STINT"], p[2062]["ETINT"]) == (1031, 1031.5)
    assert (p[2062]["SYDT"], p[2062]["NSYDT"]) == (None, 0)
    assert (c[2062]["SYDT"], c[2062]["NSYDT"]) == (1, 1)
    extra = c[-1]
    assert (extra["STINT"], extra["ETINT"]) == (1032, 1032.5)
    assert 7.99 < extra["NSYRY"] <= 8
    assert 0 <= extra["NSYPM"] < .01
    assert 0 <= report_rows(cd, "ResourceResults")[-1]["NRUM"] < .01
    assert report_rows(cd, "StockTotalResults")[-1]["NBO"] == 0
    assert extra["NFAIL"] == 0
    assert report_rows(ed, "SystemResults") == c

    result = {
        "schema": "simlox-f04-terminal-pm-author-validation/v1",
        "decision": "GO_BOUNDED",
        "run_id": RUN.name,
        "closure_sha256": sha(RUN / "closure.json"),
        "excluded_diagnostic_closure_sha256": sha(EXCLUDED / "closure.json"),
        "accepted_raw_files_verified": len(closure["raw"]),
        "excluded_raw_files_verified": len(excluded["raw"]),
        "parent_event_prefix_equal_before_h1032": True,
        "open_parent_task_533_completed_at_h1032": True,
        "parent_pm_starts_completions": [324, 323],
        "continuation_pm_starts_completions": [324, 324],
        "stock_resource_prefix_rows_equal": 2064,
        "system_prefix_exceptions": changed,
        "new_bin": {"ready": extra["NSYRY"], "pm": extra["NSYPM"],
                    "resource_booked": report_rows(cd, "ResourceResults")[-1]["NRUM"]},
        "native_default_report_trailing_comma_corrected_for_parse": cfix,
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
                      "new_bin": result["new_bin"]}))


if __name__ == "__main__":
    main()
