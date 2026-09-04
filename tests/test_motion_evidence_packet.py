from __future__ import annotations

import struct
import unittest

from putttrack.tag.motion_evidence import (
    MOTION_EVIDENCE_PACKET_SIZE,
    MotionEvidenceProtocolError,
    parse_motion_evidence,
)


class MotionEvidencePacketTests(unittest.TestCase):
    def test_parse_packet(self) -> None:
        packet = bytearray(MOTION_EVIDENCE_PACKET_SIZE)
        packet[0] = 1
        packet[1] = 2  # ROLLING
        struct.pack_into(
            "<HIQHHII",
            packet,
            2,
            (1 << 0) | (1 << 2),
            123,
            4_567_890,
            960,
            1 << 1,
            0x62C82C1A,
            7,
        )
        result = parse_motion_evidence(packet)
        self.assertEqual(result.motion_state, "ROLLING")
        self.assertEqual(result.events, ("MOTION_ONSET", "ROLLING_START"))
        self.assertEqual(result.quality, ("GYRO_CLIPPED",))
        self.assertAlmostEqual(result.confidence, 0.96)
        self.assertEqual(result.tee_arm_epoch, 7)
        self.assertFalse(result.authority)

    def test_invalid_size_fails(self) -> None:
        with self.assertRaises(MotionEvidenceProtocolError):
            parse_motion_evidence(b"\x01")

    def test_unknown_state_fails(self) -> None:
        packet = bytearray(MOTION_EVIDENCE_PACKET_SIZE)
        packet[0] = 1
        packet[1] = 99
        with self.assertRaises(MotionEvidenceProtocolError):
            parse_motion_evidence(packet)


if __name__ == "__main__":
    unittest.main()
