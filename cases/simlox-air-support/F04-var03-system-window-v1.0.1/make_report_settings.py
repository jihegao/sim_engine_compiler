"""Make a local one-field report-settings probe from installed Default.sxs.

Only the serialized GeneralSettings.OUTRP value is changed, N -> Y.
The installed file is read-only and is never copied into Git.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
HERE = Path(__file__).resolve().parent
OUT = HERE / "runs" / "report-settings" / "replications-enabled.sxs"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    raw = DEFAULT.read_bytes()
    assert sha(raw) == DEFAULT_SHA
    marker = b"GeneralSettings\x00"
    first = raw.find(marker)
    pos = raw.find(marker, first + len(marker))
    assert first >= 0 and pos > first and raw.find(marker, pos + len(marker)) < 0
    cursor = pos + len(marker)
    assert raw[cursor:cursor + 13] == bytes.fromhex("01000000000100000001000000")
    cursor += 13
    values = []
    positions = []
    for _ in range(7):
        assert raw[cursor] == 1
        size = struct.unpack_from("<I", raw, cursor + 1)[0]
        value_start = cursor + 5
        value = raw[value_start:value_start + size]
        assert value.endswith(b"\x00")
        values.append(value[:-1])
        positions.append(value_start)
        cursor = value_start + size
    assert values == [b"N", b"Y", b"N", b"HOURS", b"Y", b"", b"N"], values
    patched = bytearray(raw)
    patched[positions[2]] = ord("Y")
    assert patched[positions[2] + 1] == 0
    assert len(patched) == len(raw)
    assert sum(a != b for a, b in zip(raw, patched)) == 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        assert OUT.read_bytes() == patched, "existing settings probe differs"
    else:
        OUT.write_bytes(patched)
    print("installed_default_sha256", sha(raw))
    print("local_probe_sha256", sha(patched))
    print("changed_offset", positions[2])


if __name__ == "__main__":
    main()
