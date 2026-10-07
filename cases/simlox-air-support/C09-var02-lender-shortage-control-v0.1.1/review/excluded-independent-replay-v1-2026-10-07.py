"""Independent read-only replay of the sealed v1.0.2 ordinary control.

This script does not import the author validator or accept the prospective pair.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
CASE = PACKAGE.parent / "C09-var02-lender-shortage-v1.0.2"
RUN_ID = "c09-var02-v102-ordinary-ssh-20261007-01"
RUN = CASE / "runs" / RUN_ID
OTHER = CASE / "runs" / "c09-var02-v102-shortage-ssh-20261007-01"
EXPECTED = {
    "retrospective_contract": "2abc4d733557d97c0766c88599429cef756fcdf16315db56102076670c96632b",
    "closure": "30a99a36775224096dae27e938495dae5e12bb441cd493c2312baf5bef58d5df",
    "failure": "43a64a32e56abdcf312482c16d56b391f6bb5eb0d939efa272a330e4ff86c73e",
    "invocation": "ed2e0c12f69caac6f37597cd454a71190e9260a6726d450120a62708a694d756",
    "manifest": "0789c128a656b0d405932ec053dc80853ecc8f7dd692f9b4eb3041e80ee8ce4a",
    "approval": "ac594f3d2fd47f1a0c9faa858f1c99ed672575bd86560d32ff25f1aed3ae4250",
    "preflight": "418a93293415705ecfc7f58706368a1d07fac2b382ec5da65fa04a45f6282e47",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    text = path.read_bytes().decode("utf-8-sig")
    # Native jsonreport uses trailing commas. Remove only syntax commas outside strings.
    out = []
    quoted = escaped = False
    for i, char in enumerate(text):
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
        elif char == ',':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j >= len(text) or text[j] not in ']}':
                out.append(char)
        else:
            out.append(char)
    return json.loads(''.join(out))


def overlap(start: float, end: float, a: float, b: float) -> float:
    return max(0.0, min(end, b) - max(start, a))


def printed_uncertainty(value: float, source_exact: bool = False) -> float:
    if source_exact:
        return 0.0
    token = str(value)
    assert "." in token and "e" not in token, token
    return .5 * 10 ** (-len(token.split(".", 1)[1]))


def fractional_bound(value: float, edges: dict[str, float], uncertainties: dict[str, float],
                     contributions: dict[str, float], denominator: float,
                     ceiling: float, bin_start: float = 0.0, bin_end: float = 12.0) -> float:
    """Propagate each typed printed edge coefficient; no candidate value selects the bound."""
    time_bound = sum(abs(coefficient) * uncertainties[key] / denominator
                     for key, coefficient in contributions.items()
                     if bin_start < edges[key] < bin_end)
    serialization = 5e-7 if time_bound or not float(value).is_integer() else 0.0
    bound = time_bound + serialization
    assert bound <= ceiling + 1e-15, (contributions, bound, ceiling)
    return bound


def accepts(actual, expected, bound: float) -> bool:
    if expected is None or isinstance(expected, str):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
        return False
    return abs(actual - expected) <= bound + 1e-12


def unique_time(lines: list[str], expression: str) -> float:
    pattern = re.compile(r"^Time: ([0-9.]+)\s+" + expression + r".*$")
    found = [float(m.group(1)) for line in lines if (m := pattern.match(line))]
    assert len(found) == 1, (expression, found)
    return found[0]


def main() -> None:
    assert sha(PACKAGE / "contract.json") == EXPECTED["retrospective_contract"]
    assert RUN.is_dir() and not OTHER.exists()
    for key, path in {
        "closure": RUN / "closure.json", "failure": RUN / "failure-seal.json",
        "invocation": RUN / "invocation.json", "manifest": CASE / "prelaunch-manifest.json",
        "approval": CASE / "review" / "independent-prelaunch-go.json",
        "preflight": CASE / "review" / "preflight-ssh0-20261007T035932045Z.json",
    }.items():
        assert sha(path) == EXPECTED[key], key
    closure, failure, invocation = (load(RUN / name) for name in
        ("closure.json", "failure-seal.json", "invocation.json"))
    manifest, approval = load(CASE / "prelaunch-manifest.json"), load(CASE / "review" / "independent-prelaunch-go.json")
    pins = {item["key"]: item for item in manifest["source_files"]}
    assert len(pins) == 256 and len(manifest["source_files"]) == 256
    assert set(closure["source_hashes_before"]) == set(pins)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["source_hashes_before"] == invocation["source_hashes_before"]
    for key, item in pins.items():
        path = Path(item["path"])
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], key
        assert closure["source_hashes_before"][key] == item["sha256"], key
    assert closure["manifest_sha256"] == EXPECTED["manifest"]
    assert closure["approval_sha256"] == EXPECTED["approval"]
    assert closure["approved_preflight_sha256"] == EXPECTED["preflight"]
    assert invocation["run_id"] == closure["run_id"] == RUN_ID
    assert invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
    assert invocation["gui"] == {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}
    assert "sshd.exe" in invocation["ssh_ancestors"]
    assert closure["error"] == failure["error"] == "check_behavior rejected native result"
    assert len(closure["raw"]) == 13
    for name, entry in closure["raw"].items():
        path = RUN / name
        assert path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], name
    for name, entry in failure["files"].items():
        path = RUN / name
        assert path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], name
    assert closure["invocation_sha256"] == EXPECTED["invocation"]
    steps = load(RUN / "steps.json")
    assert [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert [s["exit_code"] for s in steps] == [0, 0, 0, 0, 0, 1]
    assert all(s["gui_preserved"] for s in steps)
    assert all(s["child_session_id"] == 0 for s in steps if "child_session_id" in s)
    assert load(RUN / "roundtrip-validation.json")["issues"] == []
    assert load(RUN / "roundtrip-validation.json")["authored_row_tables"] == 25
    assert load(RUN / "author-validation.json")["passed"] is False
    authored_tables = load(RUN / "input.json")["model"]["tables"]
    exported_tables = load(RUN / "roundtrip-raw.json")["model"]["tables"]
    assert len(authored_tables) == len(exported_tables) == 32
    authored_rows = 0
    for authored, exported in zip(authored_tables, exported_tables):
        assert authored["name"] == exported["name"]
        assert authored["columns"] == exported["columns"], authored["name"]
        assert len(authored["instances"]) == len(exported["instances"]), authored["name"]
        for left, right in zip(authored["instances"], exported["instances"]):
            assert left["instance_name"] == right["instance_name"], authored["name"]
            if left["rows"]:
                assert left["rows"] == right["rows"], authored["name"]
                authored_rows += 1
            else:
                assert not any(any(value is not None for value in row) for row in right["rows"]), authored["name"]
    assert authored_rows == 25
    run_log = (RUN / "run.log").read_text(encoding="utf-8")
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in run_log
    assert run_log.count("(warning #108)") == 1 and run_log.count("(warning #126)") == 2
    assert run_log.count("(notice #292)") == 1

    report = load(RUN / "report-raw.json")["report"]
    tables = {t["name"]: t for t in report["tables"]}
    counts = {name: (len(t["columns"]), sum(len(i["rows"]) for i in t["instances"])) for name, t in tables.items()}
    assert counts == {"ProblemDescription": (1, 1), "ResultSummary": (11, 1),
        "SystemResults": (40, 24), "StockTotalResults": (16, 24),
        "ResourceResults": (16, 24), "ResourceResultsTotal": (14, 1)}
    cells = sum(c * r for c, r in counts.values())
    assert cells == 1754
    for table in tables.values():
        count = len(table["columns"])
        for instance in table["instances"]:
            for row in instance["rows"]:
                assert len(row) == count
                assert all(not isinstance(v, float) or math.isfinite(v) for v in row if v is not None)

    log = (RUN / "model.log").read_text(encoding="utf-8").splitlines()
    prep_start = unique_time(log, r"system preparation task 0 on <TEACH-AIR-01,0> started")
    launch = unique_time(log, r"system preparation task 0 on <TEACH-AIR-01,0> completed")
    mission_end = unique_time(log, r".*aborted mission completed:")
    teach_wait = unique_time(log, r"<TEACH-AIR-01,0> nbr resourcewait increased")
    teach_repair = unique_time(log, r"direct repair subtask 2 seqno 1 within system DIRP task 2 on <TEACH-AIR-01,0> starts performing")
    teach_done = unique_time(log, r"direct repair subtask 2 seqno 1 within system DIRP task 2 on <TEACH-AIR-01,0> completed")
    home_wait = unique_time(log, r"<HOME-AIR,2> nbr resourcewait increased")
    home_pm = unique_time(log, r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing")
    home_done = unique_time(log, r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> completed")
    return_start = unique_time(log, r"return resource transport task 0 starts with 1 resources")
    return_end = unique_time(log, r"return resource transport task 0 arrives with 1 resources")
    assert (prep_start, launch, mission_end, teach_wait, teach_repair, teach_done, home_wait, home_pm, home_done, return_start, return_end) == (
        7.5, 8.0, 8.71988, 8.71988, 8.96988, 9.46988, 9.0, 9.96988, 10.2199, 9.46988, 9.96988)
    edges = {"prep": prep_start, "launch": launch, "arrival": mission_end,
             "loan_arrival": teach_repair, "repair_end": teach_done,
             "home_wait": home_wait, "return_arrival": home_pm, "home_done": home_done}
    uncertainty = {key: printed_uncertainty(value, key in {"prep", "launch", "home_wait"})
                   for key, value in edges.items()}
    system_edges = {
        "NSYRY": {"arrival": 1, "repair_end": 1, "home_done": 1},
        "NSYMA": {"prep": 2, "arrival": 2},
        "NSYMO": {"launch": 2, "arrival": 2},
        "NSYRP": {"loan_arrival": 1, "repair_end": 1},
        "NSYPM": {"return_arrival": 1, "home_done": 1},
        "NSYWR": {"arrival": 1, "loan_arrival": 1, "home_wait": 1, "return_arrival": 1},
        "NSYUA": {"arrival": 1, "repair_end": 1, "home_wait": 1, "home_done": 1},
        "NSYA": {"arrival": 1, "repair_end": 1, "home_wait": 1, "home_done": 1},
        "STACC": {"launch": 2, "arrival": 2},
        "FTMO": {"launch": 2 / 3, "arrival": 2 / 3},
    }
    resource_edges = {
        "NR": {"arrival": 1, "loan_arrival": 1, "repair_end": 1, "return_arrival": 1},
        "NRA": {"arrival": 1, "loan_arrival": 1, "repair_end": 1, "return_arrival": 1},
        "NRUM": {"prep": 2, "launch": 2, "loan_arrival": 1, "repair_end": 1,
                  "return_arrival": 1, "home_done": 1},
        "NRW": {"arrival": 1, "loan_arrival": 1, "home_wait": 1, "return_arrival": 1},
        "NRRI": {"loan_arrival": 1, "repair_end": 1},
        "NRRO": {"loan_arrival": 1, "repair_end": 1},
        "NRRT": {"arrival": 1, "loan_arrival": 1, "repair_end": 1, "return_arrival": 1},
    }
    assert any("Availability test on  <P-MECH at <BASE-02,0>> request for: 1 failed" in line for line in log)
    assert any("return transport arrives: 1" in line for line in log)
    assert any("subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> books resources" in line for line in log)
    assert unique_time(log, r"remote resource transport task 3 starts with 1 resources") == teach_wait
    assert unique_time(log, r"remote resource transport task 3 arrives with 1 resources") == teach_repair
    assert unique_time(log, r"<P-MECH at <BASE-01,0>> allocated to maintenance task: 1") == teach_repair
    assert unique_time(log, r"<P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1") == teach_done
    assert unique_time(log, r"<P-MECH at <BASE-02,0>> allocated to maintenance task: 1") == home_pm
    assert unique_time(log, r"<P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1") == home_done
    failed_request = [i for i, line in enumerate(log) if "Availability test on  <P-MECH at <BASE-02,0>> request for: 1 failed" in line]
    assert len(failed_request) == 1
    assert "Time: 9  subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> resource availability test" in log[failed_request[0] - 1]
    assert teach_wait < 9 < return_end and teach_repair < teach_done < home_pm < home_done
    assert log.count("Time: 9.96988  <P-MECH at <BASE-02,0>> allocated to maintenance task: 1  available now: 0") == 1
    assert log.count("Time: 10.2199  <P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1  available now: 1") == 1
    demand_edge = "<P-MECH at <BASE-02,0>> Resource remote demand arrives from pool  <P-MECH at <BASE-01,0>>"
    return_edge = "return resource transport task 0 created: starting from  <P-MECH at <BASE-01,0>> aiming for  <P-MECH at <BASE-02,0>>"
    assert sum(demand_edge in line for line in log) == 1
    assert sum(return_edge in line for line in log) == 1

    system = tables["SystemResults"]
    names = [col["name"] for col in system["columns"]]
    rows = system["instances"][0]["rows"]
    compared = 0
    whole_bin_residues = []
    for i, row in enumerate(rows):
        a, b = i / 2, (i + 1) / 2
        assert row[names.index("STINT")] == a and row[names.index("ETINT")] == b
        # Three physical aircraft. Mission-assigned includes the preparation interval.
        expected = {name: (None if name == "SYDT" else 0) for name in names}
        expected.update({"UNID": "Total over all Units", "SID": "Total over all Systems",
                         "STINT": a, "ETINT": b})
        expected.update({
            "NSYMA": 2 * overlap(prep_start, mission_end, a, b) / .5,
            "NSYMO": 2 * overlap(launch, mission_end, a, b) / .5,
            "NSYMP": 2 if i == 15 else 0,
            "NSYWR": (overlap(teach_wait, teach_repair, a, b) + overlap(home_wait, home_pm, a, b)) / .5,
            "NSYRP": overlap(teach_repair, teach_done, a, b) / .5,
            "NSYPM": overlap(home_pm, home_done, a, b) / .5,
            "NREPT": 1 if i == 18 else 0, "NPMT": 1 if i == 20 else 0,
            "NFAIL": 1 if i == 16 else 0, "NPMS": 1 if i == 18 else 0,
            "NPSTA": 2 if i == 15 else 0, "NPSUC": 2 if i == 16 else 0,
            "NSYDT": 1 if i in (17, 18) else 0,
            "SYDT": (teach_done - teach_wait if i == 17 else home_done - home_wait if i == 18 else None),
        })
        expected["NSYUA"] = expected["NSYWR"] + expected["NSYRP"] + expected["NSYPM"]
        expected["NSYRY"] = 3 - expected["NSYMA"] - expected["NSYUA"]
        expected["NSYA"] = 3 - expected["NSYUA"]
        expected["FTMO"] = expected["NSYMO"] / 3
        expected["STACC"] = expected["NSYMO"]
        for field, value in expected.items():
            actual = row[names.index(field)]
            bound = 0.0
            if field in system_edges:
                bound = fractional_bound(value, edges, uncertainty, system_edges[field],
                                         .5, .00012 if field == "FTMO" else .00035, a, b)
            elif field == "SYDT" and value is not None:
                affected = {"arrival": 1, "repair_end": 1} if i == 17 else {"home_wait": 1, "home_done": 1}
                bound = fractional_bound(value, edges, uncertainty, affected, 1, .0001)
            if i == 18 and field == "NSYWR":
                assert bound == 0.0 and value == 1.0
                bound = 3e-6
            assert accepts(actual, value, bound), (i, field, actual, value, bound)
            if isinstance(value, (int, float)) and float(value).is_integer() and actual != value:
                whole_bin_residues.append(("SystemResults", i, field, value, actual, bound))
            compared += 1
        assert abs(row[names.index("NSYRY")] + row[names.index("NSYMA")] + row[names.index("NSYUA")] - 3) < .00001
    stock = tables["StockTotalResults"]
    stock_names = [col["name"] for col in stock["columns"]]
    stock_compared = 0
    for i, row in enumerate(stock["instances"][0]["rows"]):
        for field, value in {"STINT": i / 2, "ETINT": (i + 1) / 2,
                             "PNB": 1, "NBO": 0, "NBOU": None, "ROS": None,
                             "ROST": None, "WT": None, "WTT": None, "WTS": None,
                             "NDF": 0, "NDD": 0, "NDR": 0, "NDP": 0,
                             "NLD": 0, "NWT": 0}.items():
            assert row[stock_names.index(field)] == value, (i, field)
            stock_compared += 1
    resource = tables["ResourceResults"]
    resource_names = [col["name"] for col in resource["columns"]]
    resource_compared = 0
    outward_start = teach_wait
    outward_end = teach_repair
    for i, row in enumerate(resource["instances"][0]["rows"]):
        a, b = i / 2, (i + 1) / 2
        duration = .5
        transport = (overlap(outward_start, outward_end, a, b) + overlap(return_start, return_end, a, b)) / duration
        loan_at_borrower = overlap(teach_repair, teach_done, a, b) / duration
        work = (2 * overlap(prep_start, launch, a, b) + overlap(teach_repair, teach_done, a, b)
                + overlap(home_pm, home_done, a, b)) / duration
        wait = (overlap(teach_wait, teach_repair, a, b) + overlap(home_wait, home_pm, a, b)) / duration
        expected = {"RID": "Total over all Resources", "STID": "Total over all Stations",
                    "STINT": a, "ETINT": b, "NR": 3 - transport, "NRMO": 0,
                    "NRMA": 0, "NRUM": work, "NRLA": 0, "NRW": wait,
                    "NRA": 3 - transport, "NRN": 3, "NRF": 0,
                    "NRRI": loan_at_borrower, "NRRT": transport, "NRRO": loan_at_borrower}
        for field, value in expected.items():
            actual = row[resource_names.index(field)]
            bound = (fractional_bound(value, edges, uncertainty, resource_edges[field], .5, .00035, a, b)
                     if field in resource_edges else 0.0)
            if i == 18 and field == "NRW":
                assert bound == 0.0 and value == 1.0
                bound = 3e-6
            assert accepts(actual, value, bound), (i, field, actual, value, bound)
            if isinstance(value, float) and value.is_integer() and actual != value:
                whole_bin_residues.append(("ResourceResults", i, field, value, actual, bound))
            resource_compared += 1
    total = tables["ResourceResultsTotal"]
    total_names = [col["name"] for col in total["columns"]]
    total_row = total["instances"][0]["rows"][0]
    totals_expected = {"RID": "Total over all Resources", "STID": "Total over all Stations",
                      "NR": 3 - ((outward_end - outward_start) + (return_end - return_start)) / 12,
                      "NRMO": 0, "NRMA": 0,
                      "NRUM": (2 * (launch - prep_start) + (teach_done - teach_repair) + (home_done - home_pm)) / 12,
                      "NRLA": 0, "NRW": ((teach_repair - teach_wait) + (home_pm - home_wait)) / 12,
                      "NRA": 3 - ((outward_end - outward_start) + (return_end - return_start)) / 12,
                      "NRN": 3, "NRF": 0, "NRRI": (teach_done - teach_repair) / 12,
                      "NRRT": ((outward_end - outward_start) + (return_end - return_start)) / 12,
                      "NRRO": (teach_done - teach_repair) / 12}
    for field, value in totals_expected.items():
        actual = total_row[total_names.index(field)]
        bound = (fractional_bound(value, edges, uncertainty, resource_edges[field], 12, .00005)
                 if field in resource_edges else 0.0)
        assert accepts(actual, value, bound), (field, actual, value, bound)
    source = load(CASE / "ordinary-input.json")["model"]["tables"]
    source_tables = {t["name"]: t for t in source}
    source_description = source_tables["ProblemDescription"]["instances"][0]["rows"][0][0]
    desc = tables["ProblemDescription"]["instances"][0]["rows"][0][0]
    assert desc == source_description
    control = source_tables["Control"]
    control_fields = {c["name"]: v for c, v in zip(control["columns"], control["instances"][0]["rows"][0])}
    assert control_fields["NREPS"] == 1 and control_fields["SIMPE"] == 12
    summary = tables["ResultSummary"]
    summary_names = [col["name"] for col in summary["columns"]]
    summary_row = summary["instances"][0]["rows"][0]
    summary_expected = {"NREP": 1, "RTILW": 0, "RTIUP": 12,
                        "MTMF": mission_end - launch, "RSMTMF": 0,
                        "MSTF": 1, "RSMSTF": 0, "MSUF": 0, "RSMSUF": 0,
                        "STMF": mission_end - launch, "RSSTMF": 0}
    for field, value in summary_expected.items():
        actual = summary_row[summary_names.index(field)]
        bound = (fractional_bound(value, edges, uncertainty, {"launch": 1, "arrival": 1}, 1, .00005)
                 if field in ("MTMF", "STMF") else 0.0)
        assert accepts(actual, value, bound), (field, actual, value, bound)
    # The decisive bin is [9.5,10): HOME waits, then performs a real PM subtask.
    row = rows[19]
    decisive = {field: row[names.index(field)] for field in ("NSYRY", "NSYMA", "NSYUA", "NSYWR", "NSYPM", "NSYRP")}
    assert abs(decisive["NSYWR"] - .9397568106651306) < .00001
    assert abs(decisive["NSYPM"] - .06024317443370819) < .00001
    tamper_rejections = 0
    def reject(probe):
        nonlocal tamper_rejections
        assert probe is False
        tamper_rejections += 1
    for bad in (1.00001, .99999):
        reject(accepts(bad, 1.0, 3e-6))  # System NSYWR and Resource NRW, separately
        reject(accepts(bad, 1.0, 3e-6))
    reject(accepts(.6667, 2 / 3, 5e-7))
    reject(accepts(1e-9, 0, 0))  # discrete count
    reject(accepts(0, None, 0))  # null -> numeric zero
    reject(accepts("OTHER", "Total over all Units", 0))
    pm_expected = rows[19][names.index("NSYPM")]
    pm_bound = fractional_bound(pm_expected, edges, uncertainty, system_edges["NSYPM"], .5, .00035, 9.5, 10)
    reject(accepts(pm_expected + pm_bound + .00001, pm_expected, pm_bound))
    total_expected = totals_expected["NRUM"]
    total_bound = fractional_bound(total_expected, edges, uncertainty, resource_edges["NRUM"], 12, .00005)
    reject(accepts(total_expected + total_bound + .00001, total_expected, total_bound))
    def rejects_missing_edge(token, pattern):
        nonlocal tamper_rejections
        altered = [line for line in log if token not in line]
        try:
            unique_time(altered, pattern)
        except AssertionError:
            tamper_rejections += 1
        else:
            raise AssertionError(("mutant accepted", token))
    rejects_missing_edge("subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing",
                         r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing")
    rejects_missing_edge("subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> completed",
                         r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> completed")
    rejects_missing_edge("return resource transport task 0 arrives with 1 resources",
                         r"return resource transport task 0 arrives with 1 resources")
    rejects_missing_edge("<P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1",
                         r"<P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1")
    for old, new, pattern in (
        ("system PM task 3 on <HOME-AIR,2> starts performing", "system PM task 3 on <HOME-AIR,1> starts performing",
         r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing"),
        ("return resource transport task 0 starts with 1", "return resource transport task 1 starts with 1",
         r"return resource transport task 0 starts with 1 resources"),
        ("<P-MECH at <BASE-02,0>> allocated to maintenance task: 1", "<P-MECH at <BASE-02,0>> allocated to maintenance task: 2",
         r"<P-MECH at <BASE-02,0>> allocated to maintenance task: 1"),
    ):
        altered = [line.replace(old, new) for line in log]
        try:
            unique_time(altered, pattern)
        except AssertionError:
            tamper_rejections += 1
        else:
            raise AssertionError(("mutant accepted", old))
    reject(sum(demand_edge in line for line in [line.replace("<P-MECH at <BASE-01,0>>", "<P-MECH at <BASE-03,0>>")
                                                 if demand_edge in line else line for line in log]) == 1)
    reject(sum(return_edge in line for line in [line.replace("aiming for  <P-MECH at <BASE-02,0>>",
                                                           "aiming for  <P-MECH at <BASE-03,0>>")
                                                 if return_edge in line else line for line in log]) == 1)
    altered_timing = list(log)
    altered_timing[failed_request[0] - 1] = altered_timing[failed_request[0] - 1].replace("Time: 9 ", "Time: 8 ")
    reject("Time: 9  subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> resource availability test"
           in altered_timing[failed_request[0] - 1])
    assert tamper_rejections == 20
    verdict = {"decision": "GO_BOUNDED_RETROSPECTIVE_CONTROL",
        "original_prospective_pair": "NO_GO_PROSPECTIVE_PAIR", "run_id": RUN_ID,
        "shortage_run_absent": True, "raw_seals": len(closure["raw"]), "manifest_pins": len(pins),
        "report_tables": counts, "report_cells_shape_checked": cells,
        "full_report_cells_compared": compared + stock_compared + resource_compared + len(totals_expected) + len(summary_expected) + 1,
        "event_derived_system_cells_compared": compared, "stock_cells_compared": stock_compared,
        "event_derived_resource_cells_compared": resource_compared,
        "event_derived_resource_total_cells_compared": len(totals_expected),
        "retrospective_control_replay": "GO_BOUNDED_REPLAY_ONLY",
        "tamper_rejections": tamper_rejections,
        "printed_whole_bin_numeric_residues": whole_bin_residues,
        "decisive_bin_19": decisive,
        "frozen_checker_gap": "PM subtask starts performing has no PM prefix; frozen prefix regex misses HOME active PM",
        "native_steps": [s["exit_code"] for s in steps]}
    serialized = json.dumps(verdict, sort_keys=True, indent=2) + "\n"
    if sys.argv[1:] == ["--write-verdict"]:
        Path(__file__).with_name("independent-verdict.json").write_bytes(serialized.encode("utf-8"))
    else:
        assert not sys.argv[1:], "usage: independent_replay.py [--write-verdict]"
    print(serialized, end="")


if __name__ == "__main__":
    main()
