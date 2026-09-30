"""Read-only validation of the two sealed A15 Mission Operation reports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A15-custom-utilization-v1.0.0"
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
SETTINGS = HERE / "runs" / "report-settings" / "operation-remapped-enabled.sxs"
RUNS = {
    "per-hour": (
        "a15-per-hour-20260930-01", "a15-soacc-hour-remapped-20261001-01",
        "696c3ec35a3cb0bf6bb96cb784fa80eb265b60e94c28995f860e50ec2c418575",
        "0a2f40c02a40b4006df58fae17b2fd2a264d99ea8a2af1537f585f986ae9eddc",
    ),
    "per-mission": (
        "a15-per-mission-20260930-01", "a15-soacc-mission-remapped-20261001-01",
        "fd7dd4c9da531965a94d3b6f214ee21c0aca43540bf18af2190d9aeb4cb72197",
        "eca691d0ca3ecafa3c306b9988e756346952b4eccf41fc1259fff4dfc4ab3999",
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(condition: bool, message: str, checks: list[str]) -> None:
    if not condition:
        raise AssertionError(message)
    checks.append(message)


def table_rows(tables: dict, name: str) -> list:
    table = tables[name]
    return [row for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks: list[str] = []
    check(sha(DEFAULT) == "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d", "installed default fingerprint", checks)
    check(sha(SETTINGS) == "c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7", "report settings fingerprint", checks)
    raw_default, raw_settings = DEFAULT.read_bytes(), SETTINGS.read_bytes()
    check(len(raw_default) == len(raw_settings), "settings length unchanged", checks)
    check(sum(a != b for a, b in zip(raw_default, raw_settings)) == 12, "exactly eight descriptor indices and four flags changed", checks)
    results = {}
    for variant, (source_id, report_id, sxo_sha, source_closure_sha) in RUNS.items():
        source = PARENT / "runs" / source_id
        run = HERE / "runs" / report_id
        closure = read_json(run / "closure.json")
        invocation = read_json(run / "invocation.json")
        check(sha(source / "model.sxo") == sxo_sha, f"{variant} source SXO", checks)
        check(sha(source / "closure.json") == source_closure_sha, f"{variant} source closure", checks)
        check(closure["error"] is None and closure["exit_code"] == 0, f"{variant} successful report exit", checks)
        check(invocation["variant"] == variant and invocation["source_run_id"] == source_id, f"{variant} invocation identity", checks)
        check(invocation["source_hashes"] == closure["source_hashes"], f"{variant} source hashes repeated in closure", checks)
        check(invocation["source_hashes"]["settings"] == sha(SETTINGS), f"{variant} settings source hash", checks)
        check(invocation["source_hashes"]["sxo"] == sxo_sha, f"{variant} SXO source hash", checks)
        check(invocation["source_hashes"]["source_closure"] == source_closure_sha, f"{variant} parent closure hash", checks)
        check(invocation["source_hashes"]["builder"] == sha(HERE / "make_report_settings.py"), f"{variant} builder hash", checks)
        check(invocation["source_hashes"]["runner"] == sha(HERE / "report_existing_sxo_ssh.ps1"), f"{variant} runner hash", checks)
        check(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation closure", checks)
        for name, item in closure["raw"].items():
            path = run / name
            check(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{variant} raw {name} closure", checks)
        check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} session-0 SSH evidence", checks)
        check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} GUI identity evidence", checks)
        check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"{variant} queue evidence", checks)
        log = (run / "report-export.log").read_text(encoding="utf-8-sig")
        check("Report completed" in log and "Export completed" in log, f"{variant} completed log", checks)
        check("could not be loaded" not in log and "Reverting to default" not in log, f"{variant} no settings fallback", checks)
        tables = {t["name"]: t for t in read_json(run / "report-raw.json")["report"]["tables"]}
        names = ("MissionOperation", "MissionOperationTotal", "MissionOperationAccumulated", "MissionOperationTotalAccumulated")
        check(all(name in tables for name in names), f"{variant} four Mission Operation tables", checks)
        for name in names:
            check("SOACC" in [c["name"] for c in tables[name]["columns"]], f"{variant} {name} SOACC column", checks)
        accumulated = [r for r in table_rows(tables, "MissionOperationAccumulated") if r[2] == "KM"]
        interval = [r for r in table_rows(tables, "MissionOperation") if r[2] == "KM"]
        total_acc = [r for r in table_rows(tables, "MissionOperationTotalAccumulated") if r[2] == "KM"]
        total_avg = [r for r in table_rows(tables, "MissionOperationTotal") if r[2] == "KM"]
        check(len(accumulated) == len(interval) == 56, f"{variant} 56 report bins", checks)
        check([(r[3], r[4], r[5]) for r in accumulated if 8 <= r[3] < 10] == [(8, 8.5, 30), (8.5, 9, 60), (9, 9.5, 90), (9.5, 10, 120)], f"{variant} cumulative KM 30/60/90/120", checks)
        check([(r[3], r[4], r[5]) for r in interval if 8 <= r[3] < 10] == [(8, 8.5, 60), (8.5, 9, 60), (9, 9.5, 60), (9.5, 10, 60)], f"{variant} mission KM rate 60", checks)
        check(len(total_acc) == 1 and total_acc[0][3] == 120, f"{variant} total accumulated KM 120", checks)
        check(len(total_avg) == 1 and abs(total_avg[0][3] - 120 / 36) < 1e-6, f"{variant} total average denominator 36 hours", checks)
        results[variant] = {name: table_rows(tables, name) for name in names}
    check(results["per-hour"] == results["per-mission"], "all Mission Operation rows equal across variants", checks)
    print(json.dumps({"schema": "simlox-a15-custom-operation-author-validation/v1", "decision": "GO_bounded_full_mission_exposure", "checks": checks, "check_count": len(checks), "limits": ["one system and one completed two-hour mission", "partial missions, per-aircraft fleet aggregation, failure and PM exposure, and cross-engine parity unverified"]}, indent=2))


if __name__ == "__main__":
    main()
