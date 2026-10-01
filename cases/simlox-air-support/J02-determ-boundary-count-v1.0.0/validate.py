"""Replay one accepted J02 deterministic or boundary-count native run."""
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
import build  # noqa: E402

RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
SOURCE_NAMES = {"contract.json", "build.py", "exact-diff.json", "run_native_ssh.ps1",
                "validate.py", "parent-input.json", "database-dictionary.txt", "manual.pdf"} | {
                    f"{arm}-input.json" for arm in build.ARMS}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def source_paths(contract: dict) -> dict[str, Path]:
    return {name: HERE / name for name in SOURCE_NAMES if name not in {
        "parent-input.json", "database-dictionary.txt", "manual.pdf"}} | {
        "parent-input.json": build.PARENT,
        "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
        "manual.pdf": Path(contract["source"]["manual"]),
    }


def validate(run: Path, arm: str) -> dict:
    errors: list[str] = []
    if arm not in build.ARMS:
        raise ValueError(f"unknown arm {arm}")
    contract = load(HERE / "contract.json")
    spec = contract["arms"][arm]
    for name in RAW | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing artifact: {name}")
    if errors:
        return {"arm": arm, "run_id": run.name, "passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if "-probe-" in run.name or not run.name.endswith("-accepted-20261001-01"):
        errors.append("run ID is not a fresh accepted run")
    if invocation.get("schema") != "simlox-j02-determ-boundary-invocation/ssh-cli-v1" or invocation.get("arm") != arm or invocation.get("run_id") != run.name or invocation.get("seed") != spec["seed"]:
        errors.append("invocation identity differs")
    if closure.get("schema") != "simlox-j02-determ-boundary-closure/v1" or closure.get("arm") != arm or closure.get("run_id") != run.name or closure.get("state") != "native_steps_complete":
        errors.append("closure identity/state differs")
    if invocation.get("input_sha256") != spec["input_sha256"] or closure.get("input_sha256") != spec["input_sha256"] or sha(run / "input.json") != spec["input_sha256"]:
        errors.append("input fingerprint differs")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []) or invocation.get("queue_mutex") != "Global\\SimloxIssue18NativeQueue":
        errors.append("SSH session or mutex provenance differs")
    if invocation.get("gui_pid") != 13340 or invocation.get("gui_start_utc") != "2026-09-28T10:09:56.8261381Z":
        errors.append("preserved GUI identity differs")
    if closure.get("invocation_sha256") != sha(run / "invocation.json") or set(closure.get("raw", {})) != RAW:
        errors.append("closure raw/invocation set differs")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw seal differs: {name}")
    paths = source_paths(contract)
    expected_sources = {name: sha(path) for name, path in paths.items()}
    if set(expected_sources) != SOURCE_NAMES or closure.get("post_source_sha256") != expected_sources:
        errors.append("post-source fingerprints differ")
    for key, name in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                      ("validator_sha256", "validate.py"), ("runner_sha256", "run_native_ssh.ps1")):
        if invocation.get(key) != expected_sources[name]:
            errors.append(f"invocation source differs: {key}")
    if expected_sources["parent-input.json"] != contract["parent_input_sha256"] or expected_sources["exact-diff.json"] != contract["exact_diff_sha256"]:
        errors.append("contract parent/diff fingerprint differs")
    if expected_sources["database-dictionary.txt"] != contract["source"]["database_dictionary_sha256"] or expected_sources["manual.pdf"] != contract["source"]["manual_sha256"]:
        errors.append("manual or dictionary fingerprint differs")
    outputs, diff = build.build()
    for name, raw in {**outputs, "exact-diff.json": diff}.items():
        if (HERE / name).read_bytes() != raw:
            errors.append(f"builder output differs: {name}")
    steps = load(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"] or any(
            step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps):
        errors.append("native steps or GUI guard differ")
    source, exported = load(run / "input.json"), load(run / "roundtrip-raw.json")
    expected_integer = [{"DISTID": "COUNTD", "PFAC": 1.0, "BASED": "<DETERM>",
                         "PARAM1": float(spec["count"]), "PARAM2": None, "PARAM3": None, "NOTE": None}]
    for label, doc in (("source", source), ("export", exported)):
        if build.rows(build.table(doc, "IntegerDistributions")) != expected_integer:
            errors.append(f"{label} integer row differs")
        profile = build.rows(build.table(doc, "OperationProfile"))
        if len(profile) != 1 or any(profile[0].get(key) != value for key, value in
                                    {"STIM": 8, "ITYPE": "RANDOM", "IQTYD": "COUNTD", "IPER": 0,
                                     "IDISP": "EQUIDIST", "DTIM": 1 / 3}.items()):
            errors.append(f"{label} operation profile differs")
        if build.rows(build.table(doc, "SystemDeployment"))[0].get("QTYPS") != spec["deployed_aircraft"]:
            errors.append(f"{label} deployment differs")
        control = build.rows(build.table(doc, "Control"))
        if len(control) != 1 or control[0].get("RSEED") != str(spec["seed"]) or control[0].get("NREPS") != 1:
            errors.append(f"{label} seed/repetition differs")
        mission = build.rows(build.table(doc, "MissionType"))[0]
        if any(mission.get(key) != value for key, value in {"NOS": 2, "MNOS": 2, "DURN": 2}.items()):
            errors.append(f"{label} formation differs")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"business roundtrip differs: {roundtrip['changed']!r}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or int(conversion[1]) != 0 or warnings != Counter({"108": 1, "126": 1, "211": 1}):
        errors.append(f"converter summary/warnings differ: {dict(warnings)}")
    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    mission = r"<BASIC-MISSION,TEACH-UNIT,0,0,(\d+)>"
    def events(pattern: str) -> list[re.Match[str]]:
        rex = re.compile(pattern)
        return [match for line in lines if (match := rex.match(line))]
    activations = [(float(m[1]), int(m[2]), int(m[3])) for m in events(rf"^Time:\s*([\d.eE+\-]+) {mission} mission activated, systems requested: (\d+)$")]
    allocations = [(float(m[1]), int(m[2]), int(m[3])) for m in events(rf"^Time:\s*([\d.eE+\-]+) {mission} mission allocates system: <TEACH-AIR-01,(\d+)>$")]
    starts = [(float(m[1]), int(m[2]), [int(x) for x in re.findall(r"<TEACH-AIR-01,(\d+)>", m[3])])
              for m in events(rf"^Time:\s*([\d.eE+\-]+) {mission} mission starting, duration: 2 : (.*)$")]
    successes = [(float(m[1]), int(m[2])) for m in events(rf"^Time:\s*([\d.eE+\-]+) {mission} mission success:")]
    completions = [(float(m[1]), int(m[2]), [int(x) for x in re.findall(r"<TEACH-AIR-01,(\d+)>", m[3])])
                   for m in events(rf"^Time:\s*([\d.eE+\-]+) {mission} mission completed: (.*)$")]
    cancellations = [(float(m[1]), int(m[2])) for m in events(rf"^Time:\s*([\d.eE+\-]+) {mission} mission cancelled:")]
    count, successes_expected = spec["count"], spec["successes"]
    ids = range(1, count + 1)
    if activations != [(7.0, n, 2) for n in ids]:
        errors.append(f"activation demand differs: {activations!r}")
    if allocations != [(7.0, n, aircraft) for n in range(1, successes_expected + 1)
                       for aircraft in (2 * n - 2, 2 * n - 1)]:
        errors.append(f"allocation or aircraft identity differs: {allocations!r}")
    if starts != [(8.0, n, [2 * n - 2, 2 * n - 1]) for n in range(1, successes_expected + 1)]:
        errors.append(f"mission starts differ: {starts!r}")
    if successes != [(10.0, n) for n in range(1, successes_expected + 1)] or completions != [
            (10.0, n, [2 * n - 2, 2 * n - 1]) for n in range(1, successes_expected + 1)]:
        errors.append("mission success/completion differs")
    expected_cancel = [(8.33333, 4)] if arm == "four-six" else []
    if len(cancellations) != len(expected_cancel) or any(abs(a[0] - b[0]) > 1e-4 or a[1] != b[1] for a, b in zip(cancellations, expected_cancel)):
        errors.append(f"mission cancellation differs: {cancellations!r}")
    if any(" mission aborted:" in line for line in lines):
        errors.append("unexpected mission abort")
    for phrase, parsed in ((" mission activated, systems requested:", activations),
                           (" mission allocates system:", allocations),
                           (" mission starting, duration:", starts),
                           (" mission completed:", completions), (" mission cancelled:", cancellations)):
        if sum(phrase in line for line in lines) != len(parsed):
            errors.append(f"unparsed event type: {phrase}")
    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    fraction = successes_expected / count if count else 0
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": fraction, "MSUF": fraction}.items()):
        errors.append("ResultSummary differs")
    system, stock = native.table_rows(report, "SystemResults"), native.table_rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        errors.append(f"System/Stock bin count differs: {len(system)}/{len(stock)}")
    flight_hours = 0.0
    for index, row in enumerate(system):
        assigned = 2 * successes_expected if 14 <= index < 20 else 0
        operating = 2 * successes_expected if 16 <= index < 20 else 0
        if any(row.get(key) != value for key, value in
               {"STINT": index * 0.5, "ETINT": (index + 1) * 0.5,
                "NSYA": spec["deployed_aircraft"], "NSYRY": spec["deployed_aircraft"] - assigned,
                "NSYMA": assigned, "NSYMO": operating,
                "NSYMR": 2 * successes_expected if 14 <= index < 16 else 0}.items()):
            errors.append(f"system occupancy bin {index} differs")
        if abs(float(row.get("FTMO") or 0) - operating / spec["deployed_aircraft"]) > 1e-6:
            errors.append(f"flight fraction bin {index} differs")
        if any(row.get(key) != 0 for key in ("NFAIL", "NPMT", "NSYMP", "NSYMC", "NSYMT", "NSYMS")):
            errors.append(f"unrelated system mechanism bin {index}")
        flight_hours += float(row.get("NSYMO") or 0) * 0.5
    for index, row in enumerate(stock):
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5 or row.get("PNB") != 1:
            errors.append(f"stock bin {index} bounds/position differ")
        if any(row.get(key) != 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
            errors.append(f"unexpected stock demand bin {index}")
    if abs(flight_hours - 4 * successes_expected) > 2e-4 or (system and (system[-1].get("NSYRY") != spec["deployed_aircraft"] or system[-1].get("NSYMA") != 0)):
        errors.append("flight hours or terminal readiness differs")
    return {"case_id": "J02", "variant_id": spec["variant_id"], "arm": arm, "run_id": run.name,
            "passed": not errors, "differences": errors, "activated": len(activations), "starts": len(starts),
            "successes": len(successes), "cancellations": cancellations, "flight_hours": flight_hours,
            "roundtrip": roundtrip, "publication_state": "not_published"}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate.py RUN_DIRECTORY ARM")
    result = validate(Path(sys.argv[1]), sys.argv[2])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
