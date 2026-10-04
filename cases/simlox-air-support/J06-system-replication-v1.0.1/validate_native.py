"""Author replay of bounded J06 System TOTAL/TIME/SNAPS native evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/j06-system-replication-v101-ssh-20261004-01"
PARENT = ROOT / "J04-var01-fixed-replications-v1.0.0"
DIAG = ROOT / "J06-system-replication-percentile-v1.0.0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "replication-report-raw.json", "replication-report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    columns = [col["name"] for col in table["columns"]]
    return [dict(zip(columns, row)) for inst in table["instances"] for row in inst["rows"]]


def validate() -> dict:
    checks = 0
    differences: list[str] = []

    def ck(name: str, passed: bool) -> None:
        nonlocal checks
        checks += 1
        if not passed:
            differences.append(name)

    contract, invocation, closure = load(HERE / "contract.json"), load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck("case and version", (contract["case_id"], contract["variant_id"]) == ("J06", "J06.var02"))
    ck("frozen input", sha(HERE / "replication-input.json") == sha(RUN / "input.json") == contract["child_input_sha256"])
    ck("exact diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    ck("parent input", sha(PARENT / "probe-input.json") == contract["accepted_parent"]["input_sha256"])
    ck("parent closure", sha(PARENT / "runs/j04-var01-fixed-reps-accepted-20261001-03/closure.json") == contract["accepted_parent"]["closure_sha256"])
    ck("excluded diagnostic", sha(DIAG / "runs/j06-system-replication-v100-ssh-20261004-01/closure.json") == contract["excluded_diagnostic"]["closure_sha256"])
    ck("run identity", invocation["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None)
    ck("SSH and queue", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("GUI", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    ck("source stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    bound = {"input": HERE / "replication-input.json", "exact_diff": HERE / "exact-diff.json", "contract": HERE / "contract.json",
             "parent": PARENT / "probe-input.json", "excluded_closure": DIAG / "runs/j06-system-replication-v100-ssh-20261004-01/closure.json",
             "report_settings": HERE / "runs/report-settings/replications-enabled.sxs",
             "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
             "build.py": HERE / "build.py", "describe_diff.py": HERE / "describe_diff.py",
             "make_report_settings.py": HERE / "make_report_settings.py", "check_roundtrip.py": HERE / "check_roundtrip.py",
             "run_native_ssh.ps1": HERE / "run_native_ssh.ps1"}
    for name, path in bound.items():
        ck(f"bound {name}", closure["source_hashes_before"].get(name) == sha(path))
    original_settings = bound["default_settings"].read_bytes()
    patched_settings = bound["report_settings"].read_bytes()
    ck("one byte OUTRP settings change", len(original_settings) == len(patched_settings) and
       [i for i, (a, b) in enumerate(zip(original_settings, patched_settings)) if a != b] == [67165] and
       original_settings[67165:67166] == b"N" and patched_settings[67165:67166] == b"Y")
    ck("raw file set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    steps = load(RUN / "steps.json")
    ck("native step order", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "replication_report", "check_import_export"])
    for step in steps:
        ck(f"step {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and (step.get("gui_preserved") is True if step["name"] != "check_import_export" else True))
    q = load(RUN / "roundtrip-validation.json")
    ck("roundtrip pass", q["passed"] is True and q["differences"] == [] and len(q["populated_tables"]) == 16)
    before, after = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    for name, table in before.items():
        ck(f"roundtrip {name}", after.get(name) == table)
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and
       Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1, "126": 1, "211": 1}) and
       "warning #502" not in runlog)
    ck("first-rep event log same parent", sha(RUN / "model.log") == sha(PARENT / "runs/j04-var01-fixed-reps-accepted-20261001-03/model.log"))
    ck("default report same parent", sha(RUN / "report-raw.json") == sha(PARENT / "runs/j04-var01-fixed-reps-accepted-20261001-03/report-raw.json"))

    default, enhanced = parse(RUN / "report-raw.json"), parse(RUN / "replication-report-raw.json")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"same aggregate {name}", rows(default, name) == rows(enhanced, name))
    summary, system, stock = rows(enhanced, "ResultSummary"), rows(enhanced, "SystemResults"), rows(enhanced, "StockTotalResults")
    ck("NREP16 and success", len(summary) == 1 and summary[0]["NREP"] == 16 and summary[0]["MTMF"] == summary[0]["MSTF"] == summary[0]["MSUF"] == 1)
    ck("72 aligned System/Stock bins", len(system) == len(stock) == 72 and all(s["STINT"] == k["STINT"] == i * .5 and s["ETINT"] == k["ETINT"] == (i + 1) * .5 for i, (s, k) in enumerate(zip(system, stock))))
    ck("no stock backorder/demand", all(k["NBO"] == k["NDD"] == 0 for k in stock))
    ck("terminal ready12", system[-1]["NSYRY"] == system[-1]["NSYA"] == 12)

    reps = rows(enhanced, "Replications")
    totals = rows(enhanced, "SystemResultsReplicationTotal")
    timed = rows(enhanced, "SystemResultsReplication")
    snaps = rows(enhanced, "SystemResultsReplicationSnapshot")
    ck("16 replication numbers", [r["REPNO"] for r in reps] == list(range(1, 17)))
    ck("first replication seed", reps[0]["RSEED"] == "1")
    ck("all replication mission success", all(r["FMTAC"] == r["FMSTA"] == r["FMSUC"] == r["FSTAC"] == 1 for r in reps))
    ck("16 System totals", len(totals) == 16 and [r["REPLID"] for r in totals] == list(range(1, 17)))
    ck("16x72 time rows", len(timed) == 1152)
    ck("16x2 snapshot rows", len(snaps) == 32)
    by_rep: dict[int, list[dict]] = defaultdict(list)
    by_time: dict[float, list[dict]] = defaultdict(list)
    for row in timed:
        by_rep[row["REPLID"]].append(row)
        by_time[row["STINT"]].append(row)
    for rep in range(1, 17):
        seq = by_rep[rep]
        ck(f"rep {rep} time coverage", len(seq) == 72 and [(x["STINT"], x["ETINT"]) for x in seq] == [(i * .5, (i + 1) * .5) for i in range(72)])
        ck(f"rep {rep} entity", all(x["UNID"] == "TEACH-UNIT" and x["SID"] == "TEACH-AIR-01" for x in seq))
        count = seq[18]["NSYMO"]
        ck(f"rep {rep} mission window", count in (0, 2, 4, 6, 8) and all(x["NSYMO"] == count for x in seq[16:20]) and all(x["NSYMO"] == 0 for x in seq[:16] + seq[20:]))
        ck(f"rep {rep} terminal ready", seq[-1]["NSYRY"] == seq[-1]["NSYA"] == 12)
        total = totals[rep - 1]
        for key in ("NSYRY", "NSYMA", "NSYMO", "STACC"):
            value = sum((x[key] or 0) * .5 for x in seq) / 36
            ck(f"rep {rep} total {key}", abs(total[key] - value) < 3e-5)
        rep_snaps = [x for x in snaps if x["REPLID"] == rep]
        ck(f"rep {rep} snapshots", [x["SSTIM"] for x in rep_snaps] == [9, 11])
        for snap in rep_snaps:
            corresponding = seq[int(snap["SSTIM"] * 2)]
            for key in ("NSYRY", "NSYMA", "NSYMO", "NSYA"):
                ck(f"rep {rep} snapshot {snap['SSTIM']} {key}", snap[key] == corresponding[key])
    for i, aggregate in enumerate(system):
        members = by_time[i * .5]
        ck(f"bin {i} sixteen members", len(members) == 16 and {r["REPLID"] for r in members} == set(range(1, 17)))
        for key, value in aggregate.items():
            if key not in members[0] or key in {"UNID", "SID", "STINT", "ETINT"} or not isinstance(value, (int, float)):
                continue
            mean = sum((r[key] or 0) for r in members) / 16
            ck(f"bin {i} mean {key}", abs(value - mean) < 3e-5)
    return {"schema": "simlox-j06-system-replication-author-validation/v1", "case_id": "J06", "variant_id": "J06.var02",
            "passed": not differences, "checks": checks, "differences": differences,
            "closure_sha256": sha(RUN / "closure.json"), "enhanced_report_sha256": sha(RUN / "replication-report-raw.json"),
            "counts": {"replications": len(reps), "system_totals": len(totals), "system_time_rows": len(timed), "system_snapshots": len(snaps)},
            "scope": "one System entity, NREPS16 fixed-seed Poisson experiment, TOTAL/TIME/SNAPS at h9/11, 36h; no percentile claim",
            "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
