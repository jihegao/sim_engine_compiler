"""Read native JSON bytes without changing the sealed file on disk."""
from __future__ import annotations

import json
from pathlib import Path


def parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = []
        quoted = escaped = False
        for index, char in enumerate(raw):
            if quoted:
                clean.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                clean.append(char)
            elif char == ",":
                lookahead = index + 1
                while lookahead < len(raw) and raw[lookahead].isspace():
                    lookahead += 1
                if lookahead == len(raw) or raw[lookahead] not in "}]":
                    clean.append(char)
            else:
                clean.append(char)
        return json.loads("".join(clean))
