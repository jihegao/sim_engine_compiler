"""Independent read-only replay of the A08.var06 native conversion rejection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A08-var02-random-count-equidist-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
CHILD = CASE / "native-input.json"
RUN_ID = "a08-var06-invalid-scheduled-qtyd-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-rejection-2026-09-30.json"
PARENT_SHA = "54e1fab467ede59829b0c8994aa4d72f1e08878cf7a39532c6fe61364ca87c84"
CHILD_SHA = "8313773e7dd0bb94914454b248745dbf42b0f6874ac03c41b54c9ac864fce4fa"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
ERROR_MESSAGE = "Initiation quantity distribution (IQTYD) only allowed for random initiation types (ITYPE)"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        # The native JSON exporter sometimes leaves trailing commas.
        out, quoted, escaped = [], False, False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
                continue
            else:
                out.append(char)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    found = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError((name, len(found)))
    return found[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for inst in t["instances"] for row in inst["rows"]]


def main() -> None:
    checks = []

    def ck(name: str, actual: object, expected: object) -> None:
        passed = actual == expected
        checks.append({"name": name, "passed": passed, **({} if passed else
            {"actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract, diff, parent, child = (load(p) for p in
        (CASE / "contract.json", CASE / "exact-diff.json", PARENT, CHILD))
    ck("accepted A08.var02 parent source hash", sha(PARENT), PARENT_SHA)
    ck("frozen negative candidate source hash", sha(CHILD), CHILD_SHA)
    ck("installed manual hash", sha(MANUAL), MANUAL_SHA)
    ck("accepted parent signoff exists", (PARENT_CASE /
       "cli-scope-signoff-2026-09-30.md").is_file(), True)
    ck("parent independent review passed", load(PARENT_CASE / "review" /
       "independent-random-count-2026-09-30.json")["passed"], True)
    ck("contract source hashes and manual p795", (
       contract["parent"]["input_sha256"], contract["native_input_sha256"],
       contract["source"]["manual_pdf_sha256"],
       795 in contract["source"]["physical_pdf_pages"]),
       (PARENT_SHA, CHILD_SHA, MANUAL_SHA, True))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("same 31 source tables", (set(pt), len(pt)), (set(ct), 31))
    ck("only two changed tables", changed, {"OperationProfile", "ProblemDescription"})
    ck("29 other tables and all schemas identical", (len(set(pt)-changed),
       all(pt[n]["columns"] == ct[n]["columns"] for n in pt)), (29, True))
    ck("exact-diff hashes and before/after tables", (
       diff["parent_sha256"], diff["child_sha256"],
       set(diff["changed_tables_only"]), diff["unchanged_table_count"],
       all(diff["changed_tables"][n] == {"before": pt[n], "after": ct[n]}
           for n in changed)), (PARENT_SHA, CHILD_SHA, changed, 29, True))
    old_profile, new_profile = (rows(doc, "model", "OperationProfile")[0]
       for doc in (parent, child))
    ck("sole behavior delta ITYPE RANDOM to SCHEDULED", {
       k: (value, new_profile[k]) for k, value in old_profile.items()
       if value != new_profile[k]}, {"ITYPE": ("RANDOM", "SCHEDULED")})
    ck("invalid combination and fixed surrounding values", (
       new_profile["ITYPE"], new_profile["IQTYD"], new_profile["IQTY"],
       new_profile["IDISP"], new_profile["STIM"], new_profile["IPER"]),
       ("SCHEDULED", "<POISSON>", 3, "EQUIDIST", 8, 12))
    ck("description label only", {k for k, value in
       rows(parent, "model", "ProblemDescription")[0].items() if value !=
       rows(child, "model", "ProblemDescription")[0][k]}, {"PDESC"})

    invocation, closure, steps = (load(RUN / n) for n in
       ("invocation.json", "closure.json", "steps.json"))
    ck("run input copy exact frozen child", (sha(RUN / "input.json"),
       (RUN / "input.json").read_bytes() == CHILD.read_bytes()),
       (CHILD_SHA, True))
    ck("invocation identity/source", (invocation["case_id"], invocation["variant"],
       invocation["run_id"], invocation["input_sha256"],
       invocation["parent_sha256"]),
       ("A08", "invalid-scheduled-qtyd", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("session0 SSH/mutex/GUI identity", (invocation["execution_mode"],
       invocation["session_id"], invocation["ssh_connection_present"],
       "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],
       invocation["queue_mutex"], invocation["gui"]["pid"],
       invocation["gui"]["session_id"], bool(invocation["gui"]["start_utc"])),
       ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue",
        13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner SSH/mutex/GUI assertions", all(s in runner for s in
       ("SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("closure invocation hash", closure["invocation_sha256"],
       sha(RUN / "invocation.json"))
    ck("closure clean and source stable", (closure["run_id"], closure["error"],
       closure["source_hashes_before"] == closure["source_hashes_after"],
       invocation["source_hashes_before"] == closure["source_hashes_before"]),
       (RUN_ID, None, True, True))
    sources = {"input": CHILD, "parent": PARENT, "contract": CASE / "contract.json",
       "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
       "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        ck("source seal " + name, closure["source_hashes_before"][name], sha(path))
    ck("exact nine raw artifacts inventoried", (len(closure["raw"]), set(closure["raw"])),
       (9, {p.name for p in RUN.iterdir() if p.is_file()} -
           {"closure.json", "invocation.json"}))
    for name, stamp in closure["raw"].items():
        path = RUN / name
        ck("raw seal " + name, (stamp["bytes"], stamp["sha256"]),
           (path.stat().st_size, sha(path)))
    ck("four expected steps with GUI preserved", [
       (s["name"], s["status"], s["exit_code"], s["gui_preserved"])
       for s in steps], [
       ("import", "completed", 0, True),
       ("export", "completed", 0, True),
       ("calc", "expected_rejection", 0, True),
       ("check_import_export", "completed", 0, True)])
    ck("planned three CLI commands, no report command", [x["name"] for x in
       invocation["planned_commands"]], ["import", "export", "calc"])
    ck("actual native CLI arguments match plan", [s["arguments"] for s in
       steps[:3]], [x["arguments"] for x in invocation["planned_commands"]])

    export = load(RUN / "roundtrip-raw.json", native=True)
    populated = [t for t in child["model"]["tables"] if any(i["rows"] for i in t["instances"])]
    ck("13 source row-containing tables", len(populated), 13)
    ck("native import-export preserves each source schema and business row", all(
       table(export, "model", t["name"])["columns"] == t["columns"] and
       table(export, "model", t["name"])["instances"] == t["instances"]
       for t in populated), True)
    roundtrip = load(RUN / "roundtrip-validation.json")
    ck("roundtrip artifact corroborates independent row comparison", (
       roundtrip["passed"], roundtrip["differences"],
       roundtrip["source_sha256"], roundtrip["roundtrip_sha256"]),
       (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    ck("import created nonempty model", (RUN / "model.sxi").stat().st_size > 4, True)

    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion exactly one error, two warnings, zero notes", re.findall(
       r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog),
       [("1", "2", "0")])
    ck("sole native error code 212", re.findall(r"error #(\d+)", runlog), ["212"])
    ck("exact error 212 text", f"(error #212) {ERROR_MESSAGE}" in runlog, True)
    ck("warnings only 108/126", sorted(re.findall(r"warning #(\d+)", runlog)),
       ["108", "126"])
    ck("calc exit0 is accompanied by actual converter rejection", (
       steps[2]["exit_code"], steps[2]["status"],
       "Input conversion completed. Errors: 1" in runlog),
       (0, "expected_rejection", True))
    sxo = RUN / "model.sxo"
    ck("unusable native output only four bytes", (sxo.stat().st_size,
       len(sxo.read_bytes())), (4, 4))
    ck("no simulation log or JSON report exists", (
       (RUN / "model.log").exists(), (RUN / "report-raw.json").exists(),
       (RUN / "report-export.log").exists()), (False, False, False))

    passed = all(c["passed"] for c in checks)
    result = {"schema": "simlox-a08-var06-independent-rejection-readonly/v1",
       "reviewer": "Standalone standard-library raw replay; no author imports or native invocation",
       "passed": passed, "passed_count": sum(c["passed"] for c in checks),
       "failed_count": sum(not c["passed"] for c in checks),
       "failed": [c for c in checks if not c["passed"]], "checks": checks,
       "hashes": {"parent_input": sha(PARENT), "child_input": sha(CHILD),
          "manual_pdf": sha(MANUAL), "invocation": sha(RUN / "invocation.json"),
          "closure": sha(RUN / "closure.json"),
          "roundtrip_raw": sha(RUN / "roundtrip-raw.json"),
          "run_log": sha(RUN / "run.log"), "model_sxo": sha(sxo)},
       "observed": {"import_export_passed": roundtrip["passed"],
          "source_row_containing_tables": len(populated),
          "calc_process_exit_code": steps[2]["exit_code"],
          "conversion_errors": 1, "conversion_error_codes": [212],
          "conversion_warning_codes": [108, 126],
          "model_sxo_bytes": sxo.stat().st_size,
          "native_report_present": (RUN / "report-raw.json").exists()},
       "manual_interpretation": "Installed manual physical page 795 labels the SCHEDULED plus IQTYD combination as error #212, with the same message observed in run.log.",
       "decision": "bounded_converter_rejection_accepted" if passed else
          "review_rejected_pending_resolution",
       "limits": [
          "This proves converter rejection of one SCHEDULED plus <POISSON> input in the installed SIMLOX 2017 executable. It supplies no mission or distribution behavior evidence.",
          "The calc process returned exit code 0; rejection rests on the exact error #212 diagnostic, unusable four-byte .sxo and absent report.",
          "No generic error precedence, GUI visual behavior or cross-engine equivalence was tested."],
       "publication_state": "independent_review_only"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
       "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
