"""Derive a mission-enabled .sxs from the pinned installed default."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path


CASE = Path(__file__).resolve().parent
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
FLAGS = (0, 2, 28, 30, 40, 42, 44, 46)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build() -> bytes:
    source = DEFAULT.read_bytes()
    assert digest(source) == DEFAULT_SHA
    marker = b"MissionSettings\0"
    start = source.index(marker, 0x10000) + len(marker) + 13
    values = []
    cursor = start
    for _ in range(54):
        assert source[cursor] == 1
        size = struct.unpack_from("<I", source, cursor + 1)[0]
        value = source[cursor + 5 : cursor + 5 + size]
        assert value.endswith(b"\0")
        values.append((cursor + 5, value[:-1]))
        cursor += 5 + size
    assert [value for _, value in values[:2]] == [b"Total over all Units", b"Total over all Missions"]
    enabled = bytearray(source)
    for index in FLAGS:
        offset, value = values[index + 2]
        assert value == b"N"
        enabled[offset] = ord("Y")
    changed = [i for i, (a, b) in enumerate(zip(source, enabled)) if a != b]
    assert len(changed) == len(FLAGS) and all(source[i] == ord("N") and enabled[i] == ord("Y") for i in changed)
    return bytes(enabled)


def main() -> None:
    target = CASE / "runs" / "settings" / "mission-enabled.sxs"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build()
    if target.exists():
        assert target.read_bytes() == payload, "frozen report settings changed"
    else:
        target.write_bytes(payload)
    print(digest(payload))


if __name__ == "__main__":
    main()
