"""Source-bound author replay of the two E06 cumulative repair boundary runs."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

INPUT_SHA = {
    "local": "b460c6948c2299c521fb9e24c69c1ebc7dfd976702b5e380b13b5f5abf666b95",
    "upstream": "7febb8c32afaa24fbf3bad94ba240e53236d8967c6fe6df51b4cfb7686828b0d",
}
PARENT_SHA = "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"
SUPPORT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_runs(local: Path, upstream: Path) -> dict:
    errors: list[str] = []
    nchecks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal nchecks
        nchecks += 1
        if not condition:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("contract identities", contract["case_id"] == "E06" and contract["variant_id"] == "E06.var01")
    ck("contract parents", contract["parent"]["input_sha256"] == PARENT_SHA
       and contract["support_prerequisite"]["input_sha256"] == SUPPORT_SHA)
    ck("parent bytes", sha(HERE.parent / "E05-local-repair-reissue-v1.0.0/native-input.json") == PARENT_SHA)
    ck("support bytes", sha(HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json") == SUPPORT_SHA)
    logs, reports = {}, {}
    for variant, run in (("local", local), ("upstream", upstream)):
        prefix = variant + ": "
        ck(prefix + "frozen input", sha(HERE / f"{variant}-input.json") == INPUT_SHA[variant]
           and contract["native_input_sha256"][variant] == INPUT_SHA[variant])
        ck(prefix + "run input", sha(run / "input.json") == INPUT_SHA[variant])
        inv, closure = load(run / "invocation.json"), load(run / "closure.json")
        ck(prefix + "invocation identity", inv.get("case_id") == "E06" and inv.get("variant") == variant
           and inv.get("run_id") == run.name and inv.get("input_sha256") == INPUT_SHA[variant]
           and inv.get("parent_sha256") == PARENT_SHA and inv.get("support_sha256") == SUPPORT_SHA)
        for field, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                                ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
            ck(prefix + "bound " + filename, inv.get(field) == sha(HERE / filename))
        ck(prefix + "executable and SSH", inv.get("simlox_exe_sha256") == EXE_SHA
           and inv.get("session_id") == 0 and inv.get("ssh_connection_present")
           and "sshd.exe" in inv.get("ssh_ancestor_names", []))
        ck(prefix + "GUI and mutex", inv.get("gui", {}).get("pid") == 13340
           and inv.get("gui", {}).get("session_id") == 1
           and inv.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
        ck(prefix + "closure", closure.get("error") is None
           and closure.get("invocation_sha256") == sha(run / "invocation.json")
           and closure.get("source_hashes_before") == closure.get("source_hashes_after") == inv.get("source_hashes_before"))
        ck(prefix + "raw file set", set(closure.get("raw", {})) == RAW)
        for name, item in closure.get("raw", {}).items():
            path = run / name
            ck(prefix + "raw " + name, path.is_file() and path.stat().st_size == item.get("bytes")
               and sha(path) == item.get("sha256"))
        steps = load(run / "steps.json")
        ck(prefix + "step order", [s.get("name") for s in steps]
           == ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            ck(prefix + "step " + step.get("name", "?"), step.get("status") == "completed"
               and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
        roundtrip = load(run / "roundtrip-validation.json")
        ck(prefix + "roundtrip", roundtrip.get("passed") is True and not roundtrip.get("differences")
           and len(roundtrip.get("populated_tables", [])) == 21)
        ck(prefix + "source rows", native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
        calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(prefix + "conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc
           and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1}))
        lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        logs[variant] = lines
        times = [float(m[1]) for line in lines if (m := re.match(r"^Time: ([0-9.]+) ", line))]
        ck(prefix + "event order and horizon", bool(times) and times == sorted(times) and times[-1] <= 36)
        report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
        reports[variant] = report
        summary = native.table_rows(report, "ResultSummary")
        ck(prefix + "report window", len(summary) == 1 and summary[0]["NREP"] == 1
           and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36)
        system, stock = native.table_rows(report, "SystemResults"), native.table_rows(report, "StockTotalResults")
        ck(prefix + "72 aligned half-hour bins", len(system) == len(stock) == 72
           and all(abs(a["STINT"] - i / 2) < 1e-9 and abs(a["ETINT"] - (i + 1) / 2) < 1e-9
                   and abs(b["STINT"] - i / 2) < 1e-9 and abs(b["ETINT"] - (i + 1) / 2) < 1e-9
                   for i, (a, b) in enumerate(zip(system, stock))))
        failures = sum("critical random failure added" in line for line in lines)
        repairs = sum(re.search(r"^Time: [0-9.]+  item DIRP task \d+ .* completed$", line) is not None for line in lines)
        system_repairs = sum(re.search(r"^Time: [0-9.]+  system SURP task \d+ .* completed$", line) is not None for line in lines)
        ck(prefix + "failure and repair counts", failures == repairs == system_repairs == (3 if variant == "local" else 1))
        ck(prefix + "report failures/repairs", sum(row["NFAIL"] for row in system) == failures
           and sum(row["NREPT"] for row in system) == system_repairs)
        ck(prefix + "final base stock", any(line.startswith("  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:")
                                            for line in lines[-25:]) if variant == "local" else
           any(line == "  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>," for line in lines))
        ck(prefix + "terminal system", system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0)

    first = "<TEACH-LRU-01,0,1>"
    for variant, lines in logs.items():
        ck(variant + ": first failure", any(line.startswith("Time: 9.25527 ") and "critical random failure added" in line for line in lines))
        ck(variant + ": first failed item", sum(f"subitem failed: {first}" in line for line in lines) == 2)
        ck(variant + ": same direct complexity", any(line.startswith("Time: 9.92193 ") and
           f"Item requiring maintenance arrives {first}" in line and "complexity: 0.0874536" in line for line in lines))
        ck(variant + ": first spare and recovery", any(line.startswith("Time: 9.75527 ") and
           "Take replacement item <TEACH-LRU-01,0,0> from stock" in line for line in lines)
           and any(line.startswith("Time: 10.2553 ") and "systems ready: 1" in line for line in lines))
    a, b = logs["local"], logs["upstream"]
    ck("local first repair station/timing", any(line == f"Time: 9.92193 <TEACH-LRU-01,0,BASE-01,0> Start repair of item {first}" for line in a)
       and any(line == f"Time: 10.9219 <TEACH-LRU-01,0,BASE-01,0> Finished repair of item {first}" for line in a))
    ck("local no physical transport", not any(re.search(r"transport task \d+ starts with", line) for line in a))
    ck("upstream dispatch identity", any(line.startswith("Time: 9.92193 ") and
       f"transport request <{first},<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in line for line in b))
    ck("upstream two-hour outward transport", any(line.startswith("Time: 9.92193 ") and
       "transport task 0 starts with 1 items/systems, transport time: 2" in line for line in b)
       and any(line.startswith("Time: 11.9219 ") and "transport task 0 arrives with 1 items/systems" in line for line in b))
    ck("depot first repair station/timing", any(line == f"Time: 11.9219 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item {first}" for line in b)
       and any(line == f"Time: 12.9219 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item {first}" for line in b))
    ck("upstream two-hour return transport", any(line.startswith("Time: 12.9219 ") and
       "transport task 2 starts with 1 items/systems, transport time: 2" in line for line in b)
       and any(line.startswith("Time: 14.9219 ") and "transport task 2 arrives with 1 items/systems" in line for line in b)
       and any(line == f"  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:{first}," for line in b))
    ck("upstream depot backorder clears", any("Backorder added" in line and "DEPOT-01" in line for line in b)
       and any("Backorder removed, waiting time was 3" in line and "DEPOT-01" in line for line in b))
    ck("later mission divergence explicit", sum("mission aborted:" in line for line in a) == 3
       and sum("mission success:" in line for line in b) == 2)
    return {"schema": "simlox-e06-var01-author-readonly-v1", "passed": not errors,
            "checks": nchecks, "differences": errors,
            "runs": {"local": local.name, "upstream": upstream.name},
            "observed_scope": "fixed-seed cumulative DIRPF 1/0 first-demand station routing",
            "later_stochastic_paths": "diverged; no paired later-failure causal claim",
            "publication_state": "not_published"}


if __name__ == "__main__":
    result = check_runs(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
