"""Independent read-only replay of the sealed E02.var03 h11 native run.

Uses Python standard library only. Does not import or invoke either author validator.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


REVIEW = Path(__file__).resolve().parent
CASE = REVIEW.parent
ROOT = CASE.parent
CHILD = ROOT / "E02-var03-terminal-repair-v1.0.0"
RUN_ID = "e02-var03-terminal-repair-v100-ssh-20261006-01"
RUN = CHILD / "runs" / RUN_ID
PARENT = ROOT / "E02-zero-stock-local-backorder-v1.0.0"
PARENT_RUN = PARENT / "runs" / "e02-v100-ssh-20260929-01"
E01 = ROOT / "E01-local-spare-explicit-replacement-v1.0.0"
E05 = ROOT / "E05-local-repair-reissue-v1.0.0"
EXPECTED = {
    "review_contract": "9fbd831d64d839b9f27762a58b85fde58c6f8e54717b04f6318b4048f850b587",
    "child_contract": "1579273272ec3ac62b3f1478e9eaa0de06bb452fab17bf6042e71b08b587498c",
    "child_input": "6d2b20e4ddc92bd5dc0894537152e12dbb3598c1d725c18eb025d4c19b14f28e",
    "child_runner": "19b94792a201e15447976c60d634a1ea853cf8cb51f1966df3623cef497dbf33",
    "child_closure": "6ab8105d82a1ef154bfb50307cdaeb6b2f9b45a7c44353e389e048662f1350c5",
    "parent_input": "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd",
    "parent_signoff": "c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6",
    "parent_closure": "a8ec55f67c710be700cb4dc3663c7f79041d69c2021edb9924c1d0daddda04ef",
    "e01_signoff": "c52dd13ba1f6fab05032ebf80597940099241bb652f2c3a73a26edbf059c1110",
    "e05_signoff": "e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f",
    "failed_author_replay": "8d8a0b20e226d1039036a0b7c88ace17024e6f1ca4ec9bc75173d0bda5e1ae72",
    "repaired_author_validator": "03dc3a9cab28b5982474baf89fe1aff8d7cf641b57aca2ef0589786c2ecf7a61",
    "repaired_author_replay": "ee8d4bfefe5b59e80e986f9e429974190261209d3daa9c7487dd411b75a215ce",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Parse native JSON with only commas before closing delimiters removed."""
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        chars: list[str] = []
        quoted = False
        escaped = False
        for pos, char in enumerate(text):
            if quoted:
                chars.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                chars.append(char)
            elif char == "," and text[pos + 1 :].lstrip().startswith(("}", "]")):
                continue
            else:
                chars.append(char)
        return json.loads("".join(chars))


def table_map(document: dict, section: str) -> dict:
    result = {}
    for table in document[section]["tables"]:
        if table["name"] in result:
            raise ValueError(f"duplicate table {table['name']}")
        result[table["name"]] = table
    return result


def rows(document: dict, section: str, name: str) -> list[dict]:
    table = table_map(document, section)[name]
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row, strict=True))
            for instance in table["instances"] for row in instance["rows"]]


def authored_tables(document: dict) -> dict:
    return {name: table for name, table in table_map(document, "model").items()
            if any(instance["rows"] for instance in table["instances"])}


