"""Replay the G02.var05 source, native closures, and localized diagnostics."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G02-var01-position-modes-v1.0.0" / "native-input.json"
PARENT_RUN = (HERE.parent / "G02-var01-position-modes-v1.0.0" / "runs" /
              "g02-var01-two-position-accepted-20261001-01")
VARIANTS = ("valid-control", "missing-fmid-mid", "missing-structure-mother")
EXPECTED_INPUTS = {
    "valid-control": "bf1e2752f9632507e3219fa68fc17b38c427041e1067f39031f02344daac0c97",
    "missing-fmid-mid": "7d48a73baa43f56906b88a94ba7e12c8671d0aed36819fb835621d2c004223cc",
    "missing-structure-mother": "6ff5e61a1f87c4f697dea37b23b1340ffef7096771bc2ed571a40d3394ac1b33",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, name: str, root: str = "model") -> dict:
    found = [t for t in doc[root]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]


def set_field(doc: dict, name: str, key: object, column: str, value: object) -> None:
    t = table(doc, name)
    fields = [c["name"] for c in t["columns"]]
    matches = [r for r in t["instances"][0]["rows"] if r[0] == key]
    assert len(matches) == 1
    matches[0][fields.index(column)] = value


def exact_input(variant: str) -> None:
    parent = load(PARENT)
    expected = copy.deepcopy(parent)
    t = table(expected, "ProblemDescription")
    fields = [c["name"] for c in t["columns"]]
    t["instances"][0]["rows"][0][fields.index("PDESC")] = (
        f"G02.var05 {variant} position-reference control")
    if variant == "missing-fmid-mid":
        set_field(expected, "FailureMode", "FM-POS-B", "MID", "POS-MISSING")
    elif variant == "missing-structure-mother":
        t = table(expected, "MaterielStructure")
        fields = [c["name"] for c in t["columns"]]
        found = [r for r in t["instances"][0]["rows"]
                 if r[0] == "POS-B" and r[1] == "TEACH-AIR-01"]
        assert len(found) == 1
        found[0][fields.index("MMID")] = "SYS-MISSING"
    assert expected == load(HERE / f"{variant}-input.json")


def one(variant: str) -> dict:
    run_id = f"g02-var05-{variant}-20261002-01"
    run = HERE / "runs" / run_id
    invocation, closure, steps, roundtrip = (load(run / x) for x in
        ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    assert invocation["run_id"] == closure["run_id"] == run_id
    assert invocation["variant"] == variant
    assert invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
    assert "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    source = closure["source_hashes_before"]
    expected_source_paths = {
        "input": HERE / f"{variant}-input.json", "parent": PARENT,
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    assert set(source) == set(expected_source_paths)
    assert all(source[key] == sha(path) for key, path in expected_source_paths.items())
    assert sha(run / "input.json") == invocation["input_sha256"] == EXPECTED_INPUTS[variant]
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == 18
    assert all(s["gui_preserved"] and s["exit_code"] == 0 for s in steps)
    assert steps[0]["name"] == "import" and steps[0]["status"] == "completed"
    assert steps[1]["name"] == "export" and steps[1]["status"] == "completed"
    assert steps[-1]["name"] == "check_import_export" and steps[-1]["status"] == "completed"
    for name, seal in closure["raw"].items():
        path = run / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if variant == "valid-control":
        assert closure["error"] is None and len(closure["raw"]) == 12
        assert [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
        assert all(s["status"] == "completed" for s in steps)
        assert "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog
        assert (run / "model.sxo").stat().st_size > 4
        assert (run / "model.log").read_bytes() == (PARENT_RUN / "model.log").read_bytes()
        report = parse_native(run / "report-raw.json")
        parent_report = parse_native(PARENT_RUN / "report-raw.json")
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            assert table(report, name, "report") == table(parent_report, name, "report")
        sys = table(report, "SystemResults", "report")
        fields = [c["name"] for c in sys["columns"]]
        rows = sys["instances"][0]["rows"]
        assert len(rows) == 72
        assert sum(r[fields.index("NFAIL")] for r in rows) == 3
        assert sum(r[fields.index("NREPT")] for r in rows) == 3
        classification = "valid_native_control"
    else:
        assert closure["error"] == "calc output model.sxo absent/empty"
        assert len(closure["raw"]) == 9
        assert [s["name"] for s in steps] == ["import", "export", "calc", "check_import_export"]
        assert [s["status"] for s in steps] == ["completed", "completed", "failed", "completed"]
        assert (run / "model.sxo").stat().st_size == 4
        assert not (run / "report-raw.json").exists()
        if variant == "missing-fmid-mid":
            assert "Form: FailureMode\nrec 2: (error #338) Unknown materiel identifier (MID): POS-MISSING" in runlog
            assert "Form: CMLocation\nrec 2: (error #342) Unknown failure mode identifier (FMID):  FM-POS-B" in runlog
            assert "Input conversion completed. Errors: 2, Warnings: 1, Notes: 0" in runlog
            classification = "failure_mode_mid_rejected"
        else:
            assert "Form: MaterielStructure\nrec 2: (error #350) Unknown mother materiel identifier (MMID): SYS-MISSING" in runlog
            assert "Form: MaterielPosition\nrec 2: (warning #378) Materiel with failure mode is not part of any configuration (using MaterielStructure): POS-B" in runlog
            assert "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in runlog
            classification = "structure_mother_rejected"
    return {"run_id": run_id, "variant": variant, "classification": classification,
            "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"]),
            "runlog_sha256": sha(run / "run.log")}


def main() -> None:
    assert sha(PARENT) == "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
    for variant in VARIANTS:
        exact_input(variant)
    runs = [one(variant) for variant in VARIANTS]
    print(json.dumps({"schema": "simlox-g02-var05-author-matrix-validation/v1",
                      "passed": True, "runs": runs,
                      "scope": "two localized native reference rejections plus fixed-seed positive control"}, indent=2))


if __name__ == "__main__":
    main()
