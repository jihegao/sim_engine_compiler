"""Author replay for manual-prohibited but natively silent double-OUTSIDE row."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2"
NATIVE = HERE / "runs/i02-var14-both-outside-v101-ssh-20261002-01"
REPORT = HERE / "runs/i02-var14-depot-item-v101-ssh-20261002-01"
CONTROL_NATIVE = PARENT / "runs/i02-var01-in-v102-ssh-20261002-01"
CONTROL_REPORT = PARENT / "runs/i02-var01-item-results-v102-ssh-20261002-01"
SOURCE_SHA = "de0e6c5acb053c48528598d91b541603f78cfdac68f866899c2240740e58ced5"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"
SELECTOR_SHA = "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native default JSON reports sometimes have trailing commas. Only a
        # parser copy is repaired; raw byte seals remain authoritative.
        out: list[str] = []
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


def rows(doc: dict, name: str) -> list[dict]:
    matches = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    keys = [c["name"] for c in matches[0]["columns"]]
    return [dict(zip(keys, row, strict=True)) for ins in matches[0]["instances"] for row in ins["rows"]]


def sealed(folder: Path, count: int) -> bool:
    inv, closure = read(folder / "invocation.json"), read(folder / "closure.json")
    return (closure["error"] is None and closure["run_id"] == folder.name
            and closure["invocation_sha256"] == sha(folder / "invocation.json")
            and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"]
            and len(closure["raw"]) == count
            and all((folder / name).stat().st_size == meta["bytes"] and sha(folder / name) == meta["sha256"]
                    for name, meta in closure["raw"].items()))


def main() -> None:
    checks: list[dict] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    check("source_pins", sha(HERE / "native-input.json") == contract["input_sha256"] == SOURCE_SHA
          and sha(PARENT / "native-input.json") == contract["direct_parent"]["source_sha256"] == PARENT_SHA)
    check("exact_delta", diff["business_cell_delta"] == {"table": "ItemTransfer", "column": "STTID", "row": 0,
                                                    "before": "DEPOT-01", "after": "<OUTSIDE>"}
          and diff["changed_tables"] == ["ItemTransfer", "ProblemDescription"]
          and diff["other_tables_identical"] == 30
          and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("selector", sha(HERE / "runs/report-settings/item-position-results.sxs") == SELECTOR_SHA)
    for name, folder, count in (("child_native", NATIVE, 12), ("child_report", REPORT, 2),
                                ("parent_native", CONTROL_NATIVE, 12), ("parent_report", CONTROL_REPORT, 2)):
        check(f"{name}_sealed", sealed(folder, count))
    nc, rc = read(NATIVE / "closure.json"), read(REPORT / "closure.json")
    pc, prc = read(CONTROL_NATIVE / "closure.json"), read(CONTROL_REPORT / "closure.json")
    check("source_bindings", nc["source_hashes_before"]["input"] == SOURCE_SHA
          and nc["source_hashes_before"]["parent"] == PARENT_SHA
          and nc["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
          and nc["source_hashes_before"]["exact_diff"] == sha(HERE / "exact-diff.json")
          and nc["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1")
          and pc["source_hashes_before"]["input"] == PARENT_SHA)
    check("report_bindings", rc["source_hashes_before"]["sxo"] == nc["raw"]["model.sxo"]["sha256"]
          and rc["source_hashes_before"]["settings"] == SELECTOR_SHA
          and rc["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
          and read(REPORT / "invocation.json")["source_closure_sha256"] == sha(NATIVE / "closure.json")
          and prc["source_hashes_before"]["sxo"] == pc["raw"]["model.sxo"]["sha256"])
    inv, ri = read(NATIVE / "invocation.json"), read(REPORT / "invocation.json")
    check("guard", inv["session_id"] == ri["session_id"] == 0
          and inv["gui"]["pid"] == ri["gui"]["pid"] == 13340
          and "sshd.exe" in inv["ssh_ancestor_names"] and "sshd.exe" in ri["ssh_ancestor_names"]
          and inv["queue_mutex"] == ri["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    steps = read(NATIVE / "steps.json")
    check("steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
          and all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
    rt = read(NATIVE / "roundtrip-validation.json")
    check("roundtrip", rt["passed"] and len(rt["populated_tables"]) == 22 and rt["source_sha256"] == SOURCE_SHA)
    check("conversion", "Input conversion completed. Errors: 0," in (NATIVE / "run.log").read_text(encoding="utf-8-sig")
          and (NATIVE / "model.sxo").stat().st_size > 4)
    child_log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (CONTROL_NATIVE / "model.log").read_text(encoding="utf-8-sig")
    check("parent_in", "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in parent_log)
    check("child_silent_at_h4", "Time: 4" not in child_log
          and "item transfer task" not in child_log.lower()
          and "Item transfer backorder added" not in child_log)
    check("same_ordinary_depot_issue", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in child_log
          and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in parent_log)
    child_report, parent_report = read(REPORT / "item-report-raw.json"), read(CONTROL_REPORT / "item-report-raw.json")
    cr, pr = rows(child_report, "ItemResults"), rows(parent_report, "ItemResults")
    check("grid", len(cr) == len(pr) == 72 and all(r["IID"] == "TEACH-LRU-01" and r["STID"] == "DEPOT-01"
          and r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(cr)))
    check("depot_timeline", all(cr[i]["STSZ"] == pr[i]["STSZ"] and cr[i]["STOHA"] == pr[i]["STOHA"] for i in range(8))
          and all(cr[i]["STSZ"] == pr[i]["STSZ"] - 1
                  and abs((pr[i]["STOHA"] - cr[i]["STOHA"]) - 1) < 1e-6
                  for i in range(8, 72))
          and cr[8]["STSZ"] == cr[8]["STOHA"] == 1 and pr[8]["STSZ"] == pr[8]["STOHA"] == 2
          and cr[20]["STSZ"] == 1 and cr[20]["STOHA"] == 0
          and cr[-1]["STSZ"] == cr[-1]["STOHA"] == 1)
    check("only_item_position_bins_differ", all({k for k in c if c[k] != p[k]} == ({"STSZ", "STOHA"} if i >= 8 else set())
          for i, (c, p) in enumerate(zip(cr, pr))))
    check("ordinary_nbo_zero", all(c["NBO"] == 0 for c in cr))
    selected_child = {t["name"]: t for t in child_report["report"]["tables"]}
    selected_parent = {t["name"]: t for t in parent_report["report"]["tables"]}
    check("selected_nonitem_equal", selected_child.keys() == selected_parent.keys()
          and all(selected_child[k] == selected_parent[k]
                  for k in selected_child if k not in {"ProblemDescription", "ItemResults", "ItemResultsTotal"}))
    check("terminal_aircraft_ready", rows(child_report, "SystemResults")[-1]["NSYRY"] == 1
          and rows(parent_report, "SystemResults")[-1]["NSYRY"] == 1)
    cit, pit = rows(child_report, "ItemResultsTotal")[0], rows(parent_report, "ItemResultsTotal")[0]
    check("average_item_position", abs((pit["STSZ"] - cit["STSZ"]) - 32 / 36) < 1e-6
          and abs((pit["STOHA"] - cit["STOHA"]) - 32 / 36) < 1e-6)
    default_child, default_parent = read(NATIVE / "report-raw.json"), read(CONTROL_NATIVE / "report-raw.json")
    dc = {t["name"]: t for t in default_child["report"]["tables"]}
    dp = {t["name"]: t for t in default_parent["report"]["tables"]}
    check("default_business_equal", dc.keys() == dp.keys()
          and all(dc[k] == dp[k] for k in dc if k != "ProblemDescription"))
    result = {"schema": "simlox-i02-var14-both-outside-author-validation/v1",
              "variant_id": "I02.var14", "source_sha256": SOURCE_SHA,
              "native_run_id": NATIVE.name, "item_report_run_id": REPORT.name,
              "checks": checks, "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks), "check_count": len(checks),
              "classification": "NO-GO for manual-prohibited-row rejection in this installed CLI: converter accepts the double-<OUTSIDE> row and emits no scheduled transfer; stock remains one below accepted IN from h4 onward.",
              "limits": "One h4 one-unit row, one IID/depot/seed; do not generalize silent handling or recommend this source syntax."}
    output = HERE / "author-validation.json"
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
