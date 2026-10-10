"""Read-only trace query of persisted result, request, Plan and optional bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .query import input_error_report, query_trace


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field {key!r}")
        value[key] = item
    return value


def _read(path):
    with Path(path).open("rb") as source:
        raw = source.read(128 * 1024 * 1024 + 1)
    if len(raw) > 128 * 1024 * 1024:
        raise ValueError("trace query input exceeds 128 MiB per-file limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result")
    parser.add_argument("--request", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--query")
    parser.add_argument("--bundle", help="JSON object of raw Business/Core/Plan/lineage artifacts")
    args = parser.parse_args(argv)
    try:
        report = query_trace(_read(args.result), _read(args.request), _read(args.plan),
                             query=_read(args.query) if args.query else None,
                             bundle=_read(args.bundle) if args.bundle else None)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        report = input_error_report(error)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 2 if report["status"] in ("invalid", "unsupported") else 0


if __name__ == "__main__":
    raise SystemExit(main())
