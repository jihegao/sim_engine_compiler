from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BINDING_PATH = (
    PROJECT_ROOT
    / "cases"
    / "simlox-air-support"
    / "preparation-resource-v1"
    / "binding.py"
)


def load_binding():
    spec = importlib.util.spec_from_file_location(
        "simlox_preparation_resource_binding_test", BINDING_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BINDING = load_binding()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def isolated_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    repo = tmp_path / "repo"
    root = repo / "cases" / "simlox-air-support" / "preparation-resource-v1"
    native = root / "native"
    parameters = root / "parameters"
    contract = root / "contracts"
    schema = root.parent / "native-schema.json"
    writer = root.parent / "tools" / "generate_native.py"
    a01_parameters = root.parent / "A01-single-aircraft-single-mission" / "parameters.json"

    source = native / "B01--fixed-30m.json"
    write_json(source, {"model": {"tables": []}})
    write_json(parameters / "B01.json", {"case_id": "B01"})
    write_json(contract / "B01.json", {"case_id": "B01"})
    write_json(schema, {"schema": "test-native-schema"})
    writer.parent.mkdir(parents=True, exist_ok=True)
    writer.write_text("# pinned test writer\n", encoding="utf-8")
    write_json(a01_parameters, {"case_id": "A01"})
    root.joinpath("run_native.ps1").write_text("# test runner\n", encoding="utf-8")
    root.joinpath("validate.py").write_text("# test validator\n", encoding="utf-8")
    root.joinpath("validate_resources.py").write_text(
        "# test resource validator\n", encoding="utf-8"
    )
    root.joinpath("generate.py").write_text("# test generator\n", encoding="utf-8")
    root.joinpath("README.md").write_text("test bundle\n", encoding="utf-8")

    candidate = {
        "case_id": "B01",
        "variant_id": "fixed-30m",
        "path": "native/B01--fixed-30m.json",
        "input_sha256": digest(source),
        "parameter_path": "parameters/B01.json",
        "parameter_sha256": digest(parameters / "B01.json"),
        "parent_diff_path": "parent-diffs/B01--fixed-30m.json",
        "native_verified": False,
    }
    manifest = {
        "schema": "simlox-preparation-resource-native-manifest/v1",
        "status": "planned_native_acceptance",
        "native_schema_path": "../native-schema.json",
        "native_schema_sha256": digest(schema),
        "generator_path": "generate.py",
        "generator_sha256": digest(root / "generate.py"),
        "candidate_count": 1,
        "candidates": [candidate],
    }
    write_json(native / "manifest.json", manifest)

    executable = tmp_path / "Simlox.exe"
    executable.write_bytes(b"test executable bytes")
    working_directory = tmp_path / "native-workspace"
    working_directory.mkdir()

    monkeypatch.setattr(BINDING, "ROOT", root)
    monkeypatch.setattr(BINDING, "REPO", repo)
    monkeypatch.setattr(BINDING, "EXE", executable)
    monkeypatch.setattr(BINDING, "EXE_SHA256", digest(executable))
    monkeypatch.setattr(BINDING, "WORKING_DIRECTORY", working_directory)

    def new_run(run_id: str = "run-001") -> Path:
        run = BINDING.expected_run("B01", "fixed-30m", run_id)
        run.mkdir(parents=True)
        (run / "input.json").write_bytes(source.read_bytes())
        return run

    def prepare(run_id: str = "run-001") -> tuple[Path, dict]:
        run = new_run(run_id)
        invocation = BINDING.prepare(
            run,
            source,
            "B01",
            "fixed-30m",
            run_id,
            digest(source),
        )
        return run, invocation

    def add_native_artifacts(
        run: Path,
        invocation: dict,
        *,
        step_names: tuple[str, ...] = BINDING.STEPS,
        failed_step: str | None = None,
        omit_artifact: str | None = None,
    ) -> None:
        arguments = BINDING.expected_arguments(run)
        steps = [
            {
                "name": name,
                "invocation_id": invocation["invocation_id"],
                "executable": str(BINDING.EXE),
                "working_directory": str(BINDING.WORKING_DIRECTORY),
                "arguments": arguments[name],
                "exit_code": 1 if name == failed_step else 0,
                "wall_seconds": 0.01,
            }
            for name in step_names
        ]
        write_json(run / "steps.json", steps)
        for name in BINDING.RAW_NAMES:
            if name in {"input.json", "steps.json", omit_artifact}:
                continue
            (run / name).write_bytes(f"test artifact: {name}\n".encode())

    return {
        "root": root,
        "source": source,
        "manifest_path": native / "manifest.json",
        "candidate": candidate,
        "new_run": new_run,
        "prepare": prepare,
        "add_native_artifacts": add_native_artifacts,
    }


@pytest.mark.parametrize(
    ("case_id", "variant_id", "message"),
    [
        ("B99", "fixed-30m", "unsupported case"),
        ("B01", "../escape", "unsafe variant ID"),
    ],
)
def test_invalid_case_or_variant_identity_is_rejected(
    case_id: str, variant_id: str, message: str
):
    with pytest.raises(ValueError, match=message):
        BINDING.validate_identity(case_id, variant_id, "run-001")


def test_prepare_records_an_exact_manifest_bound_invocation(isolated_binding):
    run, invocation = isolated_binding["prepare"]()

    assert Path(invocation["run_dir"]) == run
    assert invocation["manifest_candidate"] == isolated_binding["candidate"]
    assert invocation["copied_input_sha256"] == digest(isolated_binding["source"])
    assert (run / "invocation.json").is_file()


def test_prepare_rejects_run_path_escape(isolated_binding, tmp_path: Path):
    escaped = tmp_path / "escaped-run"
    escaped.mkdir()
    (escaped / "input.json").write_bytes(isolated_binding["source"].read_bytes())

    with pytest.raises(ValueError, match="run path outside"):
        BINDING.prepare(
            escaped,
            isolated_binding["source"],
            "B01",
            "fixed-30m",
            "run-001",
            digest(isolated_binding["source"]),
        )


def test_manifest_candidate_rejects_wrong_variant_path(isolated_binding):
    with pytest.raises(ValueError, match="exactly one case/variant candidate"):
        BINDING.manifest_candidate(
            isolated_binding["source"],
            "B01",
            "another-variant",
            digest(isolated_binding["source"]),
        )


def test_prepare_accepts_manifest_versioned_candidate_and_parameters(isolated_binding):
    root = isolated_binding["root"]
    source = root / "native" / "B02--serial-10m-20m--v1.0.1.json"
    parameters = root / "parameters" / "B02-v1.0.1.json"
    contract = root / "contracts" / "B02.json"
    write_json(source, {"model": {"tables": []}})
    write_json(parameters, {"case_id": "B02", "version": "1.0.1"})
    write_json(contract, {"case_id": "B02"})
    candidate = {
        "case_id": "B02",
        "variant_id": "serial-10m-20m",
        "path": "native/B02--serial-10m-20m--v1.0.1.json",
        "input_sha256": digest(source),
        "parameter_path": "parameters/B02-v1.0.1.json",
        "parameter_sha256": digest(parameters),
        "parent_diff_path": "parent-diffs/B02--serial-10m-20m--v1.0.1.json",
        "native_verified": False,
    }
    manifest = BINDING.read_json(isolated_binding["manifest_path"])
    manifest["candidates"] = [candidate]
    write_json(isolated_binding["manifest_path"], manifest)

    run_id = "b02-versioned"
    run = BINDING.expected_run("B02", "serial-10m-20m", run_id)
    run.mkdir(parents=True)
    (run / "input.json").write_bytes(source.read_bytes())
    invocation = BINDING.prepare(
        run,
        source,
        "B02",
        "serial-10m-20m",
        run_id,
        digest(source),
    )

    assert invocation["manifest_candidate"] == candidate
    assert invocation["source_hashes"]["parameters"] == digest(parameters)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path", "../outside.json", "unsafe manifest candidate path"),
        (
            "parameter_path",
            "parameters/../outside.json",
            "unsafe manifest parameter path",
        ),
    ],
)
def test_manifest_candidate_rejects_unsafe_manifest_paths(
    isolated_binding, field: str, value: str, message: str
):
    manifest = BINDING.read_json(isolated_binding["manifest_path"])
    manifest["candidates"][0][field] = value
    write_json(isolated_binding["manifest_path"], manifest)

    with pytest.raises(ValueError, match=message):
        BINDING.manifest_candidate(
            isolated_binding["source"],
            "B01",
            "fixed-30m",
            digest(isolated_binding["source"]),
        )


