"""Advisory NFC-to-BLE service planning; this module never performs OTA."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hmac
from typing import Any, Mapping
from urllib.parse import urlsplit

from putttrack.tag import TagIdentityError, normalize_device_id


class ServiceTouchError(ValueError):
    """Raised when reader output cannot establish a valid service touch."""


def _firmware_version(value: Any, *, field: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not 1 <= len(value) <= 8:
        raise ServiceTouchError(f"{field} must be 1..8 characters")
    parts = value.split(".")
    if not 1 <= len(parts) <= 4 or any(
        not part or any(ch < "0" or ch > "9" for ch in part) for part in parts
    ):
        raise ServiceTouchError(f"{field} must be a numeric dotted version")
    return tuple(int(part) for part in parts)


def _comparable_version(value: str, *, field: str) -> tuple[int, int, int, int]:
    parts = _firmware_version(value, field=field)
    return (*parts, *(0 for _ in range(4 - len(parts))))


@dataclass(frozen=True)
class NfcServiceTouch:
    device_id: str
    firmware_version: str
    service_uri: str
    rf_uid: str | None
    consecutive_reads: int


def parse_nfc_reader_event(payload: Mapping[str, Any]) -> NfcServiceTouch:
    """Validate redundant URI/JSON identity before any inventory lookup."""

    if payload.get("event") != "nfc_tag":
        raise ServiceTouchError("reader event must be 'nfc_tag'")
    if payload.get("ndef_ok") is not True or payload.get("service_uri_ok") is not True:
        raise ServiceTouchError("reader did not report a valid PuttTrack service URI")

    uri = payload.get("ndef_uri")
    if not isinstance(uri, str) or not uri:
        raise ServiceTouchError("reader event is missing ndef_uri")
    try:
        parsed = urlsplit(uri)
    except ValueError as exc:
        raise ServiceTouchError("NDEF URI is malformed") from exc
    if (
        parsed.scheme != "putttrack"
        or parsed.netloc != "service"
        or parsed.fragment
        or not parsed.path.startswith("/tag/")
        or "/" in parsed.path[len("/tag/") :]
    ):
        raise ServiceTouchError("NDEF URI is not the canonical PuttTrack service URI")
    try:
        uri_device_id = normalize_device_id(parsed.path[len("/tag/") :])
        event_device_id = normalize_device_id(str(payload.get("device_id", "")))
    except TagIdentityError as exc:
        raise ServiceTouchError(str(exc)) from exc
    if not hmac.compare_digest(uri_device_id, event_device_id):
        raise ServiceTouchError("reader device_id does not match NDEF URI")

    if not parsed.query.startswith("fw=") or "&" in parsed.query:
        raise ServiceTouchError("NDEF URI must contain exactly one fw parameter")
    uri_firmware = parsed.query[len("fw=") :]
    event_firmware = payload.get("firmware_version")
    _firmware_version(uri_firmware, field="NDEF firmware version")
    _firmware_version(event_firmware, field="reader firmware_version")
    if not hmac.compare_digest(uri_firmware, event_firmware):
        raise ServiceTouchError("reader firmware_version does not match NDEF URI")

    consecutive_reads = payload.get("consecutive_reads", 1)
    if isinstance(consecutive_reads, bool) or not isinstance(consecutive_reads, int):
        raise ServiceTouchError("consecutive_reads must be an integer")
    if consecutive_reads < 1:
        raise ServiceTouchError("consecutive_reads must be positive")
    rf_uid = payload.get("uid")
    if rf_uid is not None and (not isinstance(rf_uid, str) or not rf_uid):
        raise ServiceTouchError("uid must be non-empty text when supplied")

    return NfcServiceTouch(
        device_id=uri_device_id,
        firmware_version=uri_firmware,
        service_uri=uri,
        rf_uid=rf_uid,
        consecutive_reads=consecutive_reads,
    )


class ServiceDisposition(str, Enum):
    REJECT = "reject"
    NO_UPDATE = "no_update"
    OFFER_SIGNED_UPDATE = "offer_signed_update"


@dataclass(frozen=True)
class ServicePolicyTarget:
    device_id: str
    hardware_revision: str
    desired_firmware_version: str
    service_enabled: bool = True
    active_session: bool = False
    quarantined: bool = False


@dataclass(frozen=True)
class ReleaseArtifact:
    firmware_version: str
    compatible_hardware_revisions: tuple[str, ...]
    image_sha256: str
    release_authorized: bool


@dataclass(frozen=True)
class ServiceDecision:
    disposition: ServiceDisposition
    reason: str
    device_id: str
    current_firmware_version: str
    desired_firmware_version: str | None
    image_sha256: str | None = None


def _reject(touch: NfcServiceTouch, reason: str) -> ServiceDecision:
    return ServiceDecision(
        disposition=ServiceDisposition.REJECT,
        reason=reason,
        device_id=touch.device_id,
        current_firmware_version=touch.firmware_version,
        desired_firmware_version=None,
    )


def plan_nfc_service(
    touch: NfcServiceTouch,
    target: ServicePolicyTarget | None,
    release: ReleaseArtifact | None,
) -> ServiceDecision:
    """Return an advisory plan; BLE authorization and MCUboot still enforce OTA."""

    if target is None:
        return _reject(touch, "unknown_device")
    try:
        target_device_id = normalize_device_id(target.device_id)
    except TagIdentityError:
        return _reject(touch, "invalid_inventory_device_id")
    if not hmac.compare_digest(touch.device_id, target_device_id):
        return _reject(touch, "inventory_device_mismatch")
    if target.service_enabled is not True:
        return _reject(touch, "service_disabled")
    if target.active_session:
        return _reject(touch, "active_session")
    if target.quarantined:
        return _reject(touch, "quarantined_requires_explicit_recovery")

    try:
        current = _comparable_version(
            touch.firmware_version, field="current firmware"
        )
        desired = _comparable_version(
            target.desired_firmware_version, field="desired firmware"
        )
    except ServiceTouchError:
        return _reject(touch, "invalid_inventory_firmware_version")
    if desired == current:
        return ServiceDecision(
            disposition=ServiceDisposition.NO_UPDATE,
            reason="already_current",
            device_id=touch.device_id,
            current_firmware_version=touch.firmware_version,
            desired_firmware_version=target.desired_firmware_version,
        )
    if desired < current:
        return _reject(touch, "downgrade_not_allowed")
    if release is None:
        return _reject(touch, "release_missing")
    if release.firmware_version != target.desired_firmware_version:
        return _reject(touch, "release_version_mismatch")
    _firmware_version(release.firmware_version, field="release firmware")
    if (
        not isinstance(release.compatible_hardware_revisions, tuple)
        or not isinstance(target.hardware_revision, str)
        or not target.hardware_revision
        or target.hardware_revision not in release.compatible_hardware_revisions
    ):
        return _reject(touch, "hardware_incompatible")
    if release.release_authorized is not True:
        return _reject(touch, "release_not_authorized")
    digest = release.image_sha256.lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        return _reject(touch, "invalid_release_digest")

    return ServiceDecision(
        disposition=ServiceDisposition.OFFER_SIGNED_UPDATE,
        reason="eligible",
        device_id=touch.device_id,
        current_firmware_version=touch.firmware_version,
        desired_firmware_version=target.desired_firmware_version,
        image_sha256=digest,
    )
