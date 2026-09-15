import struct
import unittest
from dataclasses import replace

from putttrack.tag.telemetry import parse_motion, motion_window_from_smp, TelemetryProtocolError
from putttrack.tag.session import TagCaptureSession
from test_tag_capture_session import status, motion


class XiaoProtocolTests(unittest.TestCase):
    def test_single_imu_layout_survives_binary_decode_and_export(self):
        raw = struct.pack('<BBHIQ9iI', 2, 3, 56, 7, 120000, 1, 2, 9806650,
                          1, 2, 9806650, 100, 200, 300, 0)
        record = parse_motion(raw)
        self.assertEqual(record.to_dict()['sensor_layout'], 'lsm6ds3tr-c-single')
        self.assertEqual(record.adxl367_accel_micro_ms2, record.bmi270_accel_micro_ms2)
        self.assertEqual(record.bmi270_gyro_micro_rads, (100, 200, 300))
        with self.assertRaisesRegex(TelemetryProtocolError, 'mixes sensor protocols'):
            motion_window_from_smp(dict(proto=1, sample_size=56, count=1,
                                        start_seq=7, end_seq=7, data_hex=raw.hex()))

    def test_mixed_board_capture_cannot_pass(self):
        capture = TagCaptureSession()
        capture.start(status(protocol_version=2))
        capture.observe_motion(motion(10, 1100000))
        result = capture.finalize(status(sequence=10, uptime_ms=1200))
        self.assertFalse(result.passed)
        self.assertIn('motion_protocol_changed', result.issues)
        self.assertIn('status_protocol_changed', result.issues)

    def test_xiao_capture_can_pass_and_unknown_version_cannot_decode(self):
        capture = TagCaptureSession()
        capture.start(status(protocol_version=2))
        capture.observe_motion(motion(10, 1100000, protocol_version=2))
        self.assertTrue(capture.finalize(status(protocol_version=2, sequence=10, uptime_ms=1200)).passed)
        with self.assertRaisesRegex(TelemetryProtocolError, 'unsupported'):
            parse_motion(struct.pack('<BBHIQ9iI', 3, 3, 56, 7, 120000, *([0] * 10)))
