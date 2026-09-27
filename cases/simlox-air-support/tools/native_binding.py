"""Pre-launch invocation and post-launch raw-artifact binding for A01/A02.

An invocation is written before Simlox starts. A closure is written only after
all four native steps. Both are required for publication-grade validation.
Legacy runs can be reanalysed separately, but cannot acquire this binding.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CASES = {"A01": "A01-single-aircraft-single-mission",
         "A02": "A02-single-aircraft-repeated-missions"}
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
WORKING_DIR = Path(r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace")
RAW_NAMES = ("input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
             "report-raw.json", "model.log", "run.log", "steps.json",
             "import.log", "export.log", "report-export.log", "roundtrip-check.json")
STEPS = ("import", "export", "calc", "jsonreport")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_exclusive(path: Path, value: dict) -> None:
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def source_hashes(case_id: str) -> dict:
    folder = ROOT / CASES[case_id]
    paths = {"input": folder / "native-input.json", "schema": ROOT / "native-schema.json",
             "contract": folder / "contract.json", "parameters": folder / "parameters.json",
             "generator": ROOT / "tools/generate_native.py",
             "validator": ROOT / "tools/validate_native.py",
             "runner": ROOT / "tools/run_native_bound.ps1",
             "binding": Path(__file__)}
    return {name: sha(path) for name, path in paths.items()}


def expected_run(case_id: str, run_id: str) -> Path:
    return (REPO / "data/local/simlox-case-library/v1" / case_id / run_id).resolve()


def expected_arguments(run: Path) -> dict[str, str]:
    return {
        "import": f'-silent -jimport "{run / "input.json"}" -save "{run / "model.sxi"}" -log "{run / "import.log"}" -close',
        "export": f'"{run / "model.sxi"}" -silent -jexport "{run / "roundtrip-raw.json"}" -log "{run / "export.log"}" -close',
        "calc": f'"{run / "model.sxi"}" -silent -threads 1 -calc -log "{run / "run.log"}" -close',
        "jsonreport": f'"{run / "model.sxo"}" -silent -jsonreport "{run / "report-raw.json"}" -log "{run / "report-export.log"}" -close',
    }


def prepare(run: Path, case_id: str, run_id: str, input_sha256: str) -> dict:
    run = run.resolve()
    if run != expected_run(case_id, run_id):
        raise ValueError("run path outside case/ID evidence directory")
    if {path.name for path in run.iterdir()} != {"input.json"}:
        raise ValueError("pre-launch run directory must contain only copied input.json")
    hashes = source_hashes(case_id)
    if sha(run / "input.json") != input_sha256 or hashes["input"] != input_sha256:
        raise ValueError("pre-launch copied/checked input fingerprint mismatch")
    if sha(EXE) != EXE_SHA:
        raise ValueError("SIMLOX executable fingerprint mismatch")
    record = {"schema_version": "a01-a02-native-binding-v1", "task_id": "simlox-case-library-a01-a02-v1",
              "case_id": case_id, "run_id": run_id, "invocation_id": str(uuid.uuid4()),
              "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
              "run_dir": str(run), "input_path": str((run / "input.json").resolve()),
              "source_hashes": hashes, "copied_input_sha256": input_sha256,
              "simlox_exe_path": str(EXE), "simlox_exe_sha256": EXE_SHA,
              "native_working_directory": str(WORKING_DIR), "planned_steps": list(STEPS),
              "planned_arguments": expected_arguments(run),
              "planned_raw_paths": {name: str((run / name).resolve()) for name in RAW_NAMES}}
    write_exclusive(run / "invocation.json", record)
    return record


def seal(run: Path) -> dict:
    run = run.resolve()
    invocation = read(run / "invocation.json")
    if run != expected_run(invocation["case_id"], invocation["run_id"]):
        raise ValueError("invocation/run path mismatch")
    if sha(run / "input.json") != invocation["copied_input_sha256"]:
        raise ValueError("input changed after pre-launch binding")
    steps = read(run / "steps.json")
    if [step["name"] for step in steps] != list(STEPS) or any(step["exit_code"] != 0 for step in steps):
        raise ValueError("incomplete native command sequence")
    if any(step.get("invocation_id") != invocation["invocation_id"] for step in steps):
        raise ValueError("native command invocation identity mismatch")
    artifacts = {}
    for name in RAW_NAMES:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing/short raw artifact before seal: {name}")
        artifacts[name] = {"path": str(path.resolve()), "bytes": path.stat().st_size,
                           "sha256": sha(path)}
    closure = {"schema_version": "a01-a02-native-binding-v1",
               "case_id": invocation["case_id"], "run_id": invocation["run_id"],
               "invocation_id": invocation["invocation_id"],
               "invocation_sha256": sha(run / "invocation.json"),
               "closed_at_utc": datetime.now(timezone.utc).isoformat(),
               "artifacts": artifacts}
    write_exclusive(run / "closure.json", closure)
    return closure


def verify(run: Path, case_id: str) -> dict:
    run = run.resolve()
    pre, post = run / "invocation.json", run / "closure.json"
    if not pre.is_file() or not post.is_file():
        raise ValueError("missing pre-run invocation or post-run closure binding")
    invocation, closure = read(pre), read(post)
    run_id = run.name
    if (run != expected_run(case_id, run_id) or invocation.get("case_id") != case_id
            or invocation.get("run_id") != run_id or closure.get("case_id") != case_id
            or closure.get("run_id") != run_id or invocation.get("run_dir") != str(run)):
        raise ValueError("run/case binding identity mismatch")
    if (invocation.get("schema_version") != "a01-a02-native-binding-v1"
            or closure.get("schema_version") != invocation["schema_version"]
            or closure.get("invocation_id") != invocation.get("invocation_id")
            or closure.get("invocation_sha256") != sha(pre)):
        raise ValueError("pre-run/closure invocation binding mismatch")
    if datetime.fromisoformat(closure["closed_at_utc"]) < datetime.fromisoformat(invocation["prepared_at_utc"]):
        raise ValueError("closure predates invocation")
    if invocation.get("planned_steps") != list(STEPS) or invocation.get("planned_arguments") != expected_arguments(run):
        raise ValueError("planned step binding mismatch")
    if invocation.get("source_hashes") != source_hashes(case_id):
        raise ValueError("source/validator/runner fingerprint changed since launch")
    if (invocation.get("copied_input_sha256") != invocation["source_hashes"]["input"]
            or invocation.get("simlox_exe_sha256") != EXE_SHA
            or invocation.get("simlox_exe_path") != str(EXE)
            or invocation.get("native_working_directory") != str(WORKING_DIR)):
        raise ValueError("tool/input/working-directory binding mismatch")
    if invocation.get("input_path") != str((run / "input.json").resolve()):
        raise ValueError("copied input path binding mismatch")
    if set(invocation.get("planned_raw_paths", {})) != set(RAW_NAMES) or set(closure.get("artifacts", {})) != set(RAW_NAMES):
        raise ValueError("missing or extra planned/sealed raw artifact")
    for name in RAW_NAMES:
        path = run / name
        entry = closure["artifacts"][name]
        expected_path = str(path.resolve())
        if (invocation["planned_raw_paths"][name] != expected_path or entry.get("path") != expected_path
                or not path.is_file() or path.stat().st_size <= 4
                or entry.get("bytes") != path.stat().st_size or entry.get("sha256") != sha(path)):
            raise ValueError(f"raw artifact binding mismatch: {name}")
    steps = read(run / "steps.json")
    if [step.get("name") for step in steps] != list(STEPS) or any(step.get("exit_code") != 0 for step in steps):
        raise ValueError("sealed native command sequence invalid")
    if any(step.get("invocation_id") != invocation["invocation_id"] or
           step.get("executable") != str(EXE) or
           step.get("working_directory") != str(WORKING_DIR) or
           step.get("arguments") != invocation["planned_arguments"][step["name"]]
           for step in steps):
        raise ValueError("sealed native step invocation/tool mismatch")
    return {"invocation_id": invocation["invocation_id"],
            "invocation_sha256": sha(pre), "closure_sha256": sha(post),
            "source_hashes": invocation["source_hashes"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "seal", "verify"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--case", choices=sorted(CASES))
    parser.add_argument("--run-id")
    parser.add_argument("--input-sha256")
    args = parser.parse_args()
    if args.operation == "prepare":
        if not (args.case and args.run_id and args.input_sha256):
            parser.error("prepare needs --case, --run-id and --input-sha256")
        result = prepare(args.run_dir, args.case, args.run_id, args.input_sha256)
    elif args.operation == "seal":
        result = seal(args.run_dir)
    else:
        if not args.case:
            parser.error("verify needs --case")
        result = verify(args.run_dir, args.case)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
