"""Enable native Mission Operation reports for the all-unit A14 contrast.

The installed Default.sxs is fingerprinted and never edited. The saved value
block lacks four descriptor-tail operation flags. On this installed version,
swapping those descriptor indices with four unused extendable-mission slots
and enabling the corresponding saved flags produces a valid local selector.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
BASE_SETTINGS_SHA = "c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7"
OUT = HERE / "runs" / "report-settings"
SELECTORS = {"all": "Total over all Units"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    raw = DEFAULT.read_bytes()
    assert sha(raw) == DEFAULT_SHA
    second = raw.index(b"MissionSettings\x00", 0x10000)
    cursor = second + len(b"MissionSettings\x00") + 13
    values: list[tuple[int, bytes]] = []
    for index in range(66):  # two selectors and 64 saved flags
        assert raw[cursor] == 1
        size = struct.unpack_from("<I", raw, cursor + 1)[0]
        value = raw[cursor + 5:cursor + 5 + size]
        assert value.endswith(b"\x00")
        values.append((cursor + 5, value[:-1]))
        cursor += 5 + size
        if index == 53:
            assert raw[cursor:cursor + 4] == b"\x00" * 4
            cursor += 4
    assert [value for _, value in values[:2]] == [b"Total over all Units", b"Total over all Missions"]
    assert raw[cursor:cursor + 12].endswith(b"\x19\x00\x00\x00")
    child = bytearray(raw)
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
    for index, label in enumerate(labels):
        label_position = raw.index(label)
        old_index = 62 + index
        positions = [p for p in range(label_position - 45, label_position - 30)
                     if struct.unpack_from("<I", raw, p)[0] == old_index]
        assert len(positions) == 1
        struct.pack_into("<I", child, positions[0], old_index + (4 if index < 4 else -4))
    for index in range(60, 64):
        position, value = values[index + 2]
        assert value == b"N"
        child[position] = ord("Y")
    assert len(child) == len(raw)
    assert sum(a != b for a, b in zip(raw, child)) == 12
    assert sha(child) == BASE_SETTINGS_SHA
    OUT.mkdir(parents=True, exist_ok=True)
    for selector, unit in SELECTORS.items():
        selected = bytearray(child)
        position, old = values[0]
        replacement = unit.encode("ascii") + b"\x00"
        selected[position - 4:position] = struct.pack("<I", len(replacement))
        selected[position:position + len(old) + 1] = replacement
        path = OUT / f"{selector}.sxs"
        if path.exists():
            assert path.read_bytes() == selected, f"frozen selector changed: {path}"
        else:
            path.write_bytes(selected)
        print(selector, sha(selected), len(selected))


if __name__ == "__main__":
    main()
