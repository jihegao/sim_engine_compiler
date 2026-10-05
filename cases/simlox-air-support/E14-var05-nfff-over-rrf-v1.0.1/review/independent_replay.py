"""Independent read-only replay of the E14.var05 calc-only negative case.

This checker reads frozen sources and sealed runs; it never invokes SIMLOX.
"""

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
OLD = AIR / "E14-var05-nfff-over-rrf-v1.0.0"
PARENT = AIR / "E14-var01-02-extra-removal-v1.0.0"
E05 = AIR / "E05-local-repair-reissue-v1.0.0"
OLD_RUN_ID = "e14-var05-nfff-over-rrf-v100-ssh-20261005-01"
RUN_ID = "e14-var05-nfff-over-rrf-v101-calc-ssh-20261005-01"
OLD_RUN = OLD / "runs" / OLD_RUN_ID
RUN = CASE / "runs" / RUN_ID
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
failures: list[str] = []
checks = 0


def check(label: str, condition: bool) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def digest(path: Path) -> tuple[int, str]:
    raw = path.read_bytes()
    return len(raw), hashlib.sha256(raw).hexdigest()


def seal(label: str, path: Path, record: dict) -> None:
    check(label + " exists", path.is_file())
    if path.is_file():
        size, sha = digest(path)
        check(label + " size", size == record["bytes"])
        check(label + " sha", sha == record["sha256"])


