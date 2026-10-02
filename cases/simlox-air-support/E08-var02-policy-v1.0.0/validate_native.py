"""Author replay of sealed E08.var02 policy runs and station ledgers."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "runs"
PARENT = ROOT / "E08-var01-immediate-lateral-v1.0.2"
POLICIES = ("extended", "adjacent")
STATIONS = (("base-01", "base01"), ("base-02", "base02"), ("depot", "depot"))
REPORTS = ("ItemResults", "SystemResults", "StockTotalResults", "MissionResults", "ResultSummary")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for instance in table["instances"] for r in instance["rows"]]


def report(path):
    return {t["name"]: t for t in parse_native(path)["report"]["tables"]}


def main():
    checks = []

    def need(ok, name):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    contract = parse_native(HERE / "contract.json")
    need(sha(PARENT / "on-input.json") == contract["parent_source_sha256"], "accepted immediate parent source")
    need(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "exact source diff fingerprint")
    need(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["manual_pdf_sha256"] and
         sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["dictionary_sha256"], "installed manual and dictionary")
    base = {t["name"]: t for t in parse_native(PARENT / "on-input.json")["model"]["tables"]}
    on = report(PARENT / "runs/e08-on-base01-report-v102-ssh-20261002-01/item-report-raw.json")
    off = {station: report(PARENT / f"runs/e08-off-{old}-report-v102-ssh-20261002-01/item-report-raw.json")
           for station, old in STATIONS}
    total_raw = 0

    for policy in POLICIES:
        source = HERE / f"{policy}-input.json"
        need(sha(source) == contract[f"{policy}_source_sha256"], f"{policy} source fingerprint")
        child = {t["name"]: t for t in parse_native(source)["model"]["tables"]}
        need(set(base) == set(child) and {n for n in base if base[n] != child[n]} ==
             {"LateralSupport", "ProblemDescription"} and
             rows(child["LateralSupport"])[0]["LSRUL"] == policy.upper(), f"{policy} rule-only delta")
        need(rows(child["Control"])[0]["ENLAT"] == "Y" and
             rows(child["Item"])[0]["TRACK"] == "Y" and
             len(populated(parse_native(source))) == 24, f"{policy} original support and tracking")
        native = RUNS / f"e08-{policy}-v100-ssh-20261002-01"
        inv, closure = (parse_native(native / n) for n in ("invocation.json", "closure.json"))
        need(closure["error"] is None and closure["invocation_sha256"] == sha(native / "invocation.json") and
             inv["input_sha256"] == sha(source) == sha(native / "input.json"), f"{policy} native invocation closure")
        need(closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"] and
             inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and
             inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
             inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{policy} guard and frozen sources")
        need(len(closure["raw"]) == 12 and all((native / n).stat().st_size == m["bytes"] and
             sha(native / n) == m["sha256"] for n, m in closure["raw"].items()), f"{policy} 12 native raw seals")
        total_raw += len(closure["raw"])
        steps = parse_native(native / "steps.json")
        need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
             all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{policy} five native steps")
        roundtrip = parse_native(native / "roundtrip-validation.json")
        need(roundtrip["passed"] and len(roundtrip["populated_tables"]) == 24 and
             "Input conversion completed. Errors: 0," in (native / "run.log").read_text(encoding="utf-8-sig"),
             f"{policy} exact roundtrip and zero conversion errors")
        log = (native / "model.log").read_text(encoding="utf-8-sig")
        for marker in ("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support check, cancelled due to free items in chain",
                       "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
                       "Time: 10  transport task 0 created from <DEPOT-01,0> to <BASE-01,0>",
                       "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
                       "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1",
                       "Time: 11.3333  system SURP task 0 on <TEACH-AIR-01,0> completed"):
            need(marker in log, f"{policy} event {marker[:55]}")
        need("Take replacement item <TEACH-LRU-01,0,1> from stock" not in log and
             "from <BASE-02,0> to <BASE-01,0>" not in log, f"{policy} no peer physical draw")
        for station, old in STATIONS:
            selected_run = RUNS / f"e08-{policy}-{station}-report-v100-ssh-20261002-01"
            ri, rc = (parse_native(selected_run / n) for n in ("invocation.json", "closure.json"))
            need(rc["error"] is None and rc["invocation_sha256"] == sha(selected_run / "invocation.json") and
                 len(rc["raw"]) == 2 and all((selected_run / n).stat().st_size == m["bytes"] and
                 sha(selected_run / n) == m["sha256"] for n, m in rc["raw"].items()),
                 f"{policy} {station} report seals")
            total_raw += len(rc["raw"])
            need(ri["session_id"] == 0 and "sshd.exe" in ri["ssh_ancestor_names"] and
                 ri["gui"]["pid"] == 13340 and
                 ri["source_closure_sha256"] == sha(native / "closure.json") and
                 ri["source_hashes_before"]["sxo"] == sha(native / "model.sxo"),
                 f"{policy} {station} sealed SXO report guard")
            result = report(selected_run / "item-report-raw.json")
            need(len(rows(result["ItemResults"])) == 72, f"{policy} {station} 72 item bins")
            for name in REPORTS:
                need(result[name] == off[station][name], f"{policy} {station} {name} equals accepted ordinary control")
            if station == "base-01":
                item = {r["STINT"]: r for r in rows(result["ItemResults"])}
                system = {r["STINT"]: r for r in rows(result["SystemResults"])}
                need([item[t]["NBO"] for t in (9.5, 10, 10.5, 11, 11.5)] == [0, 1, 1, 0, 0] and
                     all(item[t]["STOHA"] == 0 for t in (10, 10.5, 11)),
                     f"{policy} one-hour base backorder and physical issue")
                need(system[11]["NSYRY"] < 1 and system[11.5]["NSYRY"] == 1,
                     f"{policy} readiness after h11 and before h11.5")
                need(result["ItemResults"] != on["ItemResults"] and
                     result["SystemResults"] != on["SystemResults"],
                     f"{policy} differs from accepted immediate lateral control")
    need(total_raw == 36, "36 sealed local raw files")
    out = {"schema": "simlox-e08-var02-policy-author-replay/v1", "passed": True,
           "checks": checks, "check_count": len(checks), "sealed_raw_files": total_raw,
           "decision": "GO_bounded_EXTENDED_ADJACENT_choose_free_ordinary_depot"}
    path = HERE / "author-validation.json"
    encoded = (json.dumps(out, indent=2) + "\n").encode()
    if path.exists():
        assert path.read_bytes() == encoded, "frozen author validation differs"
    else:
        path.write_bytes(encoded)
    print(json.dumps({"checks": len(checks), "sha256": sha(path), "sealed_raw_files": total_raw}))


if __name__ == "__main__":
    main()
