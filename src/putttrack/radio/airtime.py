"""Deterministic decentralized jitter for redundant connectionless event packets."""

from __future__ import annotations

import hashlib


def deterministic_repetition_offsets_ms(
    packet_key: str,
    *,
    repetitions: int = 3,
    window_ms: int = 120,
) -> tuple[int, ...]:
    """Return immediate-first, stable offsets that spread different Ball events.

    This is a research primitive, not a claim that collisions are independently
    distributed. Receiver captures must measure the real many-Ball result.
    """

    if not packet_key:
        raise ValueError("packet_key must be non-empty")
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    if window_ms < repetitions - 1:
        raise ValueError("window_ms is too small for unique repetition offsets")
    if repetitions == 1:
        return (0,)

    digest = hashlib.sha256(packet_key.encode("utf-8")).digest()
    candidates = list(range(1, window_ms + 1))
    selected = [0]
    counter = 0
    while len(selected) < repetitions:
        block = hashlib.sha256(digest + counter.to_bytes(4, "little")).digest()
        for offset in range(0, len(block), 2):
            index = int.from_bytes(block[offset : offset + 2], "little") % len(candidates)
            selected.append(candidates.pop(index))
            if len(selected) == repetitions:
                break
        counter += 1
    return tuple(sorted(selected))
