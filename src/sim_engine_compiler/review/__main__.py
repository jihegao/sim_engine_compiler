"""Export offline review JSON. This command never runs a model or writes input files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .exporter import export_review, input_error_report


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field {key!r}")
        value[key] = item
    return value


def _read(path):
    with Path(path).open("rb") as source:
        raw = source.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("review input exceeds 32 MiB limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="export a persisted Business or Core JSON artifact")
    export.add_argument("input")
    export.add_argument("--view", action="append", dest="views")
    for layer in ("business", "core", "plan", "lineage"):
        export.add_argument(f"--{layer}")
    args = parser.parse_args(argv)
    try:
        bundle = {layer: _read(path) for layer in ("business", "core", "plan", "lineage")
                  if (path := getattr(args, layer)) is not None}
        report = export_review(_read(args.input), bundle=bundle or None, views=args.views)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        report = input_error_report(error)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 2 if report["status"] in ("invalid", "unsupported") else 0


if __name__ == "__main__":
    raise SystemExit(main())