def test_manifest_candidate_rejects_manifest_tampering(isolated_binding):
    manifest = BINDING.read_json(isolated_binding["manifest_path"])
    manifest["candidates"][0]["input_sha256"] = "0" * 64
    write_json(isolated_binding["manifest_path"], manifest)

    with pytest.raises(ValueError, match="manifest candidate/source identity mismatch"):
        BINDING.manifest_candidate(
            isolated_binding["source"],
            "B01",
            "fixed-30m",
            digest(isolated_binding["source"]),
        )


def test_prepare_rejects_copied_input_hash_mismatch(isolated_binding):
    run = isolated_binding["new_run"]()
    (run / "input.json").write_bytes(b"different copied input")

    with pytest.raises(ValueError, match="source/copied input fingerprint mismatch"):
        BINDING.prepare(
            run,
            isolated_binding["source"],
            "B01",
            "fixed-30m",
            "run-001",
            digest(isolated_binding["source"]),
        )


def test_prepare_rejects_existing_run_content(isolated_binding):
    run = isolated_binding["new_run"]()
    (run / "existing-artifact.txt").write_text("must not overwrite\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain only copied input.json"):
        BINDING.prepare(
            run,
            isolated_binding["source"],
            "B01",
            "fixed-30m",
            "run-001",
            digest(isolated_binding["source"]),
        )


