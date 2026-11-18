"""Public, installed sim-engine CLI for the v0.1 aircraft product contract."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from sim_engine_compiler import __version__, product


def _read_json(path: str) -> dict:
    try:
        return product._json_bytes(Path(path).read_bytes(), path)
    except OSError as error:
        raise product.ProductError(
            "input_read_error", str(error), stage="load", path=path
        ) from error


def _write_json(path: str, value: dict) -> None:
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(product._canonical_bytes(value) + b"\n")
    except OSError as error:
        raise product.ProductError(
            "output_write_error", str(error), stage="write", path=path
        ) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim-engine", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser(
        "inspect", help="validate and describe a Business revision or bundle"
    )
    inspect.add_argument("source")
    inspect.add_argument(
        "--business-output", help="export the validated bundle's Business revision"
    )
    validate = commands.add_parser(
        "validate", help="validate a persisted Business revision"
    )
    validate.add_argument("source")
    seal = commands.add_parser(
        "seal", help="explicitly seal an edited Business payload"
    )
    seal.add_argument("source", help="payload JSON or an edited Business envelope")
    seal.add_argument("output")
    compile_command = commands.add_parser(
        "compile", help="compile a Business revision to .simpack"
    )
    compile_command.add_argument("source")
    compile_command.add_argument("output")
    run = commands.add_parser("run", help="execute one sample with the native runtime")
    run.add_argument("bundle")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--run-id")
    run.add_argument("--observation", choices=("full", "summary"), default="full")
    run.add_argument("--until", type=int)
    run.add_argument("--output")
    batch = commands.add_parser("batch", help="execute ordered independent seeds")
    batch.add_argument("bundle")
    batch.add_argument(
        "--seeds",
        required=True,
        help="comma-separated unsigned integers; repeats allowed",
    )
    batch.add_argument("--run-id")
    batch.add_argument("--worker-threads", type=int)
    batch.add_argument("--observation", choices=("full", "summary"), default="full")
    batch.add_argument("--until", type=int)
    batch.add_argument("--output")
    diff = commands.add_parser("diff", help="compare two paired single-run records")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--output")
    example = commands.add_parser(
        "example", help="write a packaged Business revision and bundle"
    )
    example.add_argument("directory")
    example.add_argument(
        "--profile",
        default="aircraft-support-v1",
        choices=("aircraft-support-v1", "multi-server-queue-v1"),
        help="domain profile to materialize",
    )
    return parser


def _execute(args: argparse.Namespace) -> dict:
    if args.command == "inspect":
        result = product.inspect_model(args.source)
        if args.business_output:
            if result["status"] != "valid" or Path(args.source).suffix != ".simpack":
                raise product.ProductError(
                    "invalid_export_source",
                    "Business export requires a valid bundle",
                    stage="inspect",
                    path=args.source,
                )
            _write_json(args.business_output, product.load_bundle(args.source).business)
        return result
    if args.command == "validate":
        return product.validate_business(args.source)
    if args.command == "seal":
        value = _read_json(args.source)
        if set(value) == {"version", "fingerprint", "payload"}:
            value = value["payload"]
        sealed = product.seal_business(value)
        _write_json(args.output, sealed)
        return {
            "schema_version": "sim-engine-seal/v1",
            "status": "valid",
            "business_fingerprint": sealed["fingerprint"],
            "output": args.output,
            "diagnostics": [],
        }
    if args.command == "compile":
        return product.compile_bundle(args.source, args.output)
    if args.command == "run":
        result = product.run_bundle(
            args.bundle,
            seed=args.seed,
            run_id=args.run_id,
            observation=args.observation,
            until=args.until,
        )
    elif args.command == "batch":
        try:
            seeds = [int(item.strip()) for item in args.seeds.split(",")]
        except ValueError as error:
            raise product.ProductError(
                "invalid_seeds", str(error), stage="run", path="seeds"
            ) from error
        result = product.batch_bundle(
            args.bundle,
            seeds,
            run_id=args.run_id,
            worker_threads=args.worker_threads,
            observation=args.observation,
            until=args.until,
        )
    elif args.command == "diff":
        result = product.diff_runs(_read_json(args.before), _read_json(args.after))
    elif args.command == "example":
        root = Path(args.directory)
        if args.profile == "multi-server-queue-v1":
            from sim_engine_compiler.domains.multi_server_queue.model import EXAMPLE_INPUT

            business = product.seal_business(EXAMPLE_INPUT)
        else:
            business = product._json_bytes(
                files("sim_engine_compiler.examples")
                .joinpath("aircraft_b1_business.json")
                .read_bytes(),
                "aircraft_b1_business.json",
            )
        business_path, bundle_path = root / "business.json", root / "baseline.simpack"
        _write_json(str(business_path), business)
        compiled = product.compile_bundle(business_path, bundle_path)
        return {
            "schema_version": "sim-engine-example/v1",
            "status": "valid",
            "business": str(business_path),
            "bundle": str(bundle_path),
            "bundle_id": compiled["bundle_id"],
            "diagnostics": [],
        }
    else:
        raise product.ProductError("unknown_command", "unknown command", stage="cli")
    if getattr(args, "output", None):
        _write_json(args.output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = _execute(args)
    except product.ProductError as error:
        print(
            json.dumps(
                {
                    "schema_version": "sim-engine-error/v1",
                    "status": "invalid",
                    "diagnostics": [error.diagnostic()],
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return (
            3
            if error.stage == "run"
            and error.code
            in (
                "native_runtime_unavailable",
                "runtime_error",
                "runtime_result_mismatch",
            )
            else 2
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result.get("status") not in ("invalid", "unsupported") else 2


if __name__ == "__main__":
    raise SystemExit(main())
