#!/usr/bin/env python3
"""Create an MCUboot test image with a deliberately corrupted Ed25519 signature."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


ED25519_TLV = 0x24
TLV_INFO_MAGIC = 0x6907


def corrupt_ed25519_signature(image: bytes) -> bytes:
    data = bytearray(image)
    if len(data) < 16:
        raise ValueError("image is too short for an MCUboot header")

    header_size, protected_size = struct.unpack_from("<HH", data, 8)
    body_size = struct.unpack_from("<I", data, 12)[0]
    offset = header_size + body_size + protected_size
    if offset + 4 > len(data):
        raise ValueError("image does not contain an unprotected TLV area")

    magic, total_size = struct.unpack_from("<HH", data, offset)
    if magic != TLV_INFO_MAGIC:
        raise ValueError(f"unexpected MCUboot TLV magic: 0x{magic:04x}")
    end = offset + total_size
    if end > len(data):
        raise ValueError("MCUboot TLV area extends past the image")

    offset += 4
    while offset < end:
        if offset + 4 > end:
            raise ValueError("truncated MCUboot TLV header")
        kind, _reserved, length = struct.unpack_from("<BBH", data, offset)
        offset += 4
        if offset + length > end:
            raise ValueError("truncated MCUboot TLV value")
        if kind == ED25519_TLV:
            if length == 0:
                raise ValueError("empty Ed25519 signature TLV")
            data[offset] ^= 0x01
            return bytes(data)
        offset += length

    raise ValueError("Ed25519 signature TLV was not found")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    args.output.write_bytes(corrupt_ed25519_signature(args.input.read_bytes()))
    print(args.output)


if __name__ == "__main__":
    main()