def replay() -> dict:
    failures: list[str] = []
    count = 0

    def check(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    paths = {
        "review_contract": CASE / "contract.json",
        "child_contract": CHILD / "contract.json",
        "child_input": CHILD / "native-input.json",
        "child_runner": CHILD / "run_native_ssh.ps1",
        "child_closure": RUN / "closure.json",
        "parent_input": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "parent_closure": PARENT_RUN / "closure.json",
        "e01_signoff": E01 / "cli-scope-signoff-2026-09-29.md",
        "e05_signoff": E05 / "cli-scope-signoff-2026-09-29.md",
        "failed_author_replay": REVIEW / "author-replay-v100-failed.json",
        "repaired_author_validator": CASE / "validate_native.py",
        "repaired_author_replay": REVIEW / "author-replay-v101.json",
    }
    for name, path in paths.items():
        check(f"pin {name}", path.is_file() and digest(path) == EXPECTED[name])

    contract = read_json(CASE / "contract.json")
    check("review is read-only successor", contract["version"] == "1.0.1"
          and contract["native_execution"].startswith("none")
          and contract["native_run_id"] == RUN_ID
          and contract["native_closure_sha256"] == EXPECTED["child_closure"])
    check("prior failure preserved", read_json(paths["failed_author_replay"])["failures"] == [
        "prefix item DIRP task 1 on <TEACH-LRU-01,0,0> s", "no systems ready: 1"])
    repaired_replay = read_json(paths["repaired_author_replay"])
    check("repaired author replay sealed", repaired_replay["passed"] is True
          and repaired_replay["checks"] == 260 and repaired_replay["failures"] == [])

    child_closure, parent_closure = read_json(RUN / "closure.json"), read_json(PARENT_RUN / "closure.json")
    check("child closure identity", child_closure["run_id"] == RUN_ID and child_closure["error"] is None)
    check("parent closure success", parent_closure["error"] is None
          and parent_closure["source_hashes_before"] == parent_closure["source_hashes_after"])
    for label, base, closure, expected_count in (
        ("child", RUN, child_closure, 13), ("parent", PARENT_RUN, parent_closure, 12)
    ):
        check(f"{label} raw count", len(closure["raw"]) == expected_count)
        for name, record in sorted(closure["raw"].items()):
            path = base / name
            check(f"{label} raw {name}", path.is_file() and path.stat().st_size == record["bytes"]
                  and digest(path) == record["sha256"])

    invocation = read_json(RUN / "invocation.json")
    check("invocation seal", digest(RUN / "invocation.json") == child_closure["invocation_sha256"])
    check("SSH0 and protected GUI", invocation["session_id"] == 0
          and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["gui"] == {"pid": 13340, "session_id": 1,
                                     "start_utc": "2026-09-28T10:09:56.8261381Z"})
    check("host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    before = invocation["source_hashes_before"]
    check("source stability", before == child_closure["source_hashes_before"]
          == child_closure["source_hashes_after"])
    for key, path in {
        "contract": CHILD / "contract.json", "input": CHILD / "native-input.json",
        "builder": CHILD / "build.py", "source_checker": CHILD / "check_source.py",
        "roundtrip_checker": CHILD / "check_roundtrip.py",
        "author_validator": CHILD / "validate_native.py", "runner": CHILD / "run_native_ssh.ps1",
        "contract_review": ROOT / "E02-var03-terminal-repair-v0.1.1" / "review" / "independent-contract-go-2026-10-06.md",
        "shared_validator_module": ROOT / "tools" / "validate_native.py",
        "native_binding_module": ROOT / "tools" / "native_binding.py",
        "parent_input": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "parent_closure": PARENT_RUN / "closure.json",
        "e01_signoff": E01 / "cli-scope-signoff-2026-09-29.md",
        "e05_signoff": E05 / "cli-scope-signoff-2026-09-29.md",
        "exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
    }.items():
        check(f"recorded source {key}", before[key] == digest(path))
    check("copied input", digest(RUN / "input.json") == EXPECTED["child_input"])

    steps = read_json(RUN / "steps.json")
    check("four native steps", [step["name"] for step in steps] == ["import", "export", "calc", "report"])
    for step in steps:
        check(f"guarded {step['name']}", step["status"] == "completed"
              and step["exit_code"] == 0 and step["gui_preserved"] is True)
    outcome = read_json(RUN / "outcome.json")
    check("native completion", outcome["error"] is None and outcome["roundtrip"] == "exact"
          and outcome["result"] == "native_run_completed"
          and outcome["converter_summary"] == [0, 1, 0]
          and outcome["warning_codes"] == ["108"])

    source = native_json(RUN / "input.json")
    exported = native_json(RUN / "roundtrip-raw.json")
    authored = authored_tables(source)
    native = table_map(exported, "model")
    check("20 authored tables", len(authored) == 20)
    for name, table in sorted(authored.items()):
        # The native export may add unrelated default tables; every authored
        # table's columns and instance rows must stay identical.
        candidate = native.get(name, {})
        check(f"roundtrip {name}", candidate.get("columns") == table["columns"]
              and candidate.get("instances") == table["instances"])
    source_parent = native_json(PARENT / "native-input.json")
    changes = []
    for name, table in table_map(source_parent, "model").items():
        other = table_map(source, "model")[name]
        if table != other:
            changes.append(name)
    check("three changed tables", changes == ["Control", "OperationProfile", "ResultCollection"])
    control = rows(source, "model", "Control")
    result = rows(source, "model", "ResultCollection")
    operation = rows(source, "model", "OperationProfile")
    check("h11 source fields", control[0]["SIMPE"] == control[0]["RCEND"] == 11
          and len(result) == 2 and all(r["RCEND"] == 11 for r in result))
    check("future missions removed", len(operation) == 1 and operation[0]["STIM"] == 8)

    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("converter exact", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", converter) == [("0", "1", "0")]
          and re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
    check("valid native output", (RUN / "model.sxo").stat().st_size > 1000)
    check("import and export completed", "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig", errors="replace")
          and "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig", errors="replace"))

    child_lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    parent_lines = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    cutoff = next(i for i, line in enumerate(parent_lines)
                  if line.startswith("Time: ") and float(line.split()[1]) >= 11)
    check("native h11 log header", child_lines[:2] == ["SIMLOX LOG FILE", "11"])
    check("exact pre-h11 log prefix", child_lines[2:] == parent_lines[2:cutoff])
    events = [(float(m.group(1)), m.group(2)) for line in child_lines
              if (m := re.match(r"Time: ([0-9.]+) (.*)", line))]
    check("49 event lines and no post-horizon event", len(events) == 49
          and all(time < 11 for time, _ in events))
    def event_time(fragment: str) -> list[float]:
        return [time for time, text in events if fragment in text]
    check("failure and abort", event_time("critical random failure added") == [9.8829]
          and event_time("mission aborted:") == [9.8829])
    check("backorder and ID0 demand", event_time("Backorder added") == [10]
          and event_time("Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,0>") == [10])
    check("physical removal", event_time("remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed") == [10.1667])
    dirp_start = [time for time, text in events if text.strip() == "item DIRP task 1 on <TEACH-LRU-01,0,0> started"]
    dirp_finish = [time for time, text in events if text.strip() == "item DIRP task 1 on <TEACH-LRU-01,0,0> completed"]
    check("ID0 direct repair pending", dirp_start == [10.1667]
          and event_time("direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,0> starts performing") == [10.1667]
          and not dirp_finish)
    check("fit waits without performance", event_time("fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem") == [10.1667]
          and not event_time("fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing"))
    check("BO remains open", any("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 1" in line for line in child_lines)
          and not event_time("Backorder removed") and not event_time("Finished repair of item"))
    check("no post-failure system recovery", not [time for time, text in events
          if time > 9.8829 and "systems ready: 1" in text])

    child_report = native_json(RUN / "report-raw.json")
    parent_report = native_json(PARENT_RUN / "report-raw.json")
    exceptions = {
        "SystemResults": {20: {"SYDT", "NSYDT"}},
        "StockTotalResults": {20: {"WT", "WTT", "WTS", "NWT"}},
    }
    for name in ("SystemResults", "StockTotalResults"):
        child_rows = rows(child_report, "report", name)
        parent_rows = rows(parent_report, "report", name)
        check(f"{name} 22 bins", len(child_rows) == 22 and len(parent_rows) == 72)
        for i, row in enumerate(child_rows):
            check(f"{name} bin {i} interval", row["STINT"] == i / 2
                  and row["ETINT"] == (i + 1) / 2)
            changed = {key for key in row if row[key] != parent_rows[i][key]}
            check(f"{name} bin {i} parent comparison", changed == exceptions[name].get(i, set()))
    system = rows(child_report, "report", "SystemResults")
    stock = rows(child_report, "report", "StockTotalResults")
    check("terminal aircraft unavailable", system[-1]["NSYRY"] == 0
          and system[-1]["NSYUA"] == 1 and system[-1]["NSYWI"] == 1)
    check("terminal one backorder", stock[-1]["NBO"] == 1 and stock[-1]["PNB"] == 0)
    check("demand aggregate", sum(row["NDF"] for row in stock) == 1)
    return {"schema": "simlox-e02-var03-independent-replay/v1", "run_id": RUN_ID,
            "verdict": "GO_BOUNDED" if not failures else "NO_GO", "checks": count,
            "failures": failures,
            "scope": "one seed-1 h11 CLI terminal repair/backorder observation; no installed-ID or post-horizon inference",
            "report_prefix_exception": "bin 20 finalization: System SYDT/NSYDT and StockTotal WT/WTT/WTS/NWT"}


if __name__ == "__main__":
    try:
        result = replay()
    except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration) as error:
        result = {"schema": "simlox-e02-var03-independent-replay/v1", "run_id": RUN_ID,
                  "verdict": "NO_GO", "checks": 0,
                  "failures": [f"replay exception: {type(error).__name__}: {error}"]}
    print(json.dumps(result, sort_keys=True, indent=2))
    sys.exit(0 if result["verdict"] == "GO_BOUNDED" else 1)
