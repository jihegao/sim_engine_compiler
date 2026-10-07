"""Read-only provenance and amendment audit for C02.var01 v1.0.1."""

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
SIBLING = HERE.parent
OLD = SIBLING / "C02-var01-personnel-zero-v1.0.0"
ROOT = HERE.parents[2]
OLD_DATA = json.loads((OLD / "contract.json").read_text(encoding="utf-8"))
NEW_DATA = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
FAILURES = []
CHECKS = 0


def check(value, label):
    global CHECKS
    CHECKS += 1
    if not value:
        FAILURES.append(label)


def seal(path, record, label):
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        check(False, f"{label}: {exc}")
        return
    check(len(raw) == record["bytes"], label + " size")
    check(hashlib.sha256(raw).hexdigest() == record["sha256"], label + " hash")


def differences(left, right, prefix=""):
    if type(left) is not type(right):
        yield prefix
    elif isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            path = prefix + "." + key
            if key not in left or key not in right:
                yield path
            else:
                yield from differences(left[key], right[key], path)
    elif isinstance(left, list):
        if len(left) != len(right):
            yield prefix + ".length"
        for index, (a, b) in enumerate(zip(left, right)):
            yield from differences(a, b, f"{prefix}[{index}]")
    elif left != right:
        yield prefix


def native_json(path):
    """Ignore native trailing commas without changing quoted string bytes."""
    source = path.read_text(encoding="utf-8")
    output = []
    quoted = False
    escaped = False
    for index, character in enumerate(source):
        if quoted:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
            output.append(character)
        elif character == ",":
            lookahead = index + 1
            while lookahead < len(source) and source[lookahead].isspace():
                lookahead += 1
            if lookahead >= len(source) or source[lookahead] not in "]}":
                output.append(character)
        else:
            output.append(character)
    return json.loads("".join(output))


def main():
    expected = {
        "contract.json": (48041, "e8cce2aeae398f8e725365ab7472b0a7a92b9681cc63299e581d642e76ef9d12"),
        "README.md": (1610, "e3423baddeb80d6c9bea94a83f8acfc6eadb7b816646d5dbcbe1d44055d5e00e"),
    }
    for name, (size, digest) in expected.items():
        seal(HERE / name, {"bytes": size, "sha256": digest}, "v101 " + name)
    check(NEW_DATA["version"] == "1.0.1", "version 1.0.1")
    check(NEW_DATA["ownership"]["sole_new_run_id"] == "c02-var01-v101-personnel0-ssh-20261007-01", "new reserved ID")
    check(not (HERE / "native-input.json").exists(), "no input yet")
    check(not (HERE / "runs").exists(), "no run yet")
    check(NEW_DATA["accepted_evidence"] == OLD_DATA["accepted_evidence"], "accepted evidence identical to v100")
    check(NEW_DATA["source_design"] == OLD_DATA["source_design"], "source design identical to v100")
    check(NEW_DATA["installed"] == OLD_DATA["installed"], "installed pins identical to v100")
    check(NEW_DATA["catalog"] == OLD_DATA["catalog"], "catalog pins identical to v100")
    check(NEW_DATA["execution_boundary"] == OLD_DATA["execution_boundary"], "execution gates identical to v100")
    check(NEW_DATA["negative_checks"] == OLD_DATA["negative_checks"], "negative checks identical to v100")
    check(NEW_DATA["exclusions"] == OLD_DATA["exclusions"], "limits identical to v100")
    for name in ("converter_and_roundtrip", "physical", "numeric_comparison"):
        check(NEW_DATA["prospective_hypotheses"][name] == OLD_DATA["prospective_hypotheses"][name], name + " unchanged")
    old_report = dict(OLD_DATA["prospective_hypotheses"]["report"])
    new_report = dict(NEW_DATA["prospective_hypotheses"]["report"])
    old_report.pop("child_summary")
    new_report.pop("child_summary")
    new_report.pop("summary_field_rule")
    check(old_report == new_report, "all other report rules unchanged")
    report_path = Path(NEW_DATA["accepted_evidence"]["C02_parent"]["accepted_runs"][0]["local_run_dir"]) / "report-raw.json"
    report = native_json(report_path)["report"]
    summary = next(t for t in report["tables"] if t["name"] == "ResultSummary")
    columns = [c["name"] for c in summary["columns"]]
    expected_columns = ["NREP", "RTILW", "RTIUP", "MTMF", "RSMTMF", "MSTF", "RSMSTF", "MSUF", "RSMSUF", "STMF", "RSSTMF"]
    check(columns == expected_columns, "sealed native 11-field order")
    values = NEW_DATA["prospective_hypotheses"]["report"]["child_summary"]
    check(list(values) == columns, "new expected map exactly names/orders 11 columns")
    check(list(values.values()) == [1, 0, 36, 0, 0, 0, 0, 0, 0, 0, 0], "new expected values")
    check(len([c for c in columns if c.startswith("RSM") or c == "RSSTMF"]) == 4, "four relative-variation fields")
    excluded = NEW_DATA["excluded_v100"]
    check(excluded["decision"] == "NO_GO_CONTRACT", "v100 NO_GO retained")
    for record in excluded["files"]:
        seal(SIBLING / record["path"], record, "excluded " + record["path"])
    old_audit = OLD / "review" / "independent_contract_audit.py"
    result = subprocess.run(["C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe", str(old_audit)], cwd=ROOT, capture_output=True, text=True)
    check(result.returncode == 0, "old pin auditor exits zero")
    if result.returncode == 0:
        old_result = json.loads(result.stdout)
        check(old_result == {"checks": 433, "decision": "PASS", "failures": []}, "old 433-pin audit still passes")
    print(json.dumps({"checks": CHECKS, "failures": FAILURES, "decision": "PASS" if not FAILURES else "FAIL", "changed_paths": list(differences(OLD_DATA, NEW_DATA))}, sort_keys=True))


if __name__ == "__main__":
    main()
