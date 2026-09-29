"""Replay the five sealed D02.var06 native clock probes."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
sys.path.insert(0, str(HERE))
from build import build, VARIANTS  # noqa: E402
from check_roundtrip import validate as roundtrip_validate  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_path(variant: str) -> Path:
    return HERE / "runs" / f"d02-var06-{variant}-v100-ssh-20260930-01"


def main() -> int:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    try:
        contract = read(HERE / "contract.json")
        check("contract identity", (contract["case_id"], contract["variant_id"],
              contract["publication_state"]), ("D02", "D02.var06", "not_published"))
        check("accepted parent fingerprint", sha(PARENT), contract["parent"]["input_sha256"])
        parent_raw = PARENT.read_bytes()
        parent = json.loads(parent_raw)
        parent_tables = {t["name"]: t for t in parent["model"]["tables"]}
        for variant in VARIANTS:
            prefix = f"{variant}: "
            run = run_path(variant)
            source = HERE / f"native-input-{variant}.json"
            expected_sha = contract["native_input_sha256"][variant]
            check(prefix + "frozen input SHA", sha(source), expected_sha)
            child = read(source)
            check(prefix + "builder identity", child, build(variant, parent_raw))
            child_tables = {t["name"]: t for t in child["model"]["tables"]}
            changed = {name for name in parent_tables.keys() & child_tables.keys()
                       if parent_tables[name] != child_tables[name]}
            added = set(child_tables) - set(parent_tables)
            target = "Item" if variant.startswith("item-") else "ItemFailureRate"
            check(prefix + "parent table delta", (changed, added),
                  ({"ProblemDescription", "Item"}, set()) if target == "Item"
                  else ({"ProblemDescription"}, {"ItemFailureRate"}))
            invocation, closure, steps = (read(run / name) for name in
                                          ("invocation.json", "closure.json", "steps.json"))
            check(prefix + "run identity", (invocation["case_id"], invocation["variant"],
                  invocation["input_sha256"], invocation["parent_sha256"]),
                  ("D02.var06", variant, expected_sha, contract["parent"]["input_sha256"]))
            check(prefix + "guarded invocation", (invocation["session_id"],
                  invocation["ssh_connection_present"],
                  "sshd.exe" in invocation["ssh_ancestor_names"],
                  invocation["queue_mutex"], invocation["gui"]["pid"],
                  invocation["gui"]["session_id"]),
                  (0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1))
            check(prefix + "input copy SHA", sha(run / "input.json"), expected_sha)
            check(prefix + "invocation seal", sha(run / "invocation.json"),
                  closure["invocation_sha256"])
            check(prefix + "source hashes stable", closure["source_hashes_before"],
                  closure["source_hashes_after"])
            paths = {"input": source, "parent": PARENT, "contract": HERE / "contract.json",
                     "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
                     "runner_script": HERE / "run_native_ssh.ps1"}
            paths.update({"input_" + v.replace("-", "_"): HERE / f"native-input-{v}.json"
                          for v in VARIANTS})
            for key, path in paths.items():
                check(prefix + "sealed " + key, sha(path),
                      closure["source_hashes_before"][key])
            for name, seal in sorted(closure["raw"].items()):
                path = run / name
                check(prefix + "raw " + name,
                      (sha(path), path.stat().st_size),
                      (seal["sha256"], seal["bytes"]))
            check(prefix + "roundtrip", roundtrip_validate(run)["passed"], True)
            conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
            check(prefix + "conversion summary", re.findall(
                  r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
                  conversion), [("0", "2", "0")] if variant == "rate-ophours"
                  else [("1", "1", "0")])
            if variant == "rate-ophours":
                check(prefix + "no errors", re.findall(r"error #(\d+)", conversion), [])
                check(prefix + "expected warnings", re.findall(r"warning #(\d+)", conversion),
                      ["108", "2058"])
                check(prefix + "five completed steps", [(s["name"], s["status"],
                      s["exit_code"], s["gui_preserved"]) for s in steps],
                      [(n, "completed", 0, True) for n in
                       ("import", "export", "calc", "jsonreport", "check_import_export")])
                check(prefix + "closure success", closure["error"], None)
                check(prefix + "simulated output", (run / "model.sxo").stat().st_size > 4, True)
                check(prefix + "report output", (run / "report-raw.json").stat().st_size > 4, True)
                check(prefix + "sealed roundtrip", read(run / "roundtrip-validation.json")["passed"], True)
            else:
                clock = variant.split("-", 1)[1].upper()
                check(prefix + "specific native rejection", re.findall(
                      rf"Form: {re.escape(target)}\s+rec 1: \(error #(\d+)\) "
                      rf"Predefined operation parameter not allowed:\s+{clock}\b", conversion),
                      ["2057"])
                check(prefix + "only expected error", re.findall(r"error #(\d+)", conversion),
                      ["2057"])
                check(prefix + "three guarded steps", [(s["name"], s["status"],
                      s["exit_code"], s["gui_preserved"]) for s in steps],
                      [("import", "completed", 0, True),
                       ("export", "completed", 0, True),
                       ("calc", "failed", 0, True)])
                check(prefix + "expected closure error", closure["error"],
                      "calc output model.sxo absent/empty")
                check(prefix + "empty native output", (run / "model.sxo").stat().st_size, 4)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d02-var06-clock-matrix-author-validation/v1",
              "case_id": "D02", "variant_id": "D02.var06",
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks),
              "checks": checks, "scope": "traditional_item_and_item_failure_rate_clock_conversion",
              "publication_state": "not_published"}
    output = HERE / "review" / "author-matrix-validation-2026-09-30.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
                       .encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
