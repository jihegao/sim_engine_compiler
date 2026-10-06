"""Read-only D04 long-parking catalog replay; never launches the native engine."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = ROOT / "D04-flight-hour-pm-v1.0.0" / "runs" / "d04-flight-v100-ssh-20260930-01"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def report(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))

def rows(doc: dict, name: str) -> list[dict]:
    matches = [table for table in doc["report"]["tables"] if table["name"] == name]
    assert len(matches) == 1, name
    cols = [column["name"] for column in matches[0]["columns"]]
    assert len(cols) == len(set(cols)), name
    values = [row for instance in matches[0]["instances"] for row in instance["rows"]]
    assert all(len(row) == len(cols) for row in values), name
    return [dict(zip(cols, row)) for row in values]

def main() -> int:
    checks = []
    def check(name: str, got, want):
        checks.append({"name": name, "passed": got == want, "actual": got, "expected": want})
    try:
        c = load(HERE / "contract.json")
        assert c["version"] == "1.0.1-readonly-candidate"
        old = c["preserved_contract_failure"]
        check("prior contract SHA", sha(ROOT / old["package"] / "contract.json"), old["contract_sha256"])
        check("prior NO_GO SHA", sha(ROOT / old["package"] / "review" / "independent-contract-no-go-2026-10-06.md"), old["independent_no_go_sha256"])
        p = c["accepted_parent"]
        d = c["instructional_prerequisite"]
        for name, path, expected in (
            ("D04 input", ROOT / p["package"] / "native-input.json", p["input_sha256"]),
            ("D04 signoff", ROOT / p["package"] / "cli-scope-signoff-2026-09-30.md", p["signoff_sha256"]),
            ("D04 closure", RUN / "closure.json", p["closure_sha256"]),
            ("D03 input", ROOT / d["package"] / "native-input.json", d["input_sha256"]),
            ("D03 signoff", ROOT / d["package"] / "cli-scope-signoff-2026-09-30.md", d["signoff_sha256"]),
            ("manual", Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"), c["source"]["manual_pdf_sha256"]),
            ("executable", Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"), c["source"]["native_executable_sha256"]),
        ):
            check(name + " SHA", sha(path), expected)
        closure, invocation = load(RUN / "closure.json"), load(RUN / "invocation.json")
        check("closure complete/run", [closure["error"], closure["run_id"]], [None, p["run_id"]])
        check("invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        check("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
        check("source input/parent/exe", [closure["source_hashes_before"][k] for k in ("input", "parent", "simlox_exe")],
              [p["input_sha256"], d["input_sha256"], c["source"]["native_executable_sha256"]])
        check("12 raw seals", len(closure["raw"]), 12)
        for name, pin in sorted(closure["raw"].items()):
            path = RUN / name
            check("raw " + name, [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
        check("SSH session/ancestry", [invocation["session_id"], invocation["ssh_connection_present"],
                                      "sshd.exe" in invocation["ssh_ancestor_names"]], [0, True, True])
        check("guarded GUI", invocation["gui"], {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("native mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("run copied input", sha(RUN / "input.json"), p["input_sha256"])
        check("roundtrip 18", [load(RUN / "roundtrip-validation.json")["passed"],
                                 len(load(RUN / "roundtrip-validation.json")["authored_row_containing_tables"])], [True, 18])
        converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter zero errors/two warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
        check("converter warning IDs", sorted(re.findall(r"\(warning #(\d+)\)", converter)), ["108", "126"])

        raw_report = report(RUN / "report-raw.json")
        system = rows(raw_report, "SystemResults")
        stock = rows(raw_report, "StockTotalResults")
        summary = rows(raw_report, "ResultSummary")
        check("120 System/Stock and one summary", [len(system), len(stock), len(summary)], [120, 120, 1])
        check("field widths", [len(system[0]), len(stock[0]), len(summary[0])], [40, 16, 11])
        for i, row in enumerate(system):
            check(f"System interval {i}", [row["STINT"], row["ETINT"]], [i / 2, (i + 1) / 2])
        for i, row in enumerate(stock):
            check(f"Stock interval {i}", [row["STINT"], row["ETINT"]], [i / 2, (i + 1) / 2])
        state = ("NSYRY", "NSYA", "NSYMA", "NSYMO", "NSYPM", "NPMS", "NPMT")
        for i in range(20, 78):
            check(f"parked ready h{i/2}", [system[i][k] for k in state], [1, 1, 0, 0, 0, 0, 0])
        for i in (78, 79):
            check(f"reserved, no flight h{i/2}", [system[i][k] for k in state], [0, 1, 1, 0, 0, 0, 0])
        for i in (80, 81):
            check(f"second flight h{i/2}", [system[i][k] for k in state], [0, 1, 1, 1, 0, 0, 0])
        for i, npms in ((82, 1), (83, 0)):
            check(f"PM occupancy h{i/2}", [system[i]["NSYPM"], system[i]["NPMS"], system[i]["NPMT"]], [1, npms, 0])
        check("PM completes h42", [system[84]["NSYPM"], system[84]["NPMT"], system[84]["NSYRY"]], [0, 1, 1])
        check("one PM start/completion all bins", [sum(r["NPMS"] for r in system), sum(r["NPMT"] for r in system)], [1, 1])
        check("terminal ready", [system[-1][k] for k in ("NSYRY", "NSYMO", "NSYPM")], [1, 0, 0])
        check("ready/flight/PM integrals", [sum(r[k] * .5 for r in system) for k in ("NSYRY", "NSYMO", "NSYPM")], [54, 3, 1])

        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        events = [(float(m.group(1)), m.group(2)) for line in log.splitlines()
                  if (m := re.match(r"^Time: ([\d.]+) (.*)$", line))]
        def event_time(phrase: str) -> list[float]:
            return [t for t, line in events if phrase in line]
        check("mission starts", event_time("mission starting, duration:"), [8.0, 40.0])
        check("mission success", event_time("mission success: "), [10.0, 41.0])
        check("second order/allocation", [event_time("mission ordered: SHORT-MISSION"),
                                           event_time("mission allocates system:")[-1:]], [[39.0], [39.0]])
        check("PM starts/completes", [event_time("system PM task 0 on <TEACH-AIR-01,0> started"),
                                      event_time("system PM task 0 on <TEACH-AIR-01,0> completed")], [[41.0], [42.0]])
        check("no flight/PM strictly inside parking gap", [(t, line) for t, line in events if 10 < t < 40 and
              ("mission starting" in line or "system PM task" in line or "System to PM" in line)], [])
        check("no flight during full h10-40 gap", [system[i]["NSYMO"] for i in range(20, 80)], [0] * 60)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d04-var02-v101-readonly-validation/v1", "passed": all(x["passed"] for x in checks),
              "checks_count": len(checks), "checks": checks, "scope": "accepted D04 one-gap read-only catalog mapping",
              "publication_state": "not_published"}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out = HERE / "review" / "author-readonly-validation-2026-10-06.json"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    print(json.dumps({"passed": result["passed"], "checks_count": len(checks), "failed": [x for x in checks if not x["passed"]][:10],
                      "report_sha256": hashlib.sha256(data).hexdigest()}))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
