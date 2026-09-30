"""Independent read-only A15 report-only SOACC replay; standard library only."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import struct

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "A15-custom-utilization-v1.0.0"
RUNS = CASE / "runs"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
SETTINGS = RUNS / "report-settings" / "operation-remapped-enabled.sxs"
SOURCE_IDS = {"per-hour": "a15-per-hour-20260930-01", "per-mission": "a15-per-mission-20260930-01"}
RUN_IDS = {"per-hour": "a15-soacc-hour-remapped-20261001-01", "per-mission": "a15-soacc-mission-remapped-20261001-01"}
SOURCE_SXO = {"per-hour": "696c3ec35a3cb0bf6bb96cb784fa80eb265b60e94c28995f860e50ec2c418575", "per-mission": "fd7dd4c9da531965a94d3b6f214ee21c0aca43540bf18af2190d9aeb4cb72197"}
SOURCE_CLOSURE = {"per-hour": "0a2f40c02a40b4006df58fae17b2fd2a264d99ea8a2af1537f585f986ae9eddc", "per-mission": "eca691d0ca3ecafa3c306b9988e756346952b4eccf41fc1259fff4dfc4ab3999"}
PIN = {"settings": "c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7", "default": "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d", "exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "builder": "4b8bb25189f62f34fc253cd4a6874de11cb69c9a0e07577c52782f0e28e267d7", "runner": "29e3aa528ac11647839796f51249fad9144c70c075880eb59ceae5a3121e62b1"}


class Audit:
    def __init__(self) -> None:
        self.n = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.n += 1
        if not condition:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quote = escape = False
    for i, ch in enumerate(raw):
        if quote:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                quote = False
        elif ch == '"':
            quote = True
            out.append(ch)
        elif ch == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(ch)
    return json.loads("".join(out))


def tables(document: dict, root: str) -> dict[str, dict]:
    result = {}
    for table in document[root]["tables"]:
        if table["name"] in result:
            raise ValueError("duplicate table " + table["name"])
        result[table["name"]] = table
    return result


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def near(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-5)


def verify_source_settings(a: Audit) -> dict:
    actual = {"settings": sha(SETTINGS), "default": sha(DEFAULT), "exe": sha(EXE), "builder": sha(CASE / "make_report_settings.py"), "runner": sha(CASE / "report_existing_sxo_ssh.ps1")}
    for name, value in PIN.items():
        a.check(actual[name] == value, f"source {name} SHA")
    original, remapped = DEFAULT.read_bytes(), SETTINGS.read_bytes()
    a.check(len(original) == len(remapped), "settings length preserved")
    diffs = [i for i, (x, y) in enumerate(zip(original, remapped)) if x != y]
    a.check(len(diffs) == 12, "settings twelve changed bytes")
    # Eight one-byte index remaps and four N -> Y compact flag values, no other bytes.
    a.check(sum(original[i:i+2] == b"N\x00" and remapped[i:i+2] == b"Y\x00" for i in diffs) == 4, "four compact flags enabled")
    a.check([(original[i], remapped[i]) for i in diffs[:8]] == [(62,66),(63,67),(64,68),(65,69),(66,62),(67,63),(68,64),(69,65)], "eight descriptor index remaps")
    labels = (b"Include Extendable Mission IT", b"Include Extendable Mission IG", b"Include Extendable Mission TT", b"Include Extendable Mission TG", b"Include Mission Operation IT", b"Include Mission Operation TT", b"Include Accum Mission Operation IT", b"Include Accum Mission Operation TT")
    for label in labels:
        a.check(original.count(label) == remapped.count(label) == 2, f"settings label retained {label.decode()}")
    a.check(all(x in ("per-hour", "per-mission") for x in SOURCE_IDS), "source pair defined")
    return actual


def verify_parent(a: Audit, variant: str) -> tuple[Path, dict]:
    directory = PARENT / "runs" / SOURCE_IDS[variant]
    closure = load(directory / "closure.json")
    a.check(sha(directory / "closure.json") == SOURCE_CLOSURE[variant], f"{variant} parent closure SHA")
    a.check(closure["error"] is None and closure["raw"]["model.sxo"]["sha256"] == SOURCE_SXO[variant], f"{variant} parent closure valid")
    for name, entry in closure["raw"].items():
        path = directory / name
        a.check(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"{variant} parent raw seal {name}")
    a.check(sha(directory / "model.sxo") == SOURCE_SXO[variant], f"{variant} source SXO SHA")
    source = tables(native(directory / "input.json"), "model")
    op = records(source["OperationParameter"])
    utilization = records(source["MissionTypeUtilization"])
    a.check(len(op) == len(utilization) == 1 and op[0]["OPID"] == "KM", f"{variant} custom KM source")
    want = (60, "1/HOUR") if variant == "per-hour" else (120, "1/MISSION")
    a.check(utilization[0]["UTIL"] == want[0] and utilization[0]["UTILU"] == want[1], f"{variant} source utilization")
    log = (directory / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    a.check(bool(re.search(r"Time: 8 .*mission starting", log)) and bool(re.search(r"Time: 10 .*mission success", log)), f"{variant} parent 8-10 success")
    return directory, tables(native(directory / "report-raw.json"), "report")


def verify_report(a: Audit, variant: str, run: Path, parent_report: dict) -> dict:
    report = tables(native(run / "report-raw.json"), "report")
    expected_tables = {"ProblemDescription", "ResultSummary", "MissionOperationAccumulated", "MissionOperationTotalAccumulated", "MissionOperation", "MissionOperationTotal", "SystemResults", "StockTotalResults"}
    a.check(set(report) == expected_tables, f"{variant} selected report table set")
    for name in ("ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"):
        a.check([c["name"] for c in report[name]["columns"]] == [c["name"] for c in parent_report[name]["columns"]] and rows(report[name]) == rows(parent_report[name]), f"{variant} parent result rows {name}")
    summary = records(report["ResultSummary"])[0]
    a.check(summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["STMF"] == 1, f"{variant} report horizon and success")
    a.check(len(rows(report["SystemResults"])) == len(rows(report["StockTotalResults"])) == 72, f"{variant} 72 underlying bins")
    acc = records(report["MissionOperationAccumulated"])
    instant = records(report["MissionOperation"])
    a.check(len(acc) == len(instant) == 128, f"{variant} operation row counts")
    for name, data in (("accumulated", acc), ("instant", instant)):
        by_op = {opid: [r for r in data if r["OPID"] == opid] for opid in ("KM", "OPHOURS")}
        a.check(len(by_op["KM"]) == 56 and len(by_op["OPHOURS"]) == 72, f"{variant} {name} OPID bins")
        for opid, sequence in by_op.items():
            starts = [r["STINT"] for r in sequence]
            a.check(starts == [i/2 for i in range(16 if opid == "KM" else 0, 72)] and all(near(r["ETINT"]-r["STINT"], .5) for r in sequence), f"{variant} {name} {opid} aligned intervals")
            for r in sequence:
                begin = r["STINT"]
                if name == "instant":
                    expected = (60 if opid == "KM" else 1) if 8 <= begin < 10 else 0
                else:
                    expected = (60 if opid == "KM" else 1)*max(0, min(begin + .5, 10)-8)
                a.check(near(r["SOACC"], expected), f"{variant} {name} {opid} h{begin:g}")
    total_acc = {r["OPID"]: r["SOACC"] for r in records(report["MissionOperationTotalAccumulated"])}
    total = {r["OPID"]: r["SOACC"] for r in records(report["MissionOperationTotal"])}
    a.check(set(total_acc) == set(total) == {"KM", "OPHOURS"}, f"{variant} two operation totals")
    a.check(near(total_acc["KM"], 120) and near(total_acc["OPHOURS"], 2), f"{variant} accumulated totals")
    a.check(near(total["KM"], 120/36) and near(total["OPHOURS"], 2/36), f"{variant} MissionOperationTotal 36-hour denominator")
    a.check(near(sum(r["SOACC"]*(r["ETINT"]-r["STINT"]) for r in instant if r["OPID"] == "KM"), 120), f"{variant} KM rate integral")
    return {"table_names": sorted(report), "accumulated": total_acc, "per_horizon_hour": total, "report_sha256": sha(run / "report-raw.json")}


def verify_success(a: Audit, variant: str, source: Path, source_hashes: dict, parent_report: dict) -> dict:
    directory = RUNS / RUN_IDS[variant]
    invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    a.check(invocation["run_id"] == closure["run_id"] == RUN_IDS[variant] and invocation["variant"] == closure["variant"] == variant, f"{variant} report run identity")
    a.check(invocation["source_run_id"] == SOURCE_IDS[variant], f"{variant} parent identity")
    a.check(closure["invocation_sha256"] == sha(directory / "invocation.json") and closure["error"] is None and closure["exit_code"] == 0, f"{variant} invocation/clean closure")
    a.check(invocation["source_hashes"] == closure["source_hashes"], f"{variant} source hash snapshot consistent")
    expected = {"sxo": SOURCE_SXO[variant], "source_closure": SOURCE_CLOSURE[variant], **source_hashes}
    a.check(invocation["source_hashes"] == expected, f"{variant} all source/runtime hashes")
    a.check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} SSH provenance")
    a.check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} mutex")
    a.check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]), f"{variant} GUI provenance")
    command = invocation["command"]
    a.check(str(source / "model.sxo") in command and str(SETTINGS) in command and " -report -rpts " in command and " -rjexport " in command, f"{variant} explicit report-only command")
    a.check(set(closure["raw"]) == {"report-raw.json", "report-export.log"}, f"{variant} report-only raw manifest")
    for name, entry in closure["raw"].items():
        path = directory / name
        a.check(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"{variant} raw {name} SHA/bytes")
    log = (directory / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
    a.check("Report completed" in log and "Export completed!" in log, f"{variant} report/export completion")
    a.check(not any(word in log for word in ("could not be loaded", "Reverting to default settings", "Failed to open file")), f"{variant} no settings fallback")
    result = verify_report(a, variant, directory, parent_report)
    result["run_id"] = RUN_IDS[variant]
    result["closure_sha256"] = sha(directory / "closure.json")
    return result


def verify_probe(a: Audit, run_id: str, fallback: bool, operation_tables: bool) -> dict:
    directory = RUNS / run_id
    invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    a.check(closure["invocation_sha256"] == sha(directory / "invocation.json"), f"probe {run_id} invocation seal")
    for name, entry in closure["raw"].items():
        path = directory / name
        a.check(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"probe {run_id} raw {name}")
    log = (directory / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
    has_fallback = "Reverting to default settings" in log
    a.check(has_fallback == fallback, f"probe {run_id} fallback status")
    table_names = set(tables(native(directory / "report-raw.json"), "report"))
    a.check(("MissionOperationAccumulated" in table_names) == operation_tables, f"probe {run_id} selected operation table status")
    a.check(closure["error"] is not None if run_id.endswith("relocated-20261001-01") else True, f"probe {run_id} reported failure")
    return {"run_id": run_id, "fallback": has_fallback, "tables": sorted(table_names), "closure_sha256": sha(directory / "closure.json")}


def main() -> int:
    a = Audit()
    try:
        sources = verify_source_settings(a)
        parent = {variant: verify_parent(a, variant) for variant in SOURCE_IDS}
        success = {variant: verify_success(a, variant, parent[variant][0], sources, parent[variant][1]) for variant in SOURCE_IDS}
        hour_tab = tables(native(RUNS / RUN_IDS["per-hour"] / "report-raw.json"), "report")
        mission_tab = tables(native(RUNS / RUN_IDS["per-mission"] / "report-raw.json"), "report")
        a.check(set(hour_tab) == set(mission_tab) and all(hour_tab[name] == mission_tab[name] for name in hour_tab if name != "ProblemDescription"), "semantic equivalence all report tables except description")
        a.check((parent["per-hour"][0] / "model.log").read_bytes() == (parent["per-mission"][0] / "model.log").read_bytes(), "accepted parent event logs equal")
        probes = [verify_probe(a, "a15-soacc-hour-diagnostic-20261001-01", True, False),
                  verify_probe(a, "a15-soacc-hour-relocated-20261001-01", True, True),
                  verify_probe(a, "a15-soacc-hour-descriptor-20261001-01", False, False)]
        result = {"schema": "simlox-a15-operation-report-independent/v1", "passed": not a.failures,
                  "verdict": "bounded_GO" if not a.failures else "NO_GO", "check_count": a.n, "failures": a.failures,
                  "script_sha256": sha(Path(__file__)), "source_hashes": sources, "success": success, "excluded_probes": probes,
                  "scope": "Report-only re-export of two accepted A15 SXOs with one local remapped settings file; observed SOACC 120 user-defined KM units over one successful 8-10 mission",
                  "limits": ["KM is a user label, not measured physical distance", "MissionOperationTotal is normalized over 36-hour report horizon, not the accumulated 120", "No partial mission, failure/PM clock, cross-engine, or GUI visual behavior claim"]}
    except Exception as exc:
        result = {"schema": "simlox-a15-operation-report-independent/v1", "passed": False, "verdict": "NO_GO", "check_count": a.n,
                  "failures": a.failures + [f"review exception: {type(exc).__name__}: {exc}"], "script_sha256": sha(Path(__file__))}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "verdict", "check_count", "failures")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
