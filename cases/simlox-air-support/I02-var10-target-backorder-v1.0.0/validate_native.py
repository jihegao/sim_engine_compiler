"""Read-only author replay for the I02.var10 target backorder pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0"
RUNS = HERE / "runs"
ARMS = ("early", "late")
STATIONS = ("base", "depot")
INPUT_SHA = {"early": "ed117928b3e82c8194d0d7f56fc5fe43d0fdbf0f71c400813ad67644ae0d4e84",
             "late": "5f342138a74e6453822b17684741af13ef3e5aa694d036455dfdcce53cd666f8"}
PARENT_SHA = "4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560"
SELECTOR_SHA = {"base": "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b",
                "depot": "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"}
SELECTOR_NAME = {"base": "base-item-position-results.sxs", "depot": "item-position-results.sxs"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Normalize only a parser copy of the native writer's trailing commas.
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


def table(doc: dict, name: str) -> list[dict]:
    found = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(found) == 1, (name, len(found))
    fields = [c["name"] for c in found[0]["columns"]]
    return [dict(zip(fields, row, strict=True)) for instance in found[0]["instances"]
            for row in instance["rows"]]


def sealed(folder: Path, expected_count: int) -> bool:
    inv, closed = read(folder / "invocation.json"), read(folder / "closure.json")
    return (closed["error"] is None and closed["run_id"] == folder.name
            and closed["invocation_sha256"] == sha(folder / "invocation.json")
            and closed["source_hashes_before"] == closed["source_hashes_after"] == inv["source_hashes_before"]
            and len(closed["raw"]) == expected_count
            and all((folder / name).stat().st_size == meta["bytes"]
                    and sha(folder / name) == meta["sha256"] for name, meta in closed["raw"].items()))


def main() -> None:
    checks: list[dict] = []

    def check(name: str, passed: bool) -> None:
        checks.append({"name": name, "passed": bool(passed)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    check("parent_source", sha(PARENT / "native-input.json") == PARENT_SHA
          and contract["direct_parent"]["source_sha256"] == PARENT_SHA)
    check("arm_sources", all(sha(HERE / f"{arm}-input.json") == INPUT_SHA[arm]
          == contract["arm_sha256"][arm] for arm in ARMS))
    check("source_diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
          and diff["matched_pair_delta"] == [["TFTIME", 9.0, 11.0]]
          and diff["changed_tables_per_arm"] == ["ItemTransfer", "ProblemDescription"]
          and diff["unchanged_table_count"] == 30)
    for station in STATIONS:
        check(f"selector_{station}", sha(RUNS / "report-settings" / SELECTOR_NAME[station])
              == SELECTOR_SHA[station])

    native, reports, logs, docs, rows = {}, {}, {}, {}, {}
    for arm in ARMS:
        folder = RUNS / f"i02-var10-{arm}-v100-ssh-20261002-01"
        native[arm] = folder
        check(f"native_{arm}_seals", sealed(folder, 12))
        inv, closed = read(folder / "invocation.json"), read(folder / "closure.json")
        check(f"native_{arm}_pins", closed["source_hashes_before"]["input"] == INPUT_SHA[arm]
              and closed["source_hashes_before"]["parent"] == PARENT_SHA
              and closed["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1")
              and inv["variant"] == arm)
        check(f"native_{arm}_guard", inv["session_id"] == 0 and inv["gui"]["pid"] == 13340
              and "sshd.exe" in inv["ssh_ancestor_names"]
              and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        steps = read(folder / "steps.json")
        check(f"native_{arm}_steps", [s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"]
              and all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
        rt = read(folder / "roundtrip-validation.json")
        check(f"native_{arm}_roundtrip", rt["passed"] and rt["variant"] == arm
              and len(rt["populated_tables"]) == 22)
        check(f"native_{arm}_conversion", "Input conversion completed. Errors: 0," in
              (folder / "run.log").read_text(encoding="utf-8-sig"))
        logs[arm] = (folder / "model.log").read_text(encoding="utf-8-sig")
        docs[arm] = {}
        rows[arm] = {}
        reports[arm] = {}
        for station in STATIONS:
            target = RUNS / f"i02-var10-{arm}-{station}-item-v100-ssh-20261002-01"
            reports[arm][station] = target
            check(f"report_{arm}_{station}_seals", sealed(target, 2))
            ri, rc = read(target / "invocation.json"), read(target / "closure.json")
            check(f"report_{arm}_{station}_pins", ri["variant"] == arm
                  and ri["station"] == station
                  and ri["source_closure_sha256"] == sha(folder / "closure.json")
                  and rc["source_hashes_before"]["sxo"] == closed["raw"]["model.sxo"]["sha256"]
                  and rc["source_hashes_before"]["settings"] == SELECTOR_SHA[station]
                  and rc["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1"))
            check(f"report_{arm}_{station}_export", rc["exit_code"] == 0
                  and "Export completed!" in (target / "report-export.log").read_text(encoding="utf-8-sig"))
            docs[arm][station] = read(target / "item-report-raw.json")
            rows[arm][station] = table(docs[arm][station], "ItemResults")
            expected_stid = "BASE-01" if station == "base" else "DEPOT-01"
            check(f"grid_{arm}_{station}", len(rows[arm][station]) == 72 and all(
                  r["IID"] == "TEACH-LRU-01" and r["STID"] == expected_stid
                  and r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2
                  for i, r in enumerate(rows[arm][station])))

    early, late = logs["early"], logs["late"]
    for arm, hour in (("early", 9), ("late", 11)):
        log = logs[arm]
        check(f"physical_{arm}_in", "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in log)
        check(f"physical_{arm}_between", f"Time: {hour}  item transfer task 1 (BETWEEN)  arrives with 1 items" in log)
    check("early_no_target_backorder", "Time: 9 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in early
          and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in early
          and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" not in early)
    check("late_target_backorder", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in late
          and "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1" in late)
    check("late_transfer_serves_backorder", "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>" in late
          and "Time: 11  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,1>" in late)
    check("late_ordinary_arrival_stocks", "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in late
          and "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock" in late)
    check("early_ordinary_arrival_stocks", "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>" in early
          and "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in early)
    check("readiness", "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in early
          and "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in late)

    eb, lb = rows["early"]["base"], rows["late"]["base"]
    ed, ld = rows["early"]["depot"], rows["late"]["depot"]
    check("early_base_pre_demand", eb[18]["STSZ"] == eb[18]["STOHA"] == 1
          and eb[20]["NBO"] == 0 and eb[20]["STOHA"] == 0)
    check("late_base_target_bo_bins", all(lb[i]["NBO"] == 1 and lb[i]["STSZ"] == lb[i]["STOHA"] == 0
          for i in (20, 21)))
    check("late_base_receipt_direct_to_bo", lb[22]["NBO"] == 0 and lb[22]["STSZ"] == 1
          and lb[22]["STOHA"] == 0 and lb[23]["STOHA"] == 0)
    check("late_base_ordinary_stock", lb[24]["STSZ"] == lb[24]["STOHA"] == 1)
    check("depot_sends_at_scheduled_time", ed[18]["STSZ"] == ed[18]["STOHA"] == 1
          and ld[18]["STSZ"] == ld[18]["STOHA"] == 2
          and ld[22]["STSZ"] == 1 and ld[22]["STOHA"] == 0)
    check("terminal_station_stock", all(rows[arm][station][-1]["NBO"] == 0
          and rows[arm][station][-1]["STSZ"] == rows[arm][station][-1]["STOHA"] == 1
          for arm in ARMS for station in STATIONS))
    for name in ("ResultSummary", "MissionResults", "MissionResultsTotal",
                 "FixedMissionResults", "FixedMissionResultsTotal"):
        check(f"same_{name}", table(docs["early"]["base"], name)
              == table(docs["late"]["base"], name))
    check("selected_system_difference", table(docs["early"]["base"], "SystemResults")
          != table(docs["late"]["base"], "SystemResults"))
    check("item_total_average_not_terminal", table(docs["late"]["base"], "ItemResultsTotal")[0]["STOHA"] < 1
          and lb[-1]["STOHA"] == 1)
    result = {"schema": "simlox-i02-var10-target-backorder-author-validation/v1",
              "case_id": "I02", "variant_id": "I02.var10",
              "arm_sha256": INPUT_SHA, "checks": checks,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks), "check_count": len(checks),
              "claim": "At h11 a scheduled BETWEEN item arrives at BASE-01 with an ordinary h10 backorder and goes directly to its waiting aircraft; EARLY h9 arrival precedes demand and stocks BASE-01.",
              "limits": "One unit/IID, h9 versus h11, zero transfer duration and seed1; transfer timing and ordinary response are linked, so no general priority law."}
    output = HERE / "author-validation.json"
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
