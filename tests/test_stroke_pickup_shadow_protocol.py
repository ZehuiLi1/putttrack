import copy, unittest
from putttrack.tag.stroke_pickup_shadow import EVENT, decode_snapshot, summarize_episode


class ShadowProtocol(unittest.TestCase):
    def payload(self, events=()):
        ids = [e[0] for e in events]
        latest = max(ids, default=0)
        return dict(
            algorithm_id="stroke_pickup_shadow_v1",
            config_sha256="f" * 64,
            firmware_version="0.1.19",
            device_id="12" * 8,
            boot_id="34" * 8,
            authority=False,
            candidate_only=True,
            stream_hz=50,
            generation=1,
            sensor_recovery_generation=0,
            source_seq=300,
            source_us=9000000,
            state=1,
            armed=True,
            held_hint=False,
            count_incomplete=False,
            stroke_candidates=0,
            pickup_candidates=0,
            ambiguous_contacts=0,
            unknown_onsets=0,
            quality_breaks=0,
            quality_flags=0,
            first_event_id=min(ids, default=0),
            latest_event_id=latest,
            overwritten_events=max(0, latest - 16),
            event_size=64,
            event_count=len(events),
            events_hex=b"".join(EVENT.pack(*e) for e in events).hex(),
        )

    def event(self, id=1, type=1, onset=1000000, decision=2000000):
        return (
            id,
            type,
            0,
            0,
            50,
            100,
            onset,
            decision,
            0,
            20000,
            1000,
            1000,
            10000,
            0,
        )

    def decode(self, p, **kw):
        return decode_snapshot(
            p, device_id="12" * 8, config_sha256="f" * 64, boot_id="34" * 8, **kw
        )

    def test_valid(self):
        self.assertFalse(self.decode(self.payload())["score_authoritative"])

    def test_wire_size(self):
        self.assertEqual(EVENT.size, 64)

    def test_pending_not_counted(self):
        s = self.decode(self.payload([self.event(type=6)]))
        r = summarize_episode(s, go_us=0, end_us=8000000)
        self.assertEqual(r["stroke_candidate_count"], 0)
        self.assertEqual(r["count_status"], "UNRESOLVED")

    def test_pending_resolved(self):
        s = self.decode(
            self.payload(
                [self.event(type=6), self.event(id=2, type=1, decision=2500000)]
            )
        )
        r = summarize_episode(s, go_us=0, end_us=8000000)
        self.assertEqual(r["stroke_candidate_count"], 1)
        self.assertEqual(r["pending_without_final"], 0)
        self.assertIsNone(r["confirmed_stroke_count"])

    def test_pickup_not_cheating(self):
        s = self.decode(self.payload([self.event(type=2)]))
        r = summarize_episode(s, go_us=0, end_us=8000000)
        self.assertEqual(r["pickup_suspected_count"], 1)
        self.assertFalse(r["cheating_confirmed"])

    def test_wrong_id(self):
        p = self.payload()
        p["device_id"] = "56" * 8
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_wrong_hash(self):
        p = self.payload()
        p["config_sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_wrong_version(self):
        p = self.payload()
        p["firmware_version"] = "0.1.18"
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_wrong_boot(self):
        p = self.payload()
        p["boot_id"] = "ff" * 8
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_bad_generation(self):
        with self.assertRaises(ValueError):
            self.decode(self.payload(), generation=2)

    def test_authority_rejected(self):
        p = self.payload()
        p["authority"] = True
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_bool_not_counter(self):
        p = self.payload()
        p["stroke_candidates"] = True
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_counter_regression(self):
        with self.assertRaises(ValueError):
            self.decode(self.payload(), previous_latest=3)

    def test_malformed_hex(self):
        p = self.payload([self.event()])
        p["events_hex"] = "00"
        with self.assertRaises(ValueError):
            self.decode(p)

    def test_unknown_event(self):
        with self.assertRaises(ValueError):
            self.decode(self.payload([self.event(type=99)]))

    def test_future_event(self):
        with self.assertRaises(ValueError):
            self.decode(self.payload([self.event(decision=99999999)]))

    def test_event_gap_loss_visible(self):
        p = self.payload([self.event(id=i) for i in range(3, 19)])
        s = self.decode(p, previous_latest=0)
        self.assertTrue(s["journal_loss"])
        self.assertEqual(
            summarize_episode(s, go_us=0, end_us=8000000)["count_status"],
            "INCOMPLETE_LOG",
        )

    def test_duplicate_snapshot_keys_idempotent(self):
        p = self.payload([self.event()])
        keys = {e["event_key"] for e in self.decode(p)["events"]}
        keys.update(e["event_key"] for e in self.decode(p)["events"])
        self.assertEqual(len(keys), 1)

    def test_post_episode_event_excluded(self):
        s = self.decode(self.payload([self.event(onset=3000000, decision=4000000)]))
        self.assertEqual(
            summarize_episode(s, go_us=0, end_us=2500000)["stroke_candidate_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
