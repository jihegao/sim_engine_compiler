"""Read the sealed native JSON without changing its bytes.

SIMLOX's report writer can leave commas before closing brackets. Only those
unquoted commas are removed in memory, with a linear scan.
"""
from __future__ import annotations

import json
from pathlib import Path


def loads_native(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for index, char in enumerate(text):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == ",":
                future = index + 1
                while future < len(text) and text[future].isspace():
                    future += 1
                if future == len(text) or text[future] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


def read(path: Path):
    return loads_native(path.read_text(encoding="utf-8-sig"))
