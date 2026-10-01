"""Independent read-only replay of three J03 negative distribution probes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
PARENTS = {
    "pfac-sum": BASE / "J03-var01-time-two-point-v1.0.0" / "seed-01-input.json",
    "cycle": BASE / "J03-var04-nested-time-v1.0.0" / "seed-01-input.json",
}
RUNS = {
    "pfac-sum": CASE / "runs" / "j03-pfac-sum-probe-20261001-01",
    "cycle-01": CASE / "runs" / "j03-cycle-probe-20261001-01",
    "cycle-02": CASE / "runs" / "j03-cycle-probe-20261001-02",
}
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "steps.json"}
checks = 0
failures: list[str] = []


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    value = path.read_text(encoding="utf-8-sig")
    if native:
        value = re.sub(r",\s*([}\]])", r"\1", value)
    return json.loads(value)


def tables(document: dict) -> dict:
    sequence = document["model"]["tables"]
    result = {table["name"]: table for table in sequence}
    ck(len(result) == len(sequence), "unique source/export tables")
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            ck(len(names) == len(values), f"well-formed {table['name']} row")
            result.append(dict(zip(names, values)))
    return result


def source_checks(contract: dict, difference: dict) -> dict[str, dict]:
    ck(contract["publication_state"] == difference["publication_state"] == "diagnostic_only",
       "both probes explicitly diagnostic")
    ck(sha(CASE / "probe-diff.json") == contract["probe_diff_sha256"], "frozen probe diff SHA")
    for path, key in ((Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), "manual_sha256"),
                      (Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
                       "dictionary_sha256"),
                      (Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "exe_sha256")):
        ck(sha(path) == contract[key], f"installed {key} pin")
    ck(set(contract["arms"]) == set(difference["arms"]) == set(PARENTS), "two negative arms")
    documents = {}
    for arm in PARENTS:
        parent_path = PARENTS[arm]
        source_path = CASE / f"{arm}-input.json"
        arm_contract, arm_diff = contract["arms"][arm], difference["arms"][arm]
        ck(sha(parent_path) == arm_contract["parent_input_sha256"] == arm_diff["parent_input_sha256"],
           f"{arm} accepted parent SHA")
        ck(sha(source_path) == arm_contract["input_sha256"] == arm_diff["input_sha256"],
           f"{arm} negative source SHA")
        parent, child = tables(read(parent_path)), tables(read(source_path))
        documents[arm] = child
        changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
        ck(changed == {"TimeDistributions"} == {arm_diff["changed_table"]},
           f"{arm} exact changed business table")
        old, new = parent["TimeDistributions"], child["TimeDistributions"]
        ck(old["columns"] == new["columns"] and
           [x["instance_name"] for x in old["instances"]] ==
           [x["instance_name"] for x in new["instances"]],
           f"{arm} table schema and instance preserved")
        ck(rows(old) == arm_diff["before"] and rows(new) == arm_diff["after"],
           f"{arm} exact declared row delta")
        current = rows(new)
        if arm == "pfac-sum":
            ck([row["PFAC"] for row in current] == [.5, .4] and
               sum(row["PFAC"] for row in current) == .9 and
               {row["DISTID"] for row in current} == {"PREP-DET"},
               "J03.var05 same-ID PFAC sum 0.9")
        else:
            ck(current[0]["DISTID"] == "PREP-IN" and current[0]["BASED"] == "PREP-OUT" and
               current[0]["PARAM1"] == .5 and current[2]["DISTID"] == "PREP-OUT" and
               current[2]["BASED"] == "PREP-IN" and current[2]["PARAM1"] == .5,
               "J03.var06 explicit two-node reference cycle")
        ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 16,
           f"{arm} sixteen populated business tables")
    return documents


def replay(run_key: str, document: dict, contract: dict) -> dict:
    arm = "pfac-sum" if run_key == "pfac-sum" else "cycle"
    path = RUNS[run_key]
    runner_path = (CASE / "review" / "probe_native_ssh_initial.ps1"
                   if run_key != "cycle-02" else CASE / "probe_native_ssh.ps1")
    invocation, closure, steps = (read(path / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    source_path = CASE / f"{arm}-input.json"
    ck(invocation["arm"] == closure["arm"] == arm and
       invocation["run_id"] == closure["run_id"] == path.name,
       f"{arm} probe identity")
    ck(invocation["input_sha256"] == closure["input_sha256"] == sha(source_path) and
       closure["invocation_sha256"] == sha(path / "invocation.json") and
       closure["state"] == "native_steps_complete", f"{arm} invocation closure")
    fixed = {"probe-contract.json": CASE / "probe-contract.json",
             "probe-diff.json": CASE / "probe-diff.json", "build.py": CASE / "build.py",
             "probe_native_ssh.ps1": runner_path,
             "pfac-sum-input.json": CASE / "pfac-sum-input.json",
             "cycle-input.json": CASE / "cycle-input.json", "parent-input.json": PARENTS[arm],
             "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
             "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")}
    ck(set(closure["post_source_sha256"]) == set(fixed), f"{arm} full frozen source map")
    for name, file_path in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(file_path),
           f"{arm} source seal {name}")
    for key, file_path in (("contract_sha256", CASE / "probe-contract.json"),
                           ("builder_sha256", CASE / "build.py"),
                           ("runner_sha256", runner_path)):
        ck(invocation[key] == sha(file_path), f"{arm} invocation {key}")
    ck(set(closure["raw"]) == RAW, f"{arm} eight sealed raw files")
    for name, metadata in closure["raw"].items():
        file_path = path / name
        ck(file_path.is_file() and file_path.stat().st_size == metadata["bytes"] and
           sha(file_path) == metadata["sha256"], f"{arm} raw seal {name}")
    ck(sha(path / "input.json") == sha(source_path), f"{arm} raw input copy")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui_pid"] == 13340 and
       invocation["gui_start_utc"] == "2026-09-28T10:09:56.8261381Z",
       f"{arm} session-zero SSH, mutex, preserved GUI identity")
    ck([step["name"] for step in steps] == ["import", "export", "calc"],
       f"{arm} native three-step probe")
    ck(all(step["coexisting_gui_present_after"] for step in steps) and
       [step["exit_code"] for step in steps[:2]] == [0, 0],
       f"{arm} import/export and GUI preservation")
    exported = tables(read(path / "roundtrip-raw.json", native=True))
    populated = [name for name, table in document.items() if any(i["rows"] for i in table["instances"])]
    ck(len(populated) == 16, f"{arm} populated table count")
    for name in populated:
        ck(exported.get(name) == document[name], f"{arm} exact native row roundtrip {name}")
    ck((path / "model.sxo").read_bytes() == bytes.fromhex("8bc53301"),
       f"{arm} four-byte invalid SXO signature")
    ck(not (path / "model.log").exists() and not (path / "report-raw.json").exists(),
       f"{arm} no behavior log or report")
    ck("Import completed!" in (path / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (path / "export.log").read_text(encoding="utf-8-sig"),
       f"{arm} native import/export complete")
    if arm == "pfac-sum":
        runlog = (path / "run.log").read_text(encoding="utf-8-sig")
        ck(steps[2]["exit_code"] == 0 and
           "Form: TimeDistributions" in runlog and
           "rec 2: (error #265) The sum of PFAC does not add up to 1.0" in runlog and
           "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in runlog and
           sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126"] and
           re.findall(r"error #(\d+)", runlog) == ["265"],
           "J03.var05 converter rejection #265 exact text/diagnostics")
        ck(not any(re.fullmatch(r"\$\d+@model\.sxi\$", f.name) for f in path.iterdir()),
           "PFAC probe no stray temporary SXI")
        outcome = "GO: bounded PFAC-sum converter rejection (#265)"
        extra = {}
    else:
        ck(steps[2]["exit_code"] == -1073741571 and
           (steps[2]["exit_code"] & 0xffffffff) == 0xC00000FD and
           (path / "run.log").stat().st_size == 0,
           "J03.var06 calc stack overflow and zero-byte run log")
        temporary = [f for f in path.iterdir() if re.fullmatch(r"\$\d+@model\.sxi\$", f.name)]
        ck(len(temporary) == 1 and temporary[0].stat().st_size == (path / "model.sxi").stat().st_size and
           sha(temporary[0]) == sha(path / "model.sxi") and
           temporary[0].name not in closure["raw"],
           "cycle probe one unsealed temporary SXI copy")
        outcome = "GO: bounded cycle capability limitation/process failure; no converter rejection established"
        extra = {"unsealed_temp_name": temporary[0].name,
                 "unsealed_temp_sha256": sha(temporary[0])}
    return {"arm": arm, "variant_id": contract["arms"][arm]["variant_id"],
            "run_id": path.name, "source_sha256": sha(source_path),
            "closure_sha256": sha(path / "closure.json"),
            "runner_sha256": sha(runner_path),
            "raw_seal_count": len(closure["raw"]), "calc_exit_code": steps[2]["exit_code"],
            "classification": outcome, **extra}


def replay_accepted_pfac(document: dict, difference: dict) -> dict:
    contract = read(CASE / "contract.json")
    path = CASE / "runs" / "j03-pfac-sum-accepted-20261001-01"
    invocation, closure, steps = (read(path / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    source_path = CASE / "pfac-sum-input.json"
    ck(contract["schema"] == "simlox-j03-var05-pfac-sum-rejection-contract/v1" and
       contract["variant_id"] == "J03.var05" and
       contract["arms"]["pfac-sum"]["input_sha256"] == sha(source_path) and
       contract["probe_diff_sha256"] == sha(CASE / "probe-diff.json"),
       "accepted var05 frozen contract/source/diff")
    ck(contract["manual_sha256"] == sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) and
       contract["dictionary_sha256"] == sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) and
       contract["exe_sha256"] == sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")),
       "accepted var05 manual/dictionary/executable pins")
    ck(contract["expected_observation"] ==
       {"run_id": path.name, "import_exit": 0, "export_exit": 0, "calc_exit": 0,
        "converter_error_code": 265, "converter_error_count": 1,
        "warning_codes": [108, 126], "sxo_bytes": 4, "report_present": False},
       "accepted var05 predeclared outcome gate")
    ck(invocation["arm"] == closure["arm"] == "pfac-sum" and
       invocation["run_id"] == closure["run_id"] == path.name and
       invocation["input_sha256"] == closure["input_sha256"] == sha(source_path) and
       closure["invocation_sha256"] == sha(path / "invocation.json") and
       closure["state"] == "native_steps_complete",
       "accepted var05 invocation/closure identity")
    fixed = {"contract.json": CASE / "contract.json", "probe-diff.json": CASE / "probe-diff.json",
             "build.py": CASE / "build.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
             "pfac-sum-input.json": source_path, "cycle-input.json": CASE / "cycle-input.json",
             "validate_pfac_acceptance.py": CASE / "validate_pfac_acceptance.py",
             "parent-input.json": PARENTS["pfac-sum"],
             "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
             "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")}
    ck(set(closure["post_source_sha256"]) == set(fixed),
       "accepted var05 complete frozen source map")
    for name, source_file in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(source_file),
           f"accepted var05 source seal {name}")
    for key, source_file in (("contract_sha256", CASE / "contract.json"),
                             ("builder_sha256", CASE / "build.py"),
                             ("validator_sha256", CASE / "validate_pfac_acceptance.py"),
                             ("runner_sha256", CASE / "run_native_ssh.ps1")):
        ck(invocation[key] == sha(source_file), f"accepted var05 invocation {key}")
    ck(sha(PARENTS["pfac-sum"]) == contract["arms"]["pfac-sum"]["parent_input_sha256"] ==
       difference["arms"]["pfac-sum"]["parent_input_sha256"],
       "accepted var05 parent identity")
    ck(set(closure["raw"]) == RAW, "accepted var05 eight sealed raw files")
    for name, metadata in closure["raw"].items():
        file_path = path / name
        ck(file_path.is_file() and file_path.stat().st_size == metadata["bytes"] and
           sha(file_path) == metadata["sha256"], f"accepted var05 raw seal {name}")
    ck(sha(path / "input.json") == sha(source_path), "accepted var05 raw input copy")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui_pid"] == 13340 and
       invocation["gui_start_utc"] == "2026-09-28T10:09:56.8261381Z",
       "accepted var05 guarded session-zero SSH/GUI/mutex")
    ck([step["name"] for step in steps] == ["import", "export", "calc"] and
       [step["exit_code"] for step in steps] == [0, 0, 0] and
       all(step["coexisting_gui_present_after"] for step in steps),
       "accepted var05 three successful guarded native steps")
    exported = tables(read(path / "roundtrip-raw.json", native=True))
    populated = [name for name, table in document.items() if any(i["rows"] for i in table["instances"])]
    ck(len(populated) == 16, "accepted var05 sixteen populated source tables")
    for name in populated:
        ck(exported.get(name) == document[name], f"accepted var05 exact row roundtrip {name}")
    runlog = (path / "run.log").read_text(encoding="utf-8-sig")
    ck("Form: TimeDistributions" in runlog and
       "rec 2: (error #265) The sum of PFAC does not add up to 1.0" in runlog and
       "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in runlog and
       sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126"] and
       re.findall(r"error #(\d+)", runlog) == ["265"],
       "accepted var05 exact native converter rejection")
    ck((path / "model.sxo").read_bytes() == bytes.fromhex("8bc53301") and
       not (path / "model.log").exists() and not (path / "report-raw.json").exists(),
       "accepted var05 invalid SXO, no simulation/report claim")
    ck(not any(re.fullmatch(r"\$\d+@model\.sxi\$", f.name) for f in path.iterdir()),
       "accepted var05 no stray temporary SXI")
    probe_path = RUNS["pfac-sum"]
    ck(all(sha(path / name) == sha(probe_path / name)
           for name in ("input.json", "roundtrip-raw.json", "model.sxi", "model.sxo")),
       "accepted var05 reproduces diagnostic source, roundtrip, SXI and invalid SXO bytes")
    return {"variant_id": "J03.var05", "run_id": path.name,
            "source_sha256": sha(source_path), "closure_sha256": sha(path / "closure.json"),
            "runner_sha256": sha(CASE / "run_native_ssh.ps1"),
            "raw_seal_count": len(closure["raw"]), "calc_exit_code": steps[2]["exit_code"],
            "classification": "GO: accepted bounded PFAC-sum converter rejection #265"}


def main() -> None:
    contract, difference = read(CASE / "probe-contract.json"), read(CASE / "probe-diff.json")
    documents = source_checks(contract, difference)
    arms = [replay(key, documents["pfac-sum" if key == "pfac-sum" else "cycle"], contract)
            for key in RUNS]
    ck(arms[1]["source_sha256"] == arms[2]["source_sha256"] and
       arms[1]["calc_exit_code"] == arms[2]["calc_exit_code"] == -1073741571 and
       arms[1]["unsealed_temp_sha256"] == arms[2]["unsealed_temp_sha256"],
       "fresh cycle probes repeat source, stack-overflow exit and temporary copy bytes")
    accepted = replay_accepted_pfac(documents["pfac-sum"], difference)
    result = {"schema": "j03-negative-distribution-accepted-and-probes-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failures": failures, "probe_count": 3, "accepted_count": 1,
              "raw_seal_count": sum(a["raw_seal_count"] for a in arms) + accepted["raw_seal_count"],
              "diagnostics": arms, "accepted_var05": accepted,
              "scope": "The fresh accepted PFAC-sum run establishes native converter rejection #265. Two separate cycle probes establish repeated guarded calc process stack overflow for this exact cyclic source, with no converter diagnostic or simulation behavior output.",
              "limits": ["The three probe runs are diagnostics; only the fresh PFAC-sum run is the bounded accepted negative case.",
                         "The two cycle process failures do not establish intended parser behavior or a general cycle-rejection rule.",
                         "Each cycle run left one unsealed temporary SXI copy in its run directory; each is identified and hashed separately."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
