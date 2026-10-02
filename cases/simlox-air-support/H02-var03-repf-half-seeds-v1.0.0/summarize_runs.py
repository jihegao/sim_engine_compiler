"""Print compact native event outcomes for the eight sealed -02 seed runs."""
from __future__ import annotations

import json
from pathlib import Path
import re

from check_roundtrip import parse_native

HERE = Path(__file__).resolve().parent


def ids(log: str, event: str) -> list[int]:
    return [int(x) for x in re.findall(event, log)]


def rows(report: dict, name: str) -> list[dict]:
    table, = [x for x in report["report"]["tables"] if x["name"] == name]
    columns = [x["name"] for x in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    for seed in range(1, 9):
        run = HERE / f"runs/h02-var03-half-seed{seed}-v100-ssh-20261002-02"
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        check = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        report = parse_native(run / "report-raw.json")
        system, stock, summary = (rows(report, name) for name in
                                  ("SystemResults", "StockTotalResults", "ResultSummary"))
        result = {
            "seed": seed, "closure_error": closure["error"], "roundtrip": check["passed"],
            "damage_ids": ids(log, r"Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>"),
            "discard_ids": ids(log, r"Item discarded: <TEACH-LRU-01,0,(\d+)>"),
            "repair_ids": ids(log, r"Time: [\d.]+  item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> completed"),
            "stock_return_ids": ids(log, r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock"),
            "issued_ids": ids(log, r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock"),
            "mission_starts": len(re.findall(r"mission starting, duration: 2", log)),
            "mission_aborts": len(re.findall(r"mission aborted:", log)),
            "mission_cancellations": len(re.findall(r"mission cancelled:", log)),
            "backorder_adds": len(re.findall(r"Backorder added", log)),
            "system_bins": len(system), "stock_bins": len(stock),
            "NDAM": sum(x["NDAM"] or 0 for x in system),
            "NREPT": sum(x["NREPT"] or 0 for x in system),
            "NDD": sum(x["NDD"] or 0 for x in stock),
            "NWT": sum(x["NWT"] or 0 for x in stock),
            "terminal_ready": system[-1]["NSYRY"],
            "terminal_backorder": stock[-1]["NBO"],
            "terminal_nominal_stock": stock[-1]["PNB"],
            "MSTF": summary[0]["MSTF"],
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
