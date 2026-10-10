"""Inspect persisted aircraft identity artifacts; emit JSON without executing a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .artifacts import inspect_artifact, inspect_bundle
from .common import diagnostic


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field {key!r}")
        value[key] = item
    return value


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_object)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    artifact = commands.add_parser("artifact", help="inspect a Business/Core/Plan JSON file")
    artifact.add_argument("input")
    bundle = commands.add_parser("bundle", help="verify supplied layer relationships")
    for layer in ("business", "core", "plan", "lineage"):
        bundle.add_argument(f"--{layer}")
    args = parser.parse_args(argv)
    try:
        if args.command == "artifact":
            result = inspect_artifact(_read(args.input))
        else:
            result = inspect_bundle(**{
                layer: _read(path) for layer in ("business", "core", "plan", "lineage")
                if (path := getattr(args, layer)) is not None
            })
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        result = {"schema_version": "model-identity-cli/v1", "status": "invalid",
                  "diagnostics": [diagnostic("input_read_error", str(error), stage="load")]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 2 if result["status"] in ("invalid", "unsupported") else 0


if __name__ == "__main__":
    raise SystemExit(main())
