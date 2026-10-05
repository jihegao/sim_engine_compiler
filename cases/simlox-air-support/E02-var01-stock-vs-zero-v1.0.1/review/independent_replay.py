"""Independent, read-only E02.var01 comparison of sealed E01 and E02 runs.

This script uses only Python's standard library and does not import author code.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
CONTRACT_SHA = "e7ddeeab754851d3fe5f18edb1f52d7ee98e875c0e1e57a9a681d2e3201d9f3d"
HISTORICAL = {
    "bad_contract": (ROOT / "E02-var01-stock-vs-zero-v0.1.0" / "contract.json",
                     "e0b5f7f57454760e5b5f9532641818683fdf99b5e71459f63c353700e19e302e"),
    "bad_review": (ROOT / "E02-var01-stock-vs-zero-v0.1.0" / "review" / "independent-contract-no-go-2026-10-06.md",
                   "91ec960ff2460afbc8703b84193ab16e2fabd24e66a8faaa9e6edc23dc325374"),
    "good_contract": (ROOT / "E02-var01-stock-vs-zero-v0.1.1" / "contract.json", CONTRACT_SHA),
    "good_review": (ROOT / "E02-var01-stock-vs-zero-v0.1.1" / "review" / "independent-contract-go-2026-10-06.md",
                    "44733a709bb1f291a14038057f5b8254d348bc159f8d72472e577fe3c92a92e6"),
    "failed_replay": (ROOT / "E02-var01-stock-vs-zero-v1.0.0" / "review" / "author-replay-failed.json",
                      "16e3888eea959880d43e5963ccaff2dce2a04e2ff48d12eab18d958e2990dc37"),
    "failed_checker": (ROOT / "E02-var01-stock-vs-zero-v1.0.0" / "replay.py",
                       "95d084f852d1533502911df205f0083ffa94d8299497bf398f2ad53da796f28c"),
    "failed_memo": (ROOT / "E02-var01-stock-vs-zero-v1.0.0" / "review" / "author-replay-failure-2026-10-06.md",
                    "7279de086fdf78da5b914e66fc66b0326bd92bb1ffb56ebe5b59943a4a239ee5"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordinary_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Keep the native file intact. Remove only trailing commas outside
        # quoted strings in the parser's in-memory copy.
        cleaned: list[str] = []
        inside = escaped = False
        for pos, char in enumerate(raw):
            if inside:
                cleaned.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    inside = False
            elif char == '"':
                inside = True
                cleaned.append(char)
            elif char == "," and raw[pos + 1 :].lstrip().startswith(("}", "]")):
                continue
            else:
                cleaned.append(char)
        return json.loads("".join(cleaned))


def tables(document: dict, section: str) -> dict:
    items = document[section]["tables"]
    result = {table["name"]: table for table in items}
    if len(result) != len(items):
        raise ValueError(f"duplicate {section} table")
    return result


def rows(document: dict, section: str, name: str) -> list[dict]:
    table = tables(document, section)[name]
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row, strict=True))
            for instance in table["instances"] for row in instance["rows"]]


def event_times(log: str, phrase: str) -> list[float]:
    result = []
    for line in log.splitlines():
        match = re.match(r"^Time: ([0-9.]+) (.*)$", line)
        if match and phrase in match.group(2):
            result.append(float(match.group(1)))
    return result


def replay() -> dict:
    failures: list[str] = []
    count = 0

    def check(label: str, condition: bool) -> None:
        nonlocal count
        count += 1
        if not condition:
            failures.append(label)

    check("reviewed v1.0.1 contract", sha(CASE / "contract.json") == CONTRACT_SHA)
    contract = ordinary_json(CASE / "contract.json")
    check("contract scope", contract["variant_id"] == "E02.var01"
          and contract["publication_state"] == "not_published"
          and contract["evidence_mode"].startswith("read-only comparison"))
    for label, (path, expected) in HISTORICAL.items():
        check(f"historical {label}", path.is_file() and sha(path) == expected)
    old = ordinary_json(HISTORICAL["failed_replay"][0])
    check("old author failure retained", old["passed"] is False
          and old["differences"] == ["one failed item repair", "zero failed item repair",
                                      "system availability integrals"])
    check("corrected author source pin", sha(CASE / "replay.py")
          == "ecb04bf44387a44ecd303d1817d5c25579fd6900ee9a0bbd4f37a53bcad5c9ab")
    check("corrected author output pin", sha(CASE / "author-replay.json")
          == "bcef9663fe08a325a9520665ec9c7d2c360f61bfcd186cbf65322aaedc2eb109")
    check("corrected author output sealed", ordinary_json(CASE / "author-replay.json")["passed"] is True
          and ordinary_json(CASE / "author-replay.json")["checks"] == 88)

    prereq = ROOT / "E05-local-repair-reissue-v1.0.0" / "cli-scope-signoff-2026-09-29.md"
    check("E05 prerequisite", sha(prereq) == contract["parents"]["repair_prerequisite"]["signoff_sha256"])
    observed: dict[str, dict] = {}
    for label in ("stock_one", "stock_zero"):
        pin = contract["parents"][label]
        package = ROOT / pin["package"]
        run = package / "runs" / pin["run_id"]
        check(f"{label} input pin", sha(package / "native-input.json") == pin["input_sha256"])
        check(f"{label} signoff pin", sha(package / "cli-scope-signoff-2026-09-29.md") == pin["signoff_sha256"])
        check(f"{label} closure pin", sha(run / "closure.json") == pin["closure_sha256"])
        closure, invocation = ordinary_json(run / "closure.json"), ordinary_json(run / "invocation.json")
        check(f"{label} accepted source stability", closure["error"] is None
              and closure["source_hashes_before"] == closure["source_hashes_after"]
              and closure["source_hashes_before"]["input"] == pin["input_sha256"])
        check(f"{label} invocation seal", closure["invocation_sha256"] == sha(run / "invocation.json")
              and invocation["run_id"] == pin["run_id"] and invocation["session_id"] == 0)
        check(f"{label} guarded context", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
              and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        check(f"{label} 12 raw seals", len(closure["raw"]) == 12)
        for name, record in sorted(closure["raw"].items()):
            path = run / name
            check(f"{label} raw {name}", path.is_file() and path.stat().st_size == record["bytes"]
                  and sha(path) == record["sha256"])
        check(f"{label} copied input", sha(run / "input.json") == pin["input_sha256"])
        precedent = ordinary_json(package / "review" / "independent-native-review-2026-09-29.json")
        check(f"{label} accepted independent precedent", precedent["passed"] is True
              and precedent["differences"] == [])
        steps = ordinary_json(run / "steps.json")
        check(f"{label} step order", [step["name"] for step in steps]
              == ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            check(f"{label} step {step['name']}", step["status"] == "completed"
                  and step["exit_code"] == 0 and step["gui_preserved"] is True)
        source = ordinary_json(run / "input.json")
        exported = native_json(run / "roundtrip-raw.json")
        authored = {n: t for n, t in tables(source, "model").items()
                    if any(i["rows"] for i in t["instances"])}
        native = tables(exported, "model")
        check(f"{label} 20 authored tables", len(authored) == 20)
        for name, table in sorted(authored.items()):
            check(f"{label} roundtrip {name}", native[name]["columns"] == table["columns"]
                  and native[name]["instances"] == table["instances"])
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check(f"{label} converter", re.findall(
            r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", converter)
            == [("0", "1", "0")] and re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
        check(f"{label} native output", (run / "model.sxo").stat().st_size > 1000)
        report = native_json(run / "report-raw.json")
        system, stock = rows(report, "report", "SystemResults"), rows(report, "report", "StockTotalResults")
        check(f"{label} 72 system bins", len(system) == 72)
        check(f"{label} 72 stock bins", len(stock) == 72)
        for i in range(72):
            check(f"{label} system bin {i}", system[i]["STINT"] == i / 2
                  and system[i]["ETINT"] == (i + 1) / 2)
            check(f"{label} stock bin {i}", stock[i]["STINT"] == i / 2
                  and stock[i]["ETINT"] == (i + 1) / 2)
        check(f"{label} report totals", sum(r["NFAIL"] for r in system) == 1
              and sum(r["NREPT"] for r in system) == 1
              and sum(r["NDF"] for r in stock) == 1
              and system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0)
        observed[label] = {"source": source, "run": run,
                           "log": (run / "model.log").read_text(encoding="utf-8-sig"),
                           "system": system, "stock": stock, "report": report}

    one, zero = observed["stock_one"], observed["stock_zero"]
    before = copy.deepcopy(one["source"])
    after = zero["source"]
    a, b = tables(before, "model"), tables(after, "model")
    check("source table names/order", list(a) == list(b))
    check("exact two changed tables", [name for name in a if a[name] != b[name]]
          == ["ProblemDescription", "StockAllocation"])
    stock_one, stock_zero = rows(before, "model", "StockAllocation"), rows(after, "model", "StockAllocation")
    check("stock target", len(stock_one) == len(stock_zero) == 1
          and [stock_one[0][key] for key in ("POINT", "IID", "STID", "STSIZ")]
          == ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1]
          and stock_zero[0]["STSIZ"] == 0)
    # Prove every other business cell and all table metadata are identical.
    a["StockAllocation"]["instances"][0]["rows"][0][3] = 0
    a["ProblemDescription"]["instances"][0]["rows"] = copy.deepcopy(
        b["ProblemDescription"]["instances"][0]["rows"])
    check("only description and STSIZ", before == after)

    for label, failed_id, opening, fit, ready in (
        ("stock_one", 1, 1, 10.1667, 10.5),
        ("stock_zero", 0, 0, 11.1667, 11.5),
    ):
        log = observed[label]["log"]
        check(f"{label} first failure", event_times(log, "critical random failure added") == [9.8829]
              and f"subitem failed: <TEACH-LRU-01,0,{failed_id}>" in log)
        check(f"{label} opening stock", f"Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: {opening}" in log)
        check(f"{label} demand ID", event_times(
            log, f"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,{failed_id}>") == [10])
        check(f"{label} remove and repair", event_times(
            log, "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed") == [10.1667]
            and event_times(log, f"Finished repair of item <TEACH-LRU-01,0,{failed_id}>") == [11.1667])
        check(f"{label} physical fit", event_times(
            log, "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing") == [fit]
            and event_times(log, "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed") == [ready])
        check(f"{label} aircraft ready", event_times(
            log, "<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>") == [0, ready, 22, 34])
    check("one-spare issue ID0", event_times(one["log"], "Take replacement item <TEACH-LRU-01,0,0> from stock") == [10]
          and event_times(one["log"], "Put back replacement item <TEACH-LRU-01,0,1> to stock") == [11.1667]
          and not event_times(one["log"], "Backorder added"))
    check("zero-stock backorder", event_times(zero["log"], "Backorder added") == [10]
          and event_times(zero["log"], "Backorder removed, waiting time was 1.16667") == [11.1667]
          and event_times(zero["log"], "Replacement item arrives <TEACH-LRU-01,0,0>") == [11.1667]
          and event_times(zero["log"], "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem") == [10.1667])
    expected_changes = {
        "system": {
            10: {"NSYRP", "NSYWI", "SYDT"},
            10.5: {"NSYRY", "NSYUA", "NSYA", "NSYWI", "NREPT"},
            11: {"NSYRY", "NSYUA", "NSYA", "NSYRP", "NSYWI"},
            11.5: {"NREPT"},
        },
        "stock": {
            10: {"NBO", "ROS", "ROST", "WT", "WTT", "WTS", "PNB"},
            10.5: {"NBO", "PNB"},
            11: {"NBO", "PNB"},
        },
    }
    for name in ("system", "stock"):
        for first, second in zip(one[name], zero[name], strict=True):
            changed = {key for key in first if first[key] != second[key]}
            check(f"{name} full row {first['STINT']}", changed == expected_changes[name].get(first["STINT"], set()))
    ready_one = sum(row["NSYA"] * .5 for row in one["system"])
    ready_zero = sum(row["NSYA"] * .5 for row in zero["system"])
    unit_one = sum(row["NSYRY"] * .5 for row in one["system"])
    unit_zero = sum(row["NSYRY"] * .5 for row in zero["system"])
    bo_one = sum(row["NBO"] * .5 for row in one["stock"])
    bo_zero = sum(row["NBO"] * .5 for row in zero["stock"])
    check("absolute NSYA integral", (ready_one, ready_zero) == (35.5, 34.5))
    check("ready-at-unit NSYRY integral", (unit_one, unit_zero) == (26.5, 25.5))
    check("backorder occupancy", bo_one == 0 and abs(bo_zero - 7 / 6) < 1e-5)
    check("terminal no backorder", one["stock"][-1]["NBO"] == zero["stock"][-1]["NBO"] == 0)
    return {"schema": "simlox-e02-var01-independent-derived-replay/v1",
            "variant_id": "E02.var01", "verdict": "GO_BOUNDED" if not failures else "NO_GO",
            "checks": count, "failures": failures,
            "observed": {"failure_hour": 9.8829, "failed_ids": {"stock_one": 1, "stock_zero": 0},
                         "fit_start_hours": {"stock_one": 10.1667, "stock_zero": 11.1667},
                         "aircraft_ready_hours": {"stock_one": 10.5, "stock_zero": 11.5},
                         "NSYA_integral_hours": {"stock_one": ready_one, "stock_zero": ready_zero},
                         "NSYRY_integral_hours": {"stock_one": unit_one, "stock_zero": unit_zero},
                         "backorder_integral_hours": {"stock_one": bo_one, "stock_zero": bo_zero}},
            "scope": "two accepted seed-1 CLI runs compared read-only; no new native execution or cross-run item identity"}


if __name__ == "__main__":
    try:
        verdict = replay()
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        verdict = {"schema": "simlox-e02-var01-independent-derived-replay/v1",
                   "variant_id": "E02.var01", "verdict": "NO_GO", "checks": 0,
                   "failures": [f"replay exception: {type(error).__name__}: {error}"]}
    print(json.dumps(verdict, sort_keys=True, indent=2))
    sys.exit(0 if verdict["verdict"] == "GO_BOUNDED" else 1)
