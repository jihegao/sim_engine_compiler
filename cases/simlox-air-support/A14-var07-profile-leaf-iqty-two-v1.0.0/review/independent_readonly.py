"""Independent standard-library read-only replay of A14.var07 negative probe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A14-profile-repeated-v1.0.1"
PARENT = PARENT_CASE / "profile-input.json"
RUN = CASE / "runs" / "a14-var07-leaf-two-v100-20261001-01"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path):
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == ',' and raw[i+1:].lstrip().startswith(('}', ']')):
            continue
        else:
            out.append(ch)
    return json.loads(''.join(out))


def check(name, condition, detail=None):
    CHECKS.append({"name": name, "passed": bool(condition),
                   **({"detail": detail} if detail is not None else {})})


def tables(doc):
    result = {}
    for t in doc["model"]["tables"]:
        assert t["name"] not in result
        result[t["name"]] = t
    return result


def rows(t):
    return [r for i in t["instances"] for r in i["rows"]]


def delta(a, b):
    return {name: {"before": a.get(name), "after": b.get(name)}
            for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name)}


def main():
    try:
        contract = read(CASE / "contract.json")
        diff = read(CASE / "exact-diff.json")
        manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
        dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
        check("contract negative scope and publication", contract["variant_id"] == "A14.var07" and
              contract["case_version"] == "1.0.0-candidate" and
              contract["publication_state"] == "not_published" and
              contract["schema"] == "simlox-air-support-negative-case-contract/v1")
        check("manual/dictionary frozen fingerprints", sha(manual) == contract["source"]["manual_sha256"] and
              sha(dictionary) == contract["source"]["dictionary_sha256"])
        check("accepted A14.var06 parent fingerprint", sha(PARENT) ==
              contract["parent"]["input_sha256"] == diff["parent_sha256"] and
              (CASE / contract["parent"]["signoff"]).is_file())
        check("child and diff frozen fingerprints", sha(CASE / "native-input.json") ==
              contract["native_input_sha256"] == diff["input_sha256"] and
              sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
        parent = tables(native(PARENT))
        child = tables(native(CASE / "native-input.json"))
        actual = delta(parent, child)
        check("exact two-table parsed delta", actual == diff["changed_tables"] and
              set(actual) == {"ProblemDescription", "OperationProfile"})
        p_rows, c_rows = rows(parent["OperationProfile"]), rows(child["OperationProfile"])
        cols = [c["name"] for c in parent["OperationProfile"]["columns"]]
        idx = {name: i for i, name in enumerate(cols)}
        differences = [(i, cols[j], before, after) for i, (p, c) in enumerate(zip(p_rows, c_rows))
                       for j, (before, after) in enumerate(zip(p, c)) if before != after]
        check("only EXECUTE leaf IQTY 1→2", differences == [(2, "IQTY", 1, 2)] and
              p_rows[2][idx["PRID"]] == c_rows[2][idx["PRID"]] == "A14-WAVE" and
              p_rows[2][idx["SPRID"]] == c_rows[2][idx["SPRID"]] == "EXECUTE" and
              p_rows[2][idx["STIM"]] == c_rows[2][idx["STIM"]] == 8,
              differences)
        check("profile dependence remains unchanged", parent["MissionDependenceProfile"] ==
              child["MissionDependenceProfile"] and len(rows(child["MissionDependenceProfile"])) == 1)
        inv, closure = read(RUN / "invocation.json"), read(RUN / "closure.json")
        before = closure["source_hashes_before"]
        check("run identity and input copy", inv["run_id"] == closure["run_id"] == RUN.name and
              inv["case_id"] == "A14" and inv["case_version"] == contract["case_version"] and
              inv["input_sha256"] == sha(CASE / "native-input.json") == sha(RUN / "input.json") and
              Path(inv["original_run_dir"]).resolve() == RUN.resolve())
        check("source stable and frozen through run", before == closure["source_hashes_after"] ==
              inv["source_hashes_before"] and before["input"] == sha(CASE / "native-input.json") and
              before["parent"] == sha(PARENT) and before["contract"] == sha(CASE / "contract.json") and
              before["builder"] == sha(CASE / "build.py") and
              before["exact_diff"] == sha(CASE / "exact-diff.json") and
              before["diff_checker"] == sha(CASE / "describe_diff.py") and
              before["checker"] == sha(CASE / "check_roundtrip.py") and
              before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
        check("runtime and invocation SHA closure", closure["invocation_sha256"] == sha(RUN / "invocation.json") and
              closure["error"] is None and all(inv[k + "_sha256"] == before[k]
              for k in ("parent", "contract", "builder", "checker", "python", "runner_script", "simlox_exe")))
        check("complete raw inventory", set(closure["raw"]) ==
              {p.name for p in RUN.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
        for name, meta in closure["raw"].items():
            check("raw SHA " + name, (RUN / name).stat().st_size == meta["bytes"] and
                  sha(RUN / name) == meta["sha256"])
        check("session0 SSH GUI and serial mutex", inv["session_id"] == 0 and
              inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and
              inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
              inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        steps = read(RUN / "steps.json")
        check("four guarded ordered steps, no jsonreport", [s["name"] for s in steps] ==
              ["import", "export", "calc", "check_import_export"] and
              [s["status"] for s in steps] ==
              ["completed", "completed", "calc_observed", "completed"] and
              all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None
                  for s in steps) and
              all(steps[i]["completed_utc"] <= steps[i+1]["started_utc"] for i in range(3)) and
              all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(3)) and
              steps[3]["arguments"] == inv["planned_check"]["arguments"])
        exported = tables(native(RUN / "roundtrip-raw.json"))
        populated = {name for name, t in child.items() if rows(t)}
        check("14 populated source business tables", len(populated) == 14)
        for name in sorted(populated):
            check("exact source roundtrip " + name, child[name] == exported.get(name))
        log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("exact MissionDependenceProfile converter error #514",
              "Form: MissionDependenceProfile\nrec 1: (error #514) Dependent mission with IQTY>1 for this profile: PRID: A14-WAVE, DMTID: EXECUTE" in
              log.replace("\r\n", "\n") and log.count("(error #514)") == 1)
        check("one error and two expected warnings", "Errors: 1, Warnings: 2, Notes: 0" in log and
              log.count("warning #108") == 1 and log.count("warning #126") == 1 and
              log.count("(error #") == 1)
        check("unusable four-byte SXO", (RUN / "model.sxo").stat().st_size == 4 and
              sha(RUN / "model.sxo") == closure["raw"]["model.sxo"]["sha256"])
        check("no valid report or mission event evidence", not (RUN / "report-raw.json").exists() and
              not (RUN / "model.log").exists() and
              not any(s["name"] == "jsonreport" for s in steps))
    except Exception as exc:
        check("reviewer completed without exception", False, repr(exc))
    failed = [c for c in CHECKS if not c["passed"]]
    result = {
        "schema": "simlox-a14-var07-independent-readonly/v1",
        "case_id": "A14.var07", "version": "1.0.0-candidate",
        "passed": not failed, "check_count": len(CHECKS),
        "passed_count": len(CHECKS)-len(failed), "failures": failed,
        "decision": "GO_bounded_native_conversion_rejection" if not failed else "NO_GO_evidence_mismatch",
        "finding": "The single EXECUTE leaf IQTY change from 1 to 2 roundtrips but native conversion reports one MissionDependenceProfile error #514. Calc exits zero yet creates only a four-byte invalid SXO, with no report or simulation events. This supports native rejection of this ambiguous dependency-profile leaf.",
        "limits": ["One installed SIMLOX 2017 executable, one repeated two-level profile and one IQTY change; no general ambiguity/error-precedence rule.",
                   "This is conversion behavior only; no mission behavior, GUI visual or cross-engine conclusion."],
        "source_sha256": {"parent": sha(PARENT), "contract": sha(CASE / "contract.json"),
                          "input": sha(CASE / "native-input.json"),
                          "exact_diff": sha(CASE / "exact-diff.json")},
        "raw_sha256": {"invocation": sha(RUN / "invocation.json"),
                       "closure": sha(RUN / "closure.json"), "run_log": sha(RUN / "run.log"),
                       "sxo": sha(RUN / "model.sxo")},
        "checks": CHECKS,
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
