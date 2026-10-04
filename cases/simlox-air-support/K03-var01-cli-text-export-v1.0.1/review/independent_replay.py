"""Read-only comparison of sealed K03 CLI text and JSON exports."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASES = HERE.parent
RUN = HERE / "runs/k03-var01-text-v101-ssh-20261004-01"
PARENT = CASES / "K02-var01-json-structure-v1.0.1"
PARENT_RUN = PARENT / "runs/k02-var01-named-v101-ssh-20261004-01"
OLD_RUN = CASES / "K03-var01-cli-text-export-v1.0.0/runs/k03-var01-text-v100-ssh-20261004-01"
OLD_CLOSURE_SHA = "a36ff4174fc64341cdbbbbf7930fe32a37792905b25b1c05dc729aa783af29a9"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Installed native JSON exporter leaves trailing commas.
        out = []
        quoted = escaped = False
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
            elif char == ",":
                j = i + 1
                while j < len(raw) and raw[j].isspace():
                    j += 1
                if j == len(raw) or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


count = 0
failures = []


def check(condition, label):
    global count
    count += 1
    if not condition:
        failures.append(label)


def source_paths():
    return {
        "contract": HERE / "contract.json",
        "parent_input": PARENT / "named-input.json",
        "parent_closure": PARENT_RUN / "closure.json",
        "parent_sxi": PARENT_RUN / "model.sxi",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
    }


def sections(lines):
    starts = [i for i, line in enumerate(lines) if line.startswith(" *")]
    output = []
    for number, start in enumerate(starts):
        title = lines[start][2:].strip()
        if "  (" in title:
            name, instance = title.split("  (", 1)
            instance = instance.removesuffix(")")
        else:
            name, instance = title, ""
        stop = starts[number + 1] if number + 1 < len(starts) else len(lines)
        output.append((name, instance, lines[start + 1:stop]))
    return output


def main():
    contract = load(HERE / "contract.json")
    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    old = load(OLD_RUN / "closure.json")
    check(sha(OLD_RUN / "closure.json") == OLD_CLOSURE_SHA, "v100 excluded closure SHA")
    check(old["error"] == "texport output text-export.log absent/empty", "v100 runner-only failure")
    check(old["raw"]["model.txt"]["sha256"] == closure["raw"]["model.txt"]["sha256"], "v100 same nonempty text output")
    check(contract["case_id"] == "K03" and contract["variant_id"] == "K03.var01", "contract identity")
    check(contract["version"] == "1.0.1-candidate", "contract version")
    check(sha(PARENT / "named-input.json") == contract["dependency"]["input_sha256"], "accepted parent input")
    check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "accepted parent closure")
    check(sha(PARENT_RUN / "model.sxi") == contract["dependency"]["sxi_sha256"], "accepted parent SXI")
    check(sha(RUN / "model.sxi") == sha(PARENT_RUN / "model.sxi"), "copied SXI byte-identical")
    check(closure["run_id"] == invocation["run_id"] == contract["run_id"] == RUN.name, "run ID chain")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation SHA")
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stable")
    for key, path in sorted(source_paths().items()):
        check(path.is_file() and sha(path) == closure["source_hashes_before"][key], key + " source SHA")
    check(len(closure["raw"]) == 6, "six sealed raw files")
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], name + " raw seal")
    check(closure["error"] is None, "successful closure")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, "SSH session0")
    check("sshd.exe" in invocation["ssh_ancestor_names"], "sshd ancestor")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, "preserved GUI identity")
    check([command["name"] for command in invocation["planned_commands"]] == ["texport", "jexport"], "two planned exports")
    text_args = invocation["planned_commands"][0]["arguments"]
    check("-texport" in text_args and "-twidth 4096" in text_args and "-tsep !" in text_args, "text CLI settings")
    steps = load(RUN / "steps.json")
    check([step["name"] for step in steps] == ["texport", "jexport"], "two recorded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], step["name"] + " completed/GUI")
    check((RUN / "text-export.log").stat().st_size == 0, "empty optional texport log classified")
    check((RUN / "model.txt").stat().st_size > 10000, "nonempty native text")
    check(sha(RUN / "model-raw.json") == sha(PARENT_RUN / "roundtrip-raw.json"), "same SXI native JSON export parity")

    json_tables = load(RUN / "model-raw.json")["model"]["tables"]
    by_name = {table["name"]: table for table in json_tables}
    check(len(by_name) == len(json_tables) == 31, "31 unique JSON tables")
    lines = (RUN / "model.txt").read_text(encoding="cp1252").splitlines()
    parsed = sections(lines)
    check(len(parsed) == sum(len(table["instances"]) for table in json_tables) == 33, "all JSON instances appear as text sections")
    check(Counter((name, instance) for name, instance, _ in parsed) == Counter((table["name"], item["instance_name"]) for table in json_tables for item in table["instances"]), "all table/instance identities")
    check([name for name, instance, _ in parsed if not instance] == [table["name"] for table in json_tables], "default-instance table order")
    check([(name, instance) for name, instance, _ in parsed if name == "Station"] == [("Station", ""), ("Station", "K02-BASE"), ("Station", "K02-AUX")], "Station instance names")
    precision_changes = []
    transposed = {"ProblemDescription", "ControlParameters", "Control", "GlobalParameters"}
    for name, instance, body in parsed:
        table = by_name[name]
        columns = [col["name"] for col in table["columns"]]
        original = next(item for item in table["instances"] if item["instance_name"] == instance)
        if name in transposed:
            if name == "ProblemDescription":
                check(original["rows"][0][0] in "\n".join(body), "ProblemDescription text")
            else:
                found = []
                for line in body:
                    match = re.match(r"\s*!\s*([A-Z0-9-]+)\s*:", line)
                    if match:
                        found.append(match.group(1))
                check(found == columns, name + " transposed column order/completeness")
                for key, value in zip(columns, original["rows"][0]):
                    if isinstance(value, str):
                        check(any(re.search(r"\b" + re.escape(key) + r"\b\s*:.*!\s*" + re.escape(value), line) for line in body), name + "." + key + " text value")
            continue

        headings = [field.strip() for field in body[0].split("!")]
        check(headings == columns, name + "/" + instance + " all headings")
        text_rows = [line for line in body[1:] if line.strip()]
        check(len(text_rows) == len(original["rows"]), name + "/" + instance + " row count")
        for index, (source_row, text_row) in enumerate(zip(original["rows"], text_rows)):
            cells = [field.strip() for field in text_row.split("!")]
            check(len(cells) == len(columns), name + "/" + instance + f" row{index} last column present")
            for column, value, display in zip(columns, source_row, cells):
                label = name + "/" + instance + f" row{index} {column}"
                if value is None:
                    check(display == "", label + " null")
                elif isinstance(value, str):
                    check(display == value, label + " string")
                else:
                    try:
                        shown = float(display)
                    except ValueError:
                        check(False, label + " numeric field")
                        continue
                    if shown != float(value):
                        precision_changes.append({"table": name, "instance": instance, "row": index, "column": column, "json": value, "text": display})
    authored = load(PARENT / "named-input.json")["model"]["tables"]
    check(sum(any(item["rows"] for item in table["instances"]) for table in authored) == 13, "13 source row-containing business tables")
    check(precision_changes == [{"table": "OperationProfile", "instance": "", "row": 0, "column": "DTIM", "json": 0.3333333333333333, "text": "0.3"}], "sole observed numeric precision loss")

    verdict = {
        "schema": "independent-k03-var01-v101-text-export/v1",
        "passed": not failures,
        "verdict": "GO: bounded CLI text export with documented precision loss" if not failures else "NO-GO: reviewer discrepancies",
        "checks_passed": count - len(failures),
        "checks_total": count,
        "failures": failures,
        "closure_sha256": sha(RUN / "closure.json"),
        "text_sha256": sha(RUN / "model.txt"),
        "json_sha256": sha(RUN / "model-raw.json"),
        "observed_precision_changes": precision_changes,
        "limits": ["The source SXI is unchanged and both CLI exports succeeded; no text reimport was tested.", "Text places the two named Station instances after Operations rather than adjacent to default Station as in JSON; instance identity and rows are preserved.", "The exported OperationProfile.DTIM is 0.3 in text versus 0.3333333333333333 in JSON, so numeric text fidelity is not established.", "Clipboard, Excel XML, other formatting choices and GUI pathways remain untested.", "v1.0.0 failed a runner gate on an optional empty text log after creating the same text bytes; it is excluded.", "The separate K04 sparse-include failure was caused by a default Control row in the included SXI and says nothing about this text export."],
    }
    target = HERE / "review/independent-verdict.json"
    target.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict["verdict"], "checks": [verdict["checks_passed"], count], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