def test_seal_rejects_missing_raw_artifact(isolated_binding):
    run, invocation = isolated_binding["prepare"]()
    isolated_binding["add_native_artifacts"](
        run, invocation, omit_artifact="model.sxo"
    )

    with pytest.raises(ValueError, match="missing/short raw artifact.*model.sxo"):
        BINDING.seal(run)


def test_seal_rejects_missing_steps_file(isolated_binding):
    run, _ = isolated_binding["prepare"]()

    with pytest.raises(FileNotFoundError):
        BINDING.seal(run)


@pytest.mark.parametrize(
    ("step_names", "failed_step", "message"),
    [
        (("import", "export"), None, "incomplete native command sequence"),
        (BINDING.STEPS, "calc", "native step failed"),
    ],
)
def test_seal_rejects_incomplete_or_failed_steps(
    isolated_binding, step_names, failed_step, message
):
    run, invocation = isolated_binding["prepare"]()
    isolated_binding["add_native_artifacts"](
        run,
        invocation,
        step_names=step_names,
        failed_step=failed_step,
    )

    with pytest.raises(ValueError, match=message):
        BINDING.seal(run)


def test_verify_rejects_closure_identity_tampering(isolated_binding):
    run, invocation = isolated_binding["prepare"]()
    isolated_binding["add_native_artifacts"](run, invocation)
    BINDING.seal(run)
    closure_path = run / "closure.json"
    closure = BINDING.read_json(closure_path)
    closure["variant_id"] = "tampered-variant"
    write_json(closure_path, closure)

    with pytest.raises(ValueError, match="closure case/variant/run identity mismatch"):
        BINDING.verify(run, "B01", "fixed-30m")


def test_verify_rejects_invocation_bytes_changed_after_seal(isolated_binding):
    run, invocation = isolated_binding["prepare"]()
    isolated_binding["add_native_artifacts"](run, invocation)
    BINDING.seal(run)
    invocation_path = run / "invocation.json"
    invocation_path.write_bytes(invocation_path.read_bytes() + b" \n")

    with pytest.raises(ValueError, match="closure does not bind exact invocation bytes"):
        BINDING.verify(run, "B01", "fixed-30m")


def test_verify_rejects_resource_validator_changed_after_seal(isolated_binding):
    run, invocation = isolated_binding["prepare"]()
    isolated_binding["add_native_artifacts"](run, invocation)
    BINDING.seal(run)
    resource_validator = isolated_binding["root"] / "validate_resources.py"
    resource_validator.write_text("# changed after launch\n", encoding="utf-8")

    with pytest.raises(
        ValueError, match="source/input/validator/runner fingerprint changed"
    ):
        BINDING.verify(run, "B01", "fixed-30m")


def test_complete_synthetic_binding_verifies_without_claiming_native_execution(
    isolated_binding,
):
    run, invocation = isolated_binding["prepare"]()
    isolated_binding["add_native_artifacts"](run, invocation)
    closure = BINDING.seal(run)

    verified = BINDING.verify(run, "B01", "fixed-30m")

    assert verified["invocation_id"] == invocation["invocation_id"]
    assert verified["closure_sha256"] == digest(run / "closure.json")
    assert closure["artifacts"]["model.sxo"]["bytes"] > 4
