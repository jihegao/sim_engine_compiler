"""Replay source, sealed native run, and bounded D06 failure/CM behavior."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
INPUT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = next(x for x in doc[root]["tables"] if x["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row, strict=True)) for i in t["instances"] for row in i["rows"]]


def populated(doc: dict) -> dict:
    return {t["name"]: (t["columns"], [r for i in t["instances"] for r in i["rows"]])
            for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tol,
                       "actual": actual, "expected": expected, "tolerance": tol})

    try:
        child_path = HERE / "native-input.json"
        child, contract = read(child_path), read(HERE / "contract.json")
        invocation, closure, steps = (read(run / n) for n in
                                      ("invocation.json", "closure.json", "steps.json"))
        copied, exported, report = (native(run / n) for n in
                                    ("input.json", "roundtrip-raw.json", "report-raw.json"))
        roundtrip = read(run / "roundtrip-validation.json")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")

        check("accepted parent SHA", sha(PARENT), PARENT_SHA)
        check("frozen input SHA", sha(child_path), INPUT_SHA)
        check("copied input SHA", sha(run / "input.json"), INPUT_SHA)
        check("copied model equals source", copied, child)
        check("contract binding", (contract["parent"]["input_sha256"],
              contract["native_input_sha256"], contract["publication_state"]),
              (PARENT_SHA, INPUT_SHA, "not_published"))
        diff = read(HERE / "parent-diff.json")
        check("exact parent diff scope", (set(diff["changed_tables_only"]),
              set(diff["added_tables_only"]), diff["unchanged_table_count"]),
              ({"ProblemDescription", "System", "Item", "ItemStructure", "SystemRepair",
                "ItemRepair", "StockAllocation"},
               {"MaterielPosition", "MaterielStructure", "FailureMode", "CMLocation"}, 24))
        check("traditional system FRT absent", rows(child, "model", "System")[0]["FRT"], None)
        check("traditional item FRT absent", rows(child, "model", "Item")[0]["FRT"], None)
        for name in ("ItemStructure", "SystemRepair", "ItemRepair", "StockAllocation"):
            check(f"legacy {name} rows absent", rows(child, "model", name), [])
        check("two positions", [r["MPID"] for r in rows(child, "model", "MaterielPosition")],
              ["POS-A", "POS-B"])
        check("same item at two positions", [(r["MID"], r["MMID"], r["QTYPM"])
              for r in rows(child, "model", "MaterielStructure")],
              [("POS-A", "TEACH-AIR-01", 1), ("POS-B", "TEACH-AIR-01", 1),
               ("TEACH-LRU-01", "POS-A", 1), ("TEACH-LRU-01", "POS-B", 1)])
        check("single position A FMID", [(r["FMID"], r["MID"], r["FRQ"], r["OPID"])
              for r in rows(child, "model", "FailureMode")],
              [("FM-POS-A", "POS-A", 300000, "OPHOURS")])
        check("single direct CM", [(r["FMID"], r["ID"], r["STID"], r["CMT"], r["CMF"])
              for r in rows(child, "model", "CMLocation")],
              [("FM-POS-A", "TEACH-AIR-01", "BASE-01", 0.5, 1)])
        source_tables, exported_tables = populated(copied), populated(exported)
        check("18 source row tables exact roundtrip", len(source_tables) == 18 and
              all(exported_tables.get(n) == v for n, v in source_tables.items()), True)
        check("roundtrip checker", (roundtrip["passed"], roundtrip["differences"]), (True, []))
        check("session-0 invocation", (invocation["case_id"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"], invocation["gui"]["pid"],
              invocation["queue_mutex"]),
              ("D06", INPUT_SHA, PARENT_SHA, 0, True, 13340,
               "Global\\SimloxIssue18NativeQueue"))
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("five guarded steps", [(s["name"], s["status"], s["exit_code"],
              s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in
               ("import", "export", "calc", "jsonreport", "check_import_export")])
        check("closure no error", closure["error"], None)
        check("closure invocation SHA", closure["invocation_sha256"],
              sha(run / "invocation.json"))
        check("source hashes stayed fixed", closure["source_hashes_before"],
              closure["source_hashes_after"])
        for name, path in {"input": child_path, "parent": PARENT,
                           "contract": HERE / "contract.json", "builder": HERE / "build.py",
                           "checker": HERE / "check_roundtrip.py",
                           "runner_script": HERE / "run_native_ssh.ps1"}.items():
            check(f"sealed current {name}", sha(path), closure["source_hashes_before"][name])
        for name, sealed in sorted(closure["raw"].items()):
            check(f"raw {name}", (sha(run / name), (run / name).stat().st_size),
                  (sealed["sha256"], sealed["bytes"]))
        check("conversion result", re.findall(
              r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion),
              [("0", "1", "0")])
        check("warning IDs", re.findall(r"warning #(\d+)", conversion), ["108"])
        check("native error IDs", re.findall(r"error #(\d+)", conversion), [])

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, flags=re.MULTILINE)]

        failure = times(r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical CM failure mode added")
        cm_start = times(r"^Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> started$")
        cm_end = times(r"^Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed$")
        check("two observed failure times", failure, [9.8829, 33.8602])
        check("each failure names FMID and position A", len(re.findall(
              r"Failure Mode: FM-POS-A on materiel: <POS-A,0>", log)), 4)
        check("no other failure mode or traditional failure event", bool(re.search(
              r"Failure Mode: (?!FM-POS-A)|critical random failure added", log)), False)
        check("CM starts", cm_start, [10, 34])
        check("CM completes", cm_end, [10.5, 34.5])
        check("CM task FMID lines", re.findall(r"^Time: [\d.]+  system CM task \d+ on <TEACH-AIR-01,0> FMID: (\S+)$",
              log, flags=re.MULTILINE), ["FM-POS-A", "FM-POS-A"])
        check("mission abort times", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:"),
              failure)
        check("successful mission time", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"),
              [22])
        system = rows(report, "report", "SystemResults")
        check("72 half-hour intervals", [(r["STINT"], r["ETINT"]) for r in system],
              [(i / 2, (i + 1) / 2) for i in range(72)])
        for field, expected in {"NFAIL": 2, "NREPT": 2, "NPMT": 0, "NPMS": 0}.items():
            check(f"reported {field} total", sum(r[field] or 0 for r in system), expected)
        near("reported repair aircraft-hours", sum((r["NSYRP"] or 0) *
             (r["ETINT"] - r["STINT"]) for r in system), 1.0)
        check("terminal aircraft ready", (system[-1]["NSYRY"], system[-1]["NSYRP"]), (1, 0))
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d06-position-cm-v100-author-validation/v1",
              "case_id": "D06", "run_id": run.name, "input_sha256": INPUT_SHA,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks), "checks": checks,
              "scope": "two_positions_one_explicit_fmid_direct_system_cm_cli",
              "publication_state": "not_published"}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps({k: result[k] for k in ("run_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
