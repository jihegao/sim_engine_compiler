"""Make local report-only selectors from the fingerprinted SIMLOX Default.sxs."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
OUT = HERE / "runs" / "report-settings"
SELECTORS = {
    "all": ("Total over all Units", "Total over all Missions"),
    "group": ("TEACH-GROUP", "Total over all Missions"),
    "unit-a": ("TEACH-UNIT", "Total over all Missions"),
    "unit-b": ("TEACH-UNIT-2", "Total over all Missions"),
    "type-a": ("Total over all Units", "MISSION-A"),
    "type-b": ("Total over all Units", "MISSION-B"),
    "group-type-a": ("TEACH-GROUP", "MISSION-A"),
    "group-type-b": ("TEACH-GROUP", "MISSION-B"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    raw = DEFAULT.read_bytes()
    assert sha(raw) == DEFAULT_SHA
    marker = b"MissionSettings\x00"
    start = raw.index(marker, 0x10000) + len(marker) + 13
    values: list[tuple[int, bytes]] = []
    cursor = start
    for _ in range(54):
        assert raw[cursor] == 1
        size = struct.unpack_from("<I", raw, cursor + 1)[0]
        value = raw[cursor + 5:cursor + 5 + size]
        assert value.endswith(b"\x00")
        values.append((cursor + 5, value[:-1]))
        cursor += 5 + size
    assert [v for _, v in values[:2]] == [b"Total over all Units", b"Total over all Missions"]
    assert cursor < raw.index(b"MissionFormationSettings\x00", 0x10000)

    # MissionSettings schema order: mission time IT/TT, mission system time
    # IT/TT, and fixed mission IT/TT. One-byte changes only for table flags.
    flags = {0, 2, 28, 30, 40, 42}
    enabled = bytearray(raw)
    for index in flags:
        offset, value = values[index + 2]
        assert value == b"N"
        enabled[offset] = ord("Y")
    assert [i for i, (a, b) in enumerate(zip(raw, enabled)) if a != b] == [values[i + 2][0] for i in sorted(flags)]

    OUT.mkdir(parents=True, exist_ok=True)
    for selector, (unit, mission) in SELECTORS.items():
        child = bytearray(enabled)
        for original_index, new_value in ((1, mission), (0, unit)):
            position, old_value = values[original_index]
            data = new_value.encode("ascii") + b"\x00"
            child[position - 4:position] = struct.pack("<I", len(data))
            child[position:position + len(old_value) + 1] = data
        path = OUT / f"{selector}.sxs"
        if path.exists():
            assert path.read_bytes() == child, f"settings changed: {path}"
        else:
            path.write_bytes(child)
        print(selector, sha(child))


if __name__ == "__main__":
    main()
