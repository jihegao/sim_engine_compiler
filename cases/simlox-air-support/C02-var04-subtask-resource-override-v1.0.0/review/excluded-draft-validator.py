"""Frozen read-only event and full-report gate for C02.var04."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import INPUT_SHA, parse

HERE = Path(__file__).resolve().parent
RAW = Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C02-joint-resources-v1.0.2\runs")
ZERO = RAW / "c02-v102-single-zero-ssh-20260929-02"
BOTH = RAW / "c02-v102-single-both-ssh-20260929-02"
REPORT_SHA = {
    "zero": "92ae8cdf9962f95aafea7124d3394a5161e68b866af34a40bea3cc849f495b3f",
    "both": "f0879b5c66c95568bf13bc942f59eeaa34c83f8842d02a76e59c0eb3fc5cc732",
}
RUN_IDS = {"joint": "c02-var04-v100-joint-ssh-20261007-01",
           "crewonly": "c02-var04-v100-crewonly-ssh-20261007-01"}
SHAPE = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11),
         "SystemResults": (72, 40), "StockTotalResults": (72, 16),
         "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}


class Gate:
    def __init__(self):
        self.count = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.count += 1
        if not condition:
            self.failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def near(a, b, tol=3e-5) -> bool:
    if isinstance(a, (float, int)) and not isinstance(a, bool) and isinstance(b, (float, int)) and not isinstance(b, bool):
        return math.isfinite(a) and abs(a-b) <= tol
    return type(a) is type(b) and a == b


def reports(path: Path) -> dict:
    result = {}
    for table in parse(path)["report"]["tables"]:
        assert table["name"] not in result and len(table["instances"]) == 1
        result[table["name"]] = table
    return result


def events(g: Gate, path: Path, arm: str) -> None:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    def hits(time: float, token: str) -> int:
        return sum(bool((m := re.match(r"Time:\s*([0-9.eE+-]+)\s", line))
                        and abs(float(m.group(1))-time) <= 1e-4 and token in line)
                   for line in lines)
    def required(time: float, token: str, number: int = 1) -> None:
        g.check(hits(time, token) == number, f"event {time} {token} count={hits(time,token)}")
    owner = "<TEACH-AIR-01,0>"
    required(7, "mission activated, systems requested: 1")
    required(7, f"mission allocates system: {owner}")
    required(7, f"{owner} preparation started")
    required(7, "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources")
    g.check(sum("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK" in s for s in lines) == 1, "crew availability")
    if arm == "joint":
        g.check(sum("Availability test on  <E-GSE at <BASE-01,0>> request for: 1 failed" in s for s in lines) == 1, "equipment unavailable")
        required(7.58333, "mission cancelled:")
        required(7.58333, "resource waiting stopped")
        g.check(not any("allocated to maintenance task:" in s for s in lines), "no partial booking")
        g.check(not any("starts performing" in s for s in lines), "no physical work")
        g.check(not any("mission starting" in s for s in lines), "no launch")
        g.check(path.read_bytes() == (ZERO / "model.log").read_bytes(), "joint control byte-identical event log")
    else:
        g.check(not any("Availability test on  <E-GSE" in s for s in lines), "no equipment availability test")
        g.check(not any("<E-GSE at <BASE-01,0>> allocated to maintenance task" in s for s in lines), "no equipment booking")
        required(7, "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1")
        required(7, "on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours")
        required(7.5, "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed")
        required(7.5, "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1")
        required(7.5, "Time: 7.5  system preparation task 0 on <TEACH-AIR-01,0> completed")
        required(8, "mission starting, duration: 2")
        required(10, "mission success:")
        required(10, "mission completed:")
        g.check(not any("mission cancelled" in s or "failure occurs" in s or "backorder" in s.lower() for s in lines), "no cancellation/fault/backorder")


def check_report(g: Gate, path: Path, arm: str) -> None:
    g.check(digest(ZERO / "report-raw.json") == REPORT_SHA["zero"], "zero report seal")
    g.check(digest(BOTH / "report-raw.json") == REPORT_SHA["both"], "positive report seal")
    zero, both, actual = reports(ZERO / "report-raw.json"), reports(BOTH / "report-raw.json"), reports(path)
    g.check(set(actual) == set(SHAPE), "six report tables")
    template = zero if arm == "joint" else both
    checked = 0
    for name, (nrows, ncols) in SHAPE.items():
        if name not in actual:
            continue
        t, reference = actual[name], template[name]
        g.check(t["columns"] == reference["columns"], f"{name} columns")
        g.check(t["instances"][0].get("instance_name") == reference["instances"][0].get("instance_name"), f"{name} instance")
        rows = t["instances"][0]["rows"]
        g.check(len(rows) == nrows, f"{name} row count")
        wanted = [r.copy() for r in reference["instances"][0]["rows"]]
        if name == "ProblemDescription":
            wanted[0][0] = ("C02.var04 joint explicit INSPECT set with unavailable E-GSE" if arm == "joint"
                            else "C02.var04 crew-only explicit INSPECT set omitting main E-GSE")
        if arm == "crewonly" and name.startswith("ResourceResults"):
            columns = [c["name"] for c in t["columns"]]
            for row in wanted:
                for field in ("NR", "NRA", "NRN"):
                    row[columns.index(field)] = 1
                row[columns.index("NRUM")] = row[columns.index("NRUM")] / 2
        for i, want in enumerate(wanted):
            if i >= len(rows):
                break
            g.check(len(rows[i]) == ncols, f"{name}[{i}] width")
            for j, value in enumerate(want):
                if j >= len(rows[i]):
                    break
                g.check(near(rows[i][j], value), f"{name}[{i},{j}] {rows[i][j]!r} != {value!r}")
                checked += 1
    g.check(checked == 5210, f"complete report cell count {checked}")
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        if name not in actual:
            continue
        columns = [c["name"] for c in actual[name]["columns"]]
        for i, row in enumerate(actual[name]["instances"][0]["rows"]):
            g.check(near(row[columns.index("STINT")], i*.5) and near(row[columns.index("ETINT")], (i+1)*.5), f"{name} interval {i}")


def validate(run: Path, arm: str) -> dict:
    g = Gate()
    g.check(run.name == RUN_IDS[arm], "reserved run ID")
    g.check(digest(HERE / f"{arm}-input.json") == INPUT_SHA[arm], "frozen input")
    g.check(digest(run / "input.json") == INPUT_SHA[arm], "copied input")
    inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    g.check(inv["run_id"] == RUN_IDS[arm] and inv["session_id"] == 0, "SSH invocation")
    g.check(inv["gui"] == {"pid":13340,"session_id":1,"start_unix_ms":1790590196826,"responding":True}, "GUI identity")
    g.check(inv["source_hashes_before"][f"{arm}_input"] == INPUT_SHA[arm], "invocation input pin")
    rt = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    g.check(rt.get("passed") is True and rt.get("authored_row_tables") == 21, "21-table roundtrip")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    g.check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, "converter 0/2/0")
    g.check(sorted(re.findall(r"warning\s*#(\d+)", log, re.I)) == ["108", "126"], "warnings 108/126 only")
    events(g, run / "model.log", arm)
    check_report(g, run / "report-raw.json", arm)
    return {"schema":"c02-var04-v100-author-validation/v1", "arm":arm,"run_id":RUN_IDS[arm],
            "decision":"GO_BOUNDED" if not g.failures else "NO_GO", "checks":g.count,
            "passed":g.count-len(g.failures),"failures":g.failures,
            "scope":"single fixed one-aircraft explicit subtask resource set"}


if __name__ == "__main__":
    try:
        outcome = validate(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        outcome = {"schema":"c02-var04-v100-author-validation/v1","decision":"NO_GO",
                   "checks":1,"passed":0,"failures":[f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(outcome,indent=2))
    sys.exit(0 if outcome["decision"] == "GO_BOUNDED" else 1)
