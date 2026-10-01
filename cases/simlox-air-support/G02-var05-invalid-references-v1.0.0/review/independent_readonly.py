"""Independent, standard-library replay of frozen G02.var05 native evidence.

Reads source and run artifacts only. It never imports the case builder or validator.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "G02-var01-position-modes-v1.0.0"
REPORT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
RUNS = {
    "valid-control": "g02-var05-valid-control-20261002-01",
    "missing-fmid-mid": "g02-var05-missing-fmid-mid-20261002-01",
    "missing-structure-mother": "g02-var05-missing-structure-mother-20261002-01",
}
FINGERPRINTS = {
    "parent": PARENT / "native-input.json",
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX native JSON has a trailing comma before its final table bracket.
        text = re.sub(r",(?=\s*[}\]])", "", text)
    return json.loads(text)


def tables(doc: dict, root: str = "model") -> dict:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list:
    return [(instance["instance_name"], row)
            for instance in table["instances"] for row in instance["rows"]
            ]


def field(table: dict, row: list, name: str):
    return row[[c["name"] for c in table["columns"]].index(name)]


checks: list[dict] = []


def check(name: str, truth: bool, detail=None):
    checks.append({"name": name, "pass": bool(truth), **({"detail": detail} if detail is not None else {})})


def main():
    contract = parse(CASE / "contract.json")
    original = parse(FINGERPRINTS["parent"])
    check("accepted parent SHA", digest(FINGERPRINTS["parent"]) == contract["parent"]["input_sha256"])
    for key in ("manual", "dictionary", "simlox_exe"):
        check(f"installed {key} SHA", digest(FINGERPRINTS[key]) == contract["source"][f"{ 'exe' if key == 'simlox_exe' else key}_sha256"])

    source_hashes = {k: digest(v) for k, v in FINGERPRINTS.items()}
    outcomes = {}
    total_raw = 0
    for variant, run_id in RUNS.items():
        run = CASE / "runs" / run_id
        source = CASE / f"{variant}-input.json"
        expected = copy.deepcopy(original)
        t = tables(expected)
        description = t["ProblemDescription"]["instances"][0]["rows"][0]
        description[[c["name"] for c in t["ProblemDescription"]["columns"]].index("PDESC")] = f"G02.var05 {variant} position-reference control"
        if variant == "missing-fmid-mid":
            fm = t["FailureMode"]
            target = [r for r in fm["instances"][0]["rows"] if field(fm, r, "FMID") == "FM-POS-B"]
            check(f"{variant} unique FM-POS-B", len(target) == 1)
            target[0][[c["name"] for c in fm["columns"]].index("MID")] = "POS-MISSING"
        elif variant == "missing-structure-mother":
            ms = t["MaterielStructure"]
            target = [r for r in ms["instances"][0]["rows"] if field(ms, r, "MID") == "POS-B" and field(ms, r, "MMID") == "TEACH-AIR-01"]
            check(f"{variant} unique POS-B mother", len(target) == 1)
            target[0][[c["name"] for c in ms["columns"]].index("MMID")] = "SYS-MISSING"
        expected_bytes = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        check(f"{variant} exact parent-derived source bytes", source.read_bytes() == expected_bytes)
        check(f"{variant} frozen input SHA", digest(source) == contract["input_sha256"][variant])
        check(f"{variant} run input copy", (run / "input.json").read_bytes() == source.read_bytes())

        invocation, closure, steps = (parse(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        check(f"{variant} invocation hash", closure["invocation_sha256"] == digest(run / "invocation.json"))
        check(f"{variant} run identity", invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant)
        check(f"{variant} session-0 SSH", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"])
        check(f"{variant} queue and GUI", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(s["gui_preserved"] for s in steps))
        check(f"{variant} sealed source stability", closure["source_hashes_before"] == closure["source_hashes_after"])
        for key, value in closure["source_hashes_before"].items():
            if key == "input": actual = digest(source)
            elif key == "python": actual = value  # Runtime binary is named in invocation; check its path below.
            else: actual = source_hashes[key]
            check(f"{variant} source {key}", actual == value)
        check(f"{variant} pinned runtime path", Path(invocation["planned_check"]["executable"]).is_file())
        check(f"{variant} runtime SHA", digest(Path(invocation["planned_check"]["executable"])) == closure["source_hashes_before"]["python"])
        check(f"{variant} planned step identity", [s["name"] for s in steps] == (["import", "export", "calc", "jsonreport", "check_import_export"] if variant == "valid-control" else ["import", "export", "calc", "check_import_export"]))
        check(f"{variant} import/export/check exit 0", all(s["exit_code"] == 0 for s in steps if s["name"] != "calc"))
        check(f"{variant} calc exit 0", next(s for s in steps if s["name"] == "calc")["exit_code"] == 0)

        raw = closure["raw"]
        total_raw += len(raw)
        for name, seal in raw.items():
            path = run / name
            check(f"{variant} raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and digest(path) == seal["sha256"])
        check(f"{variant} raw seal completeness", set(raw) == {p.name for p in run.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})

        source_tables = tables(parse(source))
        exported_tables = tables(parse(run / "roundtrip-raw.json", native=True))
        populated = [name for name, table in source_tables.items() if rows(table)]
        check(f"{variant} 18 source row tables", len(populated) == 18)
        for name in populated:
            a, b = source_tables[name], exported_tables.get(name)
            check(f"{variant} roundtrip {name}", b is not None and [c["name"] for c in a["columns"]] == [c["name"] for c in b["columns"]] and rows(a) == rows(b))
        check(f"{variant} no missing source table", set(source_tables) <= set(exported_tables))

        log = (run / "run.log").read_text(encoding="utf-8-sig")
        match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
        check(f"{variant} converter summary present", match is not None)
        errors, warnings, notes = map(int, match.groups())
        check(f"{variant} warning 108", "Form: Control\nrec 1: (warning #108)" in log.replace("\r\n", "\n"))
        if variant == "valid-control":
            check("control conversion", (errors, warnings, notes) == (0, 1, 0))
            check("control native steps success", all(s["status"] == "completed" for s in steps))
            check("control nontrivial SXO and report", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
            accepted = PARENT / "runs" / "g02-var01-two-position-accepted-20261001-02"
            check("control event log identical to accepted parent", (run / "model.log").read_bytes() == (accepted / "model.log").read_bytes())
            child_report = tables(parse(run / "report-raw.json", native=True), "report")
            parent_report = tables(parse(accepted / "report-raw.json", native=True), "report")
            for name in sorted(set(parent_report) | set(child_report) - {"ProblemDescription"}):
                if name == "ProblemDescription": continue
                check(f"control accepted report {name}", child_report.get(name) == parent_report.get(name))
            check("control 72 system and stock bins", all(len(rows(child_report[n])) == 72 for n in ("SystemResults", "StockTotalResults")))
            event_log = (run / "model.log").read_text(encoding="utf-8-sig")
            check("control three failure identifiers", event_log.count("FM-POS-B") >= 2 and event_log.count("FM-POS-A") >= 1)
            outcomes[variant] = {"conversion": [errors, warnings, notes], "report_sha256": digest(run / "report-raw.json"), "event_log_sha256": digest(run / "model.log"), "parent_report_non_description_equal": True}
        else:
            wanted = (2, 1, 0) if variant == "missing-fmid-mid" else (1, 2, 0)
            check(f"{variant} exact converter totals", (errors, warnings, notes) == wanted)
            if variant == "missing-fmid-mid":
                check("FMID MID specific #338", bool(re.search(r"Form: FailureMode\s+rec 2: \(error #338\) Unknown materiel identifier \(MID\): POS-MISSING", log)))
                check("downstream CMLocation #342", bool(re.search(r"Form: CMLocation\s+rec 2: \(error #342\) Unknown failure mode identifier \(FMID\):\s+FM-POS-B", log)))
            else:
                check("mother MMID specific #350", bool(re.search(r"Form: MaterielStructure\s+rec 2: \(error #350\) Unknown mother materiel identifier \(MMID\): SYS-MISSING", log)))
                check("orphan warning #378", bool(re.search(r"Form: MaterielPosition\s+rec 2: \(warning #378\).*POS-B", log)))
            check(f"{variant} calc marked failed", next(s for s in steps if s["name"] == "calc")["status"] == "failed")
            check(f"{variant} four-byte invalid SXO", (run / "model.sxo").stat().st_size == 4)
            check(f"{variant} no report or event log", not (run / "report-raw.json").exists() and not (run / "model.log").exists())
            check(f"{variant} closure retains failure", bool(closure["error"]))
            outcomes[variant] = {"conversion": [errors, warnings, notes], "sxo_bytes": 4, "report_absent": True}

    check("30 raw file seals across three runs", total_raw == 30)
    failed = [c for c in checks if not c["pass"]]
    result = {"schema": "independent-g02-var05-readonly/v1", "reviewer": "a17_static_reviewer", "verdict": "GO bounded CLI evidence" if not failed else "NO-GO", "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "outcomes": outcomes, "raw_seals": total_raw, "limitations": ["Two deliberately dangling references in one installed SIMLOX version only.", "Native CLI conversion results do not establish GUI behavior or a general reference-validation rule.", "The calc process exit code is zero even for both rejected inputs; converter diagnostics and absent valid output determine rejection."]}
    REPORT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": f"{result['checks_passed']}/{result['checks_total']}", "failures": failed, "script_sha256": digest(Path(__file__)), "report_sha256": digest(REPORT)}, indent=2))


if __name__ == "__main__":
    main()
