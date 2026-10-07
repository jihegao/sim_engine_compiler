"""Read-only diagnostic of the sealed failed v1.0.2 ordinary arm.

This script does not import the author validator or accept the prospective pair.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
RUN_ID = "c09-var02-v102-ordinary-ssh-20261007-01"
RUN = CASE / "runs" / RUN_ID
OTHER = CASE / "runs" / "c09-var02-v102-shortage-ssh-20261007-01"
EXPECTED = {
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


def unique_time(lines: list[str], expression: str) -> float:
    pattern = re.compile(r"^Time: ([0-9.]+)\s+" + expression + r".*$")
    found = [float(m.group(1)) for line in lines if (m := pattern.match(line))]
    assert len(found) == 1, (expression, found)
    return found[0]


def main() -> None:
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
    assert any("Availability test on  <P-MECH at <BASE-02,0>> request for: 1 failed" in line for line in log)
    assert any("return transport arrives: 1" in line for line in log)
    assert any("subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> books resources" in line for line in log)

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
            if value is None or isinstance(value, str):
                assert actual == value, (i, field, actual, value)
            elif field in {"STINT", "ETINT", "NREPT", "NPMT", "NFAIL", "NPMS", "NPSTA", "NPSUC", "NSYDT"}:
                assert actual == value, (i, field, actual, value)
            else:
                assert abs(actual - value) <= .00030, (i, field, actual, value)
                if isinstance(value, (int, float)) and float(value).is_integer() and actual != value:
                    whole_bin_residues.append(("SystemResults", i, field, value, actual))
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
            assert (abs(actual - value) <= .00030 if isinstance(value, float) else actual == value), (i, field, actual, value)
            if isinstance(value, float) and value.is_integer() and actual != value:
                whole_bin_residues.append(("ResourceResults", i, field, value, actual))
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
        assert (abs(actual - value) <= .00003 if isinstance(value, float) else actual == value), (field, actual, value)
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
        assert abs(actual - value) <= (.00001 if field in ("MTMF", "STMF") else 0), (field, actual, value)
    # The decisive bin is [9.5,10): HOME waits, then performs a real PM subtask.
    row = rows[19]
    decisive = {field: row[names.index(field)] for field in ("NSYRY", "NSYMA", "NSYUA", "NSYWR", "NSYPM", "NSYRP")}
    assert abs(decisive["NSYWR"] - .9397568106651306) < .00001
    assert abs(decisive["NSYPM"] - .06024317443370819) < .00001
    verdict = {"decision": "NO_GO_PROSPECTIVE_PAIR", "run_id": RUN_ID,
        "shortage_run_absent": True, "raw_seals": len(closure["raw"]), "manifest_pins": len(pins),
        "report_tables": counts, "report_cells_shape_checked": cells,
        "full_report_cells_compared": compared + stock_compared + resource_compared + len(totals_expected) + len(summary_expected) + 1,
        "event_derived_system_cells_compared": compared, "stock_cells_compared": stock_compared,
        "event_derived_resource_cells_compared": resource_compared,
        "event_derived_resource_total_cells_compared": len(totals_expected),
        "printed_whole_bin_numeric_residues": whole_bin_residues,
        "decisive_bin_19": decisive,
        "frozen_checker_gap": "PM subtask starts performing has no PM prefix; frozen prefix regex misses HOME active PM",
        "native_steps": [s["exit_code"] for s in steps]}
    serialized = json.dumps(verdict, sort_keys=True, indent=2) + "\n"
    Path(__file__).with_name("independent-failed-ordinary-verdict.json").write_bytes(serialized.encode("utf-8"))
    print(serialized, end="")


if __name__ == "__main__":
    main()
