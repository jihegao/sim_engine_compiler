"""Build three item-position report selectors from the pinned SIMLOX default."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

case = Path(__file__).resolve().parent
default = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
default_sha = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
depot_selector_sha = "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_depot() -> bytes:
    source = default.read_bytes()
    assert sha(source) == default_sha
    marker = b"MissionSettings\0"
    start = source.index(marker, 0x10000) + len(marker) + 13
    values = []
    cursor = start
    for _ in range(54):
        assert source[cursor] == 1
        size = struct.unpack_from("<I", source, cursor + 1)[0]
        value = source[cursor + 5:cursor + 5 + size]
        assert value.endswith(b"\0")
        values.append((cursor + 5, value[:-1]))
        cursor += 5 + size
    assert [v for _, v in values[:2]] == [b"Total over all Units", b"Total over all Missions"]
    enabled = bytearray(source)
    for index in (0, 2, 28, 30, 40, 42, 44, 46):
        offset, value = values[index + 2]
        assert value == b"N"
        enabled[offset] = ord("Y")
    source = bytes(enabled)

    marker = b"ItemPositionSettings\0"
    offset = source.index(marker, 0x10000) + len(marker)
    assert source[offset:offset + 9] == b"\x01\0\0\0\0\0\0\0\0"
    assert source[offset + 9:offset + 13] == b"\x0f\x0d\x01\0"
    fields = ["TEACH-LRU-01", "DEPOT-01"] + ["N"] * 32
    for index in (2, 30, 32):
        fields[index] = "Y"
    serialized = b"".join(
        b"\x01" + struct.pack("<I", len(value.encode("ascii")) + 1)
        + value.encode("ascii") + b"\0" for value in fields
    )
    child = source[:offset] + b"\x01\0\0\0\0\x01\0\0\0\x01\0\0\0" + serialized + source[offset + 9:]
    assert sha(child) == depot_selector_sha
    return child


def main() -> None:
    depot = build_depot()
    old = b"\x01" + struct.pack("<I", len(b"DEPOT-01\0")) + b"DEPOT-01\0"
    assert depot.count(old) == 1
    directory = case / "runs/report-settings"
    directory.mkdir(parents=True, exist_ok=True)
    for station in ("DEPOT-01", "BASE-01", "BASE-02"):
        new = b"\x01" + struct.pack("<I", len(station) + 1) + station.encode("ascii") + b"\0"
        payload = depot.replace(old, new, 1)
        target = directory / f"{station.lower()}.sxs"
        if target.exists():
            assert target.read_bytes() == payload, f"frozen selector changed: {station}"
        else:
            target.write_bytes(payload)
        print(station, sha(payload))


if __name__ == "__main__":
    main()
