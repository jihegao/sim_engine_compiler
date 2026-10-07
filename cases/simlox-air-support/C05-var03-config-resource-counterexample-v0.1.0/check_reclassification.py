"""Read-only source-bound replay of one sealed C05.var03 failed crew arm."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from native_json import parse
from report_oracle import check_full_report, timed_blocks

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = HERE.parent / "C05-var03-config-resource-v1.0.2"
RUN = ORIGINAL / "runs/c05-var03-v102-crew-ssh-20261007-01"
CONTRACT_SHA = "50c4f36e8756e1120db7c7e627cfb4713f387b5105fa116ed9d2affdce75ff8e"
GO_SHA = "aef173ea82dcacb2b581d7256a58a28390d6ad0c58e30851babd57ae4dd36cd5"


class Gate:
    def __init__(self):
        self.checks = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(label)


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def matches(path: Path, pin: dict) -> bool:
    return identity(path) == {key: pin[key] for key in ("bytes", "sha256")}


def table_map(doc: dict) -> dict:
    output = {}
    for table in doc["model"]["tables"]:
        assert table["name"] not in output
        output[table["name"]] = table
    return output


def table_rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def verify_sources(g: Gate, contract: dict) -> tuple[dict, dict]:
    g.check(identity(HERE / "contract.json")["sha256"] == CONTRACT_SHA, "counterexample contract identity")
    g.check(identity(HERE / "review/independent-contract-go-2026-10-07.md")["sha256"] == GO_SHA,
            "independent contract GO identity")
    for name, pin in contract["pins"].items():
        g.check(matches(ROOT / pin["path"], pin), f"direct pin {name}")
    original = json.loads((ORIGINAL / "contract.json").read_text(encoding="utf-8-sig"))
    manifest = json.loads((ORIGINAL / "prelaunch-manifest.json").read_text(encoding="utf-8-sig"))
    g.check(len(manifest["source_files"]) == 77, "77 original source entries")
    for pin in manifest["source_files"]:
        g.check(matches(Path(pin["path"]), pin), f"original source {pin['key']}")
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    g.check(closure["run_id"] == contract["source_run_id"] == invocation["run_id"], "original crew run ID")
    g.check(closure["invocation_sha256"] == contract["pins"]["crew_invocation"]["sha256"], "invocation linkage")
    g.check(len(closure["raw"]) == 13, "13 original closure raw seals")
    for name, pin in closure["raw"].items():
        g.check(matches(RUN / name, pin), f"original raw {name}")
    failure = json.loads((RUN / "failure-seal.json").read_text(encoding="utf-8-sig"))
    g.check(failure["publication_state"] == "excluded" and
            failure["error"] == "check_behavior rejected native result", "original failure preserved")
    g.check(len(failure["files"]) == 15, "15 failure-seal entries")
    for name, pin in failure["files"].items():
        g.check(matches(RUN / name, pin), f"failure seal {name}")
    for pin in manifest["source_files"]:
        g.check(closure["source_hashes_before"].get(pin["key"]) == pin["sha256"] and
                closure["source_hashes_after"].get(pin["key"]) == pin["sha256"],
                f"original before/after {pin['key']}")
    g.check(closure["error"] == "check_behavior rejected native result", "closure failed behavior check")
    g.check(closure["approval_sha256"] == identity(ORIGINAL / "review/independent-prelaunch-go.json")["sha256"],
            "approved exact-file source")
    g.check(closure["approved_preflight_sha256"] ==
            identity(ORIGINAL / "review/preflight-ssh0-20261007T012658707Z.json")["sha256"],
            "approved SSH0 preflight")
    g.check(not (ORIGINAL / "runs/c05-var03-v102-radio-ssh-20261007-01").exists(), "radio arm absent")
    for key, accepted in original["accepted_native_runs"].items():
        path = Path(accepted["path"])
        g.check(matches(path / "closure.json", accepted["closure"]), f"accepted {key} closure")
        g.check(matches(path / "invocation.json", accepted["invocation"]), f"accepted {key} invocation")
        raw = json.loads((path / "closure.json").read_text(encoding="utf-8-sig"))["raw"]
        g.check(raw == accepted["raw"], f"accepted {key} raw map")
        for name, pin in raw.items():
            g.check(matches(path / name, pin), f"accepted {key}/{name}")
    published_count = 0
    for accepted in original["accepted_source_pins"].values():
        for relative, pins in accepted["files"].items():
            local = HERE.parent / accepted["package"] / relative
            g.check(matches(local, pins["local"]), f"accepted local {relative}")
            git_path = local.relative_to(ROOT).as_posix()
            content = subprocess.run(["git", "show", f"{original['base_commit']}:{git_path}"], cwd=ROOT,
                                     capture_output=True, check=True).stdout
            g.check({"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()} == pins["published_git"],
                    f"accepted published Git {git_path}")
            published_count += 1
    g.check(published_count == 23, "23 accepted local/Git source identities")
    return original, closure


def verify_steps_and_source(g: Gate, original: dict) -> None:
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    g.check([s["name"] for s in steps] ==
            ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"],
            "six ordered steps")
    g.check(all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps[:5]) and
            steps[5]["status"] == "failed" and steps[5]["exit_code"] == 1,
            "five completions then behavior failure")
    for step in (steps[0], steps[1], steps[3], steps[4]):
        g.check(step["child_session_id"] == 0 and step["gui_preserved"] is True,
                f"native {step['name']} SSH0/protected GUI")
    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    g.check(invocation["session_id"] == 0 and invocation["gui"] ==
            {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True},
            "approved SSH0/GUI identity")
    g.check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "guarded mutex")
    g.check(invocation["input_sha256"] == identity(ORIGINAL / "crew-input.json")["sha256"], "input copy pin")
    source = parse(RUN / "input.json")
    export = parse(RUN / "roundtrip-raw.json")
    before, after = table_map(source), table_map(export)
    g.check(len(before) == len(after) == 33 and set(before) == set(after), "33-table roundtrip topology")
    row_containing = 0
    for name, table in before.items():
        native = after[name]
        g.check(table["columns"] == native["columns"], f"{name} column metadata")
        source_instances = [(i.get("instance_name"), i["rows"]) for i in table["instances"]]
        native_instances = [(i.get("instance_name"), i["rows"]) for i in native["instances"]]
        g.check(sorted(n for n, _ in source_instances) == sorted(n for n, _ in native_instances),
                f"{name} instance names")
        if any(rows for _, rows in source_instances):
            row_containing += 1
            g.check(source_instances == native_instances, f"{name} exact authored rows")
        else:
            g.check(all(v is None for row in table_rows(native) for v in row),
                    f"{name} native placeholder remains all null")
    g.check(row_containing == 24, "24 authored row-containing tables")
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    g.check(roundtrip["passed"] is True and roundtrip["authored_row_tables"] == 24,
            "original authored roundtrip PASS")
    parent = parse(HERE.parent / "A16-two-config-reconfiguration-v1.0.0/native-input.json")
    diff = json.loads((ORIGINAL / "exact-diff.json").read_text(encoding="utf-8-sig"))
    parent_tables = table_map(parent)
    crew_tables = table_map(source)
    g.check(set(diff["parent_to_arm"]["crew"]) ==
            {"ProblemDescription", "SystemDeployment", "MissionType", "OperationProfile",
             "MissionSystem", "Resource", "ResourceAllocation", "MissionResource"},
            "eight declared A16-to-crew table changes")
    for name, table in crew_tables.items():
        claim = diff["parent_to_arm"]["crew"].get(name)
        if claim is None:
            g.check(table == parent_tables[name], f"unchanged A16 table {name}")
        else:
            g.check(table == claim["after"] and parent_tables.get(name) == claim["before"],
                    f"exact A16-to-crew table {name}")
    rows = {name: table_rows(table) for name, table in crew_tables.items()}
    g.check(len(rows["MissionType"]) == 1 and rows["MissionType"][0][2:4] == [2, 2],
            "two-aircraft shared mission NOS/MNOS")
    g.check(rows["MissionResource"] == [
        ["SHARED-CONFIG-MISSION", "TEACH-CONF-A", "MISSION-CREW", 1, None],
        ["SHARED-CONFIG-MISSION", "TEACH-CONF-B", "MISSION-CREW", 1, None]],
        "A/B source each requires crew one")
    g.check(rows["ResourceAllocation"] == [["AIR_BASIC", "MISSION-CREW", "BASE-01", 2, None],
                                                ["AIR_BASIC", "MISSION-RADIO", "BASE-01", 0, None]],
            "crew capacity two and radio zero")
    radio = parse(ORIGINAL / "radio-input.json")
    radio_tables = table_map(radio)
    g.check({name for name in set(crew_tables) | set(radio_tables)
             if crew_tables.get(name) != radio_tables.get(name)} ==
            {"ProblemDescription", "MissionResource"}, "original pair table isolation")
    author = json.loads((RUN / "author-validation.json").read_text(encoding="utf-8-sig"))
    g.check(author["decision"] == "NO_GO" and author["checks"] == 1 and
            author["failures"] == ["AssertionError: "], "original author rejection preserved")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
    g.check("Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in converter,
            "strict native converter 0/4/0")
    warning_lines = re.findall(r"rec\s+(\d+):\s*\(warning\s*#(\d+)\)\s*(.*)", converter, re.I)
    g.check([(int(n), code) for n, code, _ in warning_lines] ==
            [(1, "108"), (1, "2053"), (2, "2053"), (3, "2053")],
            "exact contextual warning order/code/record")


def check_trace(g: Gate, blocks: list[tuple[float, str]]) -> None:
    def hits(token: str, hour: float | None = None) -> list[str]:
        return [body for when, body in blocks if token in body and
                (hour is None or abs(when - hour) <= 1e-4)]
    g.check(len(hits("mission ordered: SHARED-CONFIG-MISSION", 7)) == 1,
            "one shared mission ordered h7")
    for ident in ("0", "1"):
        g.check(len(hits(f"mission allocates system: <TEACH-AIR-01,{ident}>", 7)) == 1,
                f"distinct base aircraft {ident} allocation")
        fit = lambda suffix, hour: [body for when, body in blocks
                                    if abs(when - hour) <= 1e-4 and
                                    re.match(rf"^system reconfig fit task {ident} on <TEACH-AIR-01,{ident}> {suffix}(?:\s|$)", body)]
        g.check(len(fit("started", 7)) == 1 and
                len(fit("completed", 7.33333)) == 1,
                f"base aircraft {ident} fit work")
    for suffix, item in (("A", "0"), ("B", "2")):
        g.check(len(hits(f"<TEACH-LRU-{suffix},0,BASE-01,0> Stock initiated", 0)) == 1 and
                len(hits(f"Stock at: <TEACH-LRU-{suffix},0,BASE-01,0> Level: 1 Items:<TEACH-LRU-{suffix},0,{item}>", 0)) == 1,
                f"opening {suffix} physical ID {item}")
        g.check(len(hits(f"<TEACH-LRU-{suffix},0,BASE-01,0> Reconfiguration item demand arrives from pos <TEACH-AIR-01,BASE-01,0>", 7)) == 1,
                f"{suffix} demand position suffix 0 as printed")
        g.check(len(hits(f"Take replacement item <TEACH-LRU-{suffix},0,{item}> from stock", 7)) == 1 and
                len(hits(f"Stock at: <TEACH-LRU-{suffix},0,BASE-01,0> Level: 0 Items:", 7)) == 1,
                f"{suffix} physical stock take to zero")
        g.check(not hits(f"Put back replacement item <TEACH-LRU-{suffix}"),
                f"no {suffix} physical stock return")
    g.check(len(hits("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>", 0)) == 1,
            "unchanged base LRU opening physical ID1")
    g.check(len(hits("Availability test on  <MISSION-CREW at <BASE-01,0>> request for: 1 OK", 7)) == 2,
            "two h7 one-unit crew availability tests")
    g.check(len(hits("<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1", 7)) == 2,
            "two transient h7 crew bookings")
    g.check(len(hits("<MISSION-CREW at <BASE-01,0>> deallocated from  mission assigned: 1", 7)) == 2,
            "two same-hour assignment releases")
    for suffix, ident in (("A", "0"), ("B", "1")):
        g.check(len(hits(f"<TEACH-CONF-{suffix},{ident}> preparation started", 7.33333)) == 1 and
                len(hits(f"<TEACH-CONF-{suffix},{ident}> preparation ended", 7.33333)) == 1,
                f"configured {suffix}{ident} preparation")
    launches = hits("mission starting, duration: 2", 8)
    g.check(len(launches) == 1 and all(token in launches[0] for token in
            ("<TEACH-CONF-A,0>", "<TEACH-CONF-B,1>",
             "<TEACH-CONF-A,0>[MISSION-CREW 0]", "<TEACH-CONF-B,1>[MISSION-CREW 0]")),
            "h8 A0/B1 launch with crew zero each")
    for token, hour in (("task starting:", 8.5), ("task completed:", 9.5),
                        ("mission completed:", 10)):
        found = hits(token, hour)
        g.check(len(found) == 1 and all(x in found[0] for x in
                ("<TEACH-CONF-A,0>[MISSION-CREW 0]", "<TEACH-CONF-B,1>[MISSION-CREW 0]")),
                f"{token} A/B crew zero")
    g.check(len(hits("mission success:", 10)) == 1 and
            len(hits("mission completed:", 10)) == 1, "h10 success/completion")
    g.check(len(hits("<MISSION-CREW at <BASE-01,0>> deallocated from  mission operation: 0", 10)) == 2,
            "two h10 zero-quantity operation releases")
    g.check(len(hits("<TEACH-CONF-A,BASE-01,0> System arrives <TEACH-CONF-A,0>", 10)) == 1 and
            len(hits("<TEACH-CONF-B,BASE-01,0> System arrives <TEACH-CONF-B,1>", 10)) == 1,
            "configured A/B aircraft return h10")
    g.check(len(hits("systems ready: 2 :<TEACH-CONF-A,0>,<TEACH-CONF-B,1>", 10)) == 1,
            "two configured aircraft ready h10")
    g.check(len(hits("mission ordered:")) == 1 and not hits("mission cancelled:"),
            "no second mission or cancellation")
    g.check(not hits("Replacement item arrives") and not hits("Put back replacement item"),
            "no item returns by h36")
    g.check(not hits("backorder") and not hits("Backorder"), "no backorder")
    g.check(len(hits("resource shift 0 ended", 36)) == 1 and
            len(hits("resource shift 1 ended", 36)) == 1, "terminal resource shift boundary h36")


def audit() -> dict:
    g = Gate()
    try:
        contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
        original, _ = verify_sources(g, contract)
        verify_steps_and_source(g, original)
        check_trace(g, timed_blocks(RUN / "model.log"))
        cells = check_full_report(g, RUN / "report-raw.json", RUN / "model.log", "crew")
        g.check(cells == 5210, "all 5210 native report cells independently compared")
        report = parse(RUN / "report-raw.json")
        resource = next(t for t in report["report"]["tables"] if t["name"] == "ResourceResults")
        columns = [c["name"] for c in resource["columns"]]
        for index, row in enumerate(resource["instances"][0]["rows"]):
            g.check(all(row[columns.index(n)] == 0 for n in ("NRMA", "NRMO", "NRUM", "NRW")) and
                    all(row[columns.index(n)] == 2 for n in ("NR", "NRA", "NRN")),
                    f"resource bin {index} zero held crew/capacity two")
        g.check(contract["original_pair_decision"] == "NO_GO_FROZEN_PAIR" and
                contract["radio_arm"] == "not_started_not_tested" and contract["new_native_runs"] == 0,
                "scope retains original failed pair and no new run")
    except Exception as exc:
        g.check(False, f"{type(exc).__name__}: {exc}")
        cells = 0
    return {"schema": "c05-var03-counterexample-v010-author-replay/v1",
            "decision": "GO_BOUNDED" if not g.failures else "NO_GO",
            "checks": g.checks, "passed": g.checks - len(g.failures), "failures": g.failures,
            "report_cells_compared": cells,
            "original_pair_decision": "NO_GO_FROZEN_PAIR", "radio_arm": "not_started_not_tested",
            "scope": "one sealed crew-arm retrospective counterexample; no native rerun or general inheritance claim"}


if __name__ == "__main__":
    verdict = audit()
    print(json.dumps(verdict, indent=2) + "\n", end="")
    sys.exit(0 if verdict["decision"] == "GO_BOUNDED" else 1)
