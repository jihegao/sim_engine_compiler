"""Read-only acceptance replay of the OUT-delay counterexample."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var02-out-transfer-v1.0.0"
NATIVE = HERE / "runs/i02-var12-out-delay2-v100-ssh-20261002-01"
REPORT = HERE / "runs/i02-var12-depot-item-v100-ssh-20261002-01"
CONTROL_NATIVE = PARENT / "runs/i02-var02-out-v100-ssh-20261002-01"
CONTROL_REPORT = PARENT / "runs/i02-var02-item-results-v100-ssh-20261002-01"
SOURCE_SHA = "a9eec9544de1b9c52b6dcf0ecd826ccbe524dbaba383dc9e66e694571e42cfc5"
PARENT_SHA = "7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0"
SETTINGS_SHA = "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # The native default-report writer can leave trailing commas. Parse a
        # normalized copy while all evidence hashes continue to cover bytes.
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
    assert len(matches) == 1, (name, len(matches))
    cols = [c["name"] for c in matches[0]["columns"]]
    return [dict(zip(cols, row, strict=True)) for instance in matches[0]["instances"]
            for row in instance["rows"]]


def seals(folder: Path, closure: dict) -> bool:
    return (closure["error"] is None and closure["run_id"] == folder.name
            and sha(folder / "invocation.json") == closure["invocation_sha256"]
            and closure["source_hashes_before"] == closure["source_hashes_after"]
            and all((folder / name).stat().st_size == meta["bytes"]
                    and sha(folder / name) == meta["sha256"]
                    for name, meta in closure["raw"].items()))


def main() -> None:
    checks: list[dict] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    check("source_parent_pins", sha(HERE / "native-input.json") == SOURCE_SHA
          and sha(PARENT / "native-input.json") == PARENT_SHA
          and contract["source_sha256"] == SOURCE_SHA
          and contract["direct_parent"]["source_sha256"] == PARENT_SHA)
    check("exact_out_delta", diff["out_transfer_delta"] == [["TFDT", 0.0, 2.0]]
          and diff["changed_tables"] == ["ItemTransfer", "ProblemDescription"]
          and diff["unchanged_table_count"] == 30
          and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("selector", sha(HERE / "runs/report-settings/item-position-results.sxs") == SETTINGS_SHA)
    nc, rc = read(NATIVE / "closure.json"), read(REPORT / "closure.json")
    pc, prc = read(CONTROL_NATIVE / "closure.json"), read(CONTROL_REPORT / "closure.json")
    for name, folder, closure, count in (
        ("child_native", NATIVE, nc, 12), ("child_report", REPORT, rc, 2),
        ("parent_native", CONTROL_NATIVE, pc, 12), ("parent_report", CONTROL_REPORT, prc, 2),
    ):
        check(f"{name}_sealed", seals(folder, closure) and len(closure["raw"]) == count)
    check("native_source_pins", nc["source_hashes_before"]["input"] == SOURCE_SHA
          and nc["source_hashes_before"]["parent"] == PARENT_SHA
          and nc["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
    check("report_source_pins", rc["source_hashes_before"]["sxo"] == nc["raw"]["model.sxo"]["sha256"]
          and rc["source_hashes_before"]["settings"] == SETTINGS_SHA
          and rc["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
          and read(REPORT / "invocation.json")["source_closure_sha256"] == sha(NATIVE / "closure.json"))
    check("parent_source_pins", pc["source_hashes_before"]["input"] == PARENT_SHA
          and prc["source_hashes_before"]["sxo"] == pc["raw"]["model.sxo"]["sha256"])
    inv = read(NATIVE / "invocation.json")
    rinv = read(REPORT / "invocation.json")
    check("session_and_gui", inv["session_id"] == rinv["session_id"] == 0
          and inv["gui"]["pid"] == rinv["gui"]["pid"] == 13340
          and "sshd.exe" in inv["ssh_ancestor_names"] and "sshd.exe" in rinv["ssh_ancestor_names"])
    steps = read(NATIVE / "steps.json")
    check("five_native_steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"]
          and all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
    check("roundtrip", read(NATIVE / "roundtrip-validation.json")["passed"]
          and len(read(NATIVE / "roundtrip-validation.json")["populated_tables"]) == 22)
    check("conversion", "Input conversion completed. Errors: 0," in
          (NATIVE / "run.log").read_text(encoding="utf-8-sig"))
    check("selected_export", rc["exit_code"] == 0 and "Export completed!" in
          (REPORT / "report-export.log").read_text(encoding="utf-8-sig"))

    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    old_log = (CONTROL_NATIVE / "model.log").read_text(encoding="utf-8-sig")
    common = (
        "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
        "Time: 6  item transfer task 1 (OUT)  created",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
    )
    for i, event in enumerate(common):
        check(f"same_event_{i}", event in log and event in old_log)
    check("child_out_transfer_two_hours", "Time: 6  item transfer task 1 (OUT)  starts with 1 items, transfer time: 2" in log
          and "Time: 8  item transfer task 1 (OUT)  arrives with 1 items" in log)
    check("control_out_transfer_zero_hours", "Time: 6  item transfer task 1 (OUT)  starts with 1 items, transfer time: 0" in old_log
          and "Time: 6  item transfer task 1 (OUT)  arrives with 1 items" in old_log)
    check("single_out_arrival", log.count("item transfer task 1 (OUT)  arrives with 1 items") == 1)
    # The only physical-log difference is the OUT transfer's duration/arrival.
    def without_out_timing(text: str) -> list[str]:
        return [line for line in text.splitlines() if not
                ("item transfer task 1 (OUT)  starts with 1 items" in line
                 or "item transfer task 1 (OUT)  arrives with 1 items" in line)]
    check("all_other_log_lines_equal", without_out_timing(log) == without_out_timing(old_log))

    child, parent = read(REPORT / "item-report-raw.json"), read(CONTROL_REPORT / "item-report-raw.json")
    ctab = {t["name"]: t for t in child["report"]["tables"]}
    ptab = {t["name"]: t for t in parent["report"]["tables"]}
    check("all_selected_business_tables_equal", set(ctab) == set(ptab) and all(
          ctab[name] == ptab[name] for name in ctab if name != "ProblemDescription"))
    cr, pr = rows(child, "ItemResults"), rows(parent, "ItemResults")
    check("aligned_depot_grid", len(cr) == len(pr) == 72 and all(
          row["IID"] == "TEACH-LRU-01" and row["STID"] == "DEPOT-01"
          and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2
          for i, row in enumerate(cr)))
    check("depot_stock_timing", all(r["STSZ"] == r["STOHA"] == 1 for r in cr[:8])
          and all(r["STSZ"] == r["STOHA"] == 2 for r in cr[8:12])
          and all(r["STSZ"] == r["STOHA"] == 1 for r in cr[12:20])
          and cr[20]["STSZ"] == 1 and cr[20]["STOHA"] == 0
          and cr[20]["NDF"] == 1 and cr[-1]["STSZ"] == cr[-1]["STOHA"] == 1)
    check("zero_depot_backorders", all(r["NBO"] == 0 for r in cr))
    default_child, default_parent = read(NATIVE / "report-raw.json"), read(CONTROL_NATIVE / "report-raw.json")
    dt, pt = ({t["name"]: t for t in d["report"]["tables"]} for d in (default_child, default_parent))
    check("all_default_business_tables_equal", set(dt) == set(pt) and all(
          dt[name] == pt[name] for name in dt if name != "ProblemDescription"))
    result = {"schema": "simlox-i02-var12-out-delay-author-validation/v1",
              "variant_id": "I02.var12", "source_sha256": SOURCE_SHA,
              "native_run_id": NATIVE.name, "item_report_run_id": REPORT.name,
              "control_native_run_id": CONTROL_NATIVE.name, "control_item_report_run_id": CONTROL_REPORT.name,
              "checks": checks, "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks), "check_count": len(checks),
              "classification": "NO-GO for literal ignored TFDT: OUT transit/arrival is h6→h8 when TFDT2; depot stock departure and business reports match TFDT0.",
              "limits": "One available OUT following IN, one IID/depot, seed1 and TFDT0 versus 2; destination <OUTSIDE> not reported as item stock."}
    output = HERE / "author-validation.json"
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
