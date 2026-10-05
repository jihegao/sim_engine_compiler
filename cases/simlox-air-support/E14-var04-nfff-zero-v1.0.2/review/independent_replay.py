"""Independent read-only replay of E14.var04 v1.0.2 import rejection."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
AIR = CASE.parent
REPO = HERE.parents[3]
PARENT = AIR / "E14-var01-02-extra-removal-v1.0.0"
E05 = AIR / "E05-local-repair-reissue-v1.0.0"
V100 = AIR / "E14-var04-nfff-zero-v1.0.0"
V101 = AIR / "E14-var04-nfff-zero-v1.0.1"
PREVIOUS = V101 / "runs/e14-var04-nfff-zero-v101-ssh-20261005-01"
RUN_ID = "e14-var04-nfff-zero-v102-ssh-20261005-01"
RUN = CASE / "runs" / RUN_ID
PARENT_RUN = PARENT / "runs/e14-var01-02-two-sru-panel-v100-ssh-20261005-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
failed: list[str] = []
checks = 0


def check(label: str, good: bool) -> None:
    global checks
    checks += 1
    if not good:
        failed.append(label)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(label: str, path: Path, expected: str) -> None:
    check(label + " exists", path.is_file())
    if path.is_file():
        check(label + " SHA", sha(path.read_bytes()) == expected)


def seal(label: str, path: Path, record: dict) -> None:
    check(label + " exists", path.is_file())
    if path.is_file():
        data = path.read_bytes()
        check(label + " size", len(data) == record["bytes"])
        check(label + " SHA", sha(data) == record["sha256"])


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
source = load(RUN / "input.json")
exported = load(RUN / "roundtrip-raw.json")
parent = load(PARENT / "seed2-extra-input.json")
prior_closure = load(PREVIOUS / "closure.json")
old_preflight = load(V100 / "preflight-failure-20261005-01.json")

check("contract identity", (contract["case_id"], contract["variant_id"], contract["version"], contract["run_id"]) == ("E14", "E14.var04", "1.0.2-candidate", RUN_ID))
check("contract unpublished", contract["publication_state"] == "not_published")
check("old preflight excluded", old_preflight["result"] == "excluded_diagnostic" and old_preflight["native_simlox_child_started"] is False and old_preflight["run_directory_created"] is False)
check("prior run excluded", prior_closure["expected_negative"] is False and prior_closure["error"] == "exact authored-table roundtrip failed")
check("prior run only import/export", [s["name"] for s in load(PREVIOUS / "steps.json")] == ["import", "export"])
check("prior raw count", len(prior_closure["raw"]) == 8)
for name, record in prior_closure["raw"].items():
    seal("prior raw " + name, PREVIOUS / name, record)

prior = contract["previous_excluded"]
for label, path, expected in (
    ("prior closure", PREVIOUS / "closure.json", prior["closure_sha256"]),
    ("prior input", V101 / "native-input.json", prior["input_sha256"]),
    ("prior import log", PREVIOUS / "import.log", prior["import_log_sha256"]),
    ("prior index", V101 / "evidence-index.json", prior["index_sha256"]),
):
    pin(label, path, expected)
check("prior import rejection", len(re.findall(r"Value \(0\) in record: 2, Column: NFFF Table: ItemStructure cannot be imported", (PREVIOUS / "import.log").read_text(encoding="utf-8"))) == 1)
check("prior target erasure", rows(next(t for t in load(PREVIOUS / "roundtrip-raw.json")["model"]["tables"] if t["name"] == "ItemStructure"))[1][6] is None)

accepted = contract["accepted_parent"]
for label, path, expected in (
    ("parent input", PARENT / "seed2-extra-input.json", accepted["input_sha256"]),
    ("parent signoff", PARENT / "cli-scope-signoff-2026-10-05.md", accepted["signoff_sha256"]),
    ("parent local index", PARENT / "evidence-index.json", accepted["evidence_index_sha256"]),
    ("parent closure", PARENT_RUN / "closure.json", accepted["native_closure_sha256"]),
    ("parent event", PARENT_RUN / "seed2-extra.log", accepted["seed2_extra_event_sha256"]),
    ("parent SXO", PARENT_RUN / "seed2-extra.sxo", accepted["seed2_extra_sxo_sha256"]),
    ("E05 input", E05 / "native-input.json", contract["catalog_prerequisite"]["input_sha256"]),
    ("E05 signoff", E05 / "cli-scope-signoff-2026-09-29.md", contract["catalog_prerequisite"]["signoff_sha256"]),
    ("manual", MANUAL, contract["source"]["manual_pdf_sha256"]),
    ("EXE", EXE, contract["source"]["simlox_exe_sha256"]),
):
    pin(label, path, expected)
local_index = (PARENT / "evidence-index.json").read_bytes()
published_index = subprocess.check_output(["git", "show", accepted["evidence_index_published_commit"] + ":cases/simlox-air-support/E14-var01-02-extra-removal-v1.0.0/evidence-index.json"], cwd=REPO)
check("local parent index size", len(local_index) == accepted["evidence_index_local_bytes"])
check("published parent index size", len(published_index) == accepted["evidence_index_published_git_bytes"])
check("published parent index SHA", sha(published_index) == accepted["evidence_index_published_git_sha256"])
check("parent index CRLF/LF relation", local_index.replace(b"\r\n", b"\n") == published_index)

check("child frozen source SHA", sha((CASE / "native-input.json").read_bytes()) == contract["source"]["input_sha256"])
check("copied run input bytes", (RUN / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes())
parent_tables = parent["model"]["tables"]
child_tables = source["model"]["tables"]
check("31 source tables", len(parent_tables) == len(child_tables) == 31)
changed_cells = []


def compare(left, right, path="") -> None:
    if type(left) is not type(right):
        changed_cells.append((path, left, right))
    elif isinstance(left, dict):
        for key in left.keys() | right.keys():
            if key not in left or key not in right:
                changed_cells.append((path + "/" + key, left.get(key), right.get(key)))
            else:
                compare(left[key], right[key], path + "/" + key)
    elif isinstance(left, list):
        if len(left) != len(right):
            changed_cells.append((path + "/length", len(left), len(right)))
        for index, (a, b) in enumerate(zip(left, right)):
            compare(a, b, path + "/" + str(index))
    elif left != right:
        changed_cells.append((path, left, right))


compare(parent, source)
check("sole NFFF delta", changed_cells == [("/model/tables/6/instances/0/rows/1/6", 2.0, 0.0)])
authored_tables = {t["name"]: t for t in child_tables if rows(t)}
exported_tables = {t["name"]: t for t in exported["model"]["tables"]}
check("21 authored row tables", len(authored_tables) == 21)
for name, table in authored_tables.items():
    check("export table present " + name, name in exported_tables)
    if name not in exported_tables:
        continue
    actual = exported_tables[name]
    check("column equality " + name, table["columns"] == actual["columns"])
    expected_rows = json.loads(json.dumps(rows(table)))
    if name == "ItemStructure":
        check("authored invalid target", expected_rows[1][0] == "TEACH-SRU-01" and expected_rows[1][4] == 4 and expected_rows[1][6] == 0)
        expected_rows[1][6] = None
    check("row equality " + name, expected_rows == rows(actual))
check("roundtrip check passed", load(RUN / "roundtrip-check.json")["passed"] is True)

check("closure identity", closure["schema"] == "simlox-e14-var04-negative-closure/v1" and closure["run_id"] == RUN_ID)
check("closure source stability", closure["source_hashes_before"] == closure["source_hashes_after"])
check("closure accepted negative", closure["expected_negative"] is True and closure["error"] is None and closure["publication_state"] == "not_published")
source_paths = {
    "contract": CASE / "contract.json", "input": CASE / "native-input.json", "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py", "parent_index_verifier": CASE / "verify_parent_index.py",
    "parent_input": PARENT / "seed2-extra-input.json", "parent_signoff": PARENT / "cli-scope-signoff-2026-10-05.md",
    "parent_index": PARENT / "evidence-index.json", "parent_closure": PARENT_RUN / "closure.json",
    "parent_event": PARENT_RUN / "seed2-extra.log", "parent_sxo": PARENT_RUN / "seed2-extra.sxo",
    "e05_input": E05 / "native-input.json", "e05_signoff": E05 / "cli-scope-signoff-2026-09-29.md",
    "prior_closure": PREVIOUS / "closure.json", "prior_import": PREVIOUS / "import.log",
    "prior_index": V101 / "evidence-index.json", "exe": EXE, "manual": MANUAL,
    "runner": CASE / "run_native_ssh.ps1", "python": PYTHON,
}
check("20 source pins", len(source_paths) == len(closure["source_hashes_before"]) == 20)
for name, path in source_paths.items():
    pin("run source " + name, path, closure["source_hashes_before"][name])
check("frozen runner revision", closure["source_hashes_before"]["runner"] == "d045c66e5f6e05e1552c5065e032938f17aac73f18fd425e1054bce9d93eec36")

pin("invocation", RUN / "invocation.json", closure["invocation_sha256"])
check("invocation source", invocation["source_hashes_before"] == closure["source_hashes_before"])
check("SSH0 identity", invocation["run_id"] == RUN_ID and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
check("protected GUI", invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("two guarded steps", [step["name"] for step in steps] == ["import", "export"])
for step in steps:
    check("step successful " + step["name"], step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None)
check("no calc step", all("-calc" not in step["arguments"] for step in steps))
check("raw count", len(closure["raw"]) == 8)
for name, record in closure["raw"].items():
    seal("raw " + name, RUN / name, record)
check("run file set", {f.name for f in RUN.iterdir() if f.is_file()} == set(closure["raw"]) | {"closure.json", "invocation.json"})

import_log = (RUN / "import.log").read_text(encoding="utf-8")
diagnostics = re.findall(r"Value \([^)]*\) in record: \d+, Column: \S+ Table: \S+ cannot be imported[^\r\n]*", import_log)
check("sole import rejection", len(diagnostics) == 1 and diagnostics[0].startswith("Value (0) in record: 2, Column: NFFF Table: ItemStructure cannot be imported"))
check("outcome diagnostic", outcome["import_diagnostic"] == diagnostics[0])
check("outcome acceptance", outcome["import_export"] == "target_nfff_erased_only" and outcome["expected_negative"] is True and outcome["error"] is None)
check("no calc/output", all(not (RUN / name).exists() for name in ("model.sxo", "model.log", "run.log", "selected-report-raw.json", "report.json")))

verdict = {
    "schema": "simlox-e14-var04-independent-import-replay/v1",
    "verdict": "GO_BOUNDED_IMPORT_NEGATIVE" if not failed else "NO_GO",
    "passed": not failed,
    "checks_passed": checks - len(failed),
    "checks_total": checks,
    "failures": failed,
    "preflight_v100_excluded": True,
    "converter_hypothesis_v101_excluded": True,
    "prior_closure_sha256": sha((PREVIOUS / "closure.json").read_bytes()),
    "new_closure_sha256": sha((RUN / "closure.json").read_bytes()),
    "prior_raw_seals": len(prior_closure["raw"]),
    "new_raw_seals": len(closure["raw"]),
    "observed": "One JSON-import diagnostic rejects ItemStructure rec2 TEACH-SRU-01 NFFF0 and exported NFFF is null; 20 other authored tables and all remaining ItemStructure cells match. No calculation or simulation output.",
    "limits": "One traditional SRU row at RRF4/NFFF0, import/export only. No converter result, physical behavior, general lower-bound/default rule, GUI-only or cross-engine claim.",
}
(HERE / "independent-verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"verdict": verdict["verdict"], "checks": f"{checks-len(failed)}/{checks}", "failures": failed}, ensure_ascii=False))
raise SystemExit(0 if not failed else 1)
