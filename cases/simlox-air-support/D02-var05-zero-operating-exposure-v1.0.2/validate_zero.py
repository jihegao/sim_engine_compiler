"""Replay sealed D02.var05 zero-initiation evidence and two rejected probes."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json"
RUN = HERE / "runs" / "d02-var05-zero-op-v102-ssh-20260930-01"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True))
            for instance in table["instances"] for row in instance["rows"]]


def main() -> int:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    try:
        source = HERE / "native-input.json"
        parent, child, contract, diff = (read(p) for p in
                                         (PARENT, source, HERE / "contract.json",
                                          HERE / "parent-diff.json"))
        invocation, closure, steps = (read(RUN / n) for n in
                                      ("invocation.json", "closure.json", "steps.json"))
        report = native(RUN / "report-raw.json")
        roundtrip = read(RUN / "roundtrip-validation.json")
        conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check("accepted parent SHA", sha(PARENT), contract["parent"]["input_sha256"])
        check("frozen child SHA", sha(source), contract["native_input_sha256"])
        check("copied input SHA", sha(RUN / "input.json"), contract["native_input_sha256"])
        check("copied input identity", native(RUN / "input.json") == child, True)
        check("contract identity", (contract["case_id"], contract["variant_id"],
              contract["case_version"], contract["publication_state"]),
              ("D02", "D02.var05", "1.0.2-candidate", "not_published"))
        check("exact parent diff scope", (set(diff["changed_tables_only"]),
              diff["added_tables_only"], diff["unchanged_table_count"]),
              ({"ProblemDescription", "OperationProfile"}, [], 29))
        check("parent profile times and quantities", [(r["STIM"], r["IQTY"])
              for r in rows(parent, "model", "OperationProfile")],
              [(8, 1), (20, 1), (52, 1)])
        check("child profile times and zero quantities", [(r["STIM"], r["IQTY"])
              for r in rows(child, "model", "OperationProfile")],
              [(8, 0), (20, 0), (52, 0)])
        check("unit assignment retained", rows(child, "model", "Operations"),
              rows(parent, "model", "Operations"))
        check("traditional System clock retained", [(r["FRT"], r["OPID"])
              for r in rows(child, "model", "System")], [(300000, "OPHOURS")])
        check("traditional Item clock retained", [(r["FRT"], r["OPID"])
              for r in rows(child, "model", "Item")], [(300000, "OPHOURS")])
        check("seed and 60-hour horizon", [(r["RSEED"], r["SIMPE"], r["RCEND"])
              for r in rows(child, "model", "Control")], [("1", 60, 60)])
        check("session-0 guarded invocation", (invocation["case_id"],
              invocation["case_version"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"],
              "sshd.exe" in invocation["ssh_ancestor_names"],
              invocation["gui"]["pid"], invocation["gui"]["session_id"],
              invocation["queue_mutex"]),
              ("D02.var05", "1.0.2-candidate", contract["native_input_sha256"],
               contract["parent"]["input_sha256"], 0, True, True, 13340, 1,
               "Global\\SimloxIssue18NativeQueue"))
        check("five guarded steps", [(s["name"], s["status"], s["exit_code"],
              s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in
               ("import", "export", "calc", "jsonreport", "check_import_export")])
        check("closure no error", closure["error"], None)
        check("invocation sealed", sha(RUN / "invocation.json"),
              closure["invocation_sha256"])
        check("source hashes stable", closure["source_hashes_before"],
              closure["source_hashes_after"])
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json",
                          "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
                          "runner_script": HERE / "run_native_ssh.ps1"}.items():
            check("sealed current " + key, sha(path),
                  closure["source_hashes_before"][key])
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            check("raw " + name, (sha(path), path.stat().st_size),
                  (seal["sha256"], seal["bytes"]))
        check("roundtrip passed", (roundtrip["passed"], roundtrip["differences"]),
              (True, []))
        check("18 row-containing source tables", len(roundtrip["populated_tables"]), 18)
        check("conversion summary", re.findall(
              r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
              conversion), [("0", "1", "0")])
        check("only logging warning", re.findall(r"warning #(\d+)", conversion), ["108"])
        check("no conversion errors", re.findall(r"error #(\d+)", conversion), [])
        check("no generated default profile notice", "Default operational profile generated" in conversion,
              False)
        check("no mission, preparation or failure events", bool(re.search(
              r"mission (?:ordered|created|activated|starting|success|aborted)|"
              r"preparation started|critical random failure added", log)), False)
        check("only day boundaries after setup", re.findall(r"^Time: (\d+)  Start of day no (\d+)$",
              log, flags=re.MULTILINE), [("0", "0"), ("24", "1"), ("48", "2")])
        check("zero-active initial random failure marker", re.findall(
              r"^Time: 0 <TEACH-AIR-01,0> Next random failure will occur ([^\n]+)$",
              log, flags=re.MULTILINE), ["1e+010"])
        system = rows(report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        check("120 aligned system bins", [(r["STINT"], r["ETINT"]) for r in system],
              [(i / 2, (i + 1) / 2) for i in range(120)])
        check("120 aligned stock bins", [(r["STINT"], r["ETINT"]) for r in stock],
              [(i / 2, (i + 1) / 2) for i in range(120)])
        for field in ("NSYMA", "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS",
                      "NSYMR", "NSYUA", "FTMO", "NSYRP", "NREPT", "NPMT",
                      "NFAIL", "NDAM", "NPMS"):
            check(f"system {field} zero all bins", set(r[field] for r in system), {0})
        check("aircraft ready all bins", set((r["NSYRY"], r["NSYA"]) for r in system),
              {(1, 1)})
        for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD"):
            check(f"stock {field} zero all bins", set(r[field] for r in stock), {0})
        check("stock full all bins", set(r["PNB"] for r in stock), {1})
        summary = rows(report, "report", "ResultSummary")
        check("zero-mission result summary", summary, [{"NREP": 1, "RTILW": 0,
              "RTIUP": 60, "MTMF": 0, "RSMTMF": 0, "MSTF": 0,
              "RSMSTF": 0, "MSUF": 0, "RSMSUF": 0, "STMF": 0, "RSSTMF": 0}])
        prior = contract["prior_probes"]
        check("prior failed probes recorded", [(p["version"], p["input_sha256"])
              for p in prior], [("1.0.0-candidate",
                               "dc64f5644ef146cdef1ab8364bd57be0a28251f0d2f6130a45c0b90c876d2a8d"),
                              ("1.0.1-candidate",
                               "6d4b0efb01f028b09eea055d557ea1dfe7f50d22a9e6088b2de6fe1173990b08")])
        old0 = HERE.parent / "D02-var05-zero-operating-exposure-v1.0.0"
        old1 = HERE.parent / "D02-var05-zero-operating-exposure-v1.0.1"
        check("first probe source SHA", sha(old0 / "native-input.json"), prior[0]["input_sha256"])
        check("second probe source SHA", sha(old1 / "native-input.json"), prior[1]["input_sha256"])
        log0 = (old0 / "runs" / prior[0]["run_id"] / "run.log").read_text(
            encoding="utf-8-sig", errors="replace")
        log1 = (old1 / "runs" / prior[1]["run_id"] / "model.log").read_text(
            encoding="utf-8-sig", errors="replace")
        check("first probe dangling PRID error", "(error #77) Unknown operational profile (PRID):  BASIC-SCHEDULE" in log0,
              True)
        check("second probe default full-horizon mission", "mission starting, duration: 60" in log1,
              True)
        check("second probe active failure", "Time: 1.8829 <TEACH-AIR-01,0> critical random failure added" in log1,
              True)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d02-var05-zero-initiation-author-validation/v1",
              "case_id": "D02", "variant_id": "D02.var05", "run_id": RUN.name,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks),
              "checks": checks, "scope": "zero_initiation_traditional_ophours_one_seed",
              "publication_state": "not_published"}
    output = HERE / "review" / "author-zero-validation-2026-09-30.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
                       .encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("run_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