def pin(label: str, path: Path, sha: str) -> None:
    check(label + " exists", path.is_file())
    if path.is_file():
        check(label + " sha", digest(path)[1] == sha)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def row_table(document: dict, name: str) -> dict:
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
old_contract = load(OLD / "contract.json")
old_closure = load(OLD_RUN / "closure.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
old_input = load(OLD_RUN / "input.json")
old_export = load(OLD_RUN / "roundtrip-raw.json")

check("contract identity", (contract["case_id"], contract["variant_id"], contract["version"], contract["run_id"]) == ("E14", "E14.var05", "1.0.1-candidate", RUN_ID))
check("old contract excluded", old_contract["publication_state"] == "not_published")
check("new contract unpublished", contract["publication_state"] == "not_published")
check("old failed acceptance", old_closure["expected_negative"] is False and old_closure["error"] == "unexpected authored-table difference beyond target NFFF erasure")
check("old source stability", old_closure["source_hashes_before"] == old_closure["source_hashes_after"])
check("new source stability", closure["source_hashes_before"] == closure["source_hashes_after"])
check("new closure identity", closure["run_id"] == RUN_ID and closure["schema"] == "simlox-e14-var05-calc-negative-closure/v1")
check("new acceptance fields", closure["expected_negative"] is True and closure["error"] is None and closure["publication_state"] == "not_published")

old_frozen = contract["frozen_failed_import_arm"]
old_files = {
    "contract": (OLD / "contract.json", old_frozen["contract_sha256"]),
    "input": (OLD_RUN / "input.json", old_frozen["input_sha256"]),
    "closure": (OLD_RUN / "closure.json", old_frozen["closure_sha256"]),
    "sxi": (OLD_RUN / "model.sxi", old_frozen["sxi_sha256"]),
    "import": (OLD_RUN / "import.log", old_frozen["import_log_sha256"]),
    "export": (OLD_RUN / "roundtrip-raw.json", old_frozen["roundtrip_export_sha256"]),
}
for name, (path, sha) in old_files.items():
    pin("frozen old " + name, path, sha)
check("old SXI byte count", digest(OLD_RUN / "model.sxi")[0] == old_frozen["sxi_bytes"] == 190789)
check("old raw count", len(old_closure["raw"]) == 8)
for name, record in old_closure["raw"].items():
    seal("old raw " + name, OLD_RUN / name, record)
pin("old invocation", OLD_RUN / "invocation.json", old_closure["invocation_sha256"])
check("old steps import/export", [s["name"] for s in load(OLD_RUN / "steps.json")] == ["import", "export"])
check("old import accepts target", "cannot be imported" not in (OLD_RUN / "import.log").read_text(encoding="utf-8"))
check("old roundtrip passed authored cells", len(old_input["model"]["tables"]) == 31)
populated = [t for t in old_input["model"]["tables"] if rows(t)]
check("old populated table count", len(populated) == 21)
for table in populated:
    exported = row_table(old_export, table["name"])
    check("old table columns " + table["name"], table["columns"] == exported["columns"])
    check("old table rows " + table["name"], rows(table) == rows(exported))
item = rows(row_table(old_export, "ItemStructure"))[1]
check("retained invalid item", item[0] == "TEACH-SRU-01" and item[1] == "TEACH-LRU-01" and item[4] == 4 and item[6] == 5)

prior = contract["accepted_prerequisite"]
pin("E05 signoff", E05 / "cli-scope-signoff-2026-09-29.md", prior["e05_signoff_sha256"])
pin("E14 signoff", PARENT / "cli-scope-signoff-2026-10-05.md", prior["e14_signoff_sha256"])
pin("E14 local index", PARENT / "evidence-index.json", prior["e14_index_local_crlf_sha256"])
local_index = (PARENT / "evidence-index.json").read_bytes()
published_index = subprocess.check_output(["git", "show", prior["e14_index_git_commit"] + ":cases/simlox-air-support/E14-var01-02-extra-removal-v1.0.0/evidence-index.json"], cwd=REPO)
check("local index size", len(local_index) == prior["e14_index_local_bytes"])
check("Git index size", len(published_index) == prior["e14_index_git_bytes"])
check("Git index SHA", hashlib.sha256(published_index).hexdigest() == prior["e14_index_git_lf_sha256"])
check("CRLF-to-LF exact relation", local_index.replace(b"\r\n", b"\n") == published_index)
pin("manual", MANUAL, contract["source"]["manual_pdf_sha256"])
pin("EXE", EXE, contract["source"]["simlox_exe_sha256"])

source_paths = {
    "contract": CASE / "contract.json",
    "index_verifier": CASE / "verify_parent_index.py",
    "failed_contract": OLD / "contract.json",
    "failed_input": OLD_RUN / "input.json",
    "failed_closure": OLD_RUN / "closure.json",
    "failed_sxi": OLD_RUN / "model.sxi",
    "failed_import": OLD_RUN / "import.log",
    "failed_export": OLD_RUN / "roundtrip-raw.json",
    "e05_signoff": E05 / "cli-scope-signoff-2026-09-29.md",
    "e14_signoff": PARENT / "cli-scope-signoff-2026-10-05.md",
    "e14_index": PARENT / "evidence-index.json",
    "exe": EXE,
    "manual": MANUAL,
    "runner": CASE / "run_calc_ssh.ps1",
    "python": PYTHON,
}
check("source pin count", len(closure["source_hashes_before"]) == len(source_paths) == 15)
for name, path in source_paths.items():
    pin("run source " + name, path, closure["source_hashes_before"][name])
check("contract pin linked", closure["source_hashes_before"]["contract"] == digest(CASE / "contract.json")[1])
check("runner exact revision", closure["source_hashes_before"]["runner"] == "888b6c8ec4a4c0fd580efdeedf73b904752ef05448f52690965a08bf1eb715ae")

pin("new invocation", RUN / "invocation.json", closure["invocation_sha256"])
check("invocation source pins", invocation["source_hashes_before"] == closure["source_hashes_before"])
check("invocation identity", invocation["run_id"] == RUN_ID and invocation["source_run_id"] == OLD_RUN_ID and invocation["session_id"] == 0)
check("SSH ancestor", "sshd.exe" in invocation["ssh_ancestor_names"])
check("global mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
check("GUI identity", invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("one step", len(steps) == 1 and steps[0]["name"] == "calc_converter_gate")
check("step success and GUI", steps[0]["status"] == "completed" and steps[0]["exit_code"] == 0 and steps[0]["gui_preserved"] is True and steps[0]["error"] is None)
check("step within invocation", steps[0]["started_utc"] >= invocation["created_utc"] and steps[0]["completed_utc"] >= steps[0]["started_utc"])
check("new raw count", len(closure["raw"]) == 5)
for name, record in closure["raw"].items():
    seal("new raw " + name, RUN / name, record)
check("run file set", {p.name for p in RUN.iterdir() if p.is_file()} == set(closure["raw"]) | {"closure.json", "invocation.json"})
check("copied SXI byte equality", (RUN / "model.sxi").read_bytes() == (OLD_RUN / "model.sxi").read_bytes())
check("copied SXI before/after", outcome["copied_sxi_sha256_before"] == old_frozen["sxi_sha256"] == outcome["copied_sxi_sha256_after"] and outcome["copied_sxi_bytes_after"] == 190789)
check("outcome success", outcome["expected_negative"] is True and outcome["error"] is None)

log = (RUN / "run.log").read_text(encoding="utf-8")
check("one converter summary", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log) == [("1", "1", "0")])
check("outcome summary", outcome["converter_summary"] == [1, 1, 0])
check("one #143 error", re.findall(r"\(error #(\d+)\)", log) == ["143"] == outcome["error_codes"])
check("one #108 warning", re.findall(r"\(warning #(\d+)\)", log) == ["108"])
check("no notes", not re.search(r"\(note #\d+\)", log, re.I))
check("target form", re.search(r"(?m)^Form: ItemStructure\s*$\n^rec 2: \(error #143\)", log) is not None)
error_line = next((line for line in log.splitlines() if "(error #143)" in line), "")
check("NFFF/RRF text and item", "No fault found fraction (NFFF)" in error_line and "removal rate fraction (RRF)" in error_line and "TEACH-SRU-01/TEACH-LRU-01" in error_line)
check("one diagnostic line", outcome["diagnostic_lines"] == [error_line])
check("four-byte SXO", digest(RUN / "model.sxo")[0] == 4)
check("no event or report", all(not (RUN / name).exists() for name in ("model.log", "selected-report-raw.json", "report.json")))
check("no native reimport/reexport", not any((RUN / name).exists() for name in ("import.log", "export.log", "roundtrip-raw.json")))

verdict = {
    "schema": "simlox-e14-var05-independent-calc-replay/v1",
    "verdict": "GO_BOUNDED_CONVERTER_NEGATIVE" if not failures else "NO_GO",
    "passed": not failures,
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "old_import_closure_sha256": digest(OLD_RUN / "closure.json")[1],
    "calc_closure_sha256": digest(RUN / "closure.json")[1],
    "calc_raw_seals": len(closure["raw"]),
    "old_raw_seals": len(old_closure["raw"]),
    "observed": "Import/export retained NFFF5/RRF4 in v1.0.0; copied immutable SXI then gave sole converter error #143 at ItemStructure rec2, warning #108, Errors1/Warnings1/Notes0, four-byte SXO and no event/report.",
    "limits": "One invalid traditional SRU NFFF5>RRF4 source at conversion. The earlier import-erasure hypothesis is excluded. No physical simulation, general bound, GUI-only or cross-engine claim.",
}
(HERE / "independent-verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"verdict": verdict["verdict"], "checks": f"{checks-len(failures)}/{checks}", "failures": failures}, ensure_ascii=False))
raise SystemExit(0 if not failures else 1)
