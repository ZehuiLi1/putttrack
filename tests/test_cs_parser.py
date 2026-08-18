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

    def test_structured_json_line(self) -> None:
        result = self.parser.parse_line(
            '{"antenna_path":0,"distance_ifft_m":2.1,'
            '"distance_phase_m":2.0,"distance_rtt_m":2.8,'
            '"rssi_dbm":-50,"source_monotonic_ns":123,"sequence":7,'
            '"procedure_id":"p-1","quality":{"tone":0.9}}'
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source_sequence, 7)
        self.assertEqual(result.source_monotonic_ns, 123)
        self.assertEqual(result.procedure_id, "p-1")
        self.assertEqual(result.quality["timestamp_origin"], "device")

    def test_non_data_log_line_is_ignored(self) -> None:
        self.assertIsNone(self.parser.parse_line("Ranging data ready"))

    def test_malformed_structured_data_fails_explicitly(self) -> None:
        with self.assertRaises(CsParseError):
            self.parser.parse_line('{"distance_ifft_m":"bad"}')


if __name__ == "__main__":
    unittest.main()
