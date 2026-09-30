"""Derive a local Mission Operation report selector from fingerprinted Default.sxs.

The installed file's descriptor lists 68 MissionSettings flags, but its compact
value block contains only the first 64. The final four operation flags are
appended in descriptor order in this diagnostic candidate. No installed file is
modified.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
OUT = HERE / "runs" / "report-settings"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    raw = DEFAULT.read_bytes()
    assert sha(raw) == DEFAULT_SHA
    first = raw.index(b"MissionSettings\x00")
    second = raw.index(b"MissionSettings\x00", 0x10000)
    following = raw.index(b"MissionFormationSettings\x00", second)
    descriptor = raw[first:second]
    for key in (b"OPIT", b"OPTT", b"OPAIT", b"OPATT"):
        assert key in descriptor
    start = second + len(b"MissionSettings\x00") + 13
    cursor = start
    values = []
    flag_offsets = []
    for _ in range(66):  # two selectors, then 64 saved flags
        assert raw[cursor] == 1, (cursor, raw[cursor])
        size = struct.unpack_from("<I", raw, cursor + 1)[0]
        assert 2 <= size <= 64
        value = raw[cursor + 5:cursor + 5 + size]
        assert value.endswith(b"\x00")
        values.append(value[:-1])
        if len(values) > 2:
            flag_offsets.append(cursor + 5)
        cursor += 5 + size
        if len(values) == 54:
            assert raw[cursor:cursor + 4] == b"\x00" * 4
            cursor += 4
    assert values[:2] == [b"Total over all Units", b"Total over all Missions"]
    assert [i for i, value in enumerate(values[2:]) if value == b"Y"] == [1, 7]
    assert all(value in (b"N", b"Y") for value in values[2:])
    assert raw[cursor:cursor + 12] == raw[following - 12:following]
    assert cursor == following - 12
    # Each compact section starts with the absolute offset of the next one.
    # Extending MissionSettings requires relocating the pointer chain.
    appended = raw[:cursor] + (b"\x01\x02\x00\x00\x00Y\x00" * 4) + raw[cursor:]
    assert len(appended) == len(raw) + 28
    relocated = bytearray(appended)
    section = raw.index(b"GeneralSettings\x00", 0x10000) - 12
    sections = []
    while section < len(raw):
        next_section = struct.unpack_from("<I", raw, section)[0]
        assert section < next_section <= len(raw)
        sections.append((section, next_section))
        section = next_section
    assert len(sections) == 17 and section == len(raw)
    assert (second - 12, cursor) in sections
    for position, next_section in sections:
        if position >= second - 12:
            new_position = position + (28 if position >= cursor else 0)
            struct.pack_into("<I", relocated, new_position, next_section + 28)
    assert struct.unpack_from("<I", relocated, second - 12)[0] == cursor + 28
    assert struct.unpack_from("<I", relocated, len(relocated) - (len(raw) - sections[-1][0]))[0] == len(relocated)
    descriptor_child = bytearray(raw)
    for label in (
        b"Include Mission Operation IT",
        b"Include Mission Operation TT",
        b"Include Accum Mission Operation IT",
        b"Include Accum Mission Operation TT",
    ):
        marker = label + b": Y or N\x00" + b"\xff" * 8 + b"\x00" * 4 + b"\x02\x00\x00\x00"
        assert raw.count(marker) == 1
        position = raw.index(marker) + len(marker)
        assert raw[position:position + 2] == b"N\x00"
        descriptor_child[position] = ord("Y")
    assert len(descriptor_child) == len(raw)
    assert sum(a != b for a, b in zip(raw, descriptor_child)) == 4
    remapped = bytearray(raw)
    labels = (
        b"Include Extendable Mission IT",
        b"Include Extendable Mission IG",
        b"Include Extendable Mission TT",
        b"Include Extendable Mission TG",
        b"Include Mission Operation IT",
        b"Include Mission Operation TT",
        b"Include Accum Mission Operation IT",
        b"Include Accum Mission Operation TT",
    )
    for i, label in enumerate(labels):
        label_position = raw.index(label)
        old_index = 62 + i
        matches = [p for p in range(label_position - 45, label_position - 30)
                   if struct.unpack_from("<I", raw, p)[0] == old_index]
        assert len(matches) == 1, (label, matches)
        struct.pack_into("<I", remapped, matches[0], old_index + (4 if i < 4 else -4))
    for index in range(60, 64):
        assert raw[flag_offsets[index]:flag_offsets[index] + 2] == b"N\x00"
        remapped[flag_offsets[index]] = ord("Y")
    assert len(remapped) == len(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, child in (("operation-enabled.sxs", appended), ("operation-relocated-enabled.sxs", bytes(relocated)), ("operation-descriptor-enabled.sxs", bytes(descriptor_child)), ("operation-remapped-enabled.sxs", bytes(remapped))):
        path = OUT / name
        if path.exists():
            assert path.read_bytes() == child, f"existing settings differ: {path}"
        else:
            path.write_bytes(child)
        print(path, sha(child))


if __name__ == "__main__":
    main()
