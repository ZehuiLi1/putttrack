from __future__ import annotations

from dataclasses import replace
import unittest

from putttrack.service import (
    ReleaseArtifact,
    ServiceDisposition,
    ServicePolicyTarget,
    ServiceTouchError,
    parse_nfc_reader_event,
    plan_nfc_service,
)


def reader_event() -> dict[str, object]:
    return {
        "event": "nfc_tag",
        "uid": "04A1B2C3D4E5F6",
        "consecutive_reads": 3,
        "ndef_ok": True,
        "service_uri_ok": True,
        "ndef_uri": "putttrack://service/tag/0123456789ABCDEF?fw=0.1.13",
        "device_id": "0123456789abcdef",
        "firmware_version": "0.1.13",
    }


class NfcServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.touch = parse_nfc_reader_event(reader_event())
        self.target = ServicePolicyTarget(
            device_id="0123456789abcdef",
            hardware_revision="pca20072-1.0.0",
            desired_firmware_version="0.1.15",
        )
        self.release = ReleaseArtifact(
            firmware_version="0.1.15",
            compatible_hardware_revisions=("pca20072-1.0.0",),
            image_sha256="a" * 64,
            release_authorized=True,
        )

    def test_parses_and_cross_checks_reader_event(self) -> None:
        self.assertEqual(self.touch.device_id, "0123456789abcdef")
        self.assertEqual(self.touch.firmware_version, "0.1.13")
        self.assertEqual(self.touch.consecutive_reads, 3)

    def test_rejects_nonservice_and_mismatched_redundant_identity(self) -> None:
        event = reader_event()
        event["service_uri_ok"] = False
        with self.assertRaises(ServiceTouchError):
            parse_nfc_reader_event(event)

        event = reader_event()
        event["device_id"] = "ffeeddccbbaa9988"
        with self.assertRaisesRegex(ServiceTouchError, "does not match"):
            parse_nfc_reader_event(event)

    def test_rejects_query_confusion_and_version_mismatch(self) -> None:
        event = reader_event()
        event["ndef_uri"] = (
            "putttrack://service/tag/0123456789abcdef?fw=0.1.13&fw=0.1.15"
        )
        with self.assertRaises(ServiceTouchError):
            parse_nfc_reader_event(event)

        event = reader_event()
        event["firmware_version"] = "0.1.15"
        with self.assertRaisesRegex(ServiceTouchError, "does not match"):
            parse_nfc_reader_event(event)

    def test_offers_only_authorized_compatible_upgrade(self) -> None:
        decision = plan_nfc_service(self.touch, self.target, self.release)
        self.assertEqual(decision.disposition, ServiceDisposition.OFFER_SIGNED_UPDATE)
        self.assertEqual(decision.image_sha256, "a" * 64)

    def test_current_version_needs_no_release_or_connection(self) -> None:
        target = replace(self.target, desired_firmware_version="0.1.13")
        decision = plan_nfc_service(self.touch, target, None)
        self.assertEqual(decision.disposition, ServiceDisposition.NO_UPDATE)
        self.assertEqual(decision.reason, "already_current")

    def test_rejects_unknown_active_quarantined_and_downgrade(self) -> None:
        cases = (
            (None, "unknown_device"),
            (replace(self.target, active_session=True), "active_session"),
            (
                replace(self.target, quarantined=True),
                "quarantined_requires_explicit_recovery",
            ),
            (replace(self.target, desired_firmware_version="0.1.12"), "downgrade_not_allowed"),
        )
        for target, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(plan_nfc_service(self.touch, target, self.release).reason, reason)

    def test_rejects_unapproved_or_incompatible_release(self) -> None:
        cases = (
            (replace(self.release, release_authorized=False), "release_not_authorized"),
            (
                replace(self.release, compatible_hardware_revisions=("other",)),
                "hardware_incompatible",
            ),
            (replace(self.release, image_sha256="bad"), "invalid_release_digest"),
        )
        for release, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(plan_nfc_service(self.touch, self.target, release).reason, reason)

    def test_invalid_inventory_version_fails_closed(self) -> None:
        target = replace(self.target, desired_firmware_version="latest")
        decision = plan_nfc_service(self.touch, target, self.release)
        self.assertEqual(decision.disposition, ServiceDisposition.REJECT)
        self.assertEqual(decision.reason, "invalid_inventory_firmware_version")
