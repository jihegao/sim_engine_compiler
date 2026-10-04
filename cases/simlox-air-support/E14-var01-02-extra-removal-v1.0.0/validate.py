"""Read-only author replay of the fixed E14 panel and its selected reports."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
CONTRACT = json.loads((CASE / "contract.json").read_text(encoding="utf-8"))
NATIVE = CASE / "runs" / CONTRACT["run_id"]
SELECTED = CASE / "runs" / CONTRACT["selected_report_run_id"]
ITEMS = ("TEACH-LRU-01", "TEACH-SRU-01", "TEACH-SRU-02")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def populated(model: dict) -> dict:
    result = {}
    for table in model["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            assert table["name"] not in result
            assert all(len(row) == len(table["columns"]) for row in rows)
            result[table["name"]] = (table["columns"], rows)
    return result


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    matching = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(matching) == 1, name
    return ([c["name"] for c in matching[0]["columns"]],
            [row for instance in matching[0]["instances"] for row in instance["rows"]])


def main() -> dict:
    checks = 0
    findings = []

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            findings.append(message)

    for directory in (NATIVE, SELECTED):
        closure = doc(directory / "closure.json")
        invocation = doc(directory / "invocation.json")
        check(closure["error"] is None, f"{directory.name}: closure error")
        check(closure["invocation_sha256"] == sha(directory / "invocation.json"), f"{directory.name}: invocation seal")
        check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{directory.name}: SSH0")
        check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{directory.name}: GUI identity")
        check(closure["source_hashes_before"] == closure["source_hashes_after"], f"{directory.name}: source drift")
        for name, seal in closure["raw"].items():
            path = directory / name
            check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"{directory.name}: {name} seal")
        steps = doc(directory / "steps.json")
        check(len(steps) == (40 if directory == NATIVE else 30), f"{directory.name}: step count")
        for step in steps:
            check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{directory.name}: {step['name']} step")

    native_closure = doc(NATIVE / "closure.json")
    selected_closure = doc(SELECTED / "closure.json")
    check(selected_closure["source_closure_sha256"] == sha(NATIVE / "closure.json"), "selected source closure")
    summary = {}
    for seed in CONTRACT["seeds"]:
        for arm in CONTRACT["arms"]:
            key = f"seed{seed}-{arm}"
            source = CASE / f"{key}-input.json"
            check(sha(source) == CONTRACT["inputs_sha256"][key], f"{key}: input pin")
            check(sha(NATIVE / f"{key}-input.json") == sha(source), f"{key}: input copy")
            authored = populated(doc(source)["model"])
            exported = populated(doc(NATIVE / f"{key}-roundtrip-raw.json")["model"])
            check(all(exported.get(name) == contents for name, contents in authored.items()), f"{key}: populated roundtrip")
            log = (NATIVE / f"{key}-run.log").read_text(encoding="utf-8-sig", errors="replace")
            check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log, f"{key}: converter summary")
            check(re.findall(r"\(warning #(\d+)\)", log) == ["108"], f"{key}: warning identity")
            events = (NATIVE / f"{key}.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
            extra = [line for line in events if "extra removal of subitem" in line]
            nff = [line for line in events if re.search(r"^Time: [0-9.]+  item NFF task \d+ on <[^>]+> started$", line)]
            flagged = [line for line in extra if "No Fault!" in line]
            demands = [line for line in events if "Item demand arrives from pos" in line]
            issues = [line for line in events if "Take replacement item" in line]
            check(len(demands) == len(issues), f"{key}: physical demands/issues")
            check(len(flagged) == len(nff), f"{key}: NFF count")
            if arm == "control":
                check(not extra and not nff, f"{key}: control extra/NFF")
            for item in ITEMS:
                path = SELECTED / f"{key}-{item.lower()}-item-report-raw.json"
                columns, rows = table(doc(path), "ItemResults")
                check(len(rows) == 72, f"{key}/{item}: 72 bins")
                check(all(row[columns.index("IID")] == item and row[columns.index("STID")] == "BASE-01" for row in rows), f"{key}/{item}: selector identity")
                check(all(abs(row[columns.index("STINT")] - i * 0.5) < 1e-8 and abs(row[columns.index("ETINT")] - (i + 1) * 0.5) < 1e-8 for i, row in enumerate(rows)), f"{key}/{item}: collection window")
                check(all(row[columns.index("STSZ")] == (1 if item == ITEMS[0] else 4) and row[columns.index("NBO")] >= 0 for row in rows), f"{key}/{item}: stock size/backorder")
                demand_count = len([line for line in demands if f"item requiring maintenance is <{item}," in line])
                issue_count = len([line for line in issues if f"Take replacement item <{item}," in line])
                return_count = len([line for line in events if f"Put back replacement item <{item}," in line])
                stock_levels = [int(match.group(1)) for line in events if (match := re.search(r"Stock at: <" + item + r",0,BASE-01,0> Level: (\d+)", line))]
                check(sum(row[columns.index("NDF")] or 0 for row in rows) == demand_count, f"{key}/{item}: report/event demand ledger")
                check(demand_count == issue_count, f"{key}/{item}: demand/issue ledger")
                check(bool(stock_levels) and stock_levels[-1] == (1 if item == ITEMS[0] else 4) + return_count - issue_count, f"{key}/{item}: physical stock ledger")
            mission_columns, mission_rows = table(doc(SELECTED / f"{key}-{ITEMS[0].lower()}-item-report-raw.json"), "FixedMissionResults")
            check(len(mission_rows) == 3 and [row[mission_columns.index("STIM")] for row in mission_rows] == [8, 20, 32], f"{key}: three fixed missions")
            mission_successes = [row[mission_columns.index("NMSUC")] for row in mission_rows]
            check(all(value in (0, 1) for value in mission_successes), f"{key}: mission outcome values")
            summary[key] = {"extra_removals": len(extra), "nff_extra_removals": len(flagged), "nff_repairs": len(nff), "demands": len(demands), "issues": len(issues), "mission_successes_h8_h20_h32": mission_successes}

    check(sum(summary[f"seed{seed}-extra"]["extra_removals"] for seed in CONTRACT["seeds"]) > 0, "panel has extra-removal witness")
    check(sum(summary[f"seed{seed}-extra"]["nff_extra_removals"] for seed in CONTRACT["seeds"]) > 0, "panel has NFF witness")
    return {"schema": "simlox-e14-author-validation/v1", "passed": not findings,
            "checks": checks, "failures": findings, "summary": summary,
            "native_closure_sha256": sha(NATIVE / "closure.json"),
            "selected_closure_sha256": sha(SELECTED / "closure.json"),
            "scope": "fixed-seed joint RRF/NFFF panel; separate causal effects unverified",
            "publication_state": "not_published"}


if __name__ == "__main__":
    result = main()
    destination = CASE / "review" / "author-validation-2026-10-05.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
