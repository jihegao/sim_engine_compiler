"""Bind one preparation/resource native invocation to its immutable artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from pathlib import PurePosixPath
import re
import uuid


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
EXE_SHA256 = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
WORKING_DIRECTORY = Path(
    r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace"
)
CASES = {"B01", "B02", "B03", "C01", "C02", "C03"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
STEPS = ("import", "export", "calc", "jsonreport")
RAW_NAMES = (
    "input.json",
    "model.sxi",
    "model.sxo",
    "roundtrip-raw.json",
    "report-raw.json",
    "model.log",
    "run.log",
    "steps.json",
    "import.log",
    "export.log",
    "report-export.log",
    "roundtrip-check.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_exclusive(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(
            (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
                "utf-8"
            )
        )


def validate_identity(case_id: str, variant_id: str, run_id: str) -> None:
    if case_id not in CASES:
        raise ValueError(f"unsupported case: {case_id}")
    for name, value in (("variant", variant_id), ("run", run_id)):
        if not SAFE_ID.fullmatch(value):
            raise ValueError(f"unsafe {name} ID: {value!r}")


def expected_run(case_id: str, variant_id: str, run_id: str) -> Path:
    validate_identity(case_id, variant_id, run_id)
    return (
        REPO
        / "data"
        / "local"
        / "simlox-preparation-resource"
        / "v1"
        / case_id
        / variant_id
        / run_id
    ).resolve()


def expected_arguments(run: Path) -> dict[str, str]:
    return {
        "import": (
            f'-silent -jimport "{run / "input.json"}" -save "{run / "model.sxi"}" '
            f'-log "{run / "import.log"}" -close'
        ),
        "export": (
            f'"{run / "model.sxi"}" -silent -jexport "{run / "roundtrip-raw.json"}" '
            f'-log "{run / "export.log"}" -close'
        ),
        "calc": (
            f'"{run / "model.sxi"}" -silent -threads 1 -calc '
            f'-log "{run / "run.log"}" -close'
        ),
        "jsonreport": (
            f'"{run / "model.sxo"}" -silent -jsonreport "{run / "report-raw.json"}" '
            f'-log "{run / "report-export.log"}" -close'
        ),
    }


def validate_interactive_session(evidence: dict) -> dict:
    if not isinstance(evidence, dict):
        raise ValueError("invalid interactive native session evidence")
    name = evidence.get("name")
    session_id = evidence.get("id")
    user = evidence.get("user")
    query_line = evidence.get("query_line")
    if (
        not isinstance(name, str)
        or re.fullmatch(r"Console|RDP-Tcp#\d+", name, re.IGNORECASE) is None
        or type(session_id) is not int
        or session_id <= 0
        or not isinstance(user, str)
        or not user
        or not isinstance(query_line, str)
    ):
        raise ValueError("invalid interactive native session evidence")
    pattern = rf"^\s*>?\s*{re.escape(name)}\s+{re.escape(user)}\s+{session_id}\s+Active(?:\s|$)"
    if re.match(pattern, query_line, re.IGNORECASE) is None:
        raise ValueError("native session query does not identify an active matching user")
    return {"name": name, "id": session_id, "user": user, "query_line": query_line}


def resolve_manifest_path(relative: object, parent: Path, label: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError(f"manifest {label} path must be a string")
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or not parsed.parts or any(
        part in {"", ".", ".."} for part in parsed.parts
    ):
        raise ValueError(f"unsafe manifest {label} path")
    resolved = (ROOT / Path(*parsed.parts)).resolve()
    parent = parent.resolve()
    if not resolved.is_relative_to(parent):
        raise ValueError(f"manifest {label} path escapes its allowed directory")
    return resolved


def source_hashes(
    source_input: Path, case_id: str, candidate: dict
) -> dict[str, str]:
    source_input = source_input.resolve()
    if case_id not in CASES:
        raise ValueError(f"unsupported case: {case_id}")
    if source_input.suffix.lower() != ".json" or ROOT not in source_input.parents:
        raise ValueError("source input must be a JSON file below preparation-resource-v1")
    parameter_path = resolve_manifest_path(
        candidate.get("parameter_path"), ROOT / "parameters", "parameter"
    )
    required = {
        "input": source_input,
        "runner": ROOT / "run_native.ps1",
        "binding": Path(__file__),
        "validator": ROOT / "validate.py",
        "resource_validator": ROOT / "validate_resources.py",
        "generator": ROOT / "generate.py",
        "contract": ROOT / "contracts" / f"{case_id}.json",
        "readme": ROOT / "README.md",
        "parameters": parameter_path,
        "native_manifest": ROOT / "native" / "manifest.json",
        "native_schema": ROOT.parent / "native-schema.json",
        "native_writer": ROOT.parent / "tools" / "generate_native.py",
        "a01_parameters": (
            ROOT.parent / "A01-single-aircraft-single-mission" / "parameters.json"
        ),
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise ValueError(f"required source files missing: {missing}")
    return {name: sha256(path) for name, path in required.items()}


def manifest_candidate(
    source_input: Path, case_id: str, variant_id: str, input_sha256: str
) -> dict:
    source_input = source_input.resolve()
    manifest_file = ROOT / "native" / "manifest.json"
    manifest = read_json(manifest_file)
    if (
        manifest.get("schema")
        != "simlox-preparation-resource-native-manifest/v1"
        or manifest.get("status") != "planned_native_acceptance"
        or manifest.get("candidate_count") != len(manifest.get("candidates", []))
    ):
        raise ValueError("unsupported or inconsistent native manifest")
    matches = [
        candidate
        for candidate in manifest["candidates"]
        if candidate.get("case_id") == case_id
        and candidate.get("variant_id") == variant_id
    ]
    if len(matches) != 1:
        raise ValueError("manifest must contain exactly one case/variant candidate")
    candidate = matches[0]
    candidate_path = resolve_manifest_path(
        candidate.get("path"), ROOT / "native", "candidate"
    )
    parameter_path = resolve_manifest_path(
        candidate.get("parameter_path"), ROOT / "parameters", "parameter"
    )
    candidate_prefix = f"{case_id}--{variant_id}"
    parameter_prefix = case_id
    if (
        source_input != candidate_path
        or candidate_path.suffix.lower() != ".json"
        or not candidate_path.stem.startswith(candidate_prefix)
        or parameter_path.suffix.lower() != ".json"
        or not parameter_path.stem.startswith(parameter_prefix)
        or candidate.get("input_sha256") != input_sha256
        or candidate.get("native_verified") is not False
        or candidate.get("parameter_sha256") != sha256(parameter_path)
        or manifest.get("generator_path") != "generate.py"
        or manifest.get("generator_sha256") != sha256(ROOT / "generate.py")
        or manifest.get("native_schema_path") != "../native-schema.json"
        or manifest.get("native_schema_sha256")
        != sha256(ROOT.parent / "native-schema.json")
        or sha256(source_input) != input_sha256
    ):
        raise ValueError("manifest candidate/source identity mismatch")
    return candidate


def prepare(
    run: Path,
    source_input: Path,
    case_id: str,
    variant_id: str,
    run_id: str,
    input_sha256: str,
    interactive_session: dict | None = None,
) -> dict:
    run = run.resolve()
    source_input = source_input.resolve()
    if run != expected_run(case_id, variant_id, run_id):
        raise ValueError("run path outside the bound case/variant/run directory")
    if {path.name for path in run.iterdir()} != {"input.json"}:
        raise ValueError("pre-launch run directory must contain only copied input.json")
    candidate = manifest_candidate(
        source_input, case_id, variant_id, input_sha256
    )
    hashes = source_hashes(source_input, case_id, candidate)
    if hashes["input"] != input_sha256 or sha256(run / "input.json") != input_sha256:
        raise ValueError("source/copied input fingerprint mismatch")
    if not EXE.is_file() or sha256(EXE) != EXE_SHA256:
        raise ValueError("SIMLOX executable fingerprint mismatch")
    if interactive_session is None:
        raise ValueError("new native invocation requires interactive session evidence")
    invocation_id = str(uuid.uuid4())
    record = {
        "schema_version": "simlox-preparation-resource-native-binding/v2",
        "task_id": "simlox-preparation-resource-v1",
        "case_id": case_id,
        "variant_id": variant_id,
        "run_id": run_id,
        "invocation_id": invocation_id,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run),
        "source_input_path": str(source_input),
        "copied_input_path": str((run / "input.json").resolve()),
        "source_hashes": hashes,
        "manifest_candidate": candidate,
        "copied_input_sha256": input_sha256,
        "simlox_exe_path": str(EXE),
        "simlox_exe_sha256": EXE_SHA256,
        "native_working_directory": str(WORKING_DIRECTORY),
        "planned_steps": list(STEPS),
        "planned_arguments": expected_arguments(run),
        "planned_raw_paths": {
            name: str((run / name).resolve()) for name in RAW_NAMES
        },
    }
    record["interactive_session"] = validate_interactive_session(interactive_session)
    write_exclusive(run / "invocation.json", record)
    return record


def normalize_numbers(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite number in native input")
        if value.is_integer():
            return int(value)
    if isinstance(value, dict):
        return {key: normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_numbers(item) for item in value]
    return value


def business_rows(path: Path) -> dict[str, Counter]:
    document = read_json(path)
    tables = document["model"]["tables"]
    result: dict[str, Counter] = {}
    for table in tables:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table: {name}")
        columns = [column["name"] for column in table["columns"]]
        records = []
        for instance in table["instances"]:
            for row in instance["rows"]:
                if len(row) != len(columns):
                    raise ValueError(f"{name} column/row length mismatch")
                if any(value not in (None, "") for value in row):
                    record = normalize_numbers(dict(zip(columns, row)))
                    records.append(
                        json.dumps(record, ensure_ascii=False, sort_keys=True)
                    )
        result[name] = Counter(records)
    return result


def check_roundtrip(run: Path) -> dict:
    run = run.resolve()
    original = business_rows(run / "input.json")
    exported = business_rows(run / "roundtrip-raw.json")
    changed = {}
    for table in sorted(original.keys() | exported.keys()):
        left = original.get(table, Counter())
        right = exported.get(table, Counter())
        if left != right:
            changed[table] = {
                "input_only": list((left - right).elements())[:3],
                "export_only": list((right - left).elements())[:3],
            }
    result = {
        "schema_version": "simlox-native-roundtrip-check/v1",
        "all_equal": not changed,
        "changed": changed,
        "nonempty_business_tables": sum(bool(rows) for rows in original.values()),
        "input_sha256": sha256(run / "input.json"),
        "roundtrip_sha256": sha256(run / "roundtrip-raw.json"),
    }
    write_exclusive(run / "roundtrip-check.json", result)
    return result


def seal(run: Path) -> dict:
    run = run.resolve()
    invocation = read_json(run / "invocation.json")
    if run != expected_run(
        invocation["case_id"], invocation["variant_id"], invocation["run_id"]
    ):
        raise ValueError("invocation/run path mismatch")
    if sha256(run / "input.json") != invocation["copied_input_sha256"]:
        raise ValueError("input changed after pre-launch binding")
    steps = read_json(run / "steps.json")
    if [step.get("name") for step in steps] != list(STEPS):
        raise ValueError("incomplete native command sequence")
    if any(step.get("exit_code") != 0 for step in steps):
        raise ValueError("native step failed")
    if any(
        step.get("invocation_id") != invocation["invocation_id"] for step in steps
    ):
        raise ValueError("native command invocation identity mismatch")
    artifacts = {}
    for name in RAW_NAMES:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing/short raw artifact before seal: {name}")
        artifacts[name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    closure = {
        "schema_version": invocation["schema_version"],
        "task_id": invocation["task_id"],
        "case_id": invocation["case_id"],
        "variant_id": invocation["variant_id"],
        "run_id": invocation["run_id"],
        "invocation_id": invocation["invocation_id"],
        "invocation_sha256": sha256(run / "invocation.json"),
        "closed_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }
    write_exclusive(run / "closure.json", closure)
    return closure


def verify(run: Path, case_id: str, variant_id: str) -> dict:
    run = run.resolve()
    invocation_path = run / "invocation.json"
    closure_path = run / "closure.json"
    if not invocation_path.is_file() or not closure_path.is_file():
        raise ValueError("missing pre-run invocation or post-run closure binding")
    invocation = read_json(invocation_path)
    closure = read_json(closure_path)
    run_id = run.name
    if run != expected_run(case_id, variant_id, run_id):
        raise ValueError("run path outside expected case/variant evidence directory")
    identity = (case_id, variant_id, run_id)
    if tuple(invocation.get(key) for key in ("case_id", "variant_id", "run_id")) != identity:
        raise ValueError("invocation case/variant/run identity mismatch")
    if tuple(closure.get(key) for key in ("case_id", "variant_id", "run_id")) != identity:
        raise ValueError("closure case/variant/run identity mismatch")
    schema = invocation.get("schema_version")
    if schema not in {"simlox-preparation-resource-native-binding/v1", "simlox-preparation-resource-native-binding/v2"} or closure.get("schema_version") != schema:
        raise ValueError("binding schema mismatch")
    if invocation.get("task_id") != "simlox-preparation-resource-v1" or closure.get(
        "task_id"
    ) != invocation.get("task_id"):
        raise ValueError("binding task mismatch")
    if not invocation.get("invocation_id") or closure.get("invocation_id") != invocation.get(
        "invocation_id"
    ):
        raise ValueError("pre-run/closure invocation ID mismatch")
    if closure.get("invocation_sha256") != sha256(invocation_path):
        raise ValueError("closure does not bind exact invocation bytes")
    try:
        prepared = datetime.fromisoformat(invocation["prepared_at_utc"])
        closed = datetime.fromisoformat(closure["closed_at_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid binding timestamp") from exc
    if prepared.tzinfo is None or closed.tzinfo is None or closed < prepared:
        raise ValueError("closure timestamp predates invocation")
    if invocation.get("run_dir") != str(run):
        raise ValueError("invocation run directory mismatch")
    if schema.endswith("/v2"):
        validate_interactive_session(invocation.get("interactive_session", {}))

    source_input = Path(invocation.get("source_input_path", "")).resolve()
    input_sha = invocation.get("copied_input_sha256")
    candidate = manifest_candidate(source_input, case_id, variant_id, input_sha)
    if invocation.get("source_hashes") != source_hashes(
        source_input, case_id, candidate
    ):
        raise ValueError("source/input/validator/runner fingerprint changed since launch")
    copied_input = run / "input.json"
    if (
        invocation.get("copied_input_path") != str(copied_input.resolve())
        or input_sha != invocation["source_hashes"]["input"]
        or not copied_input.is_file()
        or sha256(copied_input) != input_sha
    ):
        raise ValueError("copied input binding mismatch")
    if invocation.get("manifest_candidate") != candidate:
        raise ValueError("manifest candidate binding changed since launch")
    if (
        invocation.get("simlox_exe_path") != str(EXE)
        or invocation.get("simlox_exe_sha256") != EXE_SHA256
        or not EXE.is_file()
        or sha256(EXE) != EXE_SHA256
        or invocation.get("native_working_directory") != str(WORKING_DIRECTORY)
    ):
        raise ValueError("native executable or working-directory binding mismatch")
    planned_arguments = expected_arguments(run)
    if invocation.get("planned_steps") != list(STEPS) or invocation.get(
        "planned_arguments"
    ) != planned_arguments:
        raise ValueError("planned native step binding mismatch")
    planned_paths = invocation.get("planned_raw_paths")
    artifacts = closure.get("artifacts")
    if not isinstance(planned_paths, dict) or set(planned_paths) != set(RAW_NAMES):
        raise ValueError("planned raw artifact set mismatch")
    if not isinstance(artifacts, dict) or set(artifacts) != set(RAW_NAMES):
        raise ValueError("sealed raw artifact set mismatch")
    for name in RAW_NAMES:
        path = run / name
        expected_path = str(path.resolve())
        entry = artifacts[name]
        if (
            planned_paths[name] != expected_path
            or entry.get("path") != expected_path
            or not path.is_file()
            or path.stat().st_size <= 4
            or entry.get("bytes") != path.stat().st_size
            or entry.get("sha256") != sha256(path)
        ):
            raise ValueError(f"raw artifact binding mismatch: {name}")

    steps = read_json(run / "steps.json")
    if not isinstance(steps, list) or [step.get("name") for step in steps] != list(STEPS):
        raise ValueError("sealed native command sequence mismatch")
    for step in steps:
        if (
            step.get("invocation_id") != invocation["invocation_id"]
            or step.get("executable") != str(EXE)
            or step.get("working_directory") != str(WORKING_DIRECTORY)
            or step.get("arguments") != planned_arguments[step["name"]]
            or step.get("exit_code") != 0
            or not isinstance(step.get("wall_seconds"), (int, float))
            or step["wall_seconds"] < 0
        ):
            raise ValueError(f"sealed native step mismatch: {step.get('name')}")
    return {
        "schema_version": schema,
        "case_id": case_id,
        "variant_id": variant_id,
        "run_id": run_id,
        "invocation_id": invocation["invocation_id"],
        "invocation_sha256": sha256(invocation_path),
        "closure_sha256": sha256(closure_path),
        "input_sha256": input_sha,
        "simlox_exe_sha256": EXE_SHA256,
        "source_hashes": invocation["source_hashes"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=("prepare", "roundtrip", "seal", "verify")
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--source-input", type=Path)
    parser.add_argument("--case", choices=sorted(CASES))
    parser.add_argument("--variant")
    parser.add_argument("--run-id")
    parser.add_argument("--input-sha256")
    parser.add_argument("--session-name")
    parser.add_argument("--session-id", type=int)
    parser.add_argument("--session-user")
    parser.add_argument("--session-query-line")
    args = parser.parse_args()
    if args.operation == "prepare":
        required = (
            args.source_input,
            args.case,
            args.variant,
            args.run_id,
            args.input_sha256,
        )
        if not all(required):
            parser.error(
                "prepare needs --source-input, --case, --variant, --run-id and --input-sha256"
            )
        session_parts = (args.session_name, args.session_id, args.session_user, args.session_query_line)
        if not all(part is not None for part in session_parts):
            parser.error("prepare needs all four session evidence fields")
        session = {
            "name": args.session_name,
            "id": args.session_id,
            "user": args.session_user,
            "query_line": args.session_query_line,
        }
        result = prepare(
            args.run_dir,
            args.source_input,
            args.case,
            args.variant,
            args.run_id,
            args.input_sha256,
            session,
        )
    elif args.operation == "roundtrip":
        result = check_roundtrip(args.run_dir)
    elif args.operation == "seal":
        result = seal(args.run_dir)
    else:
        if not args.case or not args.variant:
            parser.error("verify needs --case and --variant")
        result = verify(args.run_dir, args.case, args.variant)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if args.operation == "roundtrip" and not result["all_equal"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
