"""Read-only independent replay of sealed D01.var01 zero-FRT evidence."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "d01-var01-zero-v010-ssh-20261006-01"
OUT = Path(__file__).with_name("independent-verdict.json")
PARENT = CASES / "D01-installed-lru-direct-repair-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d01-lru-v100-ssh-20260929-01"
PINS = {
    "input": (CASE / "native-input.json", "f9b1d2120de85307458dfddd92f69d7fa4bec9dd7bc5ee88c06c99b9cc338786"),
    "parent": (PARENT / "native-input.json", "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"),
    "parent_signoff": (PARENT / "cli-scope-signoff-2026-09-29.md", "e2c567a5db6b1af672fa279b448b36ff43ed68a90c2c529bdf5506ed2cd39832"),
    "parent_closure": (PARENT_RUN / "closure.json", "3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0"),
    "a02_signoff": (CASES / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md", "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e"),
    "h02_signoff": (CASES / "H02-var01-primary-lru-damage-v1.0.0" / "cli-scope-signoff-2026-10-02.md", "2cbf6b91ad08106fe97fd7c928f1c3f0ca2c154228d1b0b15baf7e45ecbebaec"),
    "contract": (CASE / "contract.json", "0817838dd5829e02549c2c036ec528f43db7731c985b1c4bfd59c926f7ad430d"),
    "builder": (CASE / "build.py", "9228d6525a4328c262b212f58a41454244fa3f3c57a65a6d21b55fa8af6e1a1a"),
    "checker": (CASE / "check_roundtrip.py", "7080355a37a7829911408b837f44e108b3a72848a2c0a951554a9316db02d654"),
    "diff_checker": (CASE / "check_parent_diff.py", "5ccd65b58c75f894bf79a1514e1a48649d09a81154c2099563b485794d0bdd44"),
    "validator": (CASE / "validate_native_cli_v011.py", "194d2097e6dd9edabdd7f86c46e7d6516ed0faee7b0bab0afef84bb1a8fab588"),
    "runner_script": (CASE / "run_native_ssh.ps1", "4c6949f26c6ae3c2d102b85bedc9029e26dbb332b10ccb193b393c9abc7c1a4c"),
    "python": (Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a"),
    "simlox_exe": (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    # The native default report contains trailing commas. Preserve raw bytes.
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*(?=[}\]])", "", text))


def table_map(model: dict) -> dict:
    return {table["name"]: table for table in model["model"]["tables"]}


def cells(model: dict) -> dict:
    result = {}
    for name, table in table_map(model).items():
        for i, instance in enumerate(table["instances"]):
            for j, row in enumerate(instance["rows"]):
                assert len(row) == len(table["columns"])
                for column, value in zip(table["columns"], row):
                    key = (name, i, j, column["name"])
                    assert key not in result
                    result[key] = value
    return result


def report_rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    assert len(table["instances"]) == 1
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for row in table["instances"][0]["rows"]]


def near(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), abs_tol=1e-6, rel_tol=0)


def main():
    differences = []
    checks = 0

    def ck(label: str, condition: bool):
        nonlocal checks
        checks += 1
        if not condition:
            differences.append(label)

    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    ck("closure identity", closure["schema"] == "simlox-d01-var01-v010-native-closure/v1" and closure["run_id"] == RUN.name and closure["error"] is None)
    ck("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    ck("SSH queue", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("GUI preserved identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and invocation["gui"]["start_utc"] == "2026-09-28T10:09:56.8261381Z")
    ck("source before after equality", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    for key, (path, digest) in PINS.items():
        ck(f"source {key} bytes", path.is_file() and sha(path) == digest)
        ck(f"source {key} before", closure["source_hashes_before"].get(key) == digest)
        ck(f"source {key} after", closure["source_hashes_after"].get(key) == digest)
    ck("copied input exact", (RUN / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes())
    ck("child 12 raw seals", len(closure["raw"]) == 12)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name} bytes", path.is_file() and path.stat().st_size == seal["bytes"])
        ck(f"raw {name} SHA", path.is_file() and sha(path) == seal["sha256"])
    parent_closure = load(PARENT_RUN / "closure.json")
    ck("parent 12 raw seals", len(parent_closure["raw"]) == 12)
    for name, seal in parent_closure["raw"].items():
        path = PARENT_RUN / name
        ck(f"parent raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])

    steps = load(RUN / "steps.json")
    ck("five ordered stages", [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"])
    for step in steps:
        ck(f"step {step['name']}", step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] is True)
    ck("nonempty simulation output", (RUN / "model.sxo").stat().st_size > 1000)
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("converter exact 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog)
    ck("converter warning identity", re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "2053"] and "Form: Item\nrec 1: (warning #2053) FRT is zero for: TEACH-LRU-01" in runlog.replace("\r\n", "\n"))
    ck("no converter error/notes", not re.search(r"\((?:error|note) #\d+\)", runlog))

    parent, child, exported = (load(PINS["parent"][0]), load(PINS["input"][0]), load(RUN / "roundtrip-raw.json"))
    before, after = cells(parent), cells(child)
    ck("257 shared cell keys", len(before) == len(after) == 257 and before.keys() == after.keys())
    expected = {("ProblemDescription", 0, 0, "PDESC"), ("System", 0, 0, "FRT"), ("Item", 0, 0, "FRT")}
    ck("exact three source cells", {k for k in before if before[k] != after[k]} == expected)
    ck("both FRTs zero", all(before[k] == 300000 and after[k] == 0 for k in expected if k[3] == "FRT"))
    authored = table_map(child)
    native = table_map(exported)
    row_tables = [name for name, table in authored.items() if any(instance["rows"] for instance in table["instances"])]
    ck("18 authored row tables", len(row_tables) == 18)
    for name in row_tables:
        ck(f"roundtrip {name}", authored[name] == native.get(name))
    recorded_roundtrip = load(RUN / "roundtrip-validation.json")
    ck("recorded roundtrip", recorded_roundtrip["passed"] is True and not recorded_roundtrip["differences"] and len(recorded_roundtrip["populated_tables"]) == 18)

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    mission_events = Counter(re.findall(r"(?m)^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> (mission created|mission starting|mission success|mission completed|mission aborted|mission cancelled)", log))
    expected_mission_events = Counter()
    for i, start in enumerate((8, 20, 32)):
        for when, kind in ((start - 1, "mission created"), (start, "mission starting"), (start + 2, "mission success"), (start + 2, "mission completed")):
            expected_mission_events[(str(when), str(i), kind)] = 1
    ck("three exact mission lifecycles", mission_events == expected_mission_events)
    ck("three mission orders", len(re.findall(r"(?m)^Time: [0-9.]+ <TEACH-UNIT> mission ordered: BASIC-MISSION$", log)) == 3)
    ck("one aircraft identity", len(re.findall(r"mission allocates system: <TEACH-AIR-01,0>", log)) == 3 and not re.search(r"mission allocates system: <TEACH-AIR-01,(?!0>)", log))
    ck("no fault or maintenance event", not re.search(r"critical random failure added|non-critical random failure added|subitem failed:|Item demand arrives|Take replacement item|Start repair of item|system SURP task|item DIRP task|Backorder|backorder", log, re.I))
    ck("opening spare ID0", len(re.findall(r"Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>,", log)) == 1)
    ck("no physical stock transition", not re.search(r"Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: (?!1 Items:<TEACH-LRU-01,0,0>,)|Put back replacement item|Delivery with|Stock level decreased", log))
    ck("terminal aircraft ready", "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in log)
    ck("parent positive failure contrast", "critical random failure added" in (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig"))

    report = load_report(RUN / "report-raw.json")
    system, stock, summary = (report_rows(report, name) for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck("72+72 half-hour bins", len(system) == len(stock) == 72)
    ck("summary one success fraction", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSTF"] == 1 and summary[0]["MSUF"] == 1)
    flight = ((8, 10), (20, 22), (32, 34))
    allocated = ((7, 10), (19, 22), (31, 34))
    system_variable = {"STINT", "ETINT", "NSYRY", "NSYA", "NSYMA", "NSYMR", "NSYMO", "FTMO", "STACC"}
    stock_variable = {"STINT", "ETINT", "PNB"}
    for i, (sr, tr) in enumerate(zip(system, stock)):
        a, b = i * 0.5, (i + 1) * 0.5
        ck(f"system grid {i}", near(sr["STINT"], a) and near(sr["ETINT"], b))
        ck(f"stock grid {i}", near(tr["STINT"], a) and near(tr["ETINT"], b))
        prep = int(any(lo - 1 <= a < lo for lo, hi in flight))
        flying = int(any(lo <= a < hi for lo, hi in flight))
        ready = int(not any(lo <= a < hi for lo, hi in allocated))
        ck(f"system mission/ready {i}", all(near(sr[k], v) for k, v in {
            "NSYRY": ready, "NSYA": 1, "NSYMA": prep + flying,
            "NSYMR": prep, "NSYMO": flying, "FTMO": flying, "STACC": flying,
        }.items()))
        ck(f"zero other system metrics {i}", all((v is None or v == 0) for k, v in sr.items() if k not in system_variable and isinstance(v, (int, float, type(None)))))
        ck(f"nominal stock and zero activity {i}", tr["PNB"] == 1 and all((v is None or v == 0) for k, v in tr.items() if k not in stock_variable and isinstance(v, (int, float, type(None)))))
    ck("six flight hours", near(sum(r["FTMO"] * 0.5 for r in system), 6))
    ck("27 ready aircraft hours", near(sum(r["NSYRY"] * 0.5 for r in system), 27))
    ck("36 available aircraft hours", near(sum(r["NSYA"] * 0.5 for r in system), 36))
    ck("terminal ready and no backorder", system[-1]["NSYRY"] == 1 and all(r["NBO"] == 0 for r in stock))

    old = load(CASE / "review" / "author-validation-v011.json")
    new = load(CASE / "review" / "author-validation-v012.json")
    ck("original author false negative preserved", sha(CASE / "review" / "author-validation-v011.json") == "a4606aab12f88fa8523dad68bb6843f03bc42a7bd71b232b63f18c991b5cf9d7" and old["passed"] is False and old["checks"] == 54 and old["differences"] == ["bound validate_native_cli.py"])
    ck("versioned author pass", sha(CASE / "review" / "author-validation-v012.json") == "f1281915af1f6a8b414cae8cbe6a32d38017dd4af33d71dc8596e55401329de2" and new["passed"] is True and new["checks"] == 54 and not new["differences"])
    ck("correction binds launched validator", sha(CASE / "validate_native_cli_v012.py") == "9b4d83cd8605575b1847b1a73b95b4c52d2ead81329ccdbc60733799ea4eac61" and invocation["validator_sha256"] == PINS["validator"][1])

    verdict = {
        "schema": "simlox-d01-var01-v010-independent-postrun/v1",
        "run_id": RUN.name,
        "verdict": "GO_BOUNDED" if not differences else "NO_GO",
        "checks": checks,
        "passed_checks": checks - len(differences),
        "differences": differences,
        "closure_sha256": sha(RUN / "closure.json"),
        "invocation_sha256": sha(RUN / "invocation.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "report_raw_sha256": sha(RUN / "report-raw.json"),
        "scope": "one fixed-seed matched zero-System/Item-FRT control; three successful missions and no observed ordinary fault, demand, repair or backorder",
        "limits": [
            "opening physical LRU ID0 is observed at h0; no later stock transition is logged, so terminal on-hand is inferred from the complete event ledger rather than a terminal stock snapshot",
            "StockTotalResults.PNB is an aggregate report field, not physical on-hand inventory",
            "zero rates were changed together and do not isolate either field",
            "other failure mechanisms, seeds, executable versions, GUI visual behavior and cross-engine parity remain unverified",
        ],
    }
    OUT.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return verdict


if __name__ == "__main__":
    result = main()
    print(f"{result['verdict']} {result['passed_checks']}/{result['checks']}")
    for difference in result["differences"]:
        print("FAIL", difference)
    raise SystemExit(0 if result["verdict"] == "GO_BOUNDED" else 1)
