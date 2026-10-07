"""Reviewer-owned native report topology check; read-only and standard-library only.

The accepted C09 remote report calibrates the 36-hour form. The same function
can check the prospective 12-hour child without importing the author parser.
This checks shape and identity, not behavioral values or contract acceptance.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
FIELDS = {
    "ProblemDescription": "PDESC".split(),
    "ResultSummary": "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF".split(),
    "SystemResults": ("UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS "
                      "NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA "
                      "NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW "
                      "SYDT SYDTU NSYDT NSYSW NPSTA NPSUC").split(),
    "StockTotalResults": "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT".split(),
    "ResourceResults": "RID STID STINT ETINT NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split(),
    "ResourceResultsTotal": "RID STID NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split(),
}


def native_json(path: Path) -> dict:
    """Remove native trailing commas in memory, never in the sealed raw file."""
    source = path.read_text(encoding="utf-8-sig")
    output: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(source):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ",":
            next_index = index + 1
            while next_index < len(source) and source[next_index].isspace():
                next_index += 1
            if next_index == len(source) or source[next_index] not in "]}":
                output.append(char)
        else:
            output.append(char)
    assert not quoted, "unterminated report JSON string"
    return json.loads("".join(output))


def check_document(document: dict, horizon: int) -> dict:
    assert set(document) == {"report"}
    tables = document["report"]["tables"]
    assert [entry["name"] for entry in tables] == list(FIELDS)
    expected_instances = {
        "ProblemDescription": "",
        "ResultSummary": "",
        "SystemResults": f"Total over all Units;Total over all Systems;0.00;{horizon:.2f}",
        "StockTotalResults": f"0.00;{horizon:.2f};",
        "ResourceResults": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}",
        "ResourceResultsTotal": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}",
    }
    rows: dict[str, list[dict]] = {}
    checked = 0
    for entry in tables:
        name = entry["name"]
        columns = [column["name"] for column in entry["columns"]]
        assert columns == FIELDS[name], f"{name} columns"
        assert len(entry["instances"]) == 1, f"{name} instance count"
        instance = entry["instances"][0]
        assert instance["instance_name"] == expected_instances[name], f"{name} instance name"
        matrix = instance["rows"]
        expected_rows = 2 * horizon if name in {"SystemResults", "StockTotalResults", "ResourceResults"} else 1
        assert len(matrix) == expected_rows, f"{name} row count"
        assert all(len(row) == len(columns) for row in matrix), f"{name} row width"
        rows[name] = [dict(zip(columns, row)) for row in matrix]
        checked += len(matrix) * len(columns)
        if name in {"SystemResults", "StockTotalResults", "ResourceResults"}:
            for index, row in enumerate(rows[name]):
                assert row["STINT"] == index / 2, f"{name} start interval {index}"
                assert row["ETINT"] == (index + 1) / 2, f"{name} end interval {index}"
    assert checked == 26 + 144 * horizon, (checked, horizon)
    return {"cells": checked, "rows": {name: len(value) for name, value in rows.items()}}


def main() -> dict:
    contract = json.loads((PACKAGE / "contract.json").read_bytes())
    remote = contract["accepted_direct_parent"]["accepted_runs"]["remote"]
    report = (PACKAGE / remote["path"] / "report-raw.json").resolve()
    document = native_json(report)
    result = check_document(document, 36)
    probes = 0
    for mutation in ("instance", "column", "interval", "width"):
        mutant = copy.deepcopy(document)
        tables = {entry["name"]: entry for entry in mutant["report"]["tables"]}
        if mutation == "instance":
            tables["SystemResults"]["instances"][0]["instance_name"] = ""
        elif mutation == "column":
            tables["StockTotalResults"]["columns"][0]["name"] = "WRONG"
        elif mutation == "interval":
            tables["ResourceResults"]["instances"][0]["rows"][0][2] = 0.5
        else:
            tables["SystemResults"]["instances"][0]["rows"][0].pop()
        try:
            check_document(mutant, 36)
        except AssertionError:
            probes += 1
        else:
            raise AssertionError(f"report-shape mutation accepted: {mutation}")
    return {"schema": "independent-c09-var02-v101-report-shape/v1",
            "decision": "GO_PARENT_SHAPE_ONLY", "parent_report": result,
            "adversarial_rejections": probes, "native_process_started": False}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
