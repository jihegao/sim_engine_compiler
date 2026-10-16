"""Installable v0.1 aircraft compiler product boundary.

The bundle binds independently persisted layers. It is a consistency check,
not a signature or proof that a caller supplied authentic source data.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from sim_engine_compiler import __version__
from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.domains.aircraft_support.pack import PACK
from sim_engine_compiler.domains.multi_server_queue.model import BUSINESS_VERSION as QUEUE_BUSINESS_VERSION
from sim_engine_compiler.domains.profiles import pack_for_domain, pack_for_payload, pack_for_schema
from sim_engine_compiler.identity import (
    build_run_identity,
    inspect_bundle,
    inspect_run_identity,
)
from sim_engine_compiler.identity.common import content_digest, json_value
from sim_engine_compiler.ir.layers import BusinessIR
from sim_engine_compiler.native import _native_module, run_batch, run_plan
from sim_engine_compiler.reference.conformance import first_divergence

BUNDLE_VERSION = "sim-engine-model-bundle/v1"
RUN_VERSION = "sim-engine-run/v1"
BATCH_VERSION = "sim-engine-batch/v1"
DIFF_VERSION = "sim-engine-run-diff/v1"
RUNTIME_VERSION = "0.1.0"
LAYER_NAMES = ("business.json", "core.json", "plan.json", "lineage.json")
ZIP_NAMES = ("manifest.json", *LAYER_NAMES)
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 128 * 1024 * 1024


class ProductError(ValueError):
    """Stable SDK error; CLI serializes the same code, stage and path."""

    def __init__(self, code: str, message: str, *, stage: str, path: str | None = None):
        self.code, self.message, self.stage, self.path = code, message, stage, path
        super().__init__(message)

    def diagnostic(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": "error",
            "stage": self.stage,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class ModelBundle:
    manifest: dict[str, Any]
    business: dict[str, Any]
    core: dict[str, Any]
    plan: dict[str, Any]
    lineage: dict[str, Any]
    identity_report: dict[str, Any]

    @property
    def bundle_id(self) -> str:
        return self.manifest["bundle_id"]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _no_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError(f"invalid JSON number {value}")


def _json_bytes(raw: bytes, path: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicate_fields,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ProductError(
            "invalid_json", str(error), stage="load", path=path
        ) from error
    if type(value) is not dict:
        raise ProductError(
            "invalid_json", "expected a JSON object", stage="load", path=path
        )
    return value


def _is_canonical(raw: Any) -> bool:
    return (
        isinstance(raw, dict)
        and "schema_version" in raw
        and "sections" not in raw
        and "semantic_profile" not in raw
        and "version" not in raw
    )


def _business(source: Mapping[str, Any] | str | Path) -> BusinessIR:
    if isinstance(source, Mapping):
        try:
            raw = json_value(source)
        except ValueError as error:
            raise ProductError(
                "invalid_json", str(error), stage="load", path="business"
            ) from error
    else:
        path = Path(source)
        try:
            raw = _json_bytes(path.read_bytes(), str(path))
        except OSError as error:
            raise ProductError(
                "input_read_error", str(error), stage="load", path=str(path)
            ) from error
    try:
        return BusinessIR.from_dict(raw)
    except (AttributeError, CompilationError, KeyError, TypeError, ValueError) as error:
        raise _compiler_error(error, "business") from error


def _compiler_error(error: Exception, path: str) -> ProductError:
    source_path = getattr(error, "source_path", None) or path
    code = getattr(error, "code", None)
    if code in (None, "invalid_ir") and source_path == "business.semantic_profile":
        code = "unsupported_profile"
    if code in (None, "invalid_ir") and source_path == "business.version":
        code = "unsupported_business_version"
    return ProductError(
        code or "invalid_ir",
        getattr(error, "message", str(error)),
        stage="validate",
        path=source_path,
    )


def _compile(business: BusinessIR):
    try:
        return PACK.compile(business)
    except (
        AttributeError,
        CompilationError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise _compiler_error(error, "business") from error


def seal_business(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Explicitly seal an edited Business payload as a new revision.

    A stale fingerprint on an existing envelope is never silently repaired.
    Canonical documents are imported through the profile registered for their
    schema. Aircraft payloads stay on the aircraft-support-v1 pack.
    """
    try:
        raw = json_value(payload)
        if _is_canonical(raw):
            pack = pack_for_schema(raw.get("schema_version"))
            business = pack.import_canonical(raw)
        else:
            pack = pack_for_payload(raw)
            business = pack.load_payload(raw)
        pack.compile(business)
    except (AttributeError, CompilationError, KeyError, TypeError, ValueError) as error:
        raise _compiler_error(error, "business.payload") from error
    return business.to_dict()


