"""Independent read-only replay of the sealed A03 three-available CLI run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "a03-var01-three-avail-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "A03-two-aircraft-formation-v1.0.1"
PARENT_RUN = Path(
    "C:/Users/user/Documents/Codex/2026-09-28/simlox-issue18-ssh-current/"
    "cases/simlox-air-support/A03-two-aircraft-formation-v1.0.1/"
    "runs/a03-v101-ssh-gui-20260929-01"
)
A02 = ROOT / "A02-single-aircraft-repeated-missions"
EXPECTED_CLOSURE = "965ba78470846f2ad6634c3e82008dabc20a9beefb1762bba3ae0fef9a46396d"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIR = re.compile(r"<TEACH-AIR-01,(\d+)>")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    """Remove structural trailing commas in memory, preserving the source file."""
    content = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    for i, char in enumerate(content):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ",":
            j = i + 1
            while j < len(content) and content[j].isspace():
                j += 1
            if j == len(content) or content[j] not in "]}":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def tables(document: dict, section: str) -> dict[str, dict]:
    rows = document[section]["tables"]
    result = {row["name"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("duplicate table name")
    return result


def grid(table: dict):
    fields = [column["name"] for column in table["columns"]]
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate column")
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            if len(values) != len(fields):
                raise ValueError("nonrectangular table")
            result.append(dict(zip(fields, values)))
    return fields, result


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []
        self.groups = {}

    def eq(self, group: str, label: str, actual, expected):
        self.count += 1
        self.groups[group] = self.groups.get(group, 0) + 1
        if actual != expected:
            self.failures.append(f"{group}/{label}: {actual!r} != {expected!r}")

    def near(self, group: str, label: str, value, expected: float, tolerance=1e-5):
        self.eq(group, label, isinstance(value, (int, float)) and
                not isinstance(value, bool) and abs(value - expected) <= tolerance, True)


def sealed(a: Audit, folder: Path, closure: dict, count: int, group: str):
    a.eq(group, "sealed raw count", len(closure["raw"]), count)
    for name, seal in sorted(closure["raw"].items()):
        path = folder / name
        a.eq(group, f"{name} SHA", digest(path), seal["sha256"])
        a.eq(group, f"{name} bytes", path.stat().st_size, seal["bytes"])


def input_cells(document: dict):
    result = {}
    for table in document["model"]["tables"]:
        fields = [c["name"] for c in table["columns"]]
        for instance_number, instance in enumerate(table["instances"]):
            for row_number, values in enumerate(instance["rows"]):
                for field, value in zip(fields, values):
                    key = (table["name"], instance_number, row_number, field)
                    if key in result:
                        raise ValueError("duplicate cell")
                    result[key] = value
    return result


def source_and_run(a: Audit):
    contract = read(CASE / "contract.json")
    parent_pin = contract["accepted_parent"]
    parent_closure = read(PARENT_RUN / "closure.json")
    closure = read(RUN / "closure.json")
    invocation = read(RUN / "invocation.json")
    steps = read(RUN / "steps.json")
    a.eq("source", "child closure SHA", digest(RUN / "closure.json"), EXPECTED_CLOSURE)
    a.eq("source", "frozen contract SHA", digest(CASE / "contract.json"),
         "a466a9faab28b518e037f56b90be7a8c1cfce7be99b1fb542c6de3828b17994e")
    a.eq("source", "child input SHA", digest(CASE / "native-input.json"),
         "6fc81a5a5ce9304c007a2087a0116cb585bf3fe70312649937e43d0576be0e71")
    for key, path in {
        "input_sha256": PARENT / "native-input.json",
        "contract_sha256": PARENT / "contract.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-09-29.md",
        "independent_review_sha256": PARENT / "review/independent-readonly-2026-09-29.json",
        "closure_sha256": PARENT_RUN / "closure.json",
    }.items():
        a.eq("parent", key, digest(path), parent_pin[key])
    a.eq("parent", "run ID", parent_closure["run_id"], parent_pin["run_id"])
    sealed(a, PARENT_RUN, parent_closure, 11, "parent_raw")
    prerequisite = contract["instructional_prerequisite"]
    a.eq("source", "A02 input", digest(A02 / "native-input.json"), prerequisite["input_sha256"])
    a.eq("source", "A02 signoff", digest(A02 / "cli-scope-signoff-2026-09-29.md"), prerequisite["signoff_sha256"])
    a.eq("source", "manual", digest(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")),
         contract["manual"]["installed_pdf_sha256"])

    paths = {
        "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
        "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py", "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py", "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json", "accepted_contract": PARENT / "contract.json",
        "accepted_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "accepted_verdict": PARENT / "review/independent-readonly-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json", "a02_input": A02 / "native-input.json",
        "a02_signoff": A02 / "cli-scope-signoff-2026-09-29.md",
        "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
    }
    before = closure["source_hashes_before"]
    a.eq("source", "source labels", set(before), set(paths))
    a.eq("source", "source stable", closure["source_hashes_after"], before)
    a.eq("source", "invocation source", invocation["source_hashes_before"], before)
    for key, path in sorted(paths.items()):
        a.eq("source", key, digest(path), before[key])
    a.eq("run", "run ID", closure["run_id"], RUN_ID)
    a.eq("run", "contract copied", invocation["contract_sha256"], digest(CASE / "contract.json"))
    a.eq("run", "input copied", invocation["input_sha256"], digest(RUN / "input.json"))
    a.eq("run", "invocation SHA", digest(RUN / "invocation.json"), closure["invocation_sha256"])
    a.eq("run", "no closure error", closure.get("error"), None)
    a.eq("run", "no failure seal", (RUN / "failure-seal.json").exists(), False)
    a.eq("run", "exact raw names", set(closure["raw"]), {
        "input.json", "import.log", "model.sxi", "export.log", "roundtrip-raw.json",
        "roundtrip-validation.json", "run.log", "model.sxo", "model.log",
        "report-export.log", "report-raw.json", "steps.json",
    })
    sealed(a, RUN, closure, 12, "child_raw")
    a.eq("run", "SSH0", invocation["session_id"], 0)
    a.eq("run", "SSH connection", invocation["ssh_connection_present"], True)
    a.eq("run", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    a.eq("run", "queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    a.eq("run", "GUI identity", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                                   invocation["gui"]["start_unix_ms"]), (13340, 1, 1790590196826))
    a.eq("run", "five ordered stages", [s["name"] for s in steps],
         ["import", "export", "check_import_export", "calc", "jsonreport"])
    for number, step in enumerate(steps):
        a.eq("run", f"stage {number} exit", step["exit_code"], 0)
        a.eq("run", f"stage {number} completed", step["status"], "completed")
        a.eq("run", f"stage {number} GUI", step["gui_preserved"], True)
    return parent_closure


def model_and_converter(a: Audit):
    old = read(PARENT / "native-input.json")
    new = read(RUN / "input.json")
    old_cells, new_cells = input_cells(old), input_cells(new)
    a.eq("model", "155 cells", len(old_cells), 155)
    a.eq("model", "identical keys", set(old_cells), set(new_cells))
    a.eq("model", "sole changed cell", {key: (old_cells[key], new_cells[key]) for key in old_cells
                                        if old_cells[key] != new_cells[key]},
         {("SystemDeployment", 0, 0, "QTYPS"): (2, 3)})
    a.eq("model", "run input frozen", digest(RUN / "input.json"), digest(CASE / "native-input.json"))
    authored = tables(new, "model")
    exported = tables(read(RUN / "roundtrip-raw.json"), "model")
    populated = [name for name, table in authored.items() if any(x["rows"] for x in table["instances"])]
    a.eq("model", "13 row-containing tables", len(populated), 13)
    for name in populated:
        a.eq("model", f"{name} columns", exported[name]["columns"], authored[name]["columns"])
        a.eq("model", f"{name} instances", exported[name]["instances"], authored[name]["instances"])
    a.eq("model", "roundtrip validation", read(RUN / "roundtrip-validation.json")["passed"], True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.eq("converter", "summary 0/2/0",
         "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    a.eq("converter", "only 108/126", sorted(re.findall(r"\(warning #(\d+)\)", log)), ["108", "126"])
    a.eq("converter", "no errors", re.findall(r"\(error #(\d+)\)", log), [])
    a.eq("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)


def events(a: Audit):
    lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    a.eq("events", "horizon", lines[:2], ["SIMLOX LOG FILE", "36"])
    def hit(fragment: str):
        return [line for line in lines if fragment in line]
    def hour(line: str):
        return float(re.match(r"Time: (\d+(?:\.\d+)?) ", line).group(1))
    def ids(line: str):
        return AIR.findall(line)
    initial = hit("systems ready: 3 :")
    a.eq("events", "initial and terminal three-ready", len(initial), 2)
    first, last = initial[0], initial[-1]
    deployed = set(ids(first))
    a.eq("events", "h0 ready three distinct", (hour(first), len(ids(first)), len(deployed)), (0, 3, 3))
    a.eq("events", "h10 ready same three", (hour(last), set(ids(last))), (10, deployed))
    orders = hit("mission ordered: BASIC-MISSION")
    creates = hit(MISSION + " mission created:")
    demands = hit(MISSION + " mission activated, systems requested: 2")
    for label, found in (("order", orders), ("creation", creates), ("demand", demands)):
        a.eq("events", f"one h7 {label}", (len(found), hour(found[0])), (1, 7))
    allocations = hit(MISSION + " mission allocates system: <TEACH-AIR-01,")
    assigned = [ids(line)[0] for line in allocations]
    a.eq("events", "two distinct h7 allocations", (len(assigned), len(set(assigned)),
                                                   {hour(line) for line in allocations}), (2, 2, {7}))
    a.eq("events", "selected among three", set(assigned).issubset(deployed), True)
    a.eq("events", "unselected one", len(deployed - set(assigned)), 1)
    decreases = hit("nbr ready decreased at unit")
    a.eq("events", "exact selected ready decreases", [ids(line)[0] for line in decreases], assigned)
    for label, fragment, when in (
        ("launch", " mission starting, duration: 2 :", 8),
        ("task start", " task starting:", 8.5),
        ("task complete", " task completed:", 9.5),
        ("mission complete", " mission completed:", 10),
    ):
        found = hit(MISSION + fragment)
        a.eq("events", f"one {label}", len(found), 1)
        a.eq("events", f"{label} time/pair", (hour(found[0]), set(ids(found[0])), len(ids(found[0]))),
             (when, set(assigned), 2))
    succeeded = hit(MISSION + " mission success:")
    a.eq("events", "one h10 success", (len(succeeded), hour(succeeded[0])), (1, 10))
    arrivals = hit("System arrives <TEACH-AIR-01,")
    a.eq("events", "two h10 physical returns", (len(arrivals), {hour(line) for line in arrivals},
                                                   {re.search(r"System arrives <TEACH-AIR-01,(\d+)>", line).group(1)
                                                    for line in arrivals}), (2, {10}, set(assigned)))
    for fragment in (" mission cancelled:", " mission waiting:", "failure occurs", " PM task starting:",
                     " backorder", " Delivery with", " item issued"):
        a.eq("events", f"absent {fragment}", len(hit(fragment)), 0)


def report(a: Audit):
    child = tables(read(RUN / "report-raw.json"), "report")
    parent = tables(read(PARENT_RUN / "report-raw.json"), "report")
    a.eq("report", "table order", list(child), list(parent))
    new_fields, new_rows = grid(child["SystemResults"])
    old_fields, old_rows = grid(parent["SystemResults"])
    a.eq("report", "72x40 System", (len(new_rows), len(new_fields)), (72, 40))
    a.eq("report", "System columns", new_fields, old_fields)
    for i in range(72):
        row, prior = new_rows[i], old_rows[i]
        a.near("system", f"{i}.STINT", row["STINT"], i / 2)
        a.near("system", f"{i}.ETINT", row["ETINT"], (i + 1) / 2)
        for field in new_fields:
            if field in ("NSYA", "NSYRY"):
                a.near("system", f"{i}.{field}", row[field], prior[field] + 1)
            elif field == "FTMO":
                a.near("system", f"{i}.FTMO", row[field], 2 / 3 if 16 <= i < 20 else 0)
            else:
                a.eq("system", f"{i}.{field}", row[field], prior[field])
    for field, expected in (("NSYA", 108), ("NSYRY", 102), ("NSYMR", 2), ("NSYMO", 4)):
        a.near("report", f"{field} aircraft-hour integral",
               sum(float(row[field]) * .5 for row in new_rows), expected)
    a.eq("report", "terminal ready", new_rows[-1]["NSYRY"], 3)
    sf, stock = grid(child["StockTotalResults"])
    pf, old_stock = grid(parent["StockTotalResults"])
    a.eq("report", "72x16 Stock", (len(stock), len(sf)), (72, 16))
    a.eq("report", "Stock fields", sf, pf)
    for i in range(72):
        for field in sf:
            a.eq("stock", f"{i}.{field}", stock[i][field], old_stock[i][field])
    fields, rows = grid(child["ResultSummary"])
    old_fields, old_rows = grid(parent["ResultSummary"])
    a.eq("report", "11 summary fields/one row", (len(fields), len(rows)), (11, 1))
    a.eq("report", "summary columns", fields, old_fields)
    for field in fields:
        a.eq("summary", field, rows[0][field], old_rows[0][field])
    for field in ("NREP", "MTMF", "MSTF", "MSUF", "STMF"):
        a.eq("summary", f"{field}=1", rows[0][field], 1)
    a.eq("report", "description columns", child["ProblemDescription"]["columns"],
         parent["ProblemDescription"]["columns"])
    a.eq("report", "description rows", child["ProblemDescription"]["instances"],
         parent["ProblemDescription"]["instances"])


def replay():
    a = Audit()
    try:
        source_and_run(a)
        model_and_converter(a)
        events(a)
        report(a)
    except Exception as exc:
        a.failures.append(f"replay exception: {type(exc).__name__}: {exc}")
    return {
        "schema": "simlox-a03-var01-three-available-independent-replay/v1",
        "decision": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks": a.count,
        "groups": dict(sorted(a.groups.items())),
        "failures": a.failures,
        "run_id": RUN_ID,
        "closure_sha256": EXPECTED_CLOSURE,
        "limits": [
            "One fixed-seed, one-wave CLI observation; selection priority across seeds or fleets is untested.",
            "Two of three physical IDs are selected; their numeric identities are observed, not predeclared.",
            "The stale inherited one-aircraft Unit description is not treated as physical evidence.",
        ],
    }


if __name__ == "__main__":
    result = replay()
    path = CASE / "review/independent-verdict.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["decision"] == "GO_BOUNDED" else 1)
