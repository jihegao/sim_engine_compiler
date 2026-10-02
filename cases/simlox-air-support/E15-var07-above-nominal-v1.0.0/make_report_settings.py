"""Recreate the local item-position report selector from the pinned installation."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
EXPECTED_SHA = "841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c"
OUTPUT = HERE / "runs" / "report-settings" / "item-position-results.sxs"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    source = DEFAULT.read_bytes()
    assert sha(source) == DEFAULT_SHA

    # Retain the accepted J07 mission tables in the local report export.
    marker = b"MissionSettings\0"
    start = source.index(marker, 0x10000) + len(marker) + 13
    values: list[tuple[int, bytes]] = []
    cursor = start
    for _ in range(54):
        assert source[cursor] == 1
        size = struct.unpack_from("<I", source, cursor + 1)[0]
        value = source[cursor + 5 : cursor + 5 + size]
        assert value.endswith(b"\0")
        values.append((cursor + 5, value[:-1]))
        cursor += 5 + size
    assert [value for _, value in values[:2]] == [
        b"Total over all Units", b"Total over all Missions"
    ]
    enabled = bytearray(source)
    for index in (0, 2, 28, 30, 40, 42, 44, 46):
        offset, value = values[index + 2]
        assert value == b"N"
        enabled[offset] = ord("Y")
    source = bytes(enabled)

    # The default has no ItemPositionSettings value object. Add its 34 fields:
    # IID, STID, then the 32 report switches in the installed schema order.
    marker = b"ItemPositionSettings\0"
    offset = source.index(marker, 0x10000) + len(marker)
    assert source[offset : offset + 9] == b"\x01\0\0\0\0\0\0\0\0"
    assert source[offset + 9 : offset + 13] == b"\x0f\x0d\x01\0"
    fields = ["TEACH-DU-01", "DEPOT-01"] + ["N"] * 32
    for index in (2, 30, 32):
        fields[index] = "Y"  # SLIT, SRIT, SRTT
    assert len(fields) == 34
    serialized = b"".join(
        b"\x01" + struct.pack("<I", len(value.encode("ascii")) + 1)
        + value.encode("ascii") + b"\0"
        for value in fields
    )
    child = (
        source[:offset]
        + b"\x01\0\0\0\0\x01\0\0\0\x01\0\0\0"
        + serialized
        + source[offset + 9 :]
    )
    assert sha(child) == EXPECTED_SHA
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == child, "local report settings changed"
    else:
        OUTPUT.write_bytes(child)
    print(f"{OUTPUT}: {sha(child)}")


if __name__ == "__main__":
    main()

