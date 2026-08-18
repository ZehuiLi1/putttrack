"""Deterministic source ordering and gap diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from putttrack.contracts import BaseRecord


@dataclass(frozen=True)
class OrderingStatus:
    source_device_id: str
    source_boot_id: str
    sequence: int
    new_boot: bool = False
    duplicate_sequence: bool = False
    sequence_gap: tuple[int, int] | None = None
    out_of_order: bool = False
    clock_regression: bool = False

    @property
    def clean(self) -> bool:
        return not any(
            (
                self.duplicate_sequence,
                self.sequence_gap is not None,
                self.out_of_order,
                self.clock_regression,
            )
        )


@dataclass
class _SourceState:
    boot_id: str
    last_sequence: int
    last_monotonic_ns: int


class OrderingTracker:
    """Track sequence/time domains without discarding any evidence."""

    def __init__(self) -> None:
        self._sources: dict[str, _SourceState] = {}

    def observe(self, record: BaseRecord) -> OrderingStatus:
        prior = self._sources.get(record.source_device_id)
        if prior is None or prior.boot_id != record.source_boot_id:
            self._sources[record.source_device_id] = _SourceState(
                boot_id=record.source_boot_id,
                last_sequence=record.sequence,
                last_monotonic_ns=record.source_monotonic_ns,
            )
            return OrderingStatus(
                source_device_id=record.source_device_id,
                source_boot_id=record.source_boot_id,
                sequence=record.sequence,
                new_boot=prior is not None,
            )

        duplicate = record.sequence == prior.last_sequence
        out_of_order = record.sequence < prior.last_sequence
        gap = None
        if record.sequence > prior.last_sequence + 1:
            gap = (prior.last_sequence + 1, record.sequence - 1)
        clock_regression = record.source_monotonic_ns < prior.last_monotonic_ns

        if record.sequence > prior.last_sequence:
            prior.last_sequence = record.sequence
        if record.source_monotonic_ns > prior.last_monotonic_ns:
            prior.last_monotonic_ns = record.source_monotonic_ns

        return OrderingStatus(
            source_device_id=record.source_device_id,
            source_boot_id=record.source_boot_id,
            sequence=record.sequence,
            duplicate_sequence=duplicate,
            sequence_gap=gap,
            out_of_order=out_of_order,
            clock_regression=clock_regression,
        )
