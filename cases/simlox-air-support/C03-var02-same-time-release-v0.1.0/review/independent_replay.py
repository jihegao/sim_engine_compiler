"""Independent standard-library replay of two sealed C03 formation runs.

Read-only for accepted evidence. Writes only its own LF JSON verdict beside this file.
No SIMLOX process or author checker is loaded.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path


REVIEW = Path(__file__).resolve().parent
CASE = REVIEW.parent
REPO = CASE.parents[2]
CATALOG_DIR = REPO / "cases/simlox-air-support"
CONTRACT_SHA = "5c441afe4cd33bfda4a955e4df90bff442b923a40d7e3981692be609a748ba05"
errors = []
checks = 0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    global checks
    checks += 1
    if not condition:
        errors.append(message)


def same(observed, expected, message):
    if isinstance(observed, (int, float)) and not isinstance(observed, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        require(abs(observed - expected) <= 1e-6, f"{message}: {observed!r} vs {expected!r}")
    else:
        require(observed == expected, f"{message}: {observed!r} vs {expected!r}")


def seal(path, specification, label):
    data = path.read_bytes()
    same(len(data), specification["bytes"], label + " size")
    same(digest(data), specification["sha256"], label + " SHA")
    return data


def load(path, native=False):
    source = path.read_text(encoding="utf-8-sig")
    if native:
        source = re.sub(r",\s*([}\]])", r"\1", source)
    return json.loads(source)


def git_blob(path):
    relative = path.relative_to(REPO).as_posix()
    return subprocess.run(["git", "show", "HEAD:" + relative], cwd=REPO,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def tabmap(document, root):
    return {table["name"]: table for table in document[root]["tables"]}


def fields(table):
    return [column["name"] for column in table["columns"]]


def flatrows(table):
    return [(instance.get("instance_name", ""), row) for instance in table["instances"] for row in instance["rows"]]


def report_row(table):
    contents = flatrows(table)
    same(len(contents), 1, table["name"] + " row count")
    return dict(zip(fields(table), contents[0][1]))


def at(lines, hour, phrase, label):
    located = [index for index, line in enumerate(lines) if line.startswith(f"Time: {hour} ") and phrase in line]
    same(len(located), 1, label + " count")
    return located[0] if located else -1


def check_events(role, capacity, path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    for aircraft in (0, 1):
        ident = f"<TEACH-AIR-01,{aircraft}>"
        at(lines, "7.5", "mission allocates system: " + ident, role + " allocation " + str(aircraft))
        at(lines, "7.5", ident + " preparation started", role + " preparation " + str(aircraft))
        at(lines, "7.5", f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident} requests resources", role + " request " + str(aircraft))
    at(lines, "7.5", mission + " mission activated, systems requested: 2", role + " activation")
    at(lines, "7.5", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> books resources", role + " first booking")
    if capacity == 1:
        at(lines, "7.5", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource availability test", role + " initial ID1 test")
        same(sum("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed" in line for line in lines), 1, role + " failed request")
        chain = [
            ("8", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed"),
            ("8", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> frees resources"),
            ("8", "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1"),
            ("8", "<BASE-01,0> trig missions and tasks waiting for resources"),
            ("8", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource availability test"),
            ("8", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource received"),
            ("8", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> books resources"),
            ("8", "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0"),
            ("8", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours"),
        ]
        positions = [at(lines, hour, phrase, role + " h8 " + str(index)) for index, (hour, phrase) in enumerate(chain)]
        require(all(a < b for a, b in zip(positions, positions[1:])), role + " strict release-to-work order")
        require(any("subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1>, C, 0.5" in line
                    for line in lines[positions[3]:positions[4]]), role + " station waiter identity")
        at(lines, "8.5", "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources", role + " ID1 release")
        same(sum(line.startswith("Time: 8.5  system preparation task 1 on <TEACH-AIR-01,1> completed")
                 for line in lines), 1, role + " ID1 task complete")
        launch, finish = "8.5", "9.5"
        same(sum(" books resources" in line for line in lines), 2, role + " bookings")
    else:
        for aircraft in (0, 1):
            ident = f"<TEACH-AIR-01,{aircraft}>"
            task = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident}"
            at(lines, "7.5", task + " books resources", role + f" booking {aircraft}")
            at(lines, "7.5", task + " starts performing, planned to last for 0.5 hours", role + f" work {aircraft}")
            at(lines, "8", task + " frees resources", role + f" release {aircraft}")
        same(sum("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed" in line for line in lines), 0, role + " no failed request")
        launch, finish = "8", "9"
    at(lines, launch, mission + " mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", role + " joint launch")
    at(lines, finish, mission + " mission success", role + " success")
    at(lines, finish, mission + " mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", role + " completion")
    for aircraft in (0, 1):
        at(lines, finish, f"<TEACH-AIR-01,{aircraft}> nbr ready increased", role + f" ready {aircraft}")
    same(sum("mission cancelled:" in line for line in lines), 0, role + " no cancel")


def check_report(role, capacity, table_map):
    names = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]
    same(list(table_map), names, role + " report topology")
    sizes = [(1, 1), (1, 11), (72, 40), (72, 16), (72, 16), (1, 14)]
    count = 0
    for name, (nrow, ncol) in zip(names, sizes):
        table = table_map[name]
        same(len(fields(table)), ncol, role + " " + name + " columns")
        same(len(flatrows(table)), nrow, role + " " + name + " rows")
        same(len(table["instances"]), 1, role + " " + name + " instance count")
        count += nrow * ncol
    same(count, 5210, role + " report cell count")

    desc = report_row(table_map["ProblemDescription"])
    same(desc["PDESC"], "C03 two-aircraft shared-crew formation; no J35/F35 equivalence", role + " description")
    summary = report_row(table_map["ResultSummary"])
    wanted_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "RSMTMF": 0, "MSTF": 1,
                      "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}
    for column in fields(table_map["ResultSummary"]):
        same(summary[column], wanted_summary[column], role + " ResultSummary." + column)

    sys = table_map["SystemResults"]
    for index, (_, values) in enumerate(flatrows(sys)):
        hour = index / 2
        expected = dict.fromkeys(fields(sys), 0)
        expected.update(UNID="Total over all Units", SID="Total over all Systems", STINT=hour,
                        ETINT=hour + 0.5, NSYA=2, SYDT=None)
        finish = 9.5 if capacity == 1 else 9
        launch = 8.5 if capacity == 1 else 8
        if hour < 7.5 or hour >= finish:
            expected["NSYRY"] = 2
        else:
            expected["NSYMA"] = 2
            if hour < launch:
                if capacity == 1 and hour == 8:
                    expected["NSYMP"] = 1
                    expected["NSYMR"] = 1
                else:
                    expected["NSYMP"] = 2
            else:
                expected["NSYMO"] = 2
                expected["FTMO"] = 1
                expected["STACC"] = 2
        if hour == 7.5:
            expected["NPSTA"] = 2
        if (capacity == 2 and hour == 8):
            expected["NPSUC"] = 2
        if (capacity == 1 and hour in (8, 8.5)):
            expected["NPSUC"] = 1
        for column, observed in zip(fields(sys), values):
            same(observed, expected[column], f"{role} SystemResults[{index}].{column}")

    stock = table_map["StockTotalResults"]
    for index, (_, values) in enumerate(flatrows(stock)):
        expected = dict.fromkeys(fields(stock), 0)
        expected.update(STINT=index / 2, ETINT=(index + 1) / 2, PNB=1)
        for column in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected[column] = None
        for column, observed in zip(fields(stock), values):
            same(observed, expected[column], f"{role} StockTotalResults[{index}].{column}")

    resource = table_map["ResourceResults"]
    busy_hours = 0
    wait_hours = 0
    for index, (_, values) in enumerate(flatrows(resource)):
        hour = index / 2
        busy = 2 if capacity == 2 and hour == 7.5 else (1 if capacity == 1 and hour in (7.5, 8) else 0)
        waiting = 1 if capacity == 1 and hour == 7.5 else 0
        busy_hours += busy * 0.5
        wait_hours += waiting * 0.5
        expected = dict.fromkeys(fields(resource), 0)
        expected.update(RID="Total over all Resources", STID="Total over all Stations", STINT=hour,
                        ETINT=hour + 0.5, NR=capacity, NRUM=busy, NRW=waiting,
                        NRA=capacity, NRN=capacity)
        for column, observed in zip(fields(resource), values):
            same(observed, expected[column], f"{role} ResourceResults[{index}].{column}")
    same(busy_hours, 1, role + " person-hours")
    same(wait_hours, 0.5 if capacity == 1 else 0, role + " request wait hours")
    total = report_row(table_map["ResourceResultsTotal"])
    expected = dict.fromkeys(fields(table_map["ResourceResultsTotal"]), 0)
    expected.update(RID="Total over all Resources", STID="Total over all Stations", NR=capacity,
                    NRUM=busy_hours / 36, NRW=wait_hours / 36, NRA=capacity, NRN=capacity)
    for column in fields(table_map["ResourceResultsTotal"]):
        same(total[column], expected[column], role + " ResourceResultsTotal." + column)
    return count


def main():
    same(digest((CASE / "contract.json").read_bytes()), CONTRACT_SHA, "frozen contract")
    contract = load(CASE / "contract.json")
    source = contract["accepted_source"]
    accepted = CATALOG_DIR / source["package"]
    for label, file in [("contract", "contract.json"), ("evidence_report", "evidence-2026-09-29.md"),
                        ("original_independent_review", "review/independent-readonly-2026-09-29.json")]:
        seal(accepted / file, source[label], "accepted " + label)
    seal(Path(contract["manual"]["installed_pdf_path"]),
         {"bytes": Path(contract["manual"]["installed_pdf_path"]).stat().st_size,
          "sha256": contract["manual"]["installed_pdf_sha256"]}, "manual")
    published = CATALOG_DIR / contract["published_staffing_parent"]["package"]
    for label, file in [("contract", "contract.json"), ("evidence_index", "evidence-index.json"),
                        ("scope_signoff", "cli-scope-signoff-2026-10-07.md"),
                        ("independent_verdict", "review/independent-verdict.json")]:
        path = published / file
        seal(path, contract["published_staffing_parent"][label], "published C03.var01 " + label)
        same(git_blob(path), path.read_bytes(), "published C03.var01 Git " + label)
    listed = contract["accepted_source"]["published_source_files"]
    same(len(listed), source["published_source_file_count"], "accepted source count")
    for record in listed:
        path = accepted / record["path"]
        seal(path, record["local_disk"], "accepted local " + record["path"])
        g = git_blob(path)
        same(len(g), record["published_git"]["bytes"], "accepted Git " + record["path"] + " bytes")
        same(digest(g), record["published_git"]["sha256"], "accepted Git " + record["path"] + " SHA")
    source_tables = {}
    reports = {}
    total_cells = 0
    for role, capacity in (("one_crew", 1), ("two_crew", 2)):
        arm = source["arms"][role]
        directory = Path(arm["raw_location"])
        file_input = REPO / arm["input_path"]
        seal(file_input, arm["input"], role + " accepted input")
        seal(directory / "closure.json", arm["closure"], role + " closure")
        seal(directory / "invocation.json", arm["invocation"], role + " invocation")
        seal(directory / "model.log", arm["model_log"], role + " event log")
        seal(directory / "report-raw.json", arm["report_raw"], role + " report")
        closure = load(directory / "closure.json")
        same(closure["raw"], arm["raw"], role + " closure raw map")
        same(closure["invocation_sha256"], arm["invocation"]["sha256"], role + " invocation chain")
        same(closure["input_sha256"], arm["input"]["sha256"], role + " input chain")
        same(len(arm["raw"]), 11, role + " raw count")
        for filename, specification in arm["raw"].items():
            seal(directory / filename, specification, role + " " + filename)
        same((directory / "input.json").read_bytes(), file_input.read_bytes(), role + " native input copy")
        invocation = load(directory / "invocation.json")
        same(invocation["run_id"], arm["run_id"], role + " invocation run ID")
        same(invocation["session_id"], 0, role + " SSH session")
        require("sshd.exe" in invocation["ssh_ancestor_names"], role + " sshd ancestry")
        same(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue", role + " mutex")
        gui = invocation["coexisting_gui"]
        for key, value in (("pid", 13340), ("session_id", 1),
                           ("process_start_utc", "2026-09-28T10:09:56.8261381Z"),
                           ("responding_at_preflight", True)):
            same(gui[key], value, role + " GUI " + key)
        steps = load(directory / "steps.json")
        same([step["name"] for step in steps], ["import", "export", "calc", "jsonreport"], role + " step order")
        for step in steps:
            same(step["exit_code"], 0, role + " " + step["name"] + " exit")
            same(step["coexisting_gui_present_after"], True, role + " " + step["name"] + " GUI")
        log = (directory / "run.log").read_text(encoding="utf-8-sig")
        same(sorted(re.findall(r"\(warning #(\d+)\)", log)), ["108", "126"], role + " converter warnings")
        require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, role + " converter summary")
        require((directory / "model.sxo").stat().st_size > 1000, role + " nontrivial SXO")

        authored = tabmap(load(file_input), "model")
        exported = tabmap(load(directory / "roundtrip-raw.json", native=True), "model")
        same(list(authored), list(exported), role + " roundtrip table topology")
        same(len(authored), 31, role + " authored table count")
        populated = [name for name, table in authored.items() if flatrows(table)]
        same(len(populated), 20, role + " row-containing tables")
        for name in populated:
            a, e = authored[name], exported[name]
            acol, ecol = fields(a), fields(e)
            same(len(flatrows(a)), len(flatrows(e)), role + " " + name + " row count")
            for definition in a["columns"]:
                observed = next((col for col in e["columns"] if col["name"] == definition["name"]), {})
                same(observed.get("datatype"), definition["datatype"], role + " " + name + " " + definition["name"] + " datatype")
            for index, ((ai, av), (ei, ev)) in enumerate(zip(flatrows(a), flatrows(e))):
                same(ai, ei, role + " " + name + " instance " + str(index))
                mapped = dict(zip(ecol, ev))
                for column, expected in zip(acol, av):
                    same(mapped.get(column), expected, f"{role} {name}[{index}].{column} roundtrip")
        for name in set(authored) - set(populated):
            for _, row in flatrows(exported[name]):
                require(all(value is None for value in row), role + " " + name + " empty-table placeholder")
        source_tables[role] = authored
        check_events(role, capacity, directory / "model.log")
        reports[role] = tabmap(load(directory / "report-raw.json", native=True), "report")
        total_cells += check_report(role, capacity, reports[role])
    same(total_cells, 10420, "all report cells")

    one, two = source_tables["one_crew"], source_tables["two_crew"]
    same(list(one), list(two), "source table names")
    differences = []
    for name in one:
        a, b = one[name], two[name]
        same(a["columns"], b["columns"], name + " columns equal")
        same([x.get("instance_name", "") for x in a["instances"]],
             [x.get("instance_name", "") for x in b["instances"]], name + " instances equal")
        same(len(flatrows(a)), len(flatrows(b)), name + " row count equal")
        for index, ((_, ar), (_, br)) in enumerate(zip(flatrows(a), flatrows(b))):
            for column, av, bv in zip(fields(a), ar, br):
                if av != bv:
                    differences.append((name, index, column, av, bv))
    same(differences, [("ResourceAllocation", 0, "RQTY", 1, 2)], "sole source delta")
    allocation = dict(zip(fields(one["ResourceAllocation"]), flatrows(one["ResourceAllocation"])[0][1]))
    for key, expected in (("POINT", "AIR_BASIC"), ("RID", "P-CREW"), ("STID", "BASE-01")):
        same(allocation[key], expected, "shared pool " + key)

    pair_counts = {}
    for table in reports["one_crew"]:
        a, b = reports["one_crew"][table], reports["two_crew"][table]
        same(fields(a), fields(b), table + " comparable columns")
        same(len(flatrows(a)), len(flatrows(b)), table + " comparable rows")
        pair_counts[table] = sum(not (av == bv) for (_, ar), (_, br) in zip(flatrows(a), flatrows(b)) for av, bv in zip(ar, br))
    same(pair_counts, {"ProblemDescription": 0, "ResultSummary": 0, "SystemResults": 12,
                       "StockTotalResults": 0, "ResourceResults": 219, "ResourceResultsTotal": 4},
         "exact six-table pair difference counts")
    same(reports["one_crew"]["StockTotalResults"]["instances"][0]["rows"],
         reports["two_crew"]["StockTotalResults"]["instances"][0]["rows"], "stock equality")
    return {"schema": "c03-var02-independent-readonly/v1", "decision": "GO_BOUNDED" if not errors else "NO_GO",
            "checks": checks, "failures": errors, "contract_sha256": CONTRACT_SHA,
            "accepted_raw_seals": 22, "report_cells_compared": total_cells,
            "scope": "Two accepted fixed-seed C03 CLI runs; observed ID-specific h8 release/regrant, no new native run or general ordering law."}


if __name__ == "__main__":
    result = main()
    (REVIEW / "independent-verdict.json").write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"decision": result["decision"], "checks": result["checks"], "failures": len(result["failures"])}, sort_keys=True))
