"""Pure prospective E02.var02 v104 oracle materializer; no SIMLOX/checker calls.

Adapted from frozen v103 materialize_oracle.py (19771 bytes, SHA256
92e71f356f19a169547c4116f034083c2e3490727183071cb74a14cda397bd4a).
It reads byte-pinned accepted E02/A02 parents, v103 excluded grammar as a
disclosed template, and frozen v104 contract files. It writes only a unique
absent external directory. Its products are predictions, not observed results.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = REPO / "cases/simlox-air-support/E02-zero-stock-local-backorder-v1.0.0"
PARENT_LOG = PARENT / "runs/e02-v100-ssh-20260929-01/model.log"
PARENT_REPORT = PARENT / "runs/e02-v100-ssh-20260929-01/report-raw.json"
PARENT_INPUT = PARENT / "native-input.json"
A02_LOG = REPO / "cases/simlox-air-support/A02-var01-insufficient-gap-v0.1.1/runs/a02-var01-insufficient-gap-v011-ssh-20261006-01/model.log"
OLD_TEMPLATE = REPO / "cases/simlox-air-support/E02-var02-repair-return-after-deadline-v1.0.3/preserved-oracle/log-patterns.json"
PINS = {
    PARENT_LOG: (10714, "bdea346172a799f2c4c1630fe5f9f132dda6d5f4f6c439fc024ed329bc09dd0c"),
    PARENT_REPORT: (104974, "b5b83fbdc877eac297ba8a7492bdcdb162c6eeaab64901eacb16a3daa5cacf3e"),
    PARENT_INPUT: (43699, "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"),
    A02_LOG: (4784, "ae99693f61618e10212b414855aee1995f3744b73f8a3960d8955ebbd5ab3514"),
    OLD_TEMPLATE: (15556, "e39b2e75aac1a61a1f35bc4ce0e91735ddf2119ba077d62226dcc5adb0a536e9"),
}
SPEC_PINS: dict[Path, tuple[int, str]] = {
    HERE / "contract.json": (11182, "f8de374b6f78e661d9f453b96fe701db321f94686d02fbec92b8e4095f8fea3b"),
    HERE / "source-delta.json": (1271, "e7dcb2aa9d6f7f4b02801738045472b385a106c56a50e2bc91e6f7d01e8b9a33"),
    HERE / "event-oracle.json": (4581, "49983167aa9b17ba6de757d63759bda1030923a7960efaf01b6d3e0556c9e4aa"),
    HERE / "report-formulas.json": (11502, "868c9081eaaf801a7a1fedd33b7e733efe2804cb526a443f4fd774f87234f050"),
}
SYSTEM_FIELDS = [
    "UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMC",
    "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYUA", "NSYA", "NSYAL", "FTMO",
    "NSYRP", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH",
    "NREPT", "NPMT", "NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ",
    "STACC", "STF", "STLOW", "SYDT", "SYDTU", "NSYDT", "NSYSW", "NPSTA", "NPSUC",
]
STOCK_FIELDS = [
    "STINT", "ETINT", "NBO", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS",
    "PNB", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT",
]
SUMMARY_FIELDS = [
    "NREP", "RTILW", "RTIUP", "MTMF", "RSMTMF", "MSTF", "RSMSTF",
    "MSUF", "RSMSUF", "STMF", "RSSTMF",
]


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def exact_blob(path: Path) -> bytes:
    blob = path.read_bytes()
    size, expected = PINS[path]
    if len(blob) != size or digest(blob) != expected:
        raise ValueError(f"pinned byte mismatch: {path}")
    return blob


def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def reject_constant(value: str) -> object:
    raise ValueError(f"nonfinite JSON number: {value}")


def load_json(blob: bytes) -> dict[str, object]:
    result = json.loads(blob.decode("utf-8"), object_pairs_hook=no_duplicates,
                        parse_constant=reject_constant)
    if type(result) is not dict:
        raise ValueError("JSON root must be object")
    return result


def parent_report() -> dict[str, object]:
    blob = exact_blob(PARENT_REPORT)
    marker = b",\r\n      ]"
    if blob.count(marker) != 1:
        raise ValueError("parent report unexpected native trailing-comma cardinality")
    return load_json(blob.replace(marker, b"\r\n      ]", 1))


def one_replace(value: str, before: str, after: str) -> str:
    if value.count(before) != 1:
        raise ValueError(f"expected one log replacement: {before!r}")
    return value.replace(before, after, 1)


def log_patterns() -> list[dict[str, object]]:
    parent_blob = exact_blob(PARENT_LOG)
    if not parent_blob.endswith(b"\r\n") or parent_blob.count(b"\n") != parent_blob.count(b"\r\n"):
        raise ValueError("accepted parent log CRLF")
    parent_lines = parent_blob.decode("utf-8").splitlines()
    if len(parent_lines) != 141 or digest(
        b"\r\n".join(x.encode("utf-8") for x in parent_lines[:61]) + b"\r\n"
    ) != "b02fa06684be18b8d2e0138b1ca26b7ba614da53602dd9dc2f67f64659758db0":
        raise ValueError("accepted parent prefix changed")
    old = load_json(exact_blob(OLD_TEMPLATE))
    if set(old) != {"schema", "physical_lines", "timed_lines", "line_ending", "status", "lines"} or \
            old["schema"] != "e02-var02-prospective-full-log-patterns/v103" or \
            old["physical_lines"] != 117 or old["timed_lines"] != 99 or \
            old["line_ending"] != "CRLF" or type(old["lines"]) is not list or \
            len(old["lines"]) != 117:
        raise ValueError("v103 template identity changed")
    base = old["lines"]
    if any(type(row) is not dict or row.get("kind") != "literal" or
           type(row.get("text")) is not str or row["text"] != parent_lines[i]
           for i, row in enumerate(base[:61])):
        raise ValueError("template first 61 lines differ from accepted parent")
    predicted = copy.deepcopy(base)
    predicted[61]["text"] = one_replace(predicted[61]["text"],
                                         "10.5 hours", "10.75 hours")
    a02_blob = exact_blob(A02_LOG)
    if not a02_blob.endswith(b"\r\n") or a02_blob.count(b"\n") != a02_blob.count(b"\r\n"):
        raise ValueError("accepted A02 log CRLF")
    a02_lines = a02_blob.decode("utf-8").splitlines()
    if len(a02_lines) < 31:
        raise ValueError("accepted A02 cancellation block missing")
    continuation = a02_lines[25:31]
    continuation_blob = ("\r\n".join(continuation) + "\r\n").encode("utf-8")
    if len(continuation_blob) != 117 or digest(continuation_blob) != \
            "e7878ad17c4112b1710ceef1b6bbfc3613693adf2e70a8ae611f28b8cf6e8101":
        raise ValueError("accepted six-line cancellation grammar changed")
    for i in range(67, 80):
        row = predicted[i]
        if type(row) is not dict or row.get("kind") != "literal" or type(row.get("text")) is not str:
            raise ValueError("v103 repair block shape")
        row["text"] = row["text"].replace("Time: 20.6667", "Time: 20.9167", 1)
        row["text"] = row["text"].replace("waiting time was 10.6667", "waiting time was 10.9167", 1)
    for i in range(80, 87):
        row = predicted[i]
        if type(row) is not dict or row.get("kind") != "literal" or \
                type(row.get("text")) is not str or not row["text"].startswith("Time: 21 "):
            raise ValueError("v103 system-completion block shape")
        row["text"] = row["text"].replace("Time: 21 ", "Time: 21.25 ", 1)
    if sum("Time: 20.9167" in predicted[i]["text"] for i in range(67, 80)) != 11 or \
            sum("waiting time was 10.9167" in predicted[i]["text"] for i in range(67, 80)) != 1:
        raise ValueError("repair block replacement cardinality")
    predicted[67:67] = [{"kind": "literal", "text": text} for text in continuation]
    if len(predicted) != 123 or sum(row.get("text", "").startswith("Time:") or
                                   row["kind"] == "bounded_numeric" for row in predicted) != 99:
        raise ValueError("prospective 123/99 trace mismatch")
    return predicted


def matches_log(actual: bytes, patterns: list[dict[str, object]]) -> bool:
    """Exact CRLF/full grammar; the sole variable is finite and >34."""
    if not actual.endswith(b"\r\n") or actual.count(b"\r\n") != len(patterns) or \
            actual.count(b"\n") != len(patterns) or actual.startswith(b"\xef\xbb\xbf"):
        return False
    try:
        lines = actual.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    if len(lines) != len(patterns):
        return False
    for text, row in zip(lines, patterns):
        if row["kind"] == "literal":
            if text != row["text"]:
                return False
        elif row["kind"] == "bounded_numeric":
            if row["finite"] is not True or type(row["greater_than_hour"]) not in (int, float):
                return False
            prefix = row["prefix"]
            if not text.startswith(prefix):
                return False
            number = text[len(prefix):]
            if re.fullmatch(row["number_regex"], number) is None:
                return False
            if not math.isfinite(float(number)) or float(number) <= row["greater_than_hour"]:
                return False
        else:
            return False
    return sum(line.startswith("Time:") for line in lines) == 99


def overlap(start: float, end: float, windows: tuple[tuple[float, float], ...]) -> float:
    return 2.0 * sum(max(0.0, min(end, b) - max(start, a)) for a, b in windows)


def system_row(i: int) -> list[object]:
    a, b = i / 2.0, (i + 1) / 2.0
    d: dict[str, object] = {field: 0.0 for field in SYSTEM_FIELDS}
    d.update(UNID="Total over all Units", SID="Total over all Systems",
             STINT=a, ETINT=b, SYDT=None)
    d["NSYRY"] = overlap(a, b, ((0, 7), (21.25, 31), (34, 36)))
    d["NSYMA"] = overlap(a, b, ((7, 10), (31, 34)))
    d["NSYMO"] = overlap(a, b, ((8, 10), (32, 34)))
    d["NSYMR"] = overlap(a, b, ((7, 8), (31, 32)))
    d["NSYUA"] = overlap(a, b, ((10, 21.25),))
    d["NSYA"] = overlap(a, b, ((0, 10), (21.25, 36)))
    d["FTMO"] = d["NSYMO"]
    d["NSYRP"] = overlap(a, b, ((10, 10 + 1/6), (20 + 11/12, 21.25)))
    d["NSYWI"] = overlap(a, b, ((10 + 1/6, 20 + 11/12),))
    d["STACC"] = d["NSYMO"]
    d["NFAIL"] = 1.0 if i == 19 else 0.0
    d["NREPT"] = 1.0 if i == 42 else 0.0
    d["NSYDT"] = 1.0 if i == 20 else 0.0
    d["SYDT"] = 11.25 if i == 20 else None
    if set(d) != set(SYSTEM_FIELDS):
        raise ValueError("system field coverage")
    return [d[name] for name in SYSTEM_FIELDS]


def stock_row(i: int) -> list[object]:
    a, b = i / 2.0, (i + 1) / 2.0
    d: dict[str, object] = {field: 0.0 for field in STOCK_FIELDS}
    d.update(STINT=a, ETINT=b, NBOU=None, ROS=None, ROST=None,
             WT=None, WTT=None, WTS=None)
    d["NBO"] = overlap(a, b, ((10, 20 + 11/12),))
    d["PNB"] = 1.0 - d["NBO"]
    if i == 20:
        d.update(ROS=1.0, ROST=1.0, WT=10 + 11/12, WTT=10 + 11/12,
                 WTS=10 + 11/12, NDF=1.0, NWT=1.0)
    if set(d) != set(STOCK_FIELDS):
        raise ValueError("stock field coverage")
    return [d[name] for name in STOCK_FIELDS]


def selected_table(parent: dict[str, object], name: str) -> dict[str, object]:
    tables = parent["report"]["tables"]
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name}")
    return matches[0]


def table_with_rows(parent: dict[str, object], name: str,
                    expected_columns: list[str], rows: list[list[object]]) -> dict[str, object]:
    table = selected_table(parent, name)
    if set(table) != {"name", "columns", "instances"} or len(table["instances"]) != 1:
        raise ValueError(f"{name} topology")
    cols = table["columns"]
    if [c["name"] for c in cols] != expected_columns or any(type(c) is not dict for c in cols):
        raise ValueError(f"{name} columns")
    if any(len(row) != len(cols) for row in rows):
        raise ValueError(f"{name} row widths")
    identity = table["instances"][0]["instance_name"]
    return {"columns": cols, "instances": [{"instance_name": identity, "rows": rows}],
            "name": name}


def candidate_input() -> dict[str, object]:
    authored = load_json(exact_blob(PARENT_INPUT))
    if set(authored) != {"model"} or type(authored["model"]) is not dict or \
            type(authored["model"].get("tables")) is not list:
        raise ValueError("accepted parent source root shape")
    candidate = copy.deepcopy(authored)
    matches = [t for t in candidate["model"]["tables"] if
               type(t) is dict and t.get("name") == "ItemRepair"]
    if len(matches) != 1:
        raise ValueError("unique ItemRepair source table")
    table = matches[0]
    cols = [c["name"] for c in table["columns"]]
    if cols.count("IID") != 1 or cols.count("STID") != 1 or cols.count("DIRPT") != 1 or \
            len(table["instances"]) != 1 or len(table["instances"][0]["rows"]) != 1:
        raise ValueError("ItemRepair source topology")
    row = table["instances"][0]["rows"][0]
    if type(row) is not list or len(row) != len(cols) or \
            row[cols.index("IID")] != "TEACH-LRU-01" or \
            row[cols.index("STID")] != "BASE-01" or \
            type(row[cols.index("DIRPT")]) is not float or row[cols.index("DIRPT")] != 1.0:
        raise ValueError("accepted ItemRepair row identity or DIRPT changed")
    row[cols.index("DIRPT")] = 10.75
    return candidate


def expected_report(candidate: dict[str, object]) -> dict[str, object]:
    parent = parent_report()
    if set(parent) != {"report"} or set(parent["report"]) != {"tables"}:
        raise ValueError("parent report root topology")
    pd = selected_table(parent, "ProblemDescription")
    if [c["name"] for c in pd["columns"]] != ["PDESC"]:
        raise ValueError("PDESC topology")
    pdesc = pd["instances"][0]["rows"][0][0]
    if type(pdesc) is not str:
        raise ValueError("PDESC type")
    summary = [1, 0.0, 36.0, 2/3, 0.0, 2/3, 0.0, 1/3, 0.0, 2/3, 0.0]
    tables = [
        table_with_rows(parent, "ProblemDescription", ["PDESC"], [[pdesc]]),
        table_with_rows(parent, "ResultSummary", SUMMARY_FIELDS, [summary]),
        table_with_rows(parent, "SystemResults", SYSTEM_FIELDS,
                        [system_row(i) for i in range(72)]),
        table_with_rows(parent, "StockTotalResults", STOCK_FIELDS,
                        [stock_row(i) for i in range(72)]),
    ]
    result = {"report": {"tables": tables}}
    cells = sum(len(row) for table in tables for ins in table["instances"] for row in ins["rows"])
    if cells != 4044:
        raise ValueError("4044-cell oracle mismatch")
    # Parent representation controls: these do not prove future child behavior.
    ps = selected_table(parent, "SystemResults")
    pc = [x["name"] for x in ps["columns"]]
    for name in ("STREQ", "STF", "NPSTA", "NPSUC", "NSYAL", "STLOW", "SYDTU"):
        if any(row[pc.index(name)] != 0 for row in ps["instances"][0]["rows"]):
            raise ValueError(f"parent representation differs: {name}")
    pst = selected_table(parent, "StockTotalResults")
    sc = [x["name"] for x in pst["columns"]]
    if any(row[sc.index("NBOU")] is not None for row in pst["instances"][0]["rows"]):
        raise ValueError("parent NBOU one-rep representation changed")
    if pst["instances"][0]["rows"][20][sc.index("WTT")] != \
            pst["instances"][0]["rows"][20][sc.index("WT")]:
        raise ValueError("parent WTT=WT positive-wait witness changed")
    authored = load_json(exact_blob(PARENT_INPUT))
    if set(authored) != {"model"} or set(candidate) != {"model"}:
        raise ValueError("source root keys")
    atables = authored["model"]["tables"]
    ctables = candidate["model"]["tables"]
    if len(atables) != len(ctables):
        raise ValueError("source table count")
    changed = 0
    for before_table, after_table in zip(atables, ctables):
        if set(before_table) != set(after_table) or \
                before_table["name"] != after_table["name"] or \
                before_table["columns"] != after_table["columns"] or \
                len(before_table["instances"]) != len(after_table["instances"]):
            raise ValueError("source topology or column metadata changed")
        colnames = [col["name"] for col in before_table["columns"]]
        for before_instance, after_instance in zip(before_table["instances"], after_table["instances"]):
            if set(before_instance) != set(after_instance) or \
                    before_instance["instance_name"] != after_instance["instance_name"] or \
                    len(before_instance["rows"]) != len(after_instance["rows"]):
                raise ValueError("source instance topology changed")
            for row_index, (before_row, after_row) in enumerate(zip(before_instance["rows"],
                                                                      after_instance["rows"])):
                if type(before_row) is not list or type(after_row) is not list or \
                        len(before_row) != len(colnames) or len(after_row) != len(colnames):
                    raise ValueError("source row shape changed")
                for colname, before_value, after_value in zip(colnames, before_row, after_row):
                    if before_value == after_value and type(before_value) is type(after_value):
                        continue
                    if before_table["name"] != "ItemRepair" or colname != "DIRPT" or \
                            row_index != 0 or type(before_value) is bool or \
                            type(after_value) is bool or before_value != 1 or after_value != 10.75:
                        raise ValueError("unexpected source cell change")
                    iid = colnames.index("IID")
                    stid = colnames.index("STID")
                    if before_row[iid] != "TEACH-LRU-01" or after_row[iid] != "TEACH-LRU-01" or \
                            before_row[stid] != "BASE-01" or after_row[stid] != "BASE-01":
                        raise ValueError("ItemRepair target identity changed")
                    changed += 1
    if changed != 1:
        raise ValueError("expected one DIRPT cell change")
    ct = next(t for t in authored["model"]["tables"] if t["name"] == "Control")
    cc = [x["name"] for x in ct["columns"]]
    if ct["instances"][0]["rows"][0][cc.index("WTLIM")] is not None:
        raise ValueError("authored WTLIM must remain null")
    if candidate["model"]["database_version"] != authored["model"]["database_version"]:
        raise ValueError("candidate database version")
    return result


def matches_typed(actual: object, expected: object) -> bool:
    if type(expected) is dict:
        return type(actual) is dict and set(actual) == set(expected) and all(
            matches_typed(actual[key], expected[key]) for key in expected)
    if type(expected) is list:
        return type(actual) is list and len(actual) == len(expected) and all(
            matches_typed(a, b) for a, b in zip(actual, expected))
    if expected is None:
        return actual is None
    if type(expected) is bool:
        return type(actual) is bool and actual is expected
    if type(expected) is int:
        return type(actual) is int and actual == expected
    if type(expected) is float:
        return type(actual) in (int, float) and math.isfinite(actual) and \
            abs(actual - expected) <= 1e-5
    if type(expected) is str:
        return type(actual) is str and actual == expected
    raise ValueError(f"unexpected expected type: {type(expected)}")


def require_negative_probes(patterns: list[dict[str, object]],
                            report: dict[str, object],
                            candidate: dict[str, object],
                            positive: bytes) -> int:
    if not matches_log(positive, patterns) or not matches_typed(report, report):
        raise ValueError("pristine positive failed")
    lines = positive.split(b"\r\n")
    if lines[-1] != b"" or len(lines) != 124:
        raise ValueError("positive physical line split")
    original = lines[:-1]

    def blob_of(items: list[bytes]) -> bytes:
        return b"\r\n".join(items) + b"\r\n"

    missing = original[:67] + original[68:]
    reordered = list(original)
    reordered[67], reordered[68] = reordered[68], reordered[67]
    extra = original[:73] + original[67:73] + original[73:]
    wrong_continuation = list(original)
    wrong_continuation[67] = b" Systems ready: <TEACH-AIR-01,0>"
    if positive.count(b"Next random failure will occur 35.5") != 1:
        raise ValueError("private positive marker cardinality")
    wrong_marker = positive.replace(b"Next random failure will occur 35.5",
                                    b"Next random failure will occur 34", 1)
    log_negatives = [blob_of(missing), blob_of(reordered), blob_of(extra),
                     blob_of(wrong_continuation), wrong_marker,
                     positive.replace(b"\r\n", b"\n", 1),
                     b"\xef\xbb\xbf" + positive]
    if any(matches_log(value, patterns) for value in log_negatives):
        raise ValueError("a private log negative was accepted")

    def rows(name: str, document: dict[str, object]) -> list[list[object]]:
        return selected_table(document, name)["instances"][0]["rows"]

    sr = selected_table(report, "SystemResults")
    sc = [col["name"] for col in sr["columns"]]
    if rows("SystemResults", report)[41][sc.index("NREPT")] != 0.0 or \
            rows("SystemResults", report)[42][sc.index("NREPT")] != 1.0:
        raise ValueError("new unobserved NREPT bin oracle not 0/1")
    wrong_nrept = copy.deepcopy(report)
    rows("SystemResults", wrong_nrept)[41][sc.index("NREPT")] = 1.0
    rows("SystemResults", wrong_nrept)[42][sc.index("NREPT")] = 0.0
    bool_cell = copy.deepcopy(report)
    rows("SystemResults", bool_cell)[42][sc.index("NREPT")] = True
    null_cell = copy.deepcopy(report)
    rows("SystemResults", null_cell)[0][sc.index("SYDT")] = 0.0
    if any(matches_typed(value, report) for value in
           (wrong_nrept, bool_cell, null_cell)):
        raise ValueError("a private report negative was accepted")

    wrong_source = copy.deepcopy(candidate)
    item = next(t for t in wrong_source["model"]["tables"] if t["name"] == "ItemRepair")
    colnames = [c["name"] for c in item["columns"]]
    item["instances"][0]["rows"][0][colnames.index("DIRPT")] = 10.5
    try:
        expected_report(wrong_source)
    except ValueError:
        pass
    else:
        raise ValueError("prior observed DIRPT input was accepted as v104")
    return len(log_negatives) + 3 + 1


def main() -> int:
    if len(sys.argv) != 1:
        raise ValueError("no arguments: output directory is fixed by the frozen source")
    out = REPO / "tmp/e02-var02-oracle-materialization-v104-20261009-01"
    allowed = (REPO / "tmp").resolve(strict=True)
    if out.parent != REPO / "tmp" or out.exists() or out.is_symlink():
        raise ValueError("output must be unique absent direct child of repo/tmp")
    for ancestor in (*REPO.parents, REPO, allowed):
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ValueError("reparse/symlink output ancestor")
    if out.resolve(strict=False).parent != allowed:
        raise ValueError("resolved output escapes repo/tmp")
    if len(SPEC_PINS) != 4:
        raise ValueError("frozen v104 contract/source/event/report pins missing")
    for path, (size, expected) in SPEC_PINS.items():
        blob = path.read_bytes()
        if len(blob) != size or digest(blob) != expected:
            raise ValueError(f"spec source changed: {path}")
    contract = load_json((HERE / "contract.json").read_bytes())
    delta_spec = load_json((HERE / "source-delta.json").read_bytes())
    event_spec = load_json((HERE / "event-oracle.json").read_bytes())
    report_spec = load_json((HERE / "report-formulas.json").read_bytes())
    if contract["schema"] != "e02-var02-prospective-recovery-contract/v104-draft" or \
            contract["decision"] != "INDEPENDENT_CONTRACT_REVIEW_ONLY" or \
            contract["design_native_calls"] != 0 or \
            delta_spec["schema"] != "e02-var02-prospective-source-delta/v104" or \
            delta_spec["single_authored_cell"]["candidate_hours"] != 10.75 or \
            event_spec["schema"] != "e02-var02-prospective-event-oracle/v104" or \
            event_spec["expected_physical_lines"] != 123 or \
            event_spec["expected_timed_lines"] != 99 or \
            report_spec["schema"] != "e02-var02-prospective-report-formulas/v104" or \
            report_spec["topology"]["total_typed_cells"] != 4044 or \
            len(report_spec["SystemResults"]["formulas"]) != 40 or \
            len(report_spec["StockTotalResults"]["formulas"]) != 16:
        raise ValueError("prospective spec identity or coverage changed")
    source_before = digest(Path(__file__).read_bytes())
    lines = log_patterns()
    patterns = {"schema": "e02-var02-prospective-full-log-patterns/v104",
                "physical_lines": 123, "timed_lines": 99, "line_ending": "CRLF",
                "status": "post-v103-diagnostic_unobserved_10.75h_strict_hypothesis", "lines": lines}
    candidate = candidate_input()
    report = expected_report(candidate)
    template_lines = [row["text"] if row["kind"] == "literal" else
                      row["prefix"] + "{{FINITE_GT34}}" for row in lines]
    template_blob = ("\r\n".join(template_lines) + "\r\n").encode("utf-8")
    if template_blob.count(b"\r\n") != 123:
        raise ValueError("CRLF template line count")
    positive = template_blob.replace(b"{{FINITE_GT34}}", b"35.5")
    negative_count = require_negative_probes(lines, report, candidate, positive)
    out.mkdir(parents=False, exist_ok=False)
    outputs = {}
    for name, value in (("candidate-input.json", candidate),
                        ("log-patterns.json", patterns),
                        ("expected-report.json", report)):
        blob = (json.dumps(value, indent=2, ensure_ascii=False,
                           allow_nan=False) + "\n").encode("utf-8")
        target = out / name
        try:
            with target.open("xb") as handle:
                handle.write(blob)
        finally:
            if target.exists():
                os.chmod(target, 0o444)
        outputs[name] = {"bytes": len(blob), "sha256": digest(blob)}
    template_path = out / "expected-log-template.bin"
    try:
        with template_path.open("xb") as handle:
            handle.write(template_blob)
    finally:
        if template_path.exists():
            os.chmod(template_path, 0o444)
    outputs["expected-log-template.bin"] = {"bytes": len(template_blob),
                                           "sha256": digest(template_blob)}
    receipt = {"schema": "e02-var02-pure-materialization/v104",
               "decision": "PROSPECTIVE_ONLY_NOT_NATIVE_ACCEPTANCE",
               "source_sha256": source_before,
               "parent_pins": {str(p): {"bytes": n, "sha256": h} for p, (n, h) in PINS.items()},
               "spec_pins": {str(p): {"bytes": n, "sha256": h}
                             for p, (n, h) in SPEC_PINS.items()},
               "old_v103_basis_sha256": "92e71f356f19a169547c4116f034083c2e3490727183071cb74a14cda397bd4a",
               "negative_rejections": negative_count,
               "outputs": outputs, "native_calls": 0, "accepted_checker_calls": 0}
    blob = (json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    receipt_path = out / "receipt.json"
    try:
        with receipt_path.open("xb") as handle:
            handle.write(blob)
    finally:
        if receipt_path.exists():
            os.chmod(receipt_path, 0o444)
    if digest(Path(__file__).read_bytes()) != source_before:
        raise ValueError("materializer source changed during invocation; outputs retained")
    print(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
