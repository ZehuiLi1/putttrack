from __future__ import annotations

import unittest

from putttrack.cs import CsParseError, CsSerialParser


class CsParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = CsSerialParser()

    def test_vendor_distance_line(self) -> None:
        result = self.parser.parse_line(
            "Distance estimates on antenna path 1: ifft: 1.234, "
            "phase_slope: 1.111, rtt: 1.900"
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.antenna_path, 1)
        self.assertAlmostEqual(result.distance_ifft_m or 0, 1.234)
        self.assertEqual(result.quality["parser"], "bbo_vendor_text_v1")
        self.assertIsNone(result.source_boot_id)
        self.assertIsNone(result.source_device_id)
        self.assertEqual(result.quality["boot_id_origin"], "capture_run_fallback")
        self.assertEqual(result.quality["device_id_origin"], "capture_cli_fallback")

    def test_structured_json_line(self) -> None:
        result = self.parser.parse_line(
            '{"source_device_id":"A","antenna_path":0,"distance_ifft_m":2.1,'
            '"distance_phase_m":2.0,"distance_rtt_m":2.8,'
            '"rssi_dbm":-50,"source_monotonic_ns":123,"sequence":7,'
            '"source_boot_id":"boot-a1b2","procedure_id":"p-1",'
            '"quality":{"tone":0.9}}'
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source_sequence, 7)
        self.assertEqual(result.source_monotonic_ns, 123)
        self.assertEqual(result.source_boot_id, "boot-a1b2")
        self.assertEqual(result.source_device_id, "A")
        self.assertEqual(result.procedure_id, "p-1")
        self.assertEqual(result.quality["timestamp_origin"], "device")
        self.assertEqual(result.quality["boot_id_origin"], "device")
        self.assertEqual(result.quality["device_id_origin"], "device")

    def test_identity_aliases_are_supported(self) -> None:
        result = self.parser.parse_line(
            '{"ifft":1.2,"timestamp_ns":50,"source_sequence":2,'
            '"boot_id":"boot-alias","device_id":"A"}'
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source_boot_id, "boot-alias")
        self.assertEqual(result.source_device_id, "A")
        self.assertEqual(result.source_sequence, 2)

    def test_empty_boot_id_fails_explicitly(self) -> None:
        with self.assertRaises(CsParseError):
            self.parser.parse_line('{"ifft":1.2,"source_boot_id":""}')

    def test_empty_device_id_fails_explicitly(self) -> None:
        with self.assertRaises(CsParseError):
            self.parser.parse_line('{"ifft":1.2,"source_device_id":""}')

    def test_non_data_log_line_is_ignored(self) -> None:
        self.assertIsNone(self.parser.parse_line("Ranging data ready"))

    def test_malformed_structured_data_fails_explicitly(self) -> None:
        with self.assertRaises(CsParseError):
            self.parser.parse_line('{"distance_ifft_m":"bad"}')


if __name__ == "__main__":
    unittest.main()
