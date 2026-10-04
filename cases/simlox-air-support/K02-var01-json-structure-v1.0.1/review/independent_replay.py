"""Independent, read-only replay of the two K02.var01 CLI probes."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASES = HERE.parent
PARENT = CASES / "K01-var04-parent-child-model-diff-v1.0.0"
PARENT_RUN = PARENT / "runs/k01-var04-duration-v100-ssh-20261004-01"
OLD = CASES / "K02-var01-json-structure-v1.0.0/runs"
RUNS = {
    "inactive2": HERE / "runs/k02-var01-inactive2-v101-ssh-20261004-01",
    "named": HERE / "runs/k02-var01-named-v101-ssh-20261004-01",
}
OLD_CLOSURES = {
    "inactive": "f747cf95b1577bdebdbb27a14556ec1cd77a674d65ef986818d0fdeede209eee",
    "named": "46462267656e8550e998e99b4f60aba910c3483441b5fbc88284dc2850c80a94",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # The installed SIMLOX report exporter emits trailing commas.
        out = []
        quoted = escape = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == ",":
                j = i + 1
                while j < len(raw) and raw[j].isspace():
                    j += 1
                if j == len(raw) or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def table_map(doc, root):
    tables = doc[root]["tables"]
    result = {table["name"]: table for table in tables}
    check(len(result) == len(tables), f"{root} table names unique")
    return result


def report_tables(path):
    return table_map(load(path), "report")


def source_paths():
    return {
        "inactive2_input": HERE / "inactive2-input.json",
        "named_input": HERE / "named-input.json",
        "contract": HERE / "contract.json",
        "exact_diff": HERE / "exact-diff.json",
        "accepted_parent": PARENT / "native-input.json",
        "accepted_parent_closure": PARENT_RUN / "closure.json",
        "accepted_parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "accepted_parent_report": PARENT_RUN / "report-raw.json",
        "accepted_parent_log": PARENT_RUN / "model.log",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "build.py": HERE / "build.py",
        "check_roundtrip.py": HERE / "check_roundtrip.py",
        "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }


def main():
    contract = load(HERE / "contract.json")
    parent = table_map(load(PARENT / "native-input.json"), "model")
    check(sha(PARENT / "native-input.json") == contract["accepted_parent"]["input_sha256"], "parent source pin")
    check(sha(PARENT_RUN / "closure.json") == contract["accepted_parent"]["closure_sha256"], "parent closure pin")
    for arm, expected in OLD_CLOSURES.items():
        old_run = OLD / f"k02-var01-{arm}-v100-ssh-20261004-01"
        check(sha(old_run / "closure.json") == expected, f"excluded v100 {arm} closure pin")
    parent_report = report_tables(PARENT_RUN / "report-raw.json")
    parent_log_sha = sha(PARENT_RUN / "model.log")
    outcomes = {}

    for arm, run in RUNS.items():
        prefix = arm + ": "
        source = HERE / f"{arm}-input.json"
        check(sha(source) == contract["inputs_sha256"][arm], prefix + "contract source pin")
        check(sha(source) == sha(run / "input.json"), prefix + "run input seal")
        closure = load(run / "closure.json")
        invocation = load(run / "invocation.json")
        check(closure["arm"] == invocation["arm"] == arm, prefix + "arm identity")
        check(closure["run_id"] == invocation["run_id"] == run.name, prefix + "run identity")
        check(sha(run / "invocation.json") == closure["invocation_sha256"], prefix + "invocation seal")
        check(closure["source_hashes_before"] == closure["source_hashes_after"], prefix + "source stable")
        check(closure["source_hashes_before"] == invocation["source_hashes_before"], prefix + "invocation source map")
        check(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), prefix + "contract SHA")
        for key, path in sorted(source_paths().items()):
            check(path.is_file() and sha(path) == closure["source_hashes_before"][key], prefix + key + " source SHA")
        check(len(closure["raw"]) == 12, prefix + "12 sealed raw files")
        for name, seal in sorted(closure["raw"].items()):
            path = run / name
            check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], prefix + name + " raw seal")
        check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, prefix + "SSH session0")
        check("sshd.exe" in invocation["ssh_ancestor_names"], prefix + "sshd ancestry")
        check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", prefix + "mutex")
        check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, prefix + "GUI identity")
        steps = load(run / "steps.json")
        check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], prefix + "five steps")
        for step in steps[:4]:
            check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], prefix + step["name"] + " completed/GUI")
        check(steps[4]["status"] == ("completed" if arm == "named" else "failed"), prefix + "checker classification")
        check(steps[4]["exit_code"] == (0 if arm == "named" else 1), prefix + "checker exit")
        check(closure["error"] == (None if arm == "named" else "roundtrip checker exit=1"), prefix + "closure outcome")
        log = (run / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, prefix + "converter totals")
        check(re.findall(r"\(warning #(\d+)\)", log) == ["108", "126"], prefix + "warning codes")
        check(not re.search(r"\((?:error|notice) #", log), prefix + "no errors/notices")
        check((run / "model.sxo").stat().st_size > 4, prefix + "valid SXO")

        src = table_map(load(source), "model")
        exported = table_map(load(run / "roundtrip-raw.json"), "model")
        check(list(src) == list(parent), prefix + "same source table names/order")
        check({name for name in src if src[name] != parent[name]} == {"ProblemDescription", "Station"}, prefix + "two-table parent delta")
        check(set(src).issubset(exported), prefix + "all source tables exported")
        for name, tab in sorted(src.items()):
            check(tab["columns"] == exported[name]["columns"], prefix + name + " columns")
            if any(instance["rows"] for instance in tab["instances"]) and name != "Station":
                check(tab["instances"] == exported[name]["instances"], prefix + name + " authored instances")
        op = src["OperationProfile"]
        dtim = [col["name"] for col in op["columns"]].index("DTIM")
        check(op["instances"][0]["rows"][0][dtim] == exported["OperationProfile"]["instances"][0]["rows"][0][dtim] == 0.3333333333333333, prefix + "binary64 precision")
        s = src["Station"]["instances"]
        e = exported["Station"]["instances"]
        width = len(src["Station"]["columns"])
        check(width == 21, prefix + "Station schema width")
        if arm == "named":
            check(len(s) == 2 and [x["instance_name"] for x in s] == ["K02-BASE", "K02-AUX"], prefix + "two named source instances")
            check(len(e) == 3 and e[0] == {"instance_name": "", "rows": [[None] * width]}, prefix + "sole native empty default")
            check(e[1:] == s, prefix + "named instances exact")
        else:
            check(len(s) == len(e) == 1 and s[0].get("inactive_rows") == [2], prefix + "one-based index2 source")
            check(s[0]["rows"][0] == e[0]["rows"][0] and s[0]["rows"][0][0] == "BASE-01", prefix + "BASE-01 retained")
            check(s[0]["rows"][1][0] == "K02-INACTIVE", prefix + "inactive source row")
            check(e[0]["rows"][1] == [None] * width and "inactive_rows" not in e[0], prefix + "inactive row/marker lost")
            check(e[0] != s[0], prefix + "lossless fidelity fails")

        check(sha(run / "model.log") == parent_log_sha, prefix + "byte-identical parent event log")
        events = (run / "model.log").read_text(encoding="utf-8-sig")
        for marker in ("Time: 7 <TEACH-UNIT> mission ordered", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 3", "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", "Time: 11 <TEACH-AIR-01,BASE-01,0> System ready"):
            check(marker in events, prefix + marker)
        reports = report_tables(run / "report-raw.json")
        check(list(reports) == list(parent_report), prefix + "report table names/order")
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check(reports[name] == parent_report[name], prefix + name + " parent parity")
        for name in ("SystemResults", "StockTotalResults"):
            rows = reports[name]["instances"][0]["rows"]
            check(len(rows) == 72, prefix + name + " 72 bins")
            offset = 2 if name == "SystemResults" else 0
            for i, row in enumerate(rows):
                check(row[offset] == i * 0.5 and row[offset + 1] == (i + 1) * 0.5, prefix + name + f" interval {i}")
        sr = reports["SystemResults"]
        cols = [c["name"] for c in sr["columns"]]
        rows = sr["instances"][0]["rows"]
        check(rows[-1][cols.index("NSYRY")] == 1 and rows[-1][cols.index("NSYA")] == 1, prefix + "terminal ready one")
        check(sum(row[cols.index("NSYMO")] for row in rows) * 0.5 == 3, prefix + "three aircraft flight hours")
        stock = reports["StockTotalResults"]
        check(all(row[[c["name"] for c in stock["columns"]].index("NBO")] == 0 for row in stock["instances"][0]["rows"]), prefix + "zero stock backorder bins")
        outcomes[arm] = {
            "closure_sha256": sha(run / "closure.json"),
            "report_sha256": sha(run / "report-raw.json"),
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "classification": "GO: bounded named-instance CLI canonicalization" if arm == "named" else "NO-GO: inactive-row lossless fidelity; valid one-based-index diagnostic",
        }

    verdict = {
        "schema": "independent-k02-var01-v101-readonly/v1",
        "passed": not failures,
        "verdict": "GO named / NO-GO inactive2 lossless fidelity" if not failures else "NO-GO reviewer discrepancies",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "arms": outcomes,
        "limits": ["The index-2 result concerns this two-row Station instance only.", "The named result permits exactly one native-added empty default instance; it does not establish general multi-instance or GUI fidelity.", "Native report parity is for one fixed seed/model; v1.0.0 runs remain excluded diagnostics."],
    }
    target = HERE / "review/independent-verdict.json"
    target.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict["verdict"], "checks": [verdict["checks_passed"], checks], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
