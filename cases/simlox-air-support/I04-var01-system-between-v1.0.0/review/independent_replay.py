"""Independent read-only replay of the sealed I04 system BETWEEN pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "i04-var01-system-between-v100-ssh-20261005-01"
ARMS = ("control", "between")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, result: bool) -> None:
    CHECKS.append((label, bool(result)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check("run identity", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("clean closure", closure["error"] is None and outcome["error"] is None)
check("invocation SHA", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
check("SSH0 and sshd ancestry", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("host native mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("eight ordered steps", [s["name"] for s in steps] == [f"{a}_{phase}" for a in ARMS for phase in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step success and GUI preserved {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None)

parent = CASES / "A17-multi-unit-group-v1.0.0"
a02 = CASES / "A02-single-aircraft-repeated-missions"
d03 = CASES / "D03-calendar-pm-v1.0.0"
d09 = CASES / "D09-var01-calendar-vs-operational-v1.0.0"
source_paths = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "parent_input": parent / "native-input.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-09-29.md",
    "a02_input": a02 / "native-input.json",
    "a02_signoff": a02 / "cli-scope-signoff-2026-09-29.md",
    "d03_input": d03 / "native-input.json",
    "d03_signoff": d03 / "cli-scope-signoff-2026-09-30.md",
    "d09_input": d09 / "native-input-calendar.json",
    "d09_signoff": d09 / "cli-scope-signoff-2026-10-02.md",
    "control": CASE / "control-input.json",
    "between": CASE / "between-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check("complete source set", set(source_paths) == set(closure["source_hashes_before"]))
for key, before in closure["source_hashes_before"].items():
    check(f"source stable {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    check(f"source SHA {key}", source_paths[key].is_file() and sha(source_paths[key]) == before)
pins = {
    "parent_input": contract["dependency"]["input_sha256"],
    "parent_signoff": contract["dependency"]["signoff_sha256"],
    "builder": contract["builder_sha256"],
    "manual": contract["manual"]["sha256"],
    "dictionary": contract["manual"]["dictionary_sha256"],
}
for key in ("a02_input", "a02_signoff", "d03_input", "d03_signoff", "d09_input", "d09_signoff"):
    pins[key] = contract["instructional_prerequisites"][key[:3].upper() + key[3:] + "_sha256"]
for key, expected in pins.items():
    check(f"contract dependency pin {key}", expected == closure["source_hashes_before"][key])
check("22 raw seals", len(closure["raw"]) == 22)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    if path.is_file():
        check(f"raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", sha(path) == seal["sha256"])

models = {arm: tables(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
parent_model = tables(load(source_paths["parent_input"]), "model")
check("34 tables and 16 populated per arm", all(len(model) == 34 and sum(bool(rows(t)) for t in model.values()) == 16 for model in models.values()))
for arm, model in models.items():
    check(f"A17-derived source tables {arm}", {name for name in parent_model if parent_model[name] != model[name]} == {"ProblemDescription", "OperationProfile"} and set(model) - set(parent_model) == {"SystemTransfer"})
    check(f"two h8/h20 mission records {arm}", [row["STIM"] for row in rows(model["OperationProfile"])] == [8, 20])
    check(f"contract input SHA {arm}", sha(CASE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
    check(f"run-local input copy {arm}", sha(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
check("paired source only transfer and description", {name for name in models["control"] if models["control"][name] != models["between"][name]} == {"SystemTransfer", "ProblemDescription"})
control_transfer = rows(models["control"]["SystemTransfer"])
between_transfer = rows(models["between"]["SystemTransfer"])
check("control all-null transfer placeholder", len(control_transfer) == 1 and all(value is None for value in control_transfer[0].values()))
check("BETWEEN row with null TFPRI", between_transfer == [{"UFID": "TEACH-UNIT", "UTID": "TEACH-UNIT-2", "SID": "TEACH-AIR-01", "TFTIME": 8.5, "TFQTY": 1, "TFDT": 0.5, "TFPRI": None, "NOTE": None}])

observed = {}
for arm in ARMS:
    model = models[arm]
    exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, table in model.items():
        original = rows(table)
        if not original:
            continue
        check(f"roundtrip table present {arm}/{name}", name in exported)
        if name not in exported:
            continue
        native = exported[name]
        check(f"roundtrip exact columns {arm}/{name}", [(c["name"], c["datatype"]) for c in table["columns"]] == [(c["name"], c["datatype"]) for c in native["columns"]])
        returned = rows(native)
        check(f"roundtrip row count {arm}/{name}", len(original) == len(returned))
        for i, (authored_row, returned_row) in enumerate(zip(original, returned)):
            for field, value in authored_row.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{i}/{field}", returned_row.get(field) == value)
    check(f"transfer null field roundtrip {arm}", rows(exported["SystemTransfer"]) == (control_transfer if arm == "control" else between_transfer))
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"zero-error conversion {arm}", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter)
    check(f"classified warning codes {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108", "126"])
    check(f"outcome complete {arm}", outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0] and outcome["warning_codes"][arm] == ["108", "126"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
    starts = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-GROUP,0,0,\d+> mission starting", log)]
    successes = [float(t) for t in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-GROUP,0,0,\d+> mission success:", log)]
    check(f"h8 and h20 two-aircraft formations {arm}", starts == [8, 20] and successes == [10, 22] and len(re.findall(r"mission allocates system: <TEACH-AIR-01,[01]>", log)) == 4)
    check(f"no mission abort or cancellation {arm}", "mission aborted:" not in log and "mission cancelled:" not in log)
    if arm == "between":
        check("same physical ID leaves source at h10", "Time: 10 <TEACH-UNIT at <BASE-01,0>> system transfered out: <TEACH-AIR-01,0>." in log)
        check("same physical ID arrives target at h10.5", "Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in: <TEACH-AIR-01,0>." in log)
        check("exactly one transfer each direction", len(re.findall(r"system transfered out:", log)) == len(re.findall(r"system transfered in:", log)) == 1)
        check("h20 mission allocates both at target", "Time: 19 <BASIC-MISSION,TEACH-GROUP,0,0,1> mission allocates system: <TEACH-AIR-01,0>" in log and "Time: 19 <TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT-2 at <BASE-02,0>>" in log)
    else:
        check("control no physical transfer", "system transfered" not in log)
    ready = {"TEACH-UNIT": set(), "TEACH-UNIT-2": set()}
    no_duplicate = True
    for aircraft, direction, unit in re.findall(r"<TEACH-AIR-01,([01])> nbr ready (increased|decreased) at unit: <(TEACH-UNIT(?:-2)?) at", log):
        if direction == "increased":
            ready[unit].add(aircraft)
        else:
            ready[unit].discard(aircraft)
        no_duplicate &= not (ready["TEACH-UNIT"] & ready["TEACH-UNIT-2"])
    check(f"no ready-pool identity duplicated {arm}", no_duplicate)
    check(f"terminal per-unit ready roster {arm}", ready == ({"TEACH-UNIT": set(), "TEACH-UNIT-2": {"0", "1"}} if arm == "between" else {"TEACH-UNIT": {"0"}, "TEACH-UNIT-2": {"1"}}))
    rt = tables(native_report(RUN / f"{arm}-report-raw.json"), "report")
    check(f"four report tables {arm}", set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    system, stock = rows(rt["SystemResults"]), rows(rt["StockTotalResults"])
    check(f"72 half-hour system/stock bins {arm}", all(len(group) == 72 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(group)) for group in (system, stock)))
    by_time = {row["STINT"]: row for row in system}
    check(f"in-transit h10 aggregate bin {arm}", by_time[10]["NSYRY"] == (1 if arm == "between" else 2) and by_time[10.5]["NSYRY"] == 2)
    check(f"terminal two systems ready {arm}", system[-1]["NSYRY"] == 2 and len(ready["TEACH-UNIT"] | ready["TEACH-UNIT-2"]) == 2)
    check(f"two mission summary success {arm}", len(rows(rt["ResultSummary"])) == 1 and rows(rt["ResultSummary"])[0]["MSUF"] == 1)
    check(f"no failures or stock demands {arm}", sum(row["NFAIL"] or 0 for row in system) == 0 and all(all((row[field] or 0) == 0 for field in ("NBO", "NBOU", "NDF", "NDD", "NDR")) for row in stock))
    observed[arm] = {"mission_starts": starts, "mission_successes": successes, "ready_count_h10_bin": by_time[10]["NSYRY"], "ready_count_h10_5_bin": by_time[10.5]["NSYRY"], "terminal_roster": {key: sorted(value) for key, value in ready.items()}, "terminal_ready": system[-1]["NSYRY"]}

failed = [label for label, result in CHECKS if not result]
verdict = {"schema": "simlox-i04-var01-independent-replay/v1", "run_id": RUN.name, "verdict": "GO_BOUNDED" if not failed else "NO_GO", "checks": len(CHECKS), "passed": len(CHECKS) - len(failed), "failed": failed, "observed": observed, "limits": "One fixed seed, two units at two bases, one system type, one requested BETWEEN transfer with TFDT0.5, and two group missions. Native log shows the physical movement at h10/h10.5; the h8.5 request is source-frozen rather than separately logged. No IN/OUT, priority effect, PM retention or general transfer claim."}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in verdict.items() if k != "observed"}, indent=2))
if failed:
    raise SystemExit(1)
