"""Author replay of the four accepted G02.var04 position-PM native runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import build
import check_roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {
    "no-pm": "g02-var04-no-pm-20261002-02",
    "pos-a-only": "g02-var04-pos-a-only-20261002-02",
    "pos-b-only": "g02-var04-pos-b-only-20261002-01",
    "both": "g02-var04-both-20261002-01",
}
EXPECTED = {
    "no-pm": ([], 0),
    "pos-a-only": (["PM-POS-A", "PM-POS-A"], 2),
    "pos-b-only": (["PM-POS-B"], 1),
    "both": (["PM-POS-A", "PM-POS-B", "PM-POS-A"], 3),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["report"]["tables"] if t["name"] == name)


def report_rows(doc: dict, name: str) -> tuple[list[str], list[list]]:
    t = table(doc, name)
    return [c["name"] for c in t["columns"]], [r for i in t["instances"] for r in i["rows"]]


def one(variant: str, run_id: str) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure, steps = (load(run / x) for x in ("invocation.json", "closure.json", "steps.json"))
    assert invocation["run_id"] == closure["run_id"] == run_id
    assert invocation["variant"] == variant
    assert invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
    assert invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["error"] is None
    sources = closure["source_hashes_before"]
    paths = {
        "input": HERE / f"{variant}-input.json",
        "parent": build.PARENT,
        "pm_template": build.PM_TEMPLATE,
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json",
        "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py",
        "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    assert set(sources) == set(paths)
    assert all(sources[key] == sha(path) for key, path in paths.items())
    assert sha(run / "input.json") == sha(paths["input"])
    assert [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps)
    roundtrip = load(run / "roundtrip-validation.json")
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == (18 if variant == "no-pm" else 23)
    assert not roundtrip["differences"]
    assert len(closure["raw"]) == 12
    for name, seal in closure["raw"].items():
        path = run / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    runlog = (run / "run.log").read_text(encoding="utf-8-sig")
    assert "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog
    event = (run / "model.log").read_text(encoding="utf-8-sig")
    pmids = re.findall(r"PMID: (\S+)", event)
    assert pmids == EXPECTED[variant][0]
    report = check_roundtrip.parse_native(run / "report-raw.json")
    system_cols, system = report_rows(report, "SystemResults")
    stock_cols, stock = report_rows(report, "StockTotalResults")
    assert len(system) == len(stock) == 120
    for index, (sysrow, strow) in enumerate(zip(system, stock)):
        start, end = index * 0.5, (index + 1) * 0.5
        assert float(sysrow[system_cols.index("STINT")]) == float(strow[stock_cols.index("STINT")]) == start
        assert float(sysrow[system_cols.index("ETINT")]) == float(strow[stock_cols.index("ETINT")]) == end
    totals = {name: sum(float(r[system_cols.index(name)] or 0) for r in system)
              for name in ("NPMT", "NPMS", "NFAIL", "NREPT")}
    assert totals["NPMT"] == totals["NPMS"] == EXPECTED[variant][1]
    assert totals["NFAIL"] == totals["NREPT"]
    return {"variant": variant, "run_id": run_id, "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
            "raw_seals": len(closure["raw"]), "pmids": pmids,
            "system_totals": totals, "report_sha256": sha(run / "report-raw.json")}


def main() -> None:
    assert sha(build.PARENT) == build.PARENT_SHA and sha(build.PM_TEMPLATE) == build.PM_TEMPLATE_SHA
    assert list(RUNS) == list(build.VARIANTS)
    for variant in RUNS:
        assert (HERE / f"{variant}-input.json").read_bytes() == (
            json.dumps(build.build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    results = [one(variant, run_id) for variant, run_id in RUNS.items()]
    print(json.dumps({"schema": "simlox-g02-var04-author-matrix-validation/v1", "passed": True,
                      "runs": results, "excluded_diagnostics": ["g02-var04-no-pm-20261002-01",
                                                         "g02-var04-pos-a-only-20261002-01"],
                      "scope": "four fixed-seed position-bound calendar-PM arms"}, indent=2))


if __name__ == "__main__":
    main()