def _open_saved(source: Mapping[str, Any] | str | Path):
    """Load a persisted Business envelope and the pack that owns its version."""
    if isinstance(source, Mapping):
        try:
            raw = json_value(source)
        except ValueError as error:
            raise ProductError(
                "invalid_json", str(error), stage="load", path="business"
            ) from error
    else:
        path = Path(source)
        try:
            raw = _json_bytes(path.read_bytes(), str(path))
        except OSError as error:
            raise ProductError(
                "input_read_error", str(error), stage="load", path=str(path)
            ) from error
    try:
        version = raw.get("version") if isinstance(raw, dict) else None
        if version == QUEUE_BUSINESS_VERSION:
            pack = pack_for_domain("multi-server-queue", "multi-server-queue-pack/v1")
            business = pack.load_envelope(raw)
        else:
            pack = PACK
            business = pack.load_envelope(raw)
    except (AttributeError, CompilationError, KeyError, TypeError, ValueError) as error:
        raise _compiler_error(error, "business") from error
    return business, pack


def validate_business(source: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Validate the persisted envelope and its executable lowering."""
    try:
        business, pack = _open_saved(source)
        core, plan, _ = pack.compile(business)
    except ProductError as error:
        return {
            "schema_version": "sim-engine-validation/v1",
            "status": "invalid",
            "diagnostics": [error.diagnostic()],
        }
    return {
        "schema_version": "sim-engine-validation/v1",
        "status": "valid",
        "identity": {
            "business_fingerprint": business.fingerprint,
            "core_fingerprint": core.fingerprint,
            "plan_fingerprint": plan.fingerprint,
            "semantic_profile": plan.semantic_profile,
        },
        "diagnostics": [],
    }


def _manifest(
    business: Any, core: Any, plan: Any, layers: dict[str, bytes], pack: Any
) -> dict[str, Any]:
    manifest = {
        "schema_version": BUNDLE_VERSION,
        "compiler_version": __version__,
        "runtime_version": RUNTIME_VERSION,
        "domain_pack": {"name": pack.name, "version": pack.version},
        "ir_versions": {
            "business": pack.business_version,
            "core": pack.core_version,
            "plan": pack.plan_version,
            "lineage": pack.lineage_version,
        },
        "execution_profile": {
            "semantic": plan.semantic_profile,
            "rng": plan.rng_profile,
            "work": plan.work_policy,
            "resource_dispatch_index": "absent",
        },
        "identity": {
            "business_fingerprint": business.fingerprint,
            "core_fingerprint": core.fingerprint,
            "plan_fingerprint": plan.fingerprint,
            "source_inputs_sha256": plan.source_inputs_sha256,
        },
        "files": {name: sha256(layers[name]).hexdigest() for name in LAYER_NAMES},
    }
    manifest["bundle_id"] = content_digest(manifest)
    return manifest


def _identity_check(layers: dict[str, dict[str, Any]], pack: Any) -> dict[str, Any]:
    report = pack.associate(layers)
    if report["association_status"] != "verified":
        first = next(
            (item for item in report["diagnostics"] if item["severity"] == "error"),
            None,
        )
        raise ProductError(
            "bundle_association_invalid",
            first["message"]
            if first
            else "Business, Core, Plan and lineage association is unverified",
            stage="bundle",
            path=first.get("path") if first else None,
        )
    return report


def compile_bundle(
    source: Mapping[str, Any] | str | Path, output: str | Path
) -> dict[str, Any]:
    """Compile a persisted aircraft Business revision into a portable .simpack."""
    if __version__ != RUNTIME_VERSION:
        raise ProductError(
            "unsupported_release_matrix",
            "Python and Rust release versions disagree",
            stage="compile",
        )
    business, pack = _open_saved(source)
    try:
        core, plan, source_map = pack.compile(business)
    except (
        AttributeError,
        CompilationError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise _compiler_error(error, "business") from error
    # Dataclass serialization retains tuples in memory; persistence uses JSON arrays.
    plan_json = json.loads(
        json.dumps(plan.to_dict(), ensure_ascii=False, allow_nan=False)
    )
    layers = {
        "business.json": business.to_dict(),
        "core.json": core.to_dict(),
        "plan.json": plan_json,
        "lineage.json": source_map,
    }
    contents = {name: _canonical_bytes(value) for name, value in layers.items()}
    manifest = _manifest(business, core, plan, contents, pack)
    _identity_check(layers, pack)
    target = Path(output)
    if target.suffix != ".simpack":
        raise ProductError(
            "invalid_output",
            "bundle filename must end in .simpack",
            stage="compile",
            path=str(target),
        )
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".simpack-", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
        with ZipFile(temporary, "w") as archive:
            for name in ZIP_NAMES:
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(
                    info,
                    _canonical_bytes(manifest)
                    if name == "manifest.json"
                    else contents[name],
                )
        os.replace(temporary, target)
    except (OSError, ValueError) as error:
        raise ProductError(
            "output_write_error", str(error), stage="compile", path=str(target)
        ) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "schema_version": "sim-engine-compile/v1",
        "status": "valid",
        "bundle_id": manifest["bundle_id"],
        "plan_fingerprint": plan.fingerprint,
        "business_fingerprint": business.fingerprint,
        "output": str(target),
        "diagnostics": [],
    }


def _check_manifest(
    manifest: dict[str, Any], layers: dict[str, dict[str, Any]]
) -> None:
    expected_keys = {
        "schema_version",
        "compiler_version",
        "runtime_version",
        "domain_pack",
        "ir_versions",
        "execution_profile",
        "identity",
        "files",
        "bundle_id",
    }
    if (
        set(manifest) != expected_keys
        or manifest.get("schema_version") != BUNDLE_VERSION
    ):
        raise ProductError(
            "unsupported_bundle_schema",
            "unsupported bundle manifest schema",
            stage="bundle",
            path="manifest.json",
        )
    if (
        manifest["compiler_version"] != __version__
        or manifest["runtime_version"] != RUNTIME_VERSION
    ):
        raise ProductError(
            "unsupported_producer_version",
            "bundle compiler/runtime version does not match this release",
            stage="bundle",
            path="manifest.json",
        )
    domain_pack = manifest.get("domain_pack")
    try:
        pack = pack_for_domain(
            domain_pack.get("name") if isinstance(domain_pack, dict) else None,
            domain_pack.get("version") if isinstance(domain_pack, dict) else None,
        )
    except CompilationError as error:
        raise ProductError(
            "unsupported_domain_pack",
            error.message,
            stage="bundle",
            path="manifest.json",
        ) from error
    if manifest["ir_versions"] != {
        "business": pack.business_version,
        "core": pack.core_version,
        "plan": pack.plan_version,
        "lineage": pack.lineage_version,
    }:
        raise ProductError(
            "unsupported_ir_version",
            "unsupported IR version matrix",
            stage="bundle",
            path="manifest.json",
        )
    if (
        manifest["execution_profile"]
        != {
            "semantic": layers["plan.json"].get("semantic_profile"),
            "rng": pack.rng_profile,
            "work": pack.work_policy,
            "resource_dispatch_index": "absent",
        }
        or manifest["execution_profile"]["semantic"] not in pack.profiles
    ):
        raise ProductError(
            "unsupported_profile",
            "unsupported execution profile",
            stage="bundle",
            path="manifest.json",
        )
    plan = layers["plan.json"]
    if "resource_dispatch_index" in plan:
        raise ProductError(
            "unsupported_resource_dispatch_index",
            "indexed Plans require a later bundle identity contract",
            stage="bundle",
            path="plan.json",
        )
    expected_identity = {
        "business_fingerprint": layers["business.json"].get("fingerprint"),
        "core_fingerprint": layers["core.json"].get("fingerprint"),
        "plan_fingerprint": content_digest(plan),
        "source_inputs_sha256": plan.get("source_inputs_sha256"),
    }
    if manifest["identity"] != expected_identity:
        raise ProductError(
            "bundle_identity_mismatch",
            "manifest identity does not match persisted layers",
            stage="bundle",
            path="manifest.json",
        )
    if manifest["bundle_id"] != content_digest(
        {key: value for key, value in manifest.items() if key != "bundle_id"}
    ):
        raise ProductError(
            "bundle_id_mismatch",
            "manifest bundle ID does not match content",
            stage="bundle",
            path="manifest.json",
        )


def load_bundle(source: str | Path) -> ModelBundle:
    """Fail closed on old, modified, incomplete or unsupported bundles."""
    path = Path(source)
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) != len(ZIP_NAMES) or {info.filename for info in infos} != set(
                ZIP_NAMES
            ):
                raise ProductError(
                    "invalid_bundle_files",
                    "bundle must contain exactly the v1 files",
                    stage="bundle",
                    path=str(path),
                )
            if (
                any(
                    info.is_dir() or info.file_size > MAX_MEMBER_BYTES for info in infos
                )
                or sum(info.file_size for info in infos) > MAX_BUNDLE_BYTES
            ):
                raise ProductError(
                    "invalid_bundle_size",
                    "bundle contains oversized or directory members",
                    stage="bundle",
                    path=str(path),
                )
            contents = {name: archive.read(name) for name in ZIP_NAMES}
    except (OSError, BadZipFile, RuntimeError) as error:
        raise ProductError(
            "bundle_read_error", str(error), stage="bundle", path=str(path)
        ) from error
    manifest = _json_bytes(contents["manifest.json"], "manifest.json")
    if type(manifest.get("files")) is not dict or set(manifest["files"]) != set(
        LAYER_NAMES
    ):
        raise ProductError(
            "invalid_bundle_files",
            "manifest file list does not match v1",
            stage="bundle",
            path="manifest.json",
        )
    for name in LAYER_NAMES:
        if manifest["files"][name] != sha256(contents[name]).hexdigest():
            raise ProductError(
                "bundle_file_mismatch",
                f"checksum mismatch for {name}",
                stage="bundle",
                path=name,
            )
    layers = {name: _json_bytes(contents[name], name) for name in LAYER_NAMES}
    _check_manifest(manifest, layers)
    try:
        pack = pack_for_domain(
            manifest["domain_pack"]["name"], manifest["domain_pack"]["version"]
        )
    except CompilationError as error:
        raise ProductError(
            "unsupported_domain_pack",
            error.message,
            stage="bundle",
            path="manifest.json",
        ) from error
    report = _identity_check(layers, pack)
    return ModelBundle(
        manifest,
        layers["business.json"],
        layers["core.json"],
        layers["plan.json"],
        layers["lineage.json"],
        report,
    )


def inspect_model(source: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Inspect a bundle or Business revision using the release admission rules."""
    try:
        if not isinstance(source, Mapping) and Path(source).suffix == ".simpack":
            bundle = load_bundle(source)
            return {
                "schema_version": "sim-engine-inspection/v1",
                "status": "valid",
                "bundle_id": bundle.bundle_id,
                "manifest": bundle.manifest,
                "association_status": bundle.identity_report["association_status"],
                "mapping_coverage": bundle.identity_report["coverage"]["level"],
                "diagnostics": bundle.identity_report["diagnostics"],
            }
        report = validate_business(source)
        return {
            "schema_version": "sim-engine-inspection/v1",
            **{key: value for key, value in report.items() if key != "schema_version"},
        }
    except ProductError as error:
        return {
            "schema_version": "sim-engine-inspection/v1",
            "status": "invalid",
            "diagnostics": [error.diagnostic()],
        }


def _runtime_ready() -> None:
    try:
        version = _native_module().__version__
    except RuntimeError as error:
        raise ProductError(
            "native_runtime_unavailable", str(error), stage="run"
        ) from error
    if version != RUNTIME_VERSION:
        raise ProductError(
            "unsupported_runtime_version",
            f"installed Rust runtime {version} is not {RUNTIME_VERSION}",
            stage="run",
        )


def _model_identity(bundle: ModelBundle) -> dict[str, Any]:
    manifest = bundle.manifest
    return {
        "bundle_id": bundle.bundle_id,
        "compiler_version": manifest["compiler_version"],
        "runtime_version": manifest["runtime_version"],
        "domain_pack": manifest["domain_pack"],
        "ir_versions": manifest["ir_versions"],
        "execution_profile": manifest["execution_profile"],
        "plan_fingerprint": manifest["identity"]["plan_fingerprint"],
        "business_fingerprint": manifest["identity"]["business_fingerprint"],
    }


def _seed(seed: int) -> None:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ProductError(
            "invalid_seed",
            "seed must be an unsigned 64-bit integer",
            stage="run",
            path="seed",
        )


def _request_identity(
    bundle: ModelBundle,
    run_id: str,
    index: int,
    seed: int,
    observation: str,
    until: int | None,
) -> dict[str, Any]:
    if bundle.manifest["domain_pack"]["name"] != PACK.name:
        if not isinstance(run_id, str) or not run_id:
            raise ProductError(
                "invalid_run_id",
                "run_id must be a non-empty string",
                stage="run",
                path="run_id",
            )
        return {
            "schema_version": "multi-server-queue-run-identity/v1",
            "run_id": run_id,
            "sample_index": index,
            "seed": seed,
            "observation": observation,
            "horizon": bundle.plan["duration_minutes"] if until is None else until,
            "plan_fingerprint": bundle.manifest["identity"]["plan_fingerprint"],
            "backend": "rust-runtime",
            "diagnostics": [],
        }
    value = build_run_identity(
        run_id,
        index,
        seed,
        bundle.plan,
        bundle={
            "business": bundle.business,
            "core": bundle.core,
            "plan": bundle.plan,
            "lineage": bundle.lineage,
        },
        observation=observation,
        horizon=until,
        engine_version=RUNTIME_VERSION,
        domain_package_version=PACK.version,
    )
    if value["status"] not in ("valid", "partial"):
        reason = value["diagnostics"][0] if value["diagnostics"] else {}
        raise ProductError(
            reason.get("code", "invalid_run_request"),
            reason.get("message", "run identity contract rejected request"),
            stage="run",
            path=reason.get("path"),
        )
    return value


def run_bundle(
    source: str | Path,
    *,
    seed: int = 0,
    run_id: str | None = None,
    observation: str = "full",
    until: int | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(source)
    _runtime_ready()
    _seed(seed)
    request_id = str(uuid4()) if run_id is None else run_id
    if until is not None and until > bundle.plan["duration_minutes"]:
        raise ProductError(
            "invalid_horizon",
            "until exceeds the model horizon",
            stage="run",
            path="until",
        )
    identity = _request_identity(bundle, request_id, 0, seed, observation, until)
    try:
        result = run_plan(
            bundle.plan, seed=seed, until=until, observation_level=observation
        )
    except (RuntimeError, ValueError, TypeError) as error:
        raise ProductError("runtime_error", str(error), stage="run") from error
    if (
        result.get("plan_fingerprint")
        != bundle.manifest["identity"]["plan_fingerprint"]
        or result.get("seed") != seed
    ):
        raise ProductError(
            "runtime_result_mismatch",
            "runtime result does not match request identity",
            stage="run",
        )
    return {
        "schema_version": RUN_VERSION,
        "bundle_id": bundle.bundle_id,
        "model_identity": _model_identity(bundle),
        "request_identity": identity,
        "result": result,
        "diagnostics": identity["diagnostics"],
        "result_sha256": content_digest(result),
    }


def batch_bundle(
    source: str | Path,
    seeds: Sequence[int],
    *,
    run_id: str | None = None,
    worker_threads: int | None = None,
    observation: str = "full",
    until: int | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(source)
    _runtime_ready()
    if not seeds:
        raise ProductError(
            "invalid_seeds", "at least one seed is required", stage="run", path="seeds"
        )
    for seed in seeds:
        _seed(seed)
    if worker_threads is not None and (
        type(worker_threads) is not int or worker_threads <= 0
    ):
        raise ProductError(
            "invalid_workers", "worker_threads must be positive", stage="run"
        )
    request_id = str(uuid4()) if run_id is None else run_id
    if until is not None and until > bundle.plan["duration_minutes"]:
        raise ProductError(
            "invalid_horizon",
            "until exceeds the model horizon",
            stage="run",
            path="until",
        )
    identities = [
        _request_identity(bundle, request_id, index, seed, observation, until)
        for index, seed in enumerate(seeds)
    ]
    try:
        result = run_batch(
            bundle.plan,
            seeds,
            worker_threads=worker_threads,
            until=until,
            observation_level=observation,
        )
    except (RuntimeError, ValueError, TypeError) as error:
        raise ProductError("runtime_error", str(error), stage="run") from error
    if (
        result.get("plan_fingerprint")
        != bundle.manifest["identity"]["plan_fingerprint"]
        or result.get("sample_count") != len(seeds)
        or [
            (sample.get("sample_index"), sample.get("seed"))
            for sample in result.get("samples", [])
        ]
        != list(enumerate(seeds))
        or any(
            sample.get("result", {}).get("plan_fingerprint")
            != bundle.manifest["identity"]["plan_fingerprint"]
            or sample.get("result", {}).get("seed") != seed
            for sample, seed in zip(result.get("samples", []), seeds)
        )
    ):
        raise ProductError(
            "runtime_result_mismatch",
            "batch result does not match request identity",
            stage="run",
        )
    return {
        "schema_version": BATCH_VERSION,
        "bundle_id": bundle.bundle_id,
        "model_identity": _model_identity(bundle),
        "request_id": request_id,
        "sample_identities": identities,
        "diagnostics": identities[0]["diagnostics"],
        "result": result,
        "result_sha256": content_digest(result),
    }


def diff_runs(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Describe observed differences for paired single-sample runs."""
    for record in (before, after):
        try:
            result_digest = content_digest(record["result"])
        except (KeyError, TypeError, ValueError, RecursionError):
            result_digest = None
        if (
            not isinstance(record, Mapping)
            or record.get("schema_version") != RUN_VERSION
            or not isinstance(record.get("request_identity"), Mapping)
            or not isinstance(record.get("model_identity"), Mapping)
            or not isinstance(record.get("result"), Mapping)
            or record.get("result_sha256") != result_digest
            or not isinstance(record["result"].get("metrics"), Mapping)
        ):
            raise ProductError(
                "invalid_run_record",
                "diff expects two intact v1 single-run records",
                stage="diff",
            )
    left, right = before["request_identity"], after["request_identity"]
    for record, identity in ((before, left), (after, right)):
        inspection = inspect_run_identity(identity)
        if (
            inspection["status"] not in ("valid", "partial")
            or not isinstance(identity.get("request"), Mapping)
            or not isinstance(identity.get("execution_contract"), Mapping)
            or not {"seed", "observation", "horizon"} <= set(identity["request"])
            or identity["execution_contract"].get("plan_fingerprint")
            != record["result"].get("plan_fingerprint")
            or identity["request"].get("seed") != record["result"].get("seed")
            or record["model_identity"].get("bundle_id") != record.get("bundle_id")
            or record["model_identity"].get("plan_fingerprint")
            != record["result"].get("plan_fingerprint")
        ):
            raise ProductError(
                "invalid_run_record",
                "run request and result identities disagree",
                stage="diff",
            )
    if (
        left["request"]["seed"] != right["request"]["seed"]
        or left["request"]["observation"] != right["request"]["observation"]
        or left["request"]["horizon"] != right["request"]["horizon"]
    ):
        raise ProductError(
            "incomparable_runs",
            "seed, observation and horizon must match",
            stage="diff",
        )
    old, new = before["result"], after["result"]
    divergence = first_divergence(old.get("trace"), new.get("trace"), path="trace")
    state_difference = first_divergence(
        old.get("terminal_state"), new.get("terminal_state"), path="terminal_state"
    )
    metric_names = set(old.get("metrics", {})) | set(new.get("metrics", {}))
    metric_changes = {
        name: {
            "before": old.get("metrics", {}).get(name),
            "after": new.get("metrics", {}).get(name),
        }
        for name in sorted(metric_names)
        if old.get("metrics", {}).get(name) != new.get("metrics", {}).get(name)
    }
    diagnostics = []
    if left["request"]["observation"] == "summary":
        diagnostics.append(
            {
                "code": "trace_not_materialized",
                "severity": "warning",
                "stage": "diff",
                "path": "result.trace",
                "message": "summary observation has no materialized event trace",
            }
        )
    return {
        "schema_version": DIFF_VERSION,
        "status": "equal"
        if old == new and before["bundle_id"] == after["bundle_id"]
        else "different",
        "before": {
            "bundle_id": before["bundle_id"],
            "plan_fingerprint": old.get("plan_fingerprint"),
        },
        "after": {
            "bundle_id": after["bundle_id"],
            "plan_fingerprint": new.get("plan_fingerprint"),
        },
        "first_trace_difference": None if divergence is None else vars(divergence),
        "first_terminal_difference": None
        if state_difference is None
        else vars(state_difference),
        "metric_changes": metric_changes,
        "diagnostics": diagnostics,
    }
