import json
import unittest

from tools.prepare_tag_migration import send_migration_command, wait_for_expected_tag


DEVICE_ID = "4d53cd7b5c288607"
NONCE = "0123456789abcdef0123456789abcdef"


def tag_event(device_id: str = DEVICE_ID) -> dict:
    return {
        "event": "nfc_tag",
        "uid": "01020304",
        "ndef_ok": True,
        "service_uri_ok": True,
        "ndef_uri": f"putttrack://service/tag/{device_id}?fw=0.2.6",
        "device_id": device_id,
        "firmware_version": "0.2.6",
        "type4": True,
    }


class FakeSerial:
    def __init__(self, events: list[dict]) -> None:
        self.events = iter(events)
        self.writes: list[bytes] = []
        self.flush_count = 0

    def readline(self) -> bytes:
        try:
            return (json.dumps(next(self.events)) + "\n").encode()
        except StopIteration:
            return b""

    def write(self, value: bytes) -> int:
        self.writes.append(value)
        return len(value)

    def flush(self) -> None:
        self.flush_count += 1


class PrepareTagMigrationTests(unittest.TestCase):
    def test_sends_one_identity_locked_command(self) -> None:
        connection = FakeSerial([
            {"event": "scan_miss"},
            {
                "event": "nfc_migration_command",
                "accepted": True,
                "device_id": DEVICE_ID,
                "nonce": NONCE,
            },
        ])

        result = send_migration_command(connection, DEVICE_ID, NONCE, 10**12)

        self.assertTrue(result["accepted"])
        self.assertEqual(connection.writes, [
            f"nfc migrate {DEVICE_ID} {NONCE}\n".encode("ascii")
        ])
        self.assertEqual(connection.flush_count, 1)

    def test_rejects_reader_write_failure(self) -> None:
        connection = FakeSerial([{
            "event": "nfc_migration_command",
            "accepted": False,
            "device_id": DEVICE_ID,
            "nonce": NONCE,
            "reason": "type4_write_failed",
        }])
        with self.assertRaisesRegex(RuntimeError, "type4_write_failed"):
            send_migration_command(connection, DEVICE_ID, NONCE, 10**12)

    def test_rejects_another_ball(self) -> None:
        connection = FakeSerial([tag_event("f383571202836e6f")])
        with self.assertRaisesRegex(RuntimeError, "读到其他小球"):
            wait_for_expected_tag(connection, DEVICE_ID, 10**12)


if __name__ == "__main__":
    unittest.main()

class IncompleteTouchTests(unittest.TestCase):
    def test_waits_for_full_ndef_before_authorizing_write(self):
        connection = FakeSerial([
            {'event':'nfc_tag','uid':'01020304','ndef_ok':False,'ndef_error':'type4_ndef_unreadable'},
            tag_event(),
        ])
        self.assertEqual(wait_for_expected_tag(connection,DEVICE_ID,10**12)['device_id'],DEVICE_ID)
        self.assertEqual(connection.writes,[])
