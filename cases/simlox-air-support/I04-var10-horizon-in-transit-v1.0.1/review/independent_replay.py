"""Independent I04.var10 read-only source, exporter, log, report and run replay.

The prospective contract is a hypothesis. A native difference is a failure,
never an invitation to change the frozen oracle after observation.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
ROOT = PKG.parents[2]
PARENT = ROOT / "cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1"
PARENT_RUN = PARENT / "runs/i04-var03-idle-system-between-v101-ssh-20261008-01"
RUN_ID = "i04-var10-horizon-in-transit-v101-ssh-20261008-01"
RUN = ROOT / "tmp/native-runs/i04v10-v101-20261008-01"
CONTRACT_SHA = "40b6193c7efabf44901bab2c71f57d7090b8a2b52253117a19f96370363fa1bb"
LOG_SHA = "91f9981956a28414feeea056d963eccd4fe59904ec19b28c988fafc876d24b64"
REPORT_SHA = "cda0425d2341d45836b2f42892e157684e8ff18467e619ed95cdb87b94946d39"
DELTA_SHA = "7d53ed9c457bd0a8927e6d90bde0fbded6834ceea51911712a753347f0c620c4"
PARENT_EXPORT_SHA = "012913693d6af024f1a4176b0bc80a8229053bee6fb0ccfb75fd638c8da900c2"
PARENT_REPORT_SHA = "83d5519306d0efa692deab6b2a2a2bfd682982aa0a1a3ea1275bef9b5a5257fc"
PARENT_INDEX_SHA = "09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff"
PARENT_MANIFEST_SHA = "d05541613248279a5620349ade72bcaf80b12f3be042b470694f45b6efa690f3"
BASE_COMMIT = "17571d8dbcaa9fe3a4582b2fa6cae2599eb102a5"
SOURCE_SELECTION_SHA = "e1476616e4694df1742d095f9976eb57a512953edf6222c9a6cdc74b74ea8cde"
PYTHON = Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
SIMLOX = Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")
WORKING_DIRECTORY = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace")
PURE_TOOLS = ("build.py", "copy_context.py", "source_gate.py", "self_check.py", "make_prelaunch_manifest.py")
GUI = {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}
STAGES = ("import", "export", "check_import_export", "calc", "jsonreport", "check_behavior")
RUN_FILES = {
    "input.json", "model.sxi", "import.log", "roundtrip-raw.json", "export.log",
    "roundtrip-validation.json", "model.sxo", "model.log", "model-run.log",
    "report-raw.json", "report-export.log", "author-validation.json", "steps.json",
    "invocation.json", "closure.json",
    *(name + "-stderr.txt" for name in STAGES),
    *(name + "-stdout.txt" for name in ("import", "export", "calc", "jsonreport")),
}
NATIVE_MARKER = "         },\n      ]"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pairs(items):
    out = {}
    for key, value in items:
        assert key not in out, f"duplicate JSON key {key}"
        out[key] = value
    return out


def bad_constant(value):
    raise AssertionError(f"nonfinite JSON number {value}")


def strict_json(data: bytes, *, native_report: bool = False):
    text = data.decode("utf-8-sig")
    assert "\x00" not in text and "\r" not in text.replace("\r\n", "")
    text = text.replace("\r\n", "\n")
    if native_report:
        assert text.count(NATIVE_MARKER) == 1
        assert text.endswith("         },\n      ]\n   }\n}\n")
        text = text.replace(NATIVE_MARKER, "         }\n      ]", 1)
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)

    def finite(node):
        if isinstance(node, float):
            assert math.isfinite(node)
        elif isinstance(node, list):
            for item in node:
                finite(item)
        elif isinstance(node, dict):
            for item in node.values():
                finite(item)

    finite(value)
    return value


def typed(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(typed(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return list(a) == list(b) and all(typed(a[k], b[k]) for k in a)
    return a == b


def declared_value(actual, expected, datatype: str) -> bool:
    if expected is None:
        return actual is None
    if datatype == "integer":
        return type(actual) is type(expected) is int and actual == expected
    if datatype == "double":
        return (type(actual) in (int, float) and type(expected) in (int, float)
                and math.isfinite(actual) and math.isfinite(expected) and actual == expected)
    assert datatype == "string"
    return type(actual) is type(expected) is str and actual == expected


def pin(path: Path, size: int, digest: str) -> bytes:
    data = path.read_bytes()
    assert len(data) == size and sha(data) == digest, path
    return data


def contract() -> dict:
    data = pin(PKG / "prospective-contract.json", 17674, CONTRACT_SHA)
    out = strict_json(data)
    assert out["schema"] == "i04-var10-horizon-in-transit-prospective-contract/v2"
    assert out["phase"] == "CONTRACT_DESIGN_ONLY_NO_CASE_NO_NATIVE"
    assert out["proposed_run_id"] == RUN_ID
    assert out["proposed_native_run_directory"] == str(RUN)
    return out


def oracles(c: dict):
    specs = (("prospective-source-delta.json", DELTA_SHA, "source-delta.json"),
             ("prospective-log-oracle.json", LOG_SHA, "log-oracle.json"),
             ("prospective-report-oracle.json", REPORT_SHA, "report-oracle.json"))
    out = {}
    for owned, expected_hash, name in specs:
        spec = c["artifacts"][name]
        assert spec["sha256"] == expected_hash
        out[name] = strict_json(pin(PKG / owned, spec["bytes"], expected_hash))
    return out


def source_tables(model: dict) -> list:
    assert list(model) == ["model"] and list(model["model"]) == ["database_version", "tables"]
    tables = model["model"]["tables"]
    assert len(tables) == 34 and len({x["name"] for x in tables}) == 34
    return tables


def table(model: dict, name: str):
    matches = [t for t in source_tables(model) if t["name"] == name]
    assert len(matches) == 1
    return matches[0]


def source_expected(c: dict, delta: dict) -> dict:
    parent = c["parent"]["originals"]["input"]
    original = strict_json(pin(Path(parent["path"]), parent["bytes"], parent["sha256"]))
    assert len(source_tables(original)) == 34
    assert sum(len(i["rows"]) for t in source_tables(original) for i in t["instances"]) == 22
    assert sum(len(t["columns"]) * len(i["rows"]) for t in source_tables(original) for i in t["instances"]) == 223
    assert typed(delta["changes"], c["source_changes"])
    assert len(c["source_changes"]) == 7
    expected = copy.deepcopy(original)
    for change in c["source_changes"][:6]:
        t = table(expected, change["table"])
        column = next(i for i, item in enumerate(t["columns"]) if item["name"] == change["column"])
        rows = t["instances"][change["instance"]]["rows"]
        assert typed(rows[change["row"]][column], change["parent"])
        rows[change["row"]][column] = change["child"]
    deletion = c["source_changes"][6]
    assert deletion["table"] == "OperationProfile" and deletion["row"] == 1
    assert deletion["operation"] == "delete_entire_future_scheduled_row"
    profile = table(expected, "OperationProfile")["instances"][0]["rows"]
    assert len(profile) == 2 and typed(profile[1], deletion["parent"])
    del profile[1]
    assert len(profile) == 1 and profile[0][2] == 8.0
    assert sum(len(i["rows"]) for t in source_tables(expected) for i in t["instances"]) == 21
    assert sum(len(t["columns"]) * len(i["rows"]) for t in source_tables(expected) for i in t["instances"]) == 211
    return expected


def verify_source(c: dict, delta: dict, actual=None) -> dict:
    wanted = source_expected(c, delta)
    given = strict_json((PKG / "native-input.json").read_bytes()) if actual is None else actual
    assert typed(given, wanted), "authored source differs from frozen seven-change delta"
    return given


def expected_export(c: dict) -> dict:
    parent = strict_json(pin(PARENT / "child-roundtrip-oracle.json", 49431, PARENT_EXPORT_SHA))
    out = copy.deepcopy(parent)
    for change in c["source_changes"][:6]:
        t = table(out, change["table"])
        index = next(i for i, col in enumerate(t["columns"]) if col["name"] == change["column"])
        row = t["instances"][change["instance"]]["rows"][change["row"]]
        assert declared_value(row[index], change["parent"], t["columns"][index]["datatype"])
        row[index] = change["child"]
    profile = table(out, "OperationProfile")["instances"][0]["rows"]
    expected_deleted = c["source_changes"][6]["parent"]
    profile_columns = table(out, "OperationProfile")["columns"]
    assert len(profile) == 2 and len(profile[1]) == len(expected_deleted) == len(profile_columns)
    assert all(declared_value(value, expected, column["datatype"])
               for value, expected, column in zip(profile[1], expected_deleted, profile_columns))
    del profile[1]
    assert len(source_tables(out)) == 34
    assert sum(len(i["rows"]) for t in source_tables(out) for i in t["instances"]) == 39
    assert sum(len(t["columns"]) * len(i["rows"]) for t in source_tables(out) for i in t["instances"]) == 395
    assert sum(not any(i["rows"] for i in t["instances"]) for t in source_tables(out)) == 0
    return out


def verify_export(c: dict, actual: dict) -> None:
    wanted = expected_export(c)
    assert list(actual) == list(wanted) == ["model"]
    am, wm = actual["model"], wanted["model"]
    assert list(am) == list(wm) == ["database_version", "tables"]
    assert type(am["database_version"]) is int and am["database_version"] == wm["database_version"]
    assert len(am["tables"]) == len(wm["tables"]) == 34
    for table_actual, table_wanted in zip(am["tables"], wm["tables"]):
        assert list(table_actual) == list(table_wanted)
        assert table_actual["name"] == table_wanted["name"]
        assert typed(table_actual["columns"], table_wanted["columns"])
        assert len(table_actual["instances"]) == len(table_wanted["instances"])
        for actual_instance, wanted_instance in zip(table_actual["instances"], table_wanted["instances"]):
            assert list(actual_instance) == list(wanted_instance)
            assert actual_instance["instance_name"] == wanted_instance["instance_name"]
            assert len(actual_instance["rows"]) == len(wanted_instance["rows"])
            for actual_row, wanted_row in zip(actual_instance["rows"], wanted_instance["rows"]):
                assert len(actual_row) == len(wanted_row) == len(table_actual["columns"])
                for actual_value, wanted_value, column in zip(actual_row, wanted_row, table_actual["columns"]):
                    assert declared_value(actual_value, wanted_value, column["datatype"]), (table_actual["name"], column["name"])


def lines(data: bytes) -> list[str]:
    text = data.decode("utf-8-sig")
    assert "\x00" not in text and "\r" not in text.replace("\r\n", "")
    assert text.endswith("\n")
    return text.replace("\r\n", "\n").splitlines()


def expected_log(c: dict, oracle: dict) -> list[str]:
    parent = c["parent"]["originals"]["log"]
    accepted = lines(pin(Path(parent["path"]), parent["bytes"], parent["sha256"]))
    assert len(accepted) == 118 and sum(x.startswith("Time:") for x in accepted) == 104
    proposed = accepted[:1] + ["11"] + accepted[2:61]
    assert oracle["lines"] == proposed
    assert oracle["line_count"] == 61 and oracle["timed_record_count"] == 53
    assert proposed[-1].endswith("system transfered out: <TEACH-AIR-01,0>.")
    return proposed


def verify_log(c: dict, oracle: dict, data: bytes) -> None:
    assert data == ("\r\n".join(expected_log(c, oracle)) + "\r\n").encode("utf-8")
    actual = lines(data)
    assert actual == expected_log(c, oracle)
    assert sum(x.startswith("Time:") for x in actual) == 53
    assert all("system transfered in:" not in x for x in actual)
    assert all("mission ordered" not in x or x.startswith("Time: 7 ") for x in actual)


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def report_expected(c: dict, oracle: dict) -> dict:
    parent = strict_json(pin(PARENT / "child-report-oracle.json", 95011, PARENT_REPORT_SHA))
    old = parent["report"]["tables"]
    assert [t["name"] for t in old] == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    result = copy.deepcopy(parent)
    tables = result["report"]["tables"]
    tables[0]["instances"][0]["rows"] = [[c["source_changes"][0]["child"]]]
    tables[1]["instances"][0]["rows"] = [[1, 0.0, 11.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]]
    system = tables[2]
    stock = tables[3]
    horizon = 11.0
    labels = (f"Total over all Units;Total over all Systems;0.00;{horizon:.2f}",
              f"0.00;{horizon:.2f};")
    assert c["expected_report"]["result_instance_names"] == list(labels)
    system["instances"][0]["instance_name"] = labels[0]
    stock["instances"][0]["instance_name"] = labels[1]
    sr, st = [], []
    totals = {key: 0.0 for key in ("NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYA", "FTMO", "STACC")}
    for index in range(22):
        a, b = index / 2.0, (index + 1) / 2.0
        assigned = 2 * overlap(a, b, 7, 10) / .5
        flying = 2 * overlap(a, b, 8, 10) / .5
        reserved = 2 * overlap(a, b, 7, 8) / .5
        transit = overlap(a, b, 10.5, 12.5) / .5
        in_unit = 2 - transit
        values = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                  "STINT": a, "ETINT": b, "NSYRY": in_unit - assigned,
                  "NSYMA": assigned, "NSYMO": flying, "NSYMR": reserved,
                  "NSYA": in_unit, "FTMO": flying / 2, "STACC": flying, "SYDT": None}
        sr.append([values.get(col["name"], 0.0) for col in system["columns"]])
        for key in totals:
            totals[key] += values[key] * .5
        stock_values = {"STINT": a, "ETINT": b, "PNB": 1.0,
                        **{key: None for key in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")}}
        st.append([stock_values.get(col["name"], 0.0) for col in stock["columns"]])
    system["instances"][0]["rows"] = sr
    stock["instances"][0]["rows"] = st
    assert totals == {"NSYRY": 15.5, "NSYMA": 6.0, "NSYMO": 4.0,
                      "NSYMR": 2.0, "NSYA": 21.5, "FTMO": 2.0, "STACC": 4.0}
    assert totals == c["expected_report"]["system_integrals_hours"]
    assert sum(len(t["columns"]) * len(t["instances"][0]["rows"]) for t in tables) == 1244
    # The owned prospective oracle must agree independently with every derived cell.
    assert report_equal(oracle, result)
    return result


def report_equal(actual: dict, wanted: dict) -> bool:
    assert list(actual) == list(wanted) == ["report"]
    at, wt = actual["report"]["tables"], wanted["report"]["tables"]
    assert len(at) == len(wt) == 4
    for a, w in zip(at, wt):
        assert list(a) == list(w) and a["name"] == w["name"]
        assert typed(a["columns"], w["columns"])
        assert len(a["instances"]) == len(w["instances"]) == 1
        ai, wi = a["instances"][0], w["instances"][0]
        assert list(ai) == list(wi) and ai["instance_name"] == wi["instance_name"]
        assert len(ai["rows"]) == len(wi["rows"])
        for ar, wr in zip(ai["rows"], wi["rows"]):
            assert len(ar) == len(wr) == len(a["columns"])
            for value, expected, col in zip(ar, wr, a["columns"]):
                assert declared_value(value, expected, col["datatype"]), col["name"]
    return True


def verify_report(c: dict, oracle: dict, data: bytes) -> None:
    expected = report_expected(c, oracle)
    assert report_equal(strict_json(data, native_report=True), expected)


def verify_converter(data: bytes, run: Path = RUN) -> None:
    raw = data.decode("utf-8-sig")
    assert "\x00" not in raw and "\r" not in raw.replace("\r\n", "") and raw.endswith("\n")
    text = raw.replace("\r\n", "\n").splitlines()
    assert len(text) == 17
    fixed = {0: "Performing simulation", 3: "Simulating.", 4: "Converting input data ...",
             6: "Form: Control", 7: "rec 1: (warning #108) Enabling simulation log may generate extensive data in log file",
             8: "Form: System", 9: "rec 1: (warning #126) This system contains no items: TEACH-AIR-01",
             10: "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0",
             12: "Starting simulation...", 14: "Saving results ..."}
    for index, value in fixed.items():
        assert text[index] == value, index
    assert text[1] == "Input file: " + str(run / "model.sxi")
    assert text[2] == "Output file: " + str(run / "model.sxo")
    assert text[5] == "File: " + str(run / "model.sxi").replace("\\", "/")
    for index, label in ((11, "Input data conversion time"), (13, "Simulation time"),
                         (15, "Result saving time"), (16, "Total execution time")):
        assert re.fullmatch(re.escape(label) + r": [0-9]+(?:\.[0-9]+)? secs\.", text[index])
    assert len(text[5].encode("ascii")) == 121


def _repo_relative(relative: str) -> Path:
    assert type(relative) is str and relative and "\\" not in relative
    path = Path(relative)
    assert not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts)
    resolved = (ROOT / path).resolve(strict=True)
    assert resolved.is_relative_to(ROOT.resolve(strict=True))
    return resolved


def _git_blobs(oids: list[str]) -> tuple[dict[str, str], dict[str, bytes]]:
    """Read-only Git calls; this function is executed only by root's capture."""
    git = shutil.which("git") or "C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe"
    assert Path(git).is_file()
    tree = subprocess.run([git, "ls-tree", "-r", "-z", BASE_COMMIT], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert not tree.stderr
    paths = {}
    for item in tree.stdout.split(b"\0"):
        if item:
            head, name = item.split(b"\t", 1)
            _, kind, oid = head.decode("ascii").split(" ")
            if kind == "blob":
                relative = name.decode("utf-8")
                assert relative not in paths
                paths[relative] = oid
    unique_oids = list(dict.fromkeys(oids))
    batch = subprocess.run([git, "cat-file", "--batch"], cwd=ROOT,
                           input=("\n".join(unique_oids) + "\n").encode("ascii"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert not batch.stderr
    blobs = {}
    cursor = 0
    for oid in unique_oids:
        end = batch.stdout.index(b"\n", cursor)
        actual, kind, size = batch.stdout[cursor:end].decode("ascii").split(" ")
        assert actual == oid and kind == "blob"
        count = int(size)
        blob = batch.stdout[end + 1:end + 1 + count]
        assert len(blob) == count and batch.stdout[end + 1 + count:end + 2 + count] == b"\n"
        blobs[oid] = blob
        cursor = end + 2 + count
    assert cursor == len(batch.stdout)
    return paths, blobs


def verify_parent_custody(*, with_git: bool) -> dict:
    index = strict_json(pin(PARENT / "evidence-index.json", 176439, PARENT_INDEX_SHA))
    assert index["source_count"] == len(index["source_files"]) == 401
    assert index["raw_count"] == len(index["raw_files"]) == 153
    assert index["preflight_original_count"] == len(index["preflight_original_files"]) == 15
    assert len(index["accepted_source_pairs"]) == 76
    source_names = set()
    for row in index["source_files"]:
        relative = row["path"].replace("\\", "/")
        assert relative.casefold() not in source_names
        source_names.add(relative.casefold())
        pin(PARENT / relative, row["bytes"], row["sha256"])
    originals = [*index["raw_files"], *index["preflight_original_files"]]
    assert len({row["path"].casefold() for row in originals}) == 168
    for row in originals:
        assert set(row) == {"path", "bytes", "sha256", "role", "original_mandatory", "owned_copy"}
        assert row["original_mandatory"] is True and row["owned_copy"] is None
        pin(Path(row["path"]), row["bytes"], row["sha256"])
    for filename, count, key, schema in (
        ("raw-custody-map.json", 153, "raw_files", "i04-var10-parent-raw-custody/v101"),
        ("preflight-custody-map.json", 15, "preflight_original_files", "i04-var10-parent-preflight-custody/v101"),
    ):
        mapping = strict_json((PKG / filename).read_bytes())
        assert mapping["schema"] == schema and len(mapping["records"]) == count
        assert mapping["source_parent_index_sha256"] == PARENT_INDEX_SHA
        assert typed(mapping["records"], index[key])
    manifest = strict_json(pin(PARENT / "prelaunch-manifest.json", 161922, PARENT_MANIFEST_SHA))
    assert manifest["source_count"] == len(manifest["source_files"]) == 456
    assert manifest["local_only_context_originals"] == 2
    role_keys = set()
    role_paths = {}
    for row in manifest["source_files"]:
        key = row["key"].casefold()
        assert key not in role_keys
        role_keys.add(key)
        path = Path(row["path"]).resolve(strict=True)
        seal = row["bytes"], row["sha256"]
        assert path not in role_paths or role_paths[path] == seal
        role_paths[path] = seal
        pin(path, *seal)
    assert sum(key.startswith("local_only_context_original:") for key in role_keys) == 2
    pairs_map = strict_json((PKG / "parent-source-pairs.json").read_bytes())
    assert pairs_map["schema"] == "i04-var09-parent-disk-git-pairs/v1"
    assert pairs_map["source_parent_sha256"] == SOURCE_SELECTION_SHA
    source_pairs = pairs_map["records"]
    assert len(source_pairs) == 403
    prefix = "cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1/"
    expected = {prefix + row["path"].replace("\\", "/") for row in index["source_files"]}
    expected |= {prefix + "evidence-index.json", prefix + "review/independent-content-go-2026-10-08.md"}
    actual = [row["path"].replace("\\", "/") for row in source_pairs]
    assert len(actual) == len(set(actual)) == len({name.casefold() for name in actual}) == 403
    assert set(actual) == expected
    for row in source_pairs:
        pin(_repo_relative(row["path"]), row["bytes"], row["sha256"])
    for row in index["accepted_source_pairs"]:
        pin(_repo_relative(row["path"]), row["disk"]["bytes"], row["disk"]["sha256"])
    if with_git:
        paths, blobs = _git_blobs([row["oid"] for row in [*source_pairs, *index["accepted_source_pairs"]]])
        for row in source_pairs:
            assert paths.get(row["path"].replace("\\", "/")) == row["oid"]
            blob = blobs[row["oid"]]
            assert len(blob) == row["git"]["bytes"] and sha(blob) == row["git"]["sha256"]
        for row in index["accepted_source_pairs"]:
            assert paths.get(row["path"].replace("\\", "/")) == row["oid"]
            blob = blobs[row["oid"]]
            assert len(blob) == row["git"]["bytes"] and sha(blob) == row["git"]["sha256"]
    return index


def verify_catalog_499(c: dict) -> None:
    historical_local = c["catalog_current_499"]["local_crlf"]
    historical_git = c["catalog_current_499"]["base_git_lf"]
    local = pin(PKG / "preserved-context/catalog-local-499.json.bytes",
                historical_local["bytes"], historical_local["sha256"])
    git = pin(PKG / "preserved-context/catalog-git-499.json.bytes",
              historical_git["bytes"], historical_git["sha256"])
    assert local != git
    ldoc, gdoc = strict_json(local), strict_json(git)
    assert typed(ldoc, gdoc) and len(ldoc["entries"]) == 499
    live = strict_json((ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    assert set(live) == set(ldoc) and len(live["entries"]) >= 499
    for key in ldoc:
        if key != "entries":
            assert typed(live[key], ldoc[key])
    assert typed(live["entries"][:499], ldoc["entries"])
    ids = [row["publication_id"] for row in live["entries"]]
    assert len(ids) == len(set(ids)) and all(type(item) is str for item in ids)
    if len(live["entries"]) == 499:
        assert sha((ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes()) == sha(local)


def verify_excluded_v100(c: dict) -> None:
    history = c["excluded_v100"]
    inventory_pin = history["excluded_case_inventory"]
    inventory = strict_json(pin(ROOT / inventory_pin["path"], inventory_pin["bytes"], inventory_pin["sha256"]))
    assert inventory["source_count"] == len(inventory["source_files"]) == 24
    names = set()
    for row in inventory["source_files"]:
        assert row["path"].casefold() not in names and row["readonly"] is True
        names.add(row["path"].casefold())
        pin(_repo_relative(row["path"]), row["bytes"], row["sha256"])
    for name in ("independent_static_no_go", "prior_contract_go", "prior_generator",
                 "prior_original_generation_capture", "root_preservation_original_capture",
                 "root_preserved_v100_custody", "unexecuted_v101_generator_v1"):
        row = history[name]
        pin(ROOT / row["path"], row["bytes"], row["sha256"])


PROSPECTIVE_PROOF_ROLES = (
    "v100_excluded_inventory", "v100_preservation_method", "v100_preservation_result",
    "v100_static_no_go", "v101_design_generator_draft", "v101_design_generator",
    "independent_audit_v1_source", "independent_audit_v2_source", "v101_design_go",
    *(f"{capture}:{name}" for capture in (
        "preserve_v100", "generate_v101", "independent_audit_v1_failed",
        "independent_audit_v2_passed", "fresh_construction_boundary")
      for name in ("receipt.json", "stdout.bin", "stderr.bin")),
)


def verify_prospective_proof_custody() -> list[dict]:
    document = strict_json((PKG / "prospective-proof-custody.json").read_bytes())
    assert set(document) == {"schema", "records", "mandatory_host_original_count",
                             "original_binary_capture_dirs", "failed_audit_original_capture_present",
                             "no_manual_or_private_snapshot_copies"}
    assert document["schema"] == "i04-var10-v101-prospective-proof-custody/v1"
    rows = document["records"]
    assert len(rows) == len(PROSPECTIVE_PROOF_ROLES) == 24
    assert type(document["mandatory_host_original_count"]) is int and document["mandatory_host_original_count"] == 24
    assert type(document["original_binary_capture_dirs"]) is int and document["original_binary_capture_dirs"] == 5
    assert document["failed_audit_original_capture_present"] is True
    assert document["no_manual_or_private_snapshot_copies"] is True
    assert tuple(row["role"] for row in rows) == PROSPECTIVE_PROOF_ROLES
    paths = set()
    for row in rows:
        assert set(row) == {"role", "original_path", "bytes", "sha256", "disposition"}
        assert row["disposition"] == "mandatory_host_original"
        path = Path(row["original_path"]).resolve(strict=True)
        assert path.is_relative_to(ROOT.resolve(strict=True))
        assert str(path).casefold() not in paths
        paths.add(str(path).casefold())
        pin(path, row["bytes"], row["sha256"])
    return rows


def verify_context_custody(c: dict) -> list[dict]:
    document = strict_json((PKG / "context-custody.json").read_bytes())
    assert set(document) == {"schema", "records", "originals_mandatory_on_this_host",
                             "excluded_v100_owned", "extra_history_owned"}
    assert document["schema"] == "i04-var10-v101-context-custody/v1"
    assert document["originals_mandatory_on_this_host"] is True
    assert type(document["excluded_v100_owned"]) is int and document["excluded_v100_owned"] == 24
    assert type(document["extra_history_owned"]) is int and document["extra_history_owned"] == 6
    rows = document["records"]
    assert len(rows) == 30
    inventory_pin = c["excluded_v100"]["excluded_case_inventory"]
    inventory = strict_json(pin(ROOT / inventory_pin["path"], inventory_pin["bytes"], inventory_pin["sha256"]))
    for index, row in enumerate(rows):
        assert set(row) == {"original_path", "owned_copy", "bytes", "sha256",
                            "original_if_present_must_match"}
        assert row["original_if_present_must_match"] is True
        assert row["owned_copy"] == f"preserved-context/context-{index:03d}.bytes"
        original = Path(row["original_path"]).resolve(strict=True)
        assert original.is_relative_to(ROOT.resolve(strict=True))
        if index < 24:
            historical = inventory["source_files"][index]
            assert original == _repo_relative(historical["path"])
            assert (row["bytes"], row["sha256"]) == (historical["bytes"], historical["sha256"])
        pin(original, row["bytes"], row["sha256"])
        pin(PKG / row["owned_copy"], row["bytes"], row["sha256"])
    extra = (
        c["excluded_v100"]["root_preserved_v100_custody"],
        c["excluded_v100"]["independent_static_no_go"],
        c["excluded_v100"]["prior_contract_go"],
        {"path": "tmp/i04-var10-independent-contract-go-v101-20261008.md", "bytes": 5689,
         "sha256": "e3216eed06f7cb21c1bf65c613069f4a33e0148f8915439c9d65f3359cdc630b"},
        {"path": "tmp/i04-var10-build-prospective-v101-v2-20261008.py", "bytes": 29359,
         "sha256": "9d4846c87df8538da792b43839ba183219b847f38b69c4ae1fb93cb635c069b8"},
        {"path": "tmp/i04-var09-root-review-proofs-v100-20261008/i04-var10-prospective-v101-generation-20261008T125706458474Z-e8bf1bc0/receipt.json",
         "bytes": 1363, "sha256": "7bb69f4da050f7b23f539447d84d2bc1bc658e30b105121b92fca627b63e1c03"},
    )
    for row, known in zip(rows[24:], extra):
        assert Path(row["original_path"]).resolve(strict=True) == (ROOT / known["path"]).resolve(strict=True)
        assert (row["bytes"], row["sha256"]) == (known["bytes"], known["sha256"])
    return rows


MANIFEST_KEYS = frozenset({
    "schema", "run_id", "native_run_directory", "file_line_ascii_bytes",
    "file_line_ascii_max", "base_commit", "contract_sha256",
    "execution_binding_sha256", "source_count", "source_files",
    "live_catalog_prelaunch_pin", "historical_catalog_prefix_always_checked",
    "accepted_parent_indexed_sources", "accepted_current_source_git_pairs",
    "accepted_dependency_git_pairs", "accepted_parent_manifest_roles",
    "accepted_parent_raw", "accepted_parent_preflight_originals",
    "total_parent_original_raw", "excluded_v100_source_files",
    "owned_context_copies", "contract_originals", "local_only_context_originals",
    "mandatory_prospective_proof_originals", "converter_corrupt_file_negative_originals",
    "owned_pure_proof_copies", "new_native_runs_authorized_by_manifest",
    "independent_method_state",
})
ROLE_NAMES = {
    "prospective-contract.json": "prospective_contract",
    "execution-contract.json": "execution_binding",
    "native-input.json": "child_input",
    "validate_native_cli.py": "behavior_validator",
    "run_native_ssh.ps1": "runner_script",
    "review/independent_replay.py": "independent_replay",
    "review/independent_self_check.py": "independent_self_check",
}
CORRUPT_FILE_WITNESS = (
    ROOT / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0/runs/"
           "i04-var05-zero-transport-between-v100-ssh-20261008-01/model-run.log",
    1122, "ca209899bce7e299b49d9a482469efd8c0fee0d9f56673ffb99783cbf689457a",
)


def _contract_originals(c: dict) -> list[tuple[Path, int, str]]:
    found = {}
    def visit(node):
        if isinstance(node, dict):
            if {"path", "bytes", "sha256"} <= set(node):
                path = Path(node["path"])
                if not path.is_absolute():
                    path = _repo_relative(node["path"])
                path = path.resolve(strict=True)
                seal = node["bytes"], node["sha256"]
                identity = str(path).casefold()
                assert identity not in found or found[identity][1:] == seal
                found.setdefault(identity, (path, *seal))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(c)
    assert len(found) == 29
    return list(found.values())


def _role_expected(c: dict, inventory: dict, *, provisional: bool) -> list[tuple[str, Path, int, str]]:
    roles = []
    def add(key: str, path: Path, count: int, digest: str):
        roles.append((key, path.resolve(strict=True), count, digest))

    for row in inventory["source_files"]:
        relative = row["relative_path"].replace("\\", "/")
        add(ROLE_NAMES.get(relative, "owned:" + relative), PKG / relative, row["bytes"], row["sha256"])
    if not provisional:
        inventory_bytes = (PKG / "source-inventory.json").read_bytes()
        add("owned_source_inventory", PKG / "source-inventory.json", len(inventory_bytes), sha(inventory_bytes))
    parent_index = strict_json(pin(PARENT / "evidence-index.json", 176439, PARENT_INDEX_SHA))
    for index, row in enumerate(parent_index["source_files"]):
        add(f"accepted_parent_source:{index}", PARENT / row["path"], row["bytes"], row["sha256"])
    parent_manifest = strict_json(pin(PARENT / "prelaunch-manifest.json", 161922, PARENT_MANIFEST_SHA))
    for index, row in enumerate(parent_manifest["source_files"]):
        add(f"accepted_parent_role:{index}", Path(row["path"]), row["bytes"], row["sha256"])
    for category, filename, count in (("accepted_parent_raw", "raw_files", 153),
                                      ("accepted_parent_preflight", "preflight_original_files", 15)):
        rows = parent_index[filename]
        assert len(rows) == count
        for index, row in enumerate(rows):
            add(f"{category}:{index}", Path(row["path"]), row["bytes"], row["sha256"])
    pair_map = strict_json((PKG / "parent-source-pairs.json").read_bytes())
    assert len(pair_map["records"]) == 403
    for index, row in enumerate(pair_map["records"]):
        add(f"accepted_current_source:{index}", _repo_relative(row["path"]), row["bytes"], row["sha256"])
    for index, (path, count, digest) in enumerate(_contract_originals(c)):
        add(f"prospective_contract_original:{index}", path, count, digest)
    for index, row in enumerate(verify_context_custody(c)):
        add(f"excluded_v100_or_context_original:{index}", Path(row["original_path"]), row["bytes"], row["sha256"])
    for index, row in enumerate(verify_prospective_proof_custody()):
        add(f"prospective_review_original:{index}", Path(row["original_path"]), row["bytes"], row["sha256"])
    old = c["excluded_v100"]["excluded_case_inventory"]
    old_inventory = strict_json(pin(ROOT / old["path"], old["bytes"], old["sha256"]))
    for index, row in enumerate(old_inventory["source_files"]):
        add(f"excluded_v100_owned:{index}", _repo_relative(row["path"]), row["bytes"], row["sha256"])
    add("converter_corrupt_file_negative_original", *CORRUPT_FILE_WITNESS)
    return roles


def verify_manifest_document(c: dict, document: dict, inventory: dict, *, provisional: bool) -> dict:
    assert set(document) == MANIFEST_KEYS
    assert document["schema"] == "i04-var10-horizon-transit-prelaunch-manifest/v101"
    assert document["run_id"] == RUN_ID
    assert type(document["native_run_directory"]) is str and document["native_run_directory"] == str(RUN)
    assert type(document["file_line_ascii_bytes"]) is int and document["file_line_ascii_bytes"] == 121
    assert type(document["file_line_ascii_max"]) is int and document["file_line_ascii_max"] == 199
    assert document["base_commit"] == BASE_COMMIT and document["contract_sha256"] == CONTRACT_SHA
    binding = (PKG / "execution-contract.json").read_bytes()
    assert document["execution_binding_sha256"] == sha(binding)
    expected_counters = {
        "historical_catalog_prefix_always_checked": 499,
        "accepted_parent_indexed_sources": 401,
        "accepted_current_source_git_pairs": 403,
        "accepted_dependency_git_pairs": 76,
        "accepted_parent_manifest_roles": 456,
        "accepted_parent_raw": 153,
        "accepted_parent_preflight_originals": 15,
        "total_parent_original_raw": 168,
        "excluded_v100_source_files": 24,
        "owned_context_copies": 30,
        "contract_originals": 29,
        "local_only_context_originals": 2,
        "mandatory_prospective_proof_originals": 24,
        "converter_corrupt_file_negative_originals": 1,
        "owned_pure_proof_copies": 0 if provisional else 21,
        "new_native_runs_authorized_by_manifest": 0,
    }
    for key, value in expected_counters.items():
        assert type(document[key]) is int and document[key] == value, key
    assert document["independent_method_state"] == (
        "provisional" if provisional else "exact methods pinned; fresh approval required")
    catalog = document["live_catalog_prelaunch_pin"]
    assert set(catalog) == {"path", "bytes", "sha256"}
    assert catalog == {"path": str((ROOT / "cases/simlox-air-support/publication-index-v1.json").resolve(strict=True)),
                       "bytes": 539281,
                       "sha256": "ae07b4231038a3c02a4ecbe5959962a4d2ee401f6d810eee9d3998391ae29cdc"}
    expected = _role_expected(c, inventory, provisional=provisional)
    rows = document["source_files"]
    assert type(document["source_count"]) is int and document["source_count"] == len(rows) == len(expected)
    keys, identities = set(), {}
    for row, (key, path, count, digest) in zip(rows, expected):
        assert set(row) == {"key", "path", "bytes", "sha256"}
        assert type(row["key"]) is str and row["key"] == key
        assert type(row["path"]) is str and row["path"] == str(path)
        assert type(row["bytes"]) is int and row["bytes"] == count
        assert type(row["sha256"]) is str and row["sha256"] == digest
        assert row["key"].casefold() not in keys
        keys.add(row["key"].casefold())
        identity = str(path).casefold()
        seal = count, digest
        assert identity not in identities or identities[identity] == seal
        identities[identity] = seal
        pin(path, count, digest)
    return {row["key"]: row["sha256"] for row in rows}


def exact_integer(value, expected: int | None = None) -> int:
    assert type(value) is int
    if expected is not None:
        assert value == expected
    return value


def file_record(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha(data)}


def utc(value: str) -> datetime.datetime:
    assert type(value) is str
    result = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert result.tzinfo is not None and result.utcoffset() == datetime.timedelta(0)
    return result


def source_map_sha(mapping: dict) -> str:
    assert type(mapping) is dict
    assert all(type(key) is str and type(value) is str for key, value in mapping.items())
    return sha(json.dumps(mapping, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def strict_source_map(actual: dict, wanted: dict) -> None:
    assert type(actual) is dict and list(actual) == list(wanted)
    assert actual == wanted


PURE_CHECK_KEYS = frozenset({
    "tool", "program", "arguments", "started_utc", "completed_utc", "status", "error",
    "child_pid", "child_session_id", "exit_code", "capture_error", "stdout_path",
    "stderr_path", "stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256",
})
PURE_PROOF_KEYS = frozenset({
    "schema", "mode", "run_id", "native_run_directory", "manifest_sha256",
    "source_map_sha256", "started_utc", "completed_utc", "status", "error",
    "checks", "source_hashes_after",
})
PREFLIGHT_KEYS = frozenset({
    "schema", "run_id", "native_run_directory", "run_dirs_absent",
    "file_line_ascii_bytes", "file_line_ascii_max", "native_run_path_ancestors_no_reparse",
    "ssh_session", "ps_major", "ssh_ancestors", "mutex_free", "wts_active_gui_count",
    "gui", "accepted_parent_raw", "accepted_parent_preflight_originals",
    "excluded_v100_source_files", "total_parent_original_raw", "manifest_sha256",
    "source_map_sha256", "source_hashes", "source_hashes_after_pure",
    "pure_proof_directory", "pure_proof_path", "pure_proof_sha256", "pure_checks",
    "native_process_started",
})


def verify_pure_proof(path: Path, receipt: dict, *, mode: str, manifest_sha: str,
                      source_map: dict, source_sha: str) -> dict:
    assert mode in ("preflight", "native") and type(receipt) is dict
    directory = path.parent
    assert directory.parent == PKG / "test-output"
    assert re.fullmatch(rf"{mode}-pure-[0-9]{{8}}T[0-9]{{13}}Z-[0-9a-f]{{8}}", directory.name)
    assert path == directory / "pure-proof.json" and not path.is_symlink()
    assert file_record(path)["sha256"] == receipt["pure_proof_sha256"]
    if mode == "preflight":
        assert type(receipt["pure_proof_directory"]) is str
        assert receipt["pure_proof_directory"] == str(directory)
    else:
        assert "pure_proof_directory" not in receipt
    assert type(receipt["pure_proof_path"]) is str and receipt["pure_proof_path"] == str(path)
    proof = strict_json(path.read_bytes())
    assert set(proof) == PURE_PROOF_KEYS
    assert proof["schema"] == "i04-var10-horizon-transit-pure-proof/v101"
    assert proof["mode"] == mode and proof["run_id"] == RUN_ID
    assert type(proof["native_run_directory"]) is str and proof["native_run_directory"] == str(RUN)
    assert proof["manifest_sha256"] == manifest_sha and proof["source_map_sha256"] == source_sha
    assert proof["status"] == "passed" and proof["error"] is None
    assert type(proof["checks"]) is list and len(proof["checks"]) == 5
    assert type(receipt["pure_checks"]) is list and proof["checks"] == receipt["pure_checks"]
    strict_source_map(proof["source_hashes_after"], source_map)
    strict_source_map(receipt["source_hashes_after_pure"], source_map)
    previous = utc(proof["started_utc"])
    for index, (tool, step) in enumerate(zip(PURE_TOOLS, proof["checks"])):
        assert set(step) == PURE_CHECK_KEYS
        assert step["tool"] == tool and type(step["program"]) is str and step["program"] == str(PYTHON)
        assert step["arguments"] == f'-X utf8 -B "{PKG / tool}"'
        assert step["status"] == "completed" and step["error"] is None and step["capture_error"] is None
        exact_integer(step["child_session_id"], 0)
        exact_integer(step["exit_code"], 0)
        assert exact_integer(step["child_pid"]) > 0
        started, finished = utc(step["started_utc"]), utc(step["completed_utc"])
        assert previous <= started <= finished, index
        previous = finished
        for stream in ("stdout", "stderr"):
            stream_path = directory / f"{Path(tool).stem}-{stream}.bin"
            assert type(step[f"{stream}_path"]) is str and step[f"{stream}_path"] == str(stream_path)
            assert not stream_path.is_symlink()
            assert file_record(stream_path) == {"bytes": step[f"{stream}_bytes"],
                                                "sha256": step[f"{stream}_sha256"]}
            exact_integer(step[f"{stream}_bytes"])
        exact_integer(step["stderr_bytes"], 0)
    assert previous <= utc(proof["completed_utc"])
    return proof


def preflight_core(receipt: dict, manifest_sha: str, source_map: dict, source_sha: str) -> None:
    assert set(receipt) == PREFLIGHT_KEYS
    assert receipt["schema"] == "i04-var10-horizon-transit-ssh-preflight/v101"
    assert receipt["run_id"] == RUN_ID
    assert type(receipt["native_run_directory"]) is str and receipt["native_run_directory"] == str(RUN)
    assert receipt["manifest_sha256"] == manifest_sha and receipt["source_map_sha256"] == source_sha
    for key in ("run_dirs_absent", "native_run_path_ancestors_no_reparse", "mutex_free"):
        assert receipt[key] is True
    assert receipt["native_process_started"] is False
    for key, expected in (("file_line_ascii_bytes", 121), ("file_line_ascii_max", 199),
                          ("ssh_session", 0), ("ps_major", 5), ("wts_active_gui_count", 1),
                          ("accepted_parent_raw", 153), ("accepted_parent_preflight_originals", 15),
                          ("excluded_v100_source_files", 24), ("total_parent_original_raw", 168)):
        exact_integer(receipt[key], expected)
    assert type(receipt["ssh_ancestors"]) is list and "sshd.exe" in receipt["ssh_ancestors"]
    assert typed(receipt["gui"], GUI)
    strict_source_map(receipt["source_hashes"], source_map)
    strict_source_map(receipt["source_hashes_after_pure"], source_map)
    assert type(receipt["pure_checks"]) is list and len(receipt["pure_checks"]) == 5
    assert type(receipt["pure_proof_directory"]) is str and type(receipt["pure_proof_path"]) is str
    assert type(receipt["pure_proof_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", receipt["pure_proof_sha256"])


def verify_preflight(path: Path, preflight_sha: str, manifest_sha: str,
                     source_map: dict, source_sha: str) -> dict:
    assert path.parent == PKG / "review"
    assert re.fullmatch(r"preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json", path.name)
    assert not path.is_symlink() and file_record(path)["sha256"] == preflight_sha
    receipt = strict_json(path.read_bytes())
    preflight_core(receipt, manifest_sha, source_map, source_sha)
    verify_pure_proof(Path(receipt["pure_proof_path"]), receipt, mode="preflight",
                      manifest_sha=manifest_sha, source_map=source_map, source_sha=source_sha)
    return receipt


APPROVAL_KEYS = frozenset({
    "schema", "decision", "run_id", "native_run_directory", "manifest_sha256",
    "runner_sha256", "validator_sha256", "contract_sha256", "execution_binding_sha256",
    "input_sha256", "source_map_sha256", "independent_replay_sha256",
    "preflight_relative_path", "preflight_sha256",
})


def verify_approval(source_map: dict, source_sha: str) -> tuple[dict, Path, dict]:
    approval_path = PKG / "review/independent-prelaunch-go.json"
    approval = strict_json(approval_path.read_bytes())
    assert set(approval) == APPROVAL_KEYS
    assert approval["schema"] == "i04-var10-horizon-transit-independent-prelaunch-go/v101"
    assert approval["decision"] == "GO_PRELAUNCH" and approval["run_id"] == RUN_ID
    assert type(approval["native_run_directory"]) is str and approval["native_run_directory"] == str(RUN)
    bindings = {
        "manifest_sha256": file_record(PKG / "prelaunch-manifest.json")["sha256"],
        "runner_sha256": source_map["runner_script"],
        "validator_sha256": source_map["behavior_validator"],
        "contract_sha256": CONTRACT_SHA,
        "execution_binding_sha256": source_map["execution_binding"],
        "input_sha256": source_map["child_input"],
        "source_map_sha256": source_sha,
        "independent_replay_sha256": source_map["independent_replay"],
    }
    for key, expected in bindings.items():
        assert approval[key] == expected, key
    relative = approval["preflight_relative_path"].replace("\\", "/")
    assert re.fullmatch(r"review/preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json", relative)
    preflight = verify_preflight(PKG / relative, approval["preflight_sha256"],
                                 bindings["manifest_sha256"], source_map, source_sha)
    return approval, approval_path, preflight


def native_run_path(*, must_be_absent: bool) -> Path:
    assert RUN.is_absolute() and RUN.parent == ROOT / "tmp/native-runs"
    assert str(RUN) == "C:\\Users\\user\\Documents\\Codex\\2026-09-29\\simlox-c04-deadline\\repo\\tmp\\native-runs\\i04v10-v101-20261008-01"
    for ancestor in (RUN, *RUN.parents):
        if ancestor.exists():
            assert not ancestor.is_symlink() and not ancestor.is_junction()
    line = "File: " + (RUN / "model.sxi").as_posix()
    assert line.isascii() and len(line.encode("ascii")) == 121 <= 199
    assert RUN.exists() is (not must_be_absent)
    return RUN


def expected_plan(run: Path) -> tuple[list[dict], list[dict]]:
    native = (
        ("import", f'-silent -jimport "{run / "input.json"}" -save "{run / "model.sxi"}" -log "{run / "import.log"}" -close'),
        ("export", f'"{run / "model.sxi"}" -silent -jexport "{run / "roundtrip-raw.json"}" -log "{run / "export.log"}" -close'),
        ("calc", f'"{run / "model.sxi"}" -silent -threads 1 -calc -log "{run / "model-run.log"}" -close'),
        ("jsonreport", f'"{run / "model.sxo"}" -silent -jsonreport "{run / "report-raw.json"}" -log "{run / "report-export.log"}" -close'),
    )
    checkers = (
        ("check_import_export", f'-X utf8 -B "{PKG / "check_roundtrip.py"}" "{run}"'),
        ("check_behavior", f'-X utf8 -B "{PKG / "validate_native_cli.py"}" "{run}"'),
    )
    return ([{"name": name, "program": str(SIMLOX), "arguments": argv} for name, argv in native],
            [{"name": name, "program": str(PYTHON), "arguments": argv} for name, argv in checkers])


STEP_KEYS = frozenset({
    "sequence", "name", "program", "arguments", "started_utc", "completed_utc",
    "child_pid", "child_session_id", "exit_code", "capture_error", "stdout_path",
    "stderr_path", "stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256",
    "converter_log_bytes", "converter_log_sha256", "converter_log_validated",
    "gui_preserved", "status", "error",
})


def stage_core(step: dict, index: int, name: str, plan: dict,
               previous: datetime.datetime) -> datetime.datetime:
    assert set(step) == STEP_KEYS
    exact_integer(step["sequence"], index)
    assert step["name"] == name and step["program"] == plan["program"]
    assert step["arguments"] == plan["arguments"]
    assert step["capture_error"] is None and step["error"] is None
    assert step["status"] == "completed" and step["gui_preserved"] is True
    exact_integer(step["child_session_id"], 0)
    exact_integer(step["exit_code"], 0)
    assert exact_integer(step["child_pid"]) > 0
    started, completed = utc(step["started_utc"]), utc(step["completed_utc"])
    assert previous <= started <= completed
    for stream in ("stdout", "stderr"):
        assert type(step[f"{stream}_path"]) is str
        exact_integer(step[f"{stream}_bytes"])
        assert type(step[f"{stream}_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", step[f"{stream}_sha256"])
    exact_integer(step["stderr_bytes"], 0)
    if name == "calc":
        exact_integer(step["converter_log_bytes"])
        assert type(step["converter_log_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", step["converter_log_sha256"])
        assert step["converter_log_validated"] is True
    else:
        assert step["converter_log_bytes"] is None and step["converter_log_sha256"] is None
        assert step["converter_log_validated"] is False
    return completed


INVOCATION_KEYS = frozenset({
    "schema", "run_id", "created_utc", "original_run_dir", "native_run_directory",
    "input_sha256", "contract_sha256", "manifest_sha256", "approval_sha256",
    "approved_preflight_path", "approved_preflight_sha256", "independent_replay_sha256",
    "runner_script_sha256", "session_id", "ssh_ancestors", "gui", "queue_mutex",
    "working_directory", "planned_commands", "planned_checkers", "source_hashes_before",
    "source_hashes_after_pure", "pure_proof_path", "pure_proof_sha256", "pure_checks",
    "publication_state",
})
CLOSURE_KEYS = frozenset({
    "schema", "run_id", "native_run_directory", "invocation_sha256", "manifest_sha256",
    "approval_sha256", "approved_preflight_sha256", "source_hashes_before",
    "source_hashes_after", "raw", "step_error", "error", "publication_state",
})


def verify_run_provenance(manifest: dict, source_map: dict, source_sha: str) -> dict:
    run = native_run_path(must_be_absent=False)
    assert run == RUN and not run.is_symlink()
    assert {item.name for item in run.iterdir()} == RUN_FILES
    assert all(item.is_file() and not item.is_symlink() for item in run.iterdir())
    approval, approval_path, preflight = verify_approval(source_map, source_sha)
    invocation_blob = (run / "invocation.json").read_bytes()
    invocation = strict_json(invocation_blob)
    closure = strict_json((run / "closure.json").read_bytes())
    steps = strict_json((run / "steps.json").read_bytes())
    manifest_sha = file_record(PKG / "prelaunch-manifest.json")["sha256"]
    approval_sha = file_record(approval_path)["sha256"]
    native, checkers = expected_plan(run)
    assert set(invocation) == INVOCATION_KEYS
    assert invocation["schema"] == "i04-var10-horizon-transit-invocation/v101"
    assert invocation["run_id"] == RUN_ID
    assert type(invocation["original_run_dir"]) is str and invocation["original_run_dir"] == str(run)
    assert type(invocation["native_run_directory"]) is str and invocation["native_run_directory"] == str(run)
    utc(invocation["created_utc"])
    for key, wanted in (("input_sha256", source_map["child_input"]),
                        ("contract_sha256", CONTRACT_SHA), ("manifest_sha256", manifest_sha),
                        ("approval_sha256", approval_sha),
                        ("approved_preflight_sha256", approval["preflight_sha256"]),
                        ("independent_replay_sha256", source_map["independent_replay"]),
                        ("runner_script_sha256", source_map["runner_script"])):
        assert invocation[key] == wanted, key
    assert type(invocation["approved_preflight_path"]) is str
    assert invocation["approved_preflight_path"] == str(PKG / approval["preflight_relative_path"])
    exact_integer(invocation["session_id"], 0)
    assert type(invocation["ssh_ancestors"]) is list and "sshd.exe" in invocation["ssh_ancestors"]
    assert typed(invocation["gui"], GUI)
    assert invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
    assert invocation["working_directory"] == str(WORKING_DIRECTORY)
    assert invocation["planned_commands"] == native and invocation["planned_checkers"] == checkers
    assert invocation["publication_state"] == "not_published"
    strict_source_map(invocation["source_hashes_before"], source_map)
    verify_pure_proof(Path(invocation["pure_proof_path"]), invocation, mode="native",
                      manifest_sha=manifest_sha, source_map=source_map, source_sha=source_sha)
    assert set(closure) == CLOSURE_KEYS
    assert closure["schema"] == "i04-var10-horizon-transit-closure/v101" and closure["run_id"] == RUN_ID
    assert type(closure["native_run_directory"]) is str and closure["native_run_directory"] == str(run)
    assert closure["invocation_sha256"] == sha(invocation_blob)
    for key, wanted in (("manifest_sha256", manifest_sha), ("approval_sha256", approval_sha),
                        ("approved_preflight_sha256", approval["preflight_sha256"])):
        assert closure[key] == wanted, key
    assert closure["publication_state"] == "not_published"
    assert closure["step_error"] in (None, "") and closure["error"] in (None, "")
    strict_source_map(closure["source_hashes_before"], source_map)
    strict_source_map(closure["source_hashes_after"], source_map)
    raw = closure["raw"]
    assert type(raw) is dict and set(raw) == RUN_FILES - {"invocation.json", "closure.json"}
    assert len(raw) == 23
    for name, record in raw.items():
        assert set(record) == {"bytes", "sha256"}
        exact_integer(record["bytes"])
        assert file_record(run / name) == record
    assert (run / "input.json").read_bytes() == (PKG / "native-input.json").read_bytes()
    assert type(steps) is list and len(steps) == 6
    previous = utc(invocation["created_utc"])
    by_name = {item["name"]: item for item in [*native, *checkers]}
    for index, (name, step) in enumerate(zip(STAGES, steps)):
        previous = stage_core(step, index, name, by_name[name], previous)
        for stream in ("stdout", "stderr"):
            filename = ("roundtrip-validation.json" if name == "check_import_export" else
                        "author-validation.json" if name == "check_behavior" else
                        f"{name}-stdout.txt") if stream == "stdout" else f"{name}-stderr.txt"
            target = run / filename
            assert step[f"{stream}_path"] == str(target)
            assert file_record(target) == {"bytes": step[f"{stream}_bytes"],
                                           "sha256": step[f"{stream}_sha256"]}
        if name == "calc":
            assert {"bytes": step["converter_log_bytes"],
                    "sha256": step["converter_log_sha256"]} == raw["model-run.log"]
    return {"invocation": invocation, "closure": closure, "steps": steps,
            "approval": approval, "preflight": preflight, "raw_file_count": len(raw)}


OWNED_CORE = (
    ".gitattributes", ".gitignore", "README.md", "REPRODUCTION.md",
    "prospective-contract.json", "prospective-contract.md", "prospective-log-oracle.json",
    "prospective-report-oracle.json", "prospective-source-delta.json", "execution-contract.json",
    "native-input.json", "exact-diff.json", "child-report-oracle.json",
    "child-roundtrip-oracle.json", "parent-source-pairs.json", "raw-custody-map.json",
    "preflight-custody-map.json", "prospective-proof-custody.json",
    "make_prospective_proof_custody.py", "model_common.py", "build.py", "make_parent_custody.py",
    "check_roundtrip.py", "event_ledger.py", "report_oracle.py", "validate_native_cli.py",
    "self_check.py", "source_gate.py", "copy_context.py", "context-custody.json",
    "captured_process.ps1", "checker_receipt.ps1", "preflight_receipt.ps1",
    "run_native_ssh.ps1", "ssh_transport.py", "test_converter_gate.ps1",
    "pure_proof.py", "copy_pure_proof.py", "pure-proof-custody.json",
    "make_source_inventory.py", "make_prelaunch_manifest.py",
)
DEVELOPMENT = (
    "source-gate-v1-cwd-dependent-accepted-refs.py.bytes",
    "context-custody-v1-optional-originals.json.bytes",
    "copy-context-v2-mandatory-originals.py.bytes",
    "preflight-native-path-array-static-finding.md",
    "test-converter-v1-reparse-extraction-failure.ps1.bytes",
    "test-converter-v1-reparse-extraction-failure.md",
    "test-converter-v2-junction-removal-failure.ps1.bytes",
    "test-converter-v2-junction-removal-failure.md",
    "source-gate-v2-development-count-drift.py.bytes",
    "manifest-v1-development-count-drift.py.bytes",
    "manifest-v1-development-count-drift.md",
)
CONTEXT_DESCRIPTIVE = (
    "catalog-local-499.json.bytes", "catalog-git-499.json.bytes",
    "root-selection.json.bytes", "root-construction-boundary.json.bytes",
)
REVIEW_ORDER = (
    "review/independent_replay.py", "review/independent_self_check.py",
    "review/preserved-independent-v1-v100-template.py.bytes",
    "review/preserved-self-check-v1-converter-line-ending-probe.md",
    "review/preserved-independent-v2-pure-fixture-native-report-mode.py.bytes",
    "review/preserved-independent-v2-pure-fixture-native-report-mode.md",
    "review/independent-method-static-go-2026-10-08.md",
)
FUTURE_AUTHOR_NAMES = (
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "cli-scope-signoff-2026-10-08.md", "publication-entry.json", "make_evidence_index.py",
    "evidence-index.json", "copy_postrun_context.py", "postrun-context-custody.json",
    "postrun-context-originals.json", "make_raw_custody.py", "make_preflight_custody.py",
)
FUTURE_PATTERN = (
    r"preserved-postrun/postrun-[0-9]{3}\.bytes",
    r"preserved-postrun-development/draft-[0-9]{3}\.bytes",
    r"preserved-raw/raw-[0-9]{3}\.bytes",
    r"preserved-preflight/preflight-[0-9]{3}\.bytes",
)
FUTURE_CUSTODY_NAMES = (
    "preserved-postrun/custody.json", "preserved-postrun-development/custody.json",
    "preserved-raw/custody.json", "preserved-preflight/custody.json",
)
FUTURE_REVIEW_PREFIX = (
    "review/independent-prelaunch-", "review/independent-postrun-",
    "review/independent-content-", "review/independent-staged-",
    "review/independent-remote-", "review/independent-pr-", "review/preflight-ssh0-",
)


def owned_names(*, provisional: bool) -> list[str]:
    names = [name for name in OWNED_CORE if not (provisional and name == "pure-proof-custody.json")]
    names += ["preserved-development/" + name for name in DEVELOPMENT]
    names += ["preserved-context/" + name for name in CONTEXT_DESCRIPTIVE]
    names += [f"preserved-context/context-{index:03d}.bytes" for index in range(30)]
    if not provisional:
        names += [f"preserved-pure-proof/pure-{index:02d}.bytes" for index in range(21)]
        names += list(REVIEW_ORDER)
    assert len(names) == len(set(names))
    assert len(names) == (85 if provisional else 114), len(names)
    return names


def _allowed_future(relative: str) -> bool:
    if relative in FUTURE_AUTHOR_NAMES + FUTURE_CUSTODY_NAMES:
        return True
    if any(re.fullmatch(pattern, relative) for pattern in FUTURE_PATTERN):
        return True
    for prefix in FUTURE_REVIEW_PREFIX:
        if relative.startswith(prefix):
            suffix = relative[len(prefix):]
            return bool(suffix) and "/" not in suffix and "\\" not in suffix
    return False


def assert_inventory_order(rows: list[dict], names: list[str]) -> None:
    assert type(rows) is list and len(rows) == len(names)
    for row, name in zip(rows, names):
        assert type(row) is dict and type(row.get("relative_path")) is str
        assert row["relative_path"] == name


def verify_inventory_document(document: dict, *, provisional: bool) -> dict:
    assert type(document) is dict and set(document) == {
        "schema", "source_count", "source_files", "provisional", "excluded_future"}
    assert document["schema"] == "i04-var10-horizon-transit-owned-source-inventory/v101"
    assert document["provisional"] is provisional
    assert document["excluded_future"] == [
        "runs/", "test-output/", "transport-evidence/", *FUTURE_AUTHOR_NAMES,
        *FUTURE_PATTERN, *FUTURE_CUSTODY_NAMES, *FUTURE_REVIEW_PREFIX]
    names = owned_names(provisional=provisional)
    rows = document["source_files"]
    assert type(rows) is list and type(document["source_count"]) is int
    assert len(rows) == document["source_count"] == len(names)
    assert_inventory_order(rows, names)
    seen = set()
    for name, row in zip(names, rows):
        assert type(row) is dict and set(row) == {"relative_path", "path", "bytes", "sha256"}
        assert type(row["relative_path"]) is str and row["relative_path"] == name
        path = PKG / name
        assert path.is_file() and not path.is_symlink() and not path.is_junction()
        assert type(row["path"]) is str and row["path"] == str(path.resolve(strict=True))
        assert row["path"].casefold() not in seen
        seen.add(row["path"].casefold())
        assert type(row["bytes"]) is int and row["bytes"] >= 0
        assert type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        pin(path, row["bytes"], row["sha256"])
    allowed = set(names) | {"source-inventory.json", "prelaunch-manifest.json"}
    for path in PKG.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PKG).as_posix()
        if relative in allowed or _allowed_future(relative):
            continue
        parts = relative.split("/")
        if parts[0] in ("runs", "test-output", "transport-evidence") and len(parts) > 1:
            continue
        if relative.endswith(".pyc") and (
            len(parts) == 2 and parts[0] == "__pycache__" or
            len(parts) == 3 and parts[:2] == ["review", "__pycache__"]):
            continue
        if provisional and (relative.startswith("review/") or
                            relative == "pure-proof-custody.json" or
                            relative.startswith("preserved-pure-proof/")):
            continue
        raise AssertionError(f"unlisted publishable source: {relative}")
    return document


def verify_pure_history() -> list[dict]:
    document = strict_json((PKG / "pure-proof-custody.json").read_bytes())
    assert type(document) is dict and set(document) == {
        "schema", "records", "originals_optional_after_publication",
        "author_record_count", "independent_record_count"}
    assert document["schema"] == "i04-var10-pure-proof-custody/v101"
    assert document["originals_optional_after_publication"] is True
    exact_integer(document["author_record_count"], 15)
    exact_integer(document["independent_record_count"], 6)
    rows = document["records"]
    assert type(rows) is list and len(rows) == 21
    author_names = tuple(f"{stem}-{stream}.bin" for stem in
                         ("build", "context", "source", "selfcheck", "converter", "inventory", "manifest")
                         for stream in ("stdout", "stderr")) + ("receipt.json",)
    dirs = []
    for index, row in enumerate(rows):
        assert type(row) is dict and set(row) == {
            "original_path", "owned_copy", "bytes", "sha256", "original_if_present_must_match"}
        assert row["owned_copy"] == f"preserved-pure-proof/pure-{index:02d}.bytes"
        assert row["original_if_present_must_match"] is True
        assert type(row["original_path"]) is str
        original = Path(row["original_path"])
        assert original.is_absolute()
        assert type(row["bytes"]) is int and row["bytes"] >= 0
        assert type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        owned = PKG / row["owned_copy"]
        pin(owned, row["bytes"], row["sha256"])
        if original.exists():
            pin(original, row["bytes"], row["sha256"])
        dirs.append(original.parent)
        if index < 15:
            assert original.name == author_names[index]
        else:
            assert original.name == ("receipt.json", "stdout.bin", "stderr.bin")[(index - 15) % 3]
    assert len(set(dirs[:15])) == 1
    assert dirs[0].parent == PKG / "test-output"
    assert re.fullmatch(r"local-pure-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}", dirs[0].name)
    assert len(set(dirs[15:18])) == len(set(dirs[18:21])) == 1
    assert len({dirs[0], dirs[15], dirs[18]}) == 3
    return rows


def _provisional_inventory(manifest: dict) -> dict:
    names = owned_names(provisional=True)
    rows = []
    for name, role in zip(names, manifest["source_files"][:len(names)]):
        path = PKG / name
        record = file_record(path)
        assert role["path"] == str(path.resolve(strict=True))
        assert role["bytes"] == record["bytes"] and role["sha256"] == record["sha256"]
        rows.append({"relative_path": name, "path": str(path.resolve(strict=True)), **record})
    return {"schema": "i04-var10-horizon-transit-owned-source-inventory/v101",
            "source_count": len(rows), "source_files": rows, "provisional": True,
            "excluded_future": ["runs/", "test-output/", "transport-evidence/", *FUTURE_AUTHOR_NAMES,
                                *FUTURE_PATTERN, *FUTURE_CUSTODY_NAMES, *FUTURE_REVIEW_PREFIX]}


def pure_fixture() -> None:
    assert not RUN.exists()
    c = contract()
    oracle = oracles(c)
    verify_parent_custody(with_git=False)
    verify_catalog_499(c)
    verify_excluded_v100(c)
    verify_context_custody(c)
    verify_prospective_proof_custody()
    verify_source(c, oracle["source-delta.json"])
    verify_export(c, strict_json((PKG / "child-roundtrip-oracle.json").read_bytes()))
    expected = ("\r\n".join(expected_log(c, oracle["log-oracle.json"])) + "\r\n").encode("utf-8")
    verify_log(c, oracle["log-oracle.json"], expected)
    assert report_equal(strict_json((PKG / "child-report-oracle.json").read_bytes()),
                        report_expected(c, oracle["report-oracle.json"]))
    print("INDEPENDENT_PURE_FIXTURE_PASS 34/21/211 61/53 1244")


def pure_inventory_candidate(path: Path) -> None:
    assert not RUN.exists() and path.is_absolute() and path.is_file()
    assert path.is_relative_to(ROOT / "tmp") and path != PKG / "source-inventory.json"
    document = strict_json(path.read_bytes())
    verify_inventory_document(document, provisional=False)
    verify_pure_history()
    print(f"GO_INVENTORY_CANDIDATE {sha(path.read_bytes())} sources={document['source_count']}")


def pure_manifest_candidate(path: Path) -> None:
    assert not RUN.exists() and path.is_absolute() and path.is_file()
    assert path.is_relative_to(ROOT / "tmp") and path != PKG / "prelaunch-manifest.json"
    c = contract()
    inventory = strict_json((PKG / "source-inventory.json").read_bytes())
    verify_inventory_document(inventory, provisional=False)
    verify_pure_history()
    document = strict_json(path.read_bytes())
    roles = verify_manifest_document(c, document, inventory, provisional=False)
    assert roles["owned_source_inventory"] == file_record(PKG / "source-inventory.json")["sha256"]
    print(f"GO_MANIFEST_CANDIDATE {sha(path.read_bytes())} roles={document['source_count']}")


def pure_preflight() -> None:
    native_run_path(must_be_absent=True)
    c = contract()
    verify_parent_custody(with_git=True)
    verify_catalog_499(c)
    verify_excluded_v100(c)
    verify_context_custody(c)
    verify_prospective_proof_custody()
    verify_pure_history()
    inventory = strict_json((PKG / "source-inventory.json").read_bytes())
    verify_inventory_document(inventory, provisional=False)
    manifest = strict_json((PKG / "prelaunch-manifest.json").read_bytes())
    roles = verify_manifest_document(c, manifest, inventory, provisional=False)
    assert roles["owned_source_inventory"] == file_record(PKG / "source-inventory.json")["sha256"]
    print(f"INDEPENDENT_PURE_PREFLIGHT_PASS roles={len(roles)} native=0")


def main() -> None:
    import sys
    args = sys.argv[1:]
    if args == ["--pure-fixture"]:
        pure_fixture()
    elif args == ["--pure-preflight"]:
        pure_preflight()
    elif len(args) == 2 and args[0] == "--pure-inventory-candidate":
        pure_inventory_candidate(Path(args[1]).absolute())
    elif len(args) == 2 and args[0] == "--pure-manifest-candidate":
        pure_manifest_candidate(Path(args[1]).absolute())
    elif len(args) == 2 and args[0] == "--evidence-dir":
        sealed_replay(Path(args[1]).absolute())
    else:
        raise AssertionError("exact independent mode required")


ROUNDTRIP_KEYS = frozenset({
    "schema", "passed", "run_id", "native_run_directory", "tables", "authored_rows",
    "exported_rows", "authored_cells", "exported_cells", "all_null_placeholder_tables",
    "issues", "input_sha256", "export_sha256",
})
BEHAVIOR_KEYS = frozenset({
    "schema", "passed", "run_id", "native_run_directory", "input_sha256",
    "export_sha256", "report_cell_checks", "timed_event_records", "log_lines",
    "terminal", "issues", "native_calls",
})
TERMINAL = {
    "initial_aircraft": 2, "first_mission_completed": 1,
    "source_ready_terminal": 0, "target_ready_terminal": 1,
    "assigned_terminal": 0, "transit_terminal": 1,
    "arrived_id0_before_horizon": False, "microstates": 53,
}


def verify_checker_receipts(roundtrip: dict, behavior: dict, input_sha: str,
                            export_sha: str) -> None:
    assert type(roundtrip) is dict and set(roundtrip) == ROUNDTRIP_KEYS
    assert roundtrip["schema"] == "i04-var10-horizon-transit-roundtrip/v101"
    assert roundtrip["passed"] is True and roundtrip["run_id"] == RUN_ID
    assert type(roundtrip["native_run_directory"]) is str and roundtrip["native_run_directory"] == str(RUN)
    for key, expected in (("tables", 34), ("authored_rows", 21), ("exported_rows", 39),
                          ("authored_cells", 211), ("exported_cells", 395),
                          ("all_null_placeholder_tables", 18)):
        exact_integer(roundtrip[key], expected)
    assert type(roundtrip["issues"]) is list and roundtrip["issues"] == []
    assert roundtrip["input_sha256"] == input_sha and roundtrip["export_sha256"] == export_sha
    assert type(behavior) is dict and set(behavior) == BEHAVIOR_KEYS
    assert behavior["schema"] == "i04-var10-horizon-transit-behavior/v101"
    assert behavior["passed"] is True and behavior["run_id"] == RUN_ID
    assert type(behavior["native_run_directory"]) is str and behavior["native_run_directory"] == str(RUN)
    assert behavior["input_sha256"] == input_sha and behavior["export_sha256"] == export_sha
    for key, expected in (("report_cell_checks", 1244), ("timed_event_records", 53),
                          ("log_lines", 61), ("native_calls", 0)):
        exact_integer(behavior[key], expected)
    assert type(behavior["issues"]) is list and behavior["issues"] == []
    assert type(behavior["terminal"]) is dict and set(behavior["terminal"]) == set(TERMINAL)
    for key, expected in TERMINAL.items():
        assert type(behavior["terminal"][key]) is type(expected)
        assert behavior["terminal"][key] == expected, key


def recovered_evidence(directory: Path, closure: dict) -> dict[str, bytes]:
    assert directory.is_absolute() and directory != RUN and directory.is_dir()
    assert not directory.is_symlink() and not directory.is_junction()
    assert {entry.name for entry in directory.iterdir()} == RUN_FILES
    data = {}
    for name in RUN_FILES:
        copy_path = directory / name
        original = RUN / name
        assert copy_path.is_file() and not copy_path.is_symlink()
        raw = copy_path.read_bytes()
        assert raw == original.read_bytes(), name
        if name not in ("invocation.json", "closure.json"):
            assert {"bytes": len(raw), "sha256": sha(raw)} == closure["raw"][name]
        data[name] = raw
    return data


def sealed_replay(evidence_dir: Path) -> None:
    c = contract()
    oracle = oracles(c)
    verify_parent_custody(with_git=True)
    verify_catalog_499(c)
    verify_excluded_v100(c)
    verify_context_custody(c)
    verify_prospective_proof_custody()
    inventory = strict_json((PKG / "source-inventory.json").read_bytes())
    verify_inventory_document(inventory, provisional=False)
    manifest_blob = (PKG / "prelaunch-manifest.json").read_bytes()
    manifest = strict_json(manifest_blob)
    source_map = verify_manifest_document(c, manifest, inventory, provisional=False)
    source_sha = source_map_sha(source_map)
    native = verify_run_provenance(manifest, source_map, source_sha)
    evidence = recovered_evidence(evidence_dir, native["closure"])
    assert strict_json(evidence["input.json"]) == verify_source(c, oracle["source-delta.json"])
    exported = strict_json(evidence["roundtrip-raw.json"])
    verify_export(c, exported)
    verify_log(c, oracle["log-oracle.json"], evidence["model.log"])
    verify_report(c, oracle["report-oracle.json"], evidence["report-raw.json"])
    verify_converter(evidence["model-run.log"])
    verify_checker_receipts(strict_json(evidence["roundtrip-validation.json"]),
                            strict_json(evidence["author-validation.json"]),
                            sha(evidence["input.json"]), sha(evidence["roundtrip-raw.json"]))
    assert native["raw_file_count"] == 23 and len(evidence) == 25
    print("GO_BOUNDED 61/53 log 1244 report cells 34/21/211 source 34/39/395 export 25 raw")


if __name__ == "__main__":
    main()
