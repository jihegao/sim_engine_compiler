"""Check sealed native K03 text export against same-SXI JSON export."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k03-var01-text-v101-ssh-20261004-01"
PARENT_RUN = HERE.parent / "K02-var01-json-structure-v1.0.1" / "runs" / "k02-var01-named-v101-ssh-20261004-01"
TRANSPOSED = {"ControlParameters", "Control", "GlobalParameters"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(cond, message):
    if not cond:
        raise AssertionError(message)


def sections(lines):
    out = []
    for n, line in enumerate(lines):
        if not line.lstrip().startswith("*"):
            continue
        label = line.strip()[1:]
        body = []
        for item in lines[n + 1:]:
            if not item.strip() or item.lstrip().startswith("*"):
                break
            body.append(item)
        out.append((label, body))
    return out


def compare_cell(source, exported, key, losses):
    value = exported.strip()
    if source is None:
        check(value == "", f"nonblank null at {key}: {value!r}")
    elif isinstance(source, str):
        check(value == source, f"string mismatch at {key}: {value!r} != {source!r}")
    elif isinstance(source, (int, float)):
        try:
            parsed = float(value)
        except ValueError as exc:
            raise AssertionError(f"nonnumeric cell at {key}: {value!r}") from exc
        if parsed != float(source):
            losses.append({"table": key[0], "instance": key[1], "row": key[2],
                           "column": key[3], "json_value": source, "text_value": value})
    else:
        raise AssertionError(f"unsupported source type at {key}")


def main():
    checks = []
    def ck(cond, message):
        check(cond, message)
        checks.append(message)

    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
    ck(closure["error"] is None, "native closure has no error")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    ck(all(sha(RUN / name) == item["sha256"] and (RUN / name).stat().st_size == item["bytes"]
           for name, item in closure["raw"].items()), "all raw hashes and lengths")
    ck(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source hashes unchanged")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and invocation["gui"]["pid"] == 13340, "guarded session and GUI identity")
    ck([s["name"] for s in steps] == ["texport", "jexport"]
       and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps), "both native commands completed")
    ck("-texport" in steps[0]["arguments"] and "-twidth 4096 -tsep !" in steps[0]["arguments"], "frozen text command")
    ck(sha(RUN / "model.sxi") == contract["dependency"]["sxi_sha256"] == sha(PARENT_RUN / "model.sxi"), "copied parent SXI unchanged")
    ck(sha(RUN / "model-raw.json") == sha(PARENT_RUN / "roundtrip-raw.json"), "same-SXI JSON export byte-identical to parent")
    ck((RUN / "text-export.log").stat().st_size == 0, "native text export log is empty")

    raw = (RUN / "model.txt").read_bytes()
    ck(raw and b"\x00" not in raw, "nonempty plain text output")
    lines = raw.decode("cp1252").splitlines()
    ck(max(map(len, lines)) < 4096, "text lines below declared width")
    doc = json.loads((RUN / "model-raw.json").read_bytes())
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    ck(len(tables) == 31, "31 native JSON tables")
    rendered = sections(lines)
    ck(len(rendered) == 33, "33 text sections including three Station instances")
    seen = set()
    losses = []
    cells = 0
    for label, body in rendered:
        match = re.fullmatch(r"([^()]+?)(?:  \(([^()]+)\))?", label)
        ck(match is not None and bool(body), f"section shape: {label}")
        table_name, instance_name = match.group(1), match.group(2) or ""
        ck(table_name in tables, f"known table: {label}")
        table = tables[table_name]
        instances = [inst for inst in table["instances"] if inst["instance_name"] == instance_name]
        ck(len(instances) == 1 and (table_name, instance_name) not in seen, f"unique instance: {label}")
        seen.add((table_name, instance_name))
        instance = instances[0]
        columns = [column["name"] for column in table["columns"]]
        if table_name in TRANSPOSED:
            ck(len(instance["rows"]) == 1, f"single transposed row: {label}")
            data = [line for line in body if line.lstrip().startswith("!")]
            names = [re.search(r"!\s*([^!:]+?)\s*:", line).group(1).strip() for line in data]
            ck(names == columns, f"transposed column order: {label}")
            ck(len(data) == len(columns), f"transposed column count: {label}")
            for i, line in enumerate(data):
                pieces = line.split("!")
                ck(len(pieces) >= 4, f"transposed value frame: {label}/{columns[i]}")
                compare_cell(instance["rows"][0][i], pieces[2],
                             (table_name, instance_name, 0, columns[i]), losses)
                cells += 1
        else:
            heading = [x.strip() for x in body[0].split("!")]
            ck(heading == columns, f"column order: {label}")
            data = [[x.strip() for x in line.split("!")] for line in body[1:]]
            ck(len(data) == len(instance["rows"]), f"row count: {label}")
            for row_index, (source, exported) in enumerate(zip(instance["rows"], data)):
                ck(len(exported) == len(columns), f"full row width: {label}/{row_index}")
                for i, (value, text_value) in enumerate(zip(source, exported)):
                    compare_cell(value, text_value, (table_name, instance_name, row_index, columns[i]), losses)
                    cells += 1
    expected = {(t["name"], inst["instance_name"]) for t in tables.values() for inst in t["instances"]}
    ck(seen == expected, "every JSON table instance rendered exactly once")
    ck(losses == [{"table": "OperationProfile", "instance": "", "row": 0,
                   "column": "DTIM", "json_value": 0.3333333333333333, "text_value": "0.3"}], "only observed numeric precision loss is DTIM")
    result = {"schema": "simlox-k03-var01-author-validation/v1", "status": "PASS",
              "checks": len(checks), "cells_compared": cells, "tables": len(tables),
              "text_sections": len(rendered), "numeric_precision_losses": losses,
              "text_sha256": sha(RUN / "model.txt"), "json_sha256": sha(RUN / "model-raw.json"),
              "closure_sha256": sha(RUN / "closure.json"), "check_names": checks}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
