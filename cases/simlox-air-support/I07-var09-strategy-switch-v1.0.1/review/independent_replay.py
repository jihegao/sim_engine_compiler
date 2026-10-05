"""Read-only independent replay of the I07.var09 converter rejection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OLD = ROOT / "I07-var09-strategy-switch-v1.0.0"
OLD_RUN = OLD / "runs" / "i07-var09-time-to-stock-v100-ssh-20261005-02"
PARENT = ROOT / "E15-var01-time-based-cycle-v1.0.0"
ACCEPTED = ROOT / "E15-var01-time-based-cycle-v1.0.1"
RUN = CASE / "runs" / "i07-var09-time-to-stock-v101-ssh-20261005-01"
checks = 0
failures: list[str] = []


def check(value: bool, label: str) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model(path: Path) -> dict:
    return {t["name"]: t for t in read(path)["model"]["tables"]}


def rows(table: dict) -> list:
    return table["instances"][0]["rows"]


contract = read(CASE / "contract.json")
closure = read(RUN / "closure.json")
invocation = read(RUN / "invocation.json")
steps = read(RUN / "steps.json")
outcome = read(RUN / "outcome.json")
old_closure = read(OLD_RUN / "closure.json")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
check(closure["error"] is None and outcome["error"] is None, "clean sealing")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(len(closure["raw"]) == 10, "ten new raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), f"new raw present {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"new raw size {name}")
        check(sha(path) == seal["sha256"], f"new raw hash {name}")
check(sha(OLD_RUN / "closure.json") == contract["excluded_parent"]["closure_sha256"], "excluded closure pin")
check(len(old_closure["raw"]) == 10, "ten old raw seals")
for name, seal in sorted(old_closure["raw"].items()):
    path = OLD_RUN / name
    check(path.is_file(), f"old raw present {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"old raw size {name}")
        check(sha(path) == seal["sha256"], f"old raw hash {name}")

source_paths = {
    "contract": CASE / "contract.json",
    "input": CASE / "native-input.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input.json",
    "parent_event": PARENT / "runs" / "e15-var01-timecycle-v100-ssh-20261005-01" / "model.log",
    "accepted_signoff": ACCEPTED / "cli-scope-signoff-2026-10-05.md",
    "accepted_index": ACCEPTED / "evidence-index.json",
    "old_index": OLD / "evidence-index.json",
    "old_closure": OLD_RUN / "closure.json",
    "old_input": OLD / "native-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "before/after/invocation sources")
for key, path in sorted(source_paths.items()):
    check(sha(path) == closure["source_hashes_before"][key], f"source pin {key}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0/sshd")
check(invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}, "protected GUI identity")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host queue")
check(len(steps) == 3, "three guarded native steps")
for name in ("import", "export", "calc"):
    selected = [s for s in steps if s["name"] == name]
    check(len(selected) == 1 and selected[0]["status"] == "completed" and selected[0]["exit_code"] == 0 and selected[0]["gui_preserved"], f"guarded step {name}")

parent = model(PARENT / "native-input.json")
old = model(OLD / "native-input.json")
new = model(CASE / "native-input.json")
exported = model(RUN / "roundtrip-raw.json")
check(len(parent) == 31 and len(old) == len(new) == 32, "31/32 table shape")
check(set(old) == set(new) == set(parent) | {"ChangesItemReorder"}, "table identity")
for name in sorted(parent):
    check(new[name] == parent[name], f"accepted parent table {name}")
for name in sorted(old):
    if name != "ChangesItemReorder":
        check(new[name] == old[name], f"old diagnostic table {name}")
new_row = rows(new["ChangesItemReorder"])[0]
old_row = rows(old["ChangesItemReorder"])[0]
names = [c["name"] for c in new["ChangesItemReorder"]["columns"]]
check(names == [c["name"] for c in old["ChangesItemReorder"]["columns"]], "change columns retained")
check(len(old_row) == len(new_row) and sum(a != b for a, b in zip(old_row, new_row)) == 1, "single-cell correction")
check(dict(zip(names, new_row))["LEADT"] == 1.0 and dict(zip(names, old_row))["LEADT"] is None, "LEADT null to one")
check(dict(zip(names, new_row))["ROINT"] == 0 and dict(zip(names, new_row))["TIMEC"] == 5.0, "forbidden strategy attempt")
check(sha(RUN / "input.json") == sha(CASE / "native-input.json"), "copied input")
authored = [n for n, t in new.items() if rows(t)]
check(len(authored) == 22, "22 row-containing authored tables")
for name in authored:
    check(name in exported, f"export table {name}")
    if name in exported:
        check([c["name"] for c in new[name]["columns"]] == [c["name"] for c in exported[name]["columns"]], f"export columns {name}")
        check(rows(new[name]) == rows(exported[name]), f"export rows {name}")

log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"Input conversion completed\. Errors: 1, Warnings: 2, Notes: 0", log) is not None, "converter 1/2/0")
errors = re.findall(r"\(error #(\d+)\)", log)
warnings = re.findall(r"\(warning #(\d+)\)", log)
check(errors == ["375"], "sole #375 error")
check(warnings == ["108", "376"], "reviewed warnings")
check("Form: ChangesItemReorder\nrec 1: (error #375) Inconsistent change of ROINT:  TEACH-DU-01/DEPOT-01" in log.replace("\r\n", "\n"), "row-specific #375")
check("#84" not in log, "no undefined LEADT confound")
check(outcome["converter_summary"] == [1, 2, 0] and outcome["error_codes"] == ["375"], "outcome classification")
check((RUN / "model.sxo").stat().st_size == 4, "four-byte invalid SXO")
check(not (RUN / "model.log").exists() and not (RUN / "report-raw.json").exists(), "no event/report result")
check(old_closure["raw"]["model.sxo"]["bytes"] == 4, "old diagnostic invalid SXO")
old_log = (OLD_RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.findall(r"\(error #(\d+)\)", old_log) == ["84", "375"], "old confounded errors")

result = {
    "schema": "simlox-independent-negative-review/v1",
    "case": "I07.var09 v1.0.1",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED_CONVERTER_REJECTION" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "closure_sha256": sha(RUN / "closure.json"),
    "excluded_v100_closure_sha256": sha(OLD_RUN / "closure.json"),
    "source_input_sha256": sha(CASE / "native-input.json"),
    "scope": "One source-bound time-based ROINT16 to stock-based ROINT0 scheduled-change attempt with initial LEADT1 repeated. Converter rejects with sole error #375; no runtime change or general switch behavior is observed.",
}
out = CASE / "review" / "independent-postrun-2026-10-05.json"
out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(f"{result['verdict']} {result['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures))
    raise SystemExit(1)
