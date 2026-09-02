from __future__ import annotations

import struct
import unittest

from putttrack.tag import (
    TelemetryProtocolError,
    frozen_history_from_smp,
    frozen_history_metadata_from_smp,
    motion_from_smp,
    motion_window_from_smp,
    parse_motion,
    parse_status,
    status_from_smp,
)


class TagTelemetryTests(unittest.TestCase):
    def test_status_packet(self) -> None:
        packet = bytearray(64)
        struct.pack_into("<BBHIQIII4B", packet, 0, 1, 0x1F, 64, 42, 1234, 9, 2, 3, 8, 8, 5, 0)
        packet[32:40] = bytes.fromhex("0011223344556677")
        packet[48:56] = bytes.fromhex("8899aabbccddeeff")
        packet[56:61] = b"0.1.0"

        status = parse_status(packet)

        self.assertEqual(status.sequence, 42)
        self.assertEqual(status.uptime_ms, 1234)
        self.assertTrue(status.adxl367_ready)
        self.assertTrue(status.bmi270_ready)
        self.assertTrue(status.notify_active)
        self.assertEqual(status.device_id, "0011223344556677")
        self.assertEqual(status.boot_id, "8899aabbccddeeff")
        self.assertEqual(status.firmware_version, "0.1.0")
        self.assertEqual(status.sensor_error_count, 2)
        self.assertEqual(status.notify_drop_count, 3)
        self.assertEqual(status.power_policy, "auto")
        self.assertEqual(status.runtime_state, "active")

    def test_motion_packet(self) -> None:
        packet = struct.pack(
            "<BBHIQ9iI",
            1,
            0x03,
            56,
            7,
            998877,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            0,
        )

        motion = parse_motion(packet)

        self.assertEqual(motion.sequence, 7)
        self.assertEqual(motion.source_monotonic_us, 998877)
        self.assertEqual(motion.adxl367_accel_micro_ms2, (1, 2, 3))
        self.assertEqual(motion.bmi270_accel_micro_ms2, (4, 5, 6))
        self.assertEqual(motion.bmi270_gyro_micro_rads, (7, 8, 9))
        self.assertTrue(motion.adxl367_valid)
        self.assertTrue(motion.bmi270_valid)

    def test_rejects_wrong_size_and_version(self) -> None:
        with self.assertRaises(TelemetryProtocolError):
            parse_motion(b"short")

        packet = bytearray(64)
        struct.pack_into("<BBH", packet, 0, 2, 0, 64)
        with self.assertRaises(TelemetryProtocolError):
            parse_status(packet)

    def test_status_rejects_missing_device_or_wrong_boot_id_size(self) -> None:
        packet = bytearray(64)
        struct.pack_into(
            "<BBHIQIII4B",
            packet,
            0,
            1,
            0x03,
            64,
            1,
            10,
            0,
            0,
            0,
            0,
            8,
            5,
            0,
        )
        packet[48:56] = bytes.fromhex("8899aabbccddeeff")
        packet[56:61] = b"0.1.0"
        with self.assertRaisesRegex(TelemetryProtocolError, "device ID length"):
            parse_status(packet)

        packet[28] = 8
        packet[29] = 7
        packet[32:40] = bytes.fromhex("0011223344556677")
        with self.assertRaisesRegex(TelemetryProtocolError, "boot ID length"):
            parse_status(packet)

    def test_normalizes_smp_status(self) -> None:
        status = status_from_smp(
            {
                "proto": 1,
                "seq": 44,
                "uptime_ms": 4453,
                "reset": 2,
                "sensor_errors": 0,
                "notify_drops": 0,
                "adxl_ready": True,
                "bmi_ready": True,
                "device_id": "F383571202836E6F",
                "boot_id": "d025bbc2516a54f9",
                "fw": "0.1.2",
                "stream_hz": 50,
                "adxl_odr_hz": 100,
                "adxl_range_g": 2,
                "bmi_accel_odr_hz": 100,
                "bmi_accel_range_g": 16,
                "bmi_gyro_odr_hz": 100,
                "bmi_gyro_range_dps": 2000,
                "adxl_clips": 3,
                "bmi_accel_clips": 1,
                "bmi_gyro_clips": 2,
                "power_policy": "auto",
                "runtime_state": "idle",
                "power_transitions": 4,
                "idle_timeout_ms": 30000,
                "wake_poll_ms": 80,
                "adv_interval_min_ms": 1000,
                "adv_interval_max_ms": 1200,
                "adv_start_errors": 2,
                "pm_errors": 0,
                "bmi_spi_suspended": True,
                "wake_interrupt": True,
                "adxl_wakeup_mode": True,
                "battery_supported": False,
                "nfc_enabled": True,
                "nfc_setup_error": 0,
                "nfc_field_on": 4,
                "nfc_field_off": 3,
                "nfc_field_present": True,
                "nfc_service_window": True,
                "nfc_service_window_ms": 10000,
                "nfc_service_window_opens": 2,
                "nfc_service_window_suppressed": 1,
                "sensor_health": "healthy",
                "capture_safe": True,
                "sensor_faults": 2,
                "recovery_generation": 3,
                "recovery_attempts": 4,
                "recovery_successes": 1,
                "recovery_failures": 3,
                "adxl_error_streak": 0,
                "bmi_error_streak": 0,
                "last_sensor_error_bits": 1,
                "last_sensor_error_ms": 4321,
                "auto_reboots": 1,
                "auto_reboot_fault_bits": 1,
                "auto_reboot_guard": True,
                "auto_reboot_pending": False,
                "idle_health_check_ms": 600000,
            }
        )

        self.assertEqual(status.device_id, "f383571202836e6f")
        self.assertEqual(status.sequence, 44)
        self.assertTrue(status.adxl367_ready)
        self.assertEqual(status.stream_rate_hz, 50)
        self.assertEqual(status.adxl367_range_g, 2)
        self.assertEqual(status.bmi270_accel_range_g, 16)
        self.assertEqual(status.bmi270_gyro_range_dps, 2000)
        self.assertEqual(status.adxl367_clip_count, 3)
        self.assertEqual(status.bmi270_accel_clip_count, 1)
        self.assertEqual(status.bmi270_gyro_clip_count, 2)
        self.assertEqual(status.power_policy, "auto")
        self.assertEqual(status.runtime_state, "idle")
        self.assertEqual(status.power_transition_count, 4)
        self.assertEqual(status.idle_timeout_ms, 30000)
        self.assertEqual(status.wake_poll_ms, 80)
        self.assertEqual(status.advertising_interval_min_ms, 1000)
        self.assertEqual(status.advertising_interval_max_ms, 1200)
        self.assertEqual(status.advertising_start_error_count, 2)
        self.assertEqual(status.power_management_error_count, 0)
        self.assertTrue(status.bmi270_spi_suspended)
        self.assertTrue(status.idle_wake_interrupt_enabled)
        self.assertTrue(status.adxl367_wakeup_mode_enabled)
        self.assertFalse(status.battery_supported)
        self.assertTrue(status.nfc_enabled)
        self.assertEqual(status.nfc_setup_error, 0)
        self.assertEqual(status.nfc_field_on_count, 4)
        self.assertEqual(status.nfc_field_off_count, 3)
        self.assertTrue(status.nfc_field_present)
        self.assertTrue(status.nfc_service_window_active)
        self.assertEqual(status.nfc_service_window_ms, 10000)
        self.assertEqual(status.nfc_service_window_open_count, 2)
        self.assertEqual(status.nfc_service_window_suppressed_count, 1)
        self.assertEqual(status.sensor_health, "healthy")
        self.assertTrue(status.capture_safe)
        self.assertEqual(status.sensor_fault_count, 2)
        self.assertEqual(status.sensor_recovery_generation, 3)
        self.assertEqual(status.sensor_recovery_attempt_count, 4)
        self.assertEqual(status.sensor_recovery_success_count, 1)
        self.assertEqual(status.sensor_recovery_failure_count, 3)
        self.assertEqual(status.last_sensor_error_bits, 1)
        self.assertEqual(status.last_sensor_error_uptime_ms, 4321)
        self.assertEqual(status.sensor_auto_reboot_count, 1)
        self.assertEqual(status.sensor_auto_reboot_fault_bits, 1)
        self.assertTrue(status.sensor_auto_reboot_guard)
        self.assertFalse(status.sensor_auto_reboot_pending)
        self.assertEqual(status.idle_sensor_health_check_ms, 600000)

    def test_old_smp_status_has_no_nfc_claim(self) -> None:
        status = status_from_smp(
            {
                "proto": 1,
                "seq": 1,
                "uptime_ms": 2,
                "reset": 0,
                "sensor_errors": 0,
                "notify_drops": 0,
                "adxl_ready": True,
                "bmi_ready": True,
                "device_id": "0011223344556677",
                "boot_id": "8899aabbccddeeff",
                "fw": "0.1.13",
            }
        )

        self.assertIsNone(status.nfc_enabled)
        self.assertIsNone(status.nfc_setup_error)
        self.assertFalse(status.nfc_service_window_active)
        self.assertEqual(status.nfc_service_window_open_count, 0)
        self.assertIsNone(status.sensor_health)
        self.assertIsNone(status.capture_safe)

    def test_rejects_unknown_power_state(self) -> None:
        payload = {
            "proto": 1,
            "seq": 1,
            "uptime_ms": 2,
            "reset": 0,
            "sensor_errors": 0,
            "notify_drops": 0,
            "adxl_ready": True,
            "bmi_ready": True,
            "device_id": "00",
            "boot_id": "00",
            "fw": "0.1.8",
            "power_policy": "magic",
        }
        with self.assertRaises(TelemetryProtocolError):
            status_from_smp(payload)

    def test_smp_status_rejects_short_boot_id_and_negative_counters(self) -> None:
        payload = {
            "proto": 1,
            "seq": 1,
            "uptime_ms": 2,
            "reset": 0,
            "sensor_errors": 0,
            "notify_drops": 0,
            "adxl_ready": True,
            "bmi_ready": True,
            "device_id": "0011223344556677",
            "boot_id": "00",
            "fw": "0.1.13",
        }
        with self.assertRaisesRegex(TelemetryProtocolError, "exactly 8 bytes"):
            status_from_smp(payload)

        payload["boot_id"] = "8899aabbccddeeff"
        payload["sensor_errors"] = -1
        with self.assertRaisesRegex(TelemetryProtocolError, "non-negative"):
            status_from_smp(payload)

    def test_normalizes_smp_motion(self) -> None:
        payload = {
            "proto": 1,
            "seq": 118,
            "t_us": 10242368,
            "errors": 0,
            "adxl_valid": True,
            "bmi_valid": True,
            "adxl_ax": 1,
            "adxl_ay": 2,
            "adxl_az": 3,
            "bmi_ax": 4,
            "bmi_ay": 5,
            "bmi_az": 6,
            "bmi_gx": 7,
            "bmi_gy": 8,
            "bmi_gz": 9,
        }

        motion = motion_from_smp(payload)

        self.assertEqual(motion.sequence, 118)
        self.assertEqual(motion.bmi270_gyro_micro_rads, (7, 8, 9))

    def test_rejects_malformed_smp_response(self) -> None:
        with self.assertRaises(TelemetryProtocolError):
            status_from_smp({"proto": True})

    def test_decodes_smp_motion_window(self) -> None:
        packets = [
            struct.pack("<BBHIQ9iI", 1, 3, 56, sequence, sequence * 20_000, *range(9), 0)
            for sequence in (10, 11)
        ]
        records = motion_window_from_smp(
            {
                "proto": 1,
                "sample_size": 56,
                "count": 2,
                "start_seq": 10,
                "end_seq": 11,
                "data_hex": b"".join(packets).hex(),
            }
        )

        self.assertEqual([record.sequence for record in records], [10, 11])

    def test_rejects_noncontiguous_smp_motion_window(self) -> None:
        packets = [
            struct.pack("<BBHIQ9iI", 1, 3, 56, sequence, sequence * 20_000, *range(9), 0)
            for sequence in (10, 12)
        ]
        with self.assertRaises(TelemetryProtocolError):
            motion_window_from_smp(
                {
                    "proto": 1,
                    "sample_size": 56,
                    "count": 2,
                    "start_seq": 10,
                    "end_seq": 12,
                    "data_hex": b"".join(packets).hex(),
                }
            )

    def test_reassembles_frozen_history_chunks(self) -> None:
        packets = [
            struct.pack("<BBHIQ9iI", 1, 3, 56, sequence, sequence * 20_000, *range(9), 0)
            for sequence in range(100, 170)
        ]
        metadata = frozen_history_metadata_from_smp(
            {
                "proto": 1,
                "capture_id": 7,
                "sample_size": 56,
                "count": 70,
                "chunk_size": 64,
                "chunk_count": 2,
                "start_seq": 100,
                "end_seq": 169,
            }
        )
        chunks = []
        for chunk_index, chunk_packets in enumerate((packets[:64], packets[64:])):
            chunks.append(
                {
                    "proto": 1,
                    "capture_id": 7,
                    "chunk_index": chunk_index,
                    "sample_size": 56,
                    "count": len(chunk_packets),
                    "start_seq": 100 if chunk_index == 0 else 164,
                    "end_seq": 163 if chunk_index == 0 else 169,
                    "data_hex": b"".join(chunk_packets).hex(),
                }
            )

        records = frozen_history_from_smp(metadata, chunks)

        self.assertEqual(len(records), 70)
        self.assertEqual(records[0].sequence, 100)
        self.assertEqual(records[-1].sequence, 169)

    def test_rejects_frozen_history_capture_id_change(self) -> None:
        metadata = frozen_history_metadata_from_smp(
            {
                "proto": 1,
                "capture_id": 7,
                "sample_size": 56,
                "count": 1,
                "chunk_size": 64,
                "chunk_count": 1,
                "start_seq": 10,
                "end_seq": 10,
            }
        )
        with self.assertRaises(TelemetryProtocolError):
            frozen_history_from_smp(metadata, [{"capture_id": 8}])


if __name__ == "__main__":
    unittest.main()
