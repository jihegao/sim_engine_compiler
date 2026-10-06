"""Read-only author check of three accepted C01 1.0.2 capacity runs."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCEPTED = HERE.parent / "C01-personnel-capacity-v1.0.2"
RUN_ROOT = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C01-personnel-capacity-v1.0.2/runs")
CONTRACT_SHA = "1cfcfd8200a81dd9d19745770581b6d33f28096bc58c03685dc412ea183b7d6a"
ORIGINAL_REVIEW_SHA = "b8b0bd11bfbde8c84e6e9bf9a4bb82a58da23e3436ce775082265d28c6d31f73"
PINS = {
    2: ("capacity-2", "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c", "c01-v102-cap2-ssh-20260929-05", "770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163"),
    1: ("capacity-1", "12804f3f589abddf1a4a85e27e0bdf7f965ba6750517f4de18715e7e065ba2ad", "c01-v102-cap1-ssh-20260929-04", "f8aacea0884523cc0f703bb16afc1cf08d59ae5a3dc4e7cb51c2feb377239cc5"),
    0: ("capacity-0", "02d1e3c1cdb585b73a00cf73b58f9d5fe6295c45c6fdc282a7c80c443499fdeb", "c01-v102-cap0-ssh-20260929-03", "722e9eab571f8a7bc32aa593fe8782b30cc182a4a196b93f0f559129f85f4dcd"),
}
CHECKS: dict[str, bool] = {}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def check(name: str, passed: bool):
    CHECKS[name] = bool(passed)


def load(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
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
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc, root):
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(doc, name, root):
    table = tables(doc, root)[name]
    keys = [column["name"] for column in table["columns"]]
    return [dict(zip(keys, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, phrase: str):
    return [float(match.group(1)) for line in log.splitlines() if phrase in line and (match := re.match(r"Time:\s*([0-9.]+)", line))]


def close(got, want, tol=0.00005):
    return len(got) == len(want) and all(abs(a - b) < tol for a, b in zip(got, want))


def verify_source_git():
    files = [path for path in ACCEPTED.rglob("*") if path.is_file() and "runs" not in path.parts and "__pycache__" not in path.parts]
    check("accepted source count", len(files) == 18)
    for path in files:
        rel = path.relative_to(ACCEPTED).as_posix()
        git_path = f"cases/simlox-air-support/{ACCEPTED.name}/{rel}"
        blob = subprocess.run(["git", "show", f"HEAD:{git_path}"], capture_output=True, check=True).stdout
        disk = path.read_bytes()
        if rel == ".gitignore":
            check("accepted .gitignore distinct disk/Git identities", len(disk) == 8 and sha_bytes(disk) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f" and len(blob) == 7 and sha_bytes(blob) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933" and disk.replace(b"\r\n", b"\n") == blob)
        else:
            check(f"published source {rel}", disk == blob)


def verify_run(capacity: int):
    variant, input_sha, run_id, closure_sha = PINS[capacity]
    source_path = ACCEPTED / "inputs" / f"{variant}.json"
    directory = RUN_ROOT / run_id
    check(f"{variant} input SHA", sha(source_path) == input_sha)
    check(f"{variant} closure SHA", sha(directory / "closure.json") == closure_sha)
    closure = load(directory / "closure.json")
    invocation = load(directory / "invocation.json")
    check(f"{variant} run identity", closure["run_id"] == run_id and closure["variant_id"] == variant and invocation["run_id"] == run_id and invocation["variant_id"] == variant)
    check(f"{variant} invocation seal", sha(directory / "invocation.json") == closure["invocation_sha256"])
    check(f"{variant} guarded provenance", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["coexisting_gui"]["pid"] == 13340 and invocation["coexisting_gui"]["session_id"] == 1 and invocation["coexisting_gui"]["process_start_utc"] == "2026-09-28T10:09:56.8261381Z")
    check(f"{variant} 11 raw seals", len(closure["raw"]) == 11)
    for name, seal in closure["raw"].items():
        path = directory / name
        check(f"{variant} raw {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    source = load(source_path)
    child = load(directory / "input.json")
    exported = load(directory / "roundtrip-raw.json")
    check(f"{variant} exact native input", source == child)
    populated = {name: rows(source, name, "model") for name, table in tables(source, "model").items() if any(any(value not in (None, "") for value in row) for instance in table["instances"] for row in instance["rows"])}
    check(f"{variant} 17 populated tables", len(populated) == 17)
    for name, authored in populated.items():
        check(f"{variant} roundtrip {name}", authored == rows(exported, name, "model"))
    alloc = rows(source, "ResourceAllocation", "model")
    check(f"{variant} allocation", [(r["RID"], r["RQTY"]) for r in alloc] == [("P-CREW", capacity), ("P-OTHER", 0)])
    request = rows(source, "SubTaskResource", "model")
    check(f"{variant} two crew request", len(request) == 1 and all(request[0][key] == value for key, value in {"TID": "PREP-FIXED", "SEQ": 1, "RID": "P-CREW", "QTY": 2, "ARID": None}.items()))
    log = (directory / "model.log").read_text(encoding="utf-8-sig")
    check(f"{variant} notice", close(times(log, " mission ordered:"), [7]))
    check(f"{variant} request", log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 2 ") == 1)
    if capacity == 2:
        for label, phrase, expected in (("booking", " allocated to maintenance task:", [7]), ("release", " deallocated from  maintenance task:", [7.16667]), ("SEQ1 work", "seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", [7]), ("SEQ2 work", "seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", [7.16667]), ("launch", " mission starting, duration:", [8]), ("success", " mission success:", [10])):
            check(f"{variant} {label}", close(times(log, phrase), expected))
        check(f"{variant} no cancel", not times(log, " mission cancelled:"))
        labels = (" books resources", " allocated to maintenance task:", " starts performing, planned to last for 0.166667 hours", " completed", " frees resources", " deallocated from  maintenance task:", " starts performing, planned to last for 0.333333 hours")
        fragments = ("subtask 0 seqno 1", "<P-CREW at <BASE-01,0>>", "subtask 0 seqno 1", "subtask 0 seqno 1", "subtask 0 seqno 1", "<P-CREW at <BASE-01,0>>", "subtask 1 seqno 2")
        positions = [[i for i, line in enumerate(log.splitlines()) if a in line and b in line] for a, b in zip(labels, fragments)]
        check(f"{variant} booking/work/release order", all(len(p) == 1 for p in positions) and all(a[0] < b[0] for a, b in zip(positions, positions[1:])))
    else:
        check(f"{variant} request failed", "Availability test on  <P-CREW at <BASE-01,0>> request for: 2 failed" in log)
        check(f"{variant} no booking/work/launch", " books resources" not in log and " starts performing," not in log and " mission starting, duration:" not in log)
        check(f"{variant} observed cancellation", close(times(log, " mission cancelled:"), [7.58333]))
    report = load(directory / "report-raw.json")
    names = list(tables(report, "report"))
    check(f"{variant} six report tables", names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"])
    system = rows(report, "SystemResults", "report")
    stock = rows(report, "StockTotalResults", "report")
    resource = rows(report, "ResourceResults", "report")
    summary = rows(report, "ResultSummary", "report")
    total = rows(report, "ResourceResultsTotal", "report")
    check(f"{variant} report row counts", (len(system), len(stock), len(resource), len(summary), len(total)) == (72, 72, 72, 1, 1))
    for name, ledger in (("system", system), ("stock", stock), ("resource", resource)):
        check(f"{variant} {name} complete half-hours", all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(ledger)))
    check(f"{variant} summary success", summary[0]["MSTF"] == int(capacity == 2) and summary[0]["MSUF"] == int(capacity == 2))
    check(f"{variant} system timeline", all(r["NPSTA"] == int(i == 14) and r["NPSUC"] == int(capacity == 2 and i == 15) and r["FTMO"] == int(capacity == 2 and 16 <= i < 20) for i, r in enumerate(system)))
    check(f"{variant} resource capacity/utilization", all(r["NR"] == capacity and abs(r["NRUM"] - (2 / 3 if capacity == 2 and i == 14 else 0)) < 1e-5 for i, r in enumerate(resource)))
    expected_wait = 0 if capacity == 2 else 1 if capacity == 1 else 2
    check(f"{variant} resource wait", all(abs(r["NRW"] - (expected_wait if i == 14 else expected_wait / 6 if i == 15 else 0)) < 1e-5 for i, r in enumerate(resource)))
    check(f"{variant} resource total", total[0]["NR"] == capacity and abs(total[0]["NRUM"] - (1 / 108 if capacity == 2 else 0)) < 1e-6)
    check(f"{variant} resource total waiting integral", abs(total[0]["NRW"] - sum(r["NRW"] / 72 for r in resource)) < 1e-6)
    check(f"{variant} terminal aircraft", system[-1]["NSYRY"] == 1 and system[-1]["ETINT"] == 36)
    check(f"{variant} stock idle", all(r["NBO"] == 0 and r["NDF"] == 0 for r in stock))
    return source, report


def main():
    check("contract pin", sha(HERE / "contract.json") == CONTRACT_SHA)
    check("v0.1.0 excluded no-go memo", sha(HERE.parent / "C01-var02-capacity-threshold-v0.1.0/review/independent-contract-no-go-2026-10-07.md") == "fcccb580fb24da792141bbc692cbebd4b9766e91bbc84593629c7d2cc4619656")
    check("v0.1.1 author first-pass NO_GO preserved", sha(HERE / "review/author-firstpass-no-go.json") == "dce64d54ab6e04e78f851a9f31e0d09ca6dd9703cc708d93bc6ec5f96efc59aa")
    check("original independent review pin", sha(ACCEPTED / "review/independent-readonly-2026-09-29.json") == ORIGINAL_REVIEW_SHA)
    original = load(ACCEPTED / "review/independent-readonly-2026-09-29.json")
    check("original independent acceptance", original["passed"] is True and original["differences"] == [])
    verify_source_git()
    data = {capacity: verify_run(capacity) for capacity in (2, 1, 0)}
    controls = data[2][0]
    for capacity in (1, 0):
        other = data[capacity][0]
        changed = [name for name in tables(controls, "model") if tables(controls, "model")[name] != tables(other, "model")[name]]
        check(f"capacity {capacity} sole changed table", changed == ["ResourceAllocation"])
        a, b = rows(controls, "ResourceAllocation", "model"), rows(other, "ResourceAllocation", "model")
        check(f"capacity {capacity} sole RQTY cell", len(a) == len(b) == 2 and [k for i in range(2) for k in a[i] if a[i][k] != b[i][k]] == ["RQTY"] and a[0]["RQTY"] == 2 and b[0]["RQTY"] == capacity)
    check("three identical descriptions", len({json.dumps(rows(data[c][1], "ProblemDescription", "report")) for c in (2, 1, 0)}) == 1)
    check("capacity-one/zero identical system and stock", all(tables(data[1][1], "report")[name] == tables(data[0][1], "report")[name] for name in ("ResultSummary", "SystemResults", "StockTotalResults")))
    failures = [name for name, passed in CHECKS.items() if not passed]
    result = {"schema": "simlox-c01-var02-author-readonly-reclassification/v1", "decision": "GO_BOUNDED" if not failures else "NO_GO", "passed": not failures, "check_count": len(CHECKS), "failures": failures, "new_native_run_count": 0, "accepted_parent": ACCEPTED.name, "selected_run_ids": [PINS[c][2] for c in (2, 1, 0)]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))
    return not failures


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
