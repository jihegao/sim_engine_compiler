"""Validate the fresh native J03.var05 PFAC-sum rejection run."""
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate(run: Path) -> dict:
    errors: list[str] = []
    contract = load(HERE / "contract.json")
    diff = load(HERE / "probe-diff.json")
    arm = "pfac-sum"
    run_id = contract["expected_observation"]["run_id"]
    if run.name != run_id:
        errors.append("accepted run identity")
    for name in ("input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "steps.json", "invocation.json", "closure.json"):
        if not (run / name).is_file():
            errors.append(f"missing raw artifact: {name}")
    if errors:
        return {"passed": False, "differences": errors}
    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    if (closure.get("schema"), closure.get("arm"), closure.get("run_id"), closure.get("state")) != (
        "simlox-j03-var05-pfac-sum-closure/v1", arm, run_id, "native_steps_complete"
    ):
        errors.append("closure identity/state")
    if closure.get("invocation_sha256") != sha(run / "invocation.json"):
        errors.append("invocation seal")
    if (invocation.get("schema"), invocation.get("arm"), invocation.get("run_id")) != (
        "simlox-j03-var05-pfac-sum-invocation/ssh-cli-v1", arm, run_id
    ):
        errors.append("invocation identity")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("session-0 SSH ancestry")
    if invocation.get("gui_pid") != 13340 or invocation.get("gui_start_utc") != "2026-09-28T10:09:56.8261381Z" or invocation.get("queue_mutex") != "Global\\SimloxIssue18NativeQueue":
        errors.append("GUI/mutex identity")
    expected_source = {
        "contract_sha256": HERE / "contract.json",
        "builder_sha256": HERE / "build.py",
        "runner_sha256": HERE / "run_native_ssh.ps1",
        "validator_sha256": HERE / "validate_pfac_acceptance.py",
    }
    for key, path in expected_source.items():
        if invocation.get(key) != sha(path):
            errors.append(f"invocation source seal: {key}")
    source_files = {
        "contract.json": HERE / "contract.json",
        "probe-diff.json": HERE / "probe-diff.json",
        "build.py": HERE / "build.py",
        "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
        "validate_pfac_acceptance.py": HERE / "validate_pfac_acceptance.py",
        "pfac-sum-input.json": HERE / "pfac-sum-input.json",
        "cycle-input.json": HERE / "cycle-input.json",
        "parent-input.json": build.PARENTS[arm][0],
        "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    }
    if set(closure.get("post_source_sha256", {})) != set(source_files):
        errors.append("source seal file set")
    for name, path in source_files.items():
        if closure.get("post_source_sha256", {}).get(name) != sha(path):
            errors.append(f"source seal mismatch: {name}")
    raw = closure.get("raw", {})
    required_raw = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "steps.json"}
    if set(raw) != required_raw:
        errors.append("raw seal file set")
    for name, record in raw.items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw seal mismatch: {name}")
    input_sha = contract["arms"][arm]["input_sha256"]
    if sha(run / "input.json") != input_sha or invocation.get("input_sha256") != input_sha or diff["arms"][arm]["input_sha256"] != input_sha:
        errors.append("input fingerprint")
    outputs, expected_diff = build.build()
    if (HERE / "pfac-sum-input.json").read_bytes() != outputs["pfac-sum-input.json"] or (HERE / "probe-diff.json").read_bytes() != expected_diff:
        errors.append("builder source mismatch")
    source, exported = load(run / "input.json"), load(run / "roundtrip-raw.json")
    expected_rows = [
        {"DISTID": "PREP-DET", "PFAC": 0.5, "BASED": "<DETERM>", "PARAM1": 0.25, "PARAM2": None, "PARAM3": None, "NOTE": None},
        {"DISTID": "PREP-DET", "PFAC": 0.4, "BASED": "<DETERM>", "PARAM1": 0.75, "PARAM2": None, "PARAM3": None, "NOTE": None},
    ]
    for label, document in (("source", source), ("export", exported)):
        if build.rows(build.table(document, "TimeDistributions")) != expected_rows:
            errors.append(f"{label} PFAC rows")
        prep = build.rows(build.table(document, "MissionPreparation"))
        if len(prep) != 1 or prep[0].get("DURN") != 0.5 or prep[0].get("DURND") != "PREP-DET":
            errors.append(f"{label} preparation reference")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append("business roundtrip")
    steps = load(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc"] or any(step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps):
        errors.append("native steps/GUI")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    errors_found = re.findall(r"\(error #(\d+)\) ([^\r\n]+)", log)
    warning_codes = Counter(re.findall(r"\(warning #(\d+)\)", log))
    if errors_found != [("265", "The sum of PFAC does not add up to 1.0")]:
        errors.append("converter error code/message")
    if warning_codes != Counter({"108": 1, "126": 1}) or not re.search(r"Input conversion completed\. Errors: 1, Warnings: 2, Notes: 0", log):
        errors.append("converter summary/warnings")
    if (run / "model.sxo").stat().st_size != 4 or (run / "model.log").exists() or (run / "report-raw.json").exists():
        errors.append("rejected model yielded simulation/report content")
    return {
        "schema": "simlox-j03-var05-pfac-sum-accepted-rejection-validation/v1",
        "case_id": "J03", "variant_id": "J03.var05", "version": "1.0.0",
        "run_id": run_id, "passed": not errors, "differences": errors,
        "converter_error_code": 265, "sxo_bytes": (run / "model.sxo").stat().st_size,
        "roundtrip": roundtrip, "publication_state": "not_published",
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_pfac_acceptance.py RUN_DIRECTORY")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
