"""Read-only independent replay of the sealed B01 zero-preparation run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "B01-fixed-preparation-v1.0.1"
PARENT_RUN = Path("C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/"
                  "simlox-air-support/B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06")
A01 = ROOT / "A01-single-aircraft-single-mission"
RUN_ID = "b01-var01-zero-prep-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
EXPECTED_CLOSURE = "ed20962a1a02d315f4c316b40c87651a43bd6a8b515557d0852f1700ab6c5028"
A01_RUN_IDS = ("a01-bound-final-20260927-03", "a01-bound-replay-20260927-04")
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIR = "<TEACH-AIR-01,0>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path):
    """Remove native trailing delimiters in memory, never in a sealed file."""
    text = path.read_text(encoding="utf-8-sig")
    result = []
    in_string = escape = False
    for i, char in enumerate(text):
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            result.append(char)
        elif char == ",":
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j == len(text) or text[j] not in "]}":
                result.append(char)
        else:
            result.append(char)
    return json.loads("".join(result))


def table_dict(document, section):
    sequence = document[section]["tables"]
    answer = {t["name"]: t for t in sequence}
    if len(answer) != len(sequence):
        raise ValueError("duplicate table")
    return answer


def rows(table):
    fields = [column["name"] for column in table["columns"]]
    output = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            if len(values) != len(fields):
                raise ValueError("nonrectangular row")
            output.append(dict(zip(fields, values)))
    return fields, output


class Check:
    def __init__(self):
        self.total = 0
        self.failed = []
        self.groups = {}

    def eq(self, group, label, actual, expected):
        self.total += 1
        self.groups[group] = self.groups.get(group, 0) + 1
        if actual != expected:
            self.failed.append(f"{group}/{label}: {actual!r} != {expected!r}")

    def close(self, group, label, actual, expected, epsilon=1e-6):
        self.eq(group, label, isinstance(actual, (int, float)) and
                not isinstance(actual, bool) and abs(actual - expected) <= epsilon, True)


def raw_seals(check, folder, records, count, group):
    check.eq(group, "count", len(records), count)
    for name, seal in sorted(records.items()):
        path = folder / name
        check.eq(group, f"{name} bytes", path.stat().st_size, seal["bytes"])
        check.eq(group, f"{name} SHA", sha(path), seal["sha256"])


def source_and_provenance(check):
    contract = parse(CASE / "contract.json")
    closure = parse(RUN / "closure.json")
    invocation = parse(RUN / "invocation.json")
    steps = parse(RUN / "steps.json")
    check.eq("source", "closure SHA", sha(RUN / "closure.json"), EXPECTED_CLOSURE)
    check.eq("source", "contract SHA", sha(CASE / "contract.json"),
             "57fdc32138535c4982e50265c0a57e8e72b79ced8c3710c6ea00df861ef42399")
    check.eq("source", "input SHA", sha(CASE / "native-input.json"),
             "5e2d473cdd617955e2920da0a473854a7576a041aa2653e65397dfc1746f1aee")
    check.eq("source", "reserved run", contract["ownership"]["native_run_id_reserved"], RUN_ID)
    pins = contract["accepted_parent"]
    for label, path in (
        ("input_sha256", PARENT / "native-input.json"),
        ("contract_sha256", PARENT / "contract.json"),
        ("publication_sha256", PARENT / "evidence-2026-09-29.md"),
        ("independent_review_sha256", PARENT / "review/independent-readonly-rerun-2026-09-29.json"),
        ("closure_sha256", PARENT_RUN / "closure.json"),
    ):
        check.eq("parent", label, sha(path), pins[label])
    old_closure = parse(PARENT_RUN / "closure.json")
    check.eq("parent", "run ID", old_closure["run_id"], pins["run_id"])
    raw_seals(check, PARENT_RUN, old_closure["raw"], 11, "parent_raw")
    prereq = contract["instructional_prerequisite"]
    check.eq("a01", "input", sha(A01 / "native-input.json"), prereq["input_sha256"])
    check.eq("a01", "signoff", sha(A01 / "cli-scope-signoff-2026-09-29.md"),
             prereq["signoff_sha256"])
    index = parse(A01 / "evidence-index.json")
    check.eq("a01", "two indexed runs", len(index["runs"]), 2)
    for run_id, entry in zip(A01_RUN_IDS, index["runs"]):
        check.eq("a01", f"{run_id} identity", entry["run_id"], run_id)
        raw_seals(check, Path(entry["directory"]), entry["artifacts"], 17, f"a01_{run_id}")

    paths = {
        "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
        "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py", "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py", "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json", "accepted_contract": PARENT / "contract.json",
        "accepted_diff": PARENT / "parent-diff.json", "accepted_evidence": PARENT / "evidence-2026-09-29.md",
        "accepted_verdict": PARENT / "review/independent-readonly-rerun-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json", "prereq_input": A01 / "native-input.json",
        "prereq_contract": A01 / "contract.json",
        "prereq_signoff": A01 / "cli-scope-signoff-2026-09-29.md",
        "prereq_index": A01 / "evidence-index.json",
        "prereq_final_closure": Path(index["runs"][0]["directory"]) / "closure.json",
        "prereq_replay_closure": Path(index["runs"][1]["directory"]) / "closure.json",
        "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
    }
    before = closure["source_hashes_before"]
    check.eq("source", "all 26 source labels", set(before), set(paths))
    check.eq("source", "before/after stable", closure["source_hashes_after"], before)
    check.eq("source", "invocation source map", invocation["source_hashes_before"], before)
    for label, path in sorted(paths.items()):
        check.eq("source", label, sha(path), before[label])
    check.eq("run", "run ID", closure["run_id"], RUN_ID)
    check.eq("run", "no runner error", closure.get("error"), None)
    check.eq("run", "invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    check.eq("run", "input copy", sha(RUN / "input.json"), sha(CASE / "native-input.json"))
    check.eq("run", "invocation input", invocation["input_sha256"], sha(CASE / "native-input.json"))
    check.eq("run", "invocation contract", invocation["contract_sha256"], sha(CASE / "contract.json"))
    check.eq("run", "failure seal absent", (RUN / "failure-seal.json").exists(), False)
    check.eq("run", "raw file names", set(closure["raw"]), {
        "input.json", "import.log", "model.sxi", "export.log", "roundtrip-raw.json",
        "roundtrip-validation.json", "run.log", "model.sxo", "model.log",
        "report-export.log", "report-raw.json", "steps.json",
    })
    raw_seals(check, RUN, closure["raw"], 12, "child_raw")
    check.eq("guard", "SSH0", invocation["session_id"], 0)
    check.eq("guard", "SSH connection", invocation["ssh_connection_present"], True)
    check.eq("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    check.eq("guard", "host mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    check.eq("guard", "GUI identity", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                                     invocation["gui"]["start_unix_ms"]), (13340, 1, 1790590196826))
    check.eq("guard", "five stages", [step["name"] for step in steps],
             ["import", "export", "check_import_export", "calc", "jsonreport"])
    for number, step in enumerate(steps):
        check.eq("guard", f"step{number} exit", step["exit_code"], 0)
        check.eq("guard", f"step{number} status", step["status"], "completed")
        check.eq("guard", f"step{number} GUI", step["gui_preserved"], True)


def model_and_converter(check):
    parent = parse(PARENT / "native-input.json")
    child = parse(RUN / "input.json")
    def flatten(document):
        result = {}
        for table in document["model"]["tables"]:
            columns = [c["name"] for c in table["columns"]]
            for ii, instance in enumerate(table["instances"]):
                for ri, values in enumerate(instance["rows"]):
                    if len(columns) != len(values):
                        raise ValueError("nonrectangular authored input")
                    for field, value in zip(columns, values):
                        result[(table["name"], ii, ri, field)] = value
        return result
    old, new = flatten(parent), flatten(child)
    check.eq("model", "167 cells", len(old), 167)
    check.eq("model", "same keys", set(new), set(old))
    check.eq("model", "only MissionPreparation DURN", {key: (old[key], new[key]) for key in old
                                                if old[key] != new[key]},
             {("MissionPreparation", 0, 0, "DURN"): (0.5, 0)})
    authored = table_dict(child, "model")
    exported = table_dict(parse(RUN / "roundtrip-raw.json"), "model")
    occupied = [name for name, table in authored.items() if any(i["rows"] for i in table["instances"])]
    check.eq("roundtrip", "15 row-containing tables", len(occupied), 15)
    for name in occupied:
        check.eq("roundtrip", f"{name} columns", exported[name]["columns"], authored[name]["columns"])
        check.eq("roundtrip", f"{name} instances", exported[name]["instances"], authored[name]["instances"])
    check.eq("roundtrip", "checker passed", parse(RUN / "roundtrip-validation.json")["passed"], True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check.eq("converter", "0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    check.eq("converter", "warning IDs", sorted(re.findall(r"\(warning #(\d+)\)", log)), ["108", "126"])
    check.eq("converter", "no errors", re.findall(r"\(error #(\d+)\)", log), [])
    check.eq("converter", "substantive SXO", (RUN / "model.sxo").stat().st_size > 4, True)


def physical_events(check):
    lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    check.eq("events", "horizon", lines[:2], ["SIMLOX LOG FILE", "36"])
    def matching(fragment):
        return [line for line in lines if fragment in line]
    def when(line):
        return float(re.match(r"Time: (\d+(?:\.\d+)?)\s", line).group(1))
    evidence = (
        ("mission order", "mission ordered: BASIC-MISSION", 7),
        ("mission creation", MISSION + " mission created:", 7),
        ("one-aircraft request", MISSION + " mission activated, systems requested: 1", 7),
        ("physical allocation", MISSION + " mission allocates system: " + AIR, 7),
        ("preparation start", AIR + " preparation started, mission: " + MISSION, 7),
        ("preparation end", AIR + " preparation ended, mission: " + MISSION, 7),
        ("h8 launch", MISSION + " mission starting, duration: 2 : " + AIR, 8),
        ("h8.5 task", MISSION + " task starting: " + AIR, 8.5),
        ("h9.5 task completion", MISSION + " task completed: " + AIR, 9.5),
        ("h10 success", MISSION + " mission success:", 10),
        ("h10 completion", MISSION + " mission completed: " + AIR, 10),
        ("h10 physical return", "System arrives " + AIR + ", mission success", 10),
    )
    for label, fragment, expected in evidence:
        found = matching(fragment)
        check.eq("events", f"one {label}", len(found), 1)
        if found:
            check.close("events", f"{label} hour", when(found[0]), expected)
    task_lines = {
        "task start": "  system preparation task 0 on " + AIR + " started",
        "subtask start": "  subtask 0 seqno 0 within system preparation task 0 on " + AIR + " started",
        "no resource": "  subtask 0 seqno 0 within system preparation task 0 on " + AIR +
                       " requests resources: no resources needed",
        "zero work": "  subtask 0 seqno 0 within system preparation task 0 on " + AIR +
                     " starts performing, planned to last for 0 hours",
        "subtask complete": "  subtask 0 seqno 0 within system preparation task 0 on " + AIR + " completed",
        "task complete": "  system preparation task 0 on " + AIR + " completed",
    }
    for label, fragment in task_lines.items():
        found = matching(fragment)
        check.eq("events", f"one {label}", len(found), 1)
        if found:
            check.close("events", f"{label} at h7", when(found[0]), 7)
    ordered_fragments = [
        MISSION + " mission allocates system: " + AIR,
        AIR + " preparation started, mission: " + MISSION,
        task_lines["task start"], task_lines["subtask start"], task_lines["zero work"],
        task_lines["subtask complete"], task_lines["task complete"],
        AIR + " preparation ended, mission: " + MISSION,
        MISSION + " mission starting, duration: 2 : " + AIR,
        MISSION + " task starting: " + AIR,
        MISSION + " task completed: " + AIR,
        MISSION + " mission success:",
        MISSION + " mission completed: " + AIR,
        "System arrives " + AIR + ", mission success",
    ]
    positions = [next(i for i, line in enumerate(lines) if fragment in line)
                 for fragment in ordered_fragments]
    check.eq("events", "physical lifecycle order", positions, sorted(positions))
    check.eq("events", "one prep lifecycle pair", len(matching("preparation started, mission:")) +
             len(matching("preparation ended, mission:")), 2)
    check.eq("events", "one work interval", len(matching("starts performing, planned to last for")), 1)
    check.eq("events", "initial physical ID0 ready",
             len([line for line in lines if line.startswith("Time: 0 ") and
                  "systems ready: 1 :<TEACH-AIR-01,0>" in line]), 1)
    check.eq("events", "terminal ID0 ready",
             len([line for line in lines if line.startswith("Time: 10 ") and
                  "systems ready: 1 :<TEACH-AIR-01,0>" in line]), 1)
    for label, regex in (
        ("extra missions", r"mission created:"),
        ("waiting", r"mission waiting:"),
        ("resource wait", r"waiting for resource|resource wait"),
        ("cancellation", r"mission cancelled:|mission aborted"),
        ("fault", r"failure occurs|system failure"),
        ("stock demand", r"backorder|item issued|stock issued"),
        ("positive prep work", r"planned to last for (?!0(?:\.0*)? hours)\d"),
    ):
        count = sum(bool(re.search(regex, line)) for line in lines)
        check.eq("events", label, count, 1 if label == "extra missions" else 0)


def all_report_cells(check):
    parent = table_dict(parse(PARENT_RUN / "report-raw.json"), "report")
    child = table_dict(parse(RUN / "report-raw.json"), "report")
    check.eq("report", "four table order", list(child), list(parent))
    fields, current = rows(child["SystemResults"])
    old_fields, previous = rows(parent["SystemResults"])
    check.eq("report", "72x40 System", (len(current), len(fields)), (72, 40))
    check.eq("report", "System columns", fields, old_fields)
    changes = {(14, "NSYMP"): (1, 0), (14, "NSYMR"): (0, 1),
               (14, "NPSUC"): (0, 1), (15, "NPSUC"): (1, 0)}
    for i in range(72):
        row, prior = current[i], previous[i]
        check.close("system", f"{i}.STINT", row["STINT"], i / 2)
        check.close("system", f"{i}.ETINT", row["ETINT"], (i + 1) / 2)
        for field in fields:
            if (i, field) in changes:
                before, after = changes[(i, field)]
                check.eq("system", f"parent {i}.{field}", prior[field], before)
                check.eq("system", f"child {i}.{field}", row[field], after)
            else:
                check.eq("system", f"{i}.{field}", row[field], prior[field])
    for field, expected in (("NSYMP", 0), ("NSYMR", 1), ("NSYMO", 2), ("NSYRY", 33)):
        check.close("report", f"{field} integral", sum(row[field] * .5 for row in current), expected)
    check.eq("report", "one prep start/success", (sum(r["NPSTA"] for r in current),
                                                  sum(r["NPSUC"] for r in current)), (1, 1))
    check.eq("report", "terminal ready one", current[-1]["NSYRY"], 1)
    sf, stock = rows(child["StockTotalResults"])
    old_sf, old_stock = rows(parent["StockTotalResults"])
    check.eq("report", "72x16 Stock", (len(stock), len(sf)), (72, 16))
    check.eq("report", "Stock columns", sf, old_sf)
    for i in range(72):
        for field in sf:
            check.eq("stock", f"{i}.{field}", stock[i][field], old_stock[i][field])
    summary_fields, summary = rows(child["ResultSummary"])
    old_summary_fields, old_summary = rows(parent["ResultSummary"])
    check.eq("report", "11 summary fields", (len(summary_fields), len(summary)), (11, 1))
    check.eq("report", "summary columns", summary_fields, old_summary_fields)
    for field in summary_fields:
        check.eq("summary", field, summary[0][field], old_summary[0][field])
    for field in ("NREP", "MTMF", "MSTF", "MSUF", "STMF"):
        check.eq("summary", f"{field}=1", summary[0][field], 1)
    check.eq("report", "description columns", child["ProblemDescription"]["columns"],
             parent["ProblemDescription"]["columns"])
    check.eq("report", "description rows", child["ProblemDescription"]["instances"],
             parent["ProblemDescription"]["instances"])


def replay():
    check = Check()
    try:
        source_and_provenance(check)
        model_and_converter(check)
        physical_events(check)
        all_report_cells(check)
    except Exception as exc:
        check.failed.append(f"replay exception: {type(exc).__name__}: {exc}")
    return {
        "schema": "simlox-b01-var01-zero-preparation-independent-replay/v1",
        "decision": "GO_BOUNDED" if not check.failed else "NO_GO",
        "checks": check.total, "failures": check.failed,
        "groups": dict(sorted(check.groups.items())),
        "run_id": RUN_ID, "closure_sha256": EXPECTED_CLOSURE,
        "limits": [
            "One fixed-seed zero-hour linked preparation at one base and one mission only.",
            "The inherited Tasks.DESCR says 30-minute; DURN=0 and the native event/report timing are the evidence.",
            "The A01 zero-row diagnostic supports plausibility but is not the B01 parent or a general rule.",
        ],
    }


if __name__ == "__main__":
    verdict = replay()
    (CASE / "review/independent-verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(verdict, indent=2))
    raise SystemExit(0 if verdict["decision"] == "GO_BOUNDED" else 1)
