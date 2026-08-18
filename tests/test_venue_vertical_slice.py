from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from putttrack.gameplay import EventType, GameplayEvent
from putttrack.venue import (
    BallAsset,
    CheckInError,
    CheckInService,
    LocalRoundRuntime,
    VenueApplication,
    build_server,
    course_from_dict,
)
from putttrack.venue.web import TEE_SCREEN_HTML


COURSE = {
    "course_id": "demo",
    "title": "Demo",
    "holes": [
        {
            "hole_id": "H01",
            "number": 1,
            "title": "Risk Ridge",
            "instructions": "Precision Gate +25",
            "score_curve": {"1": 100, "2": 80, "3": 65},
            "features": [
                {
                    "feature_id": "precision_gate",
                    "label": "Precision Gate",
                    "kind": "bonus",
                    "points_delta": 25,
                }
            ],
        }
    ],
}
BALLS = [
    BallAsset("b1", "Blue 07", "blue", "07"),
    BallAsset("b2", "Orange 12", "orange", "12"),
    BallAsset("b3", "Purple 03", "purple", "03"),
]


class CourseTests(unittest.TestCase):
    def test_course_loader_and_feature(self) -> None:
        course = course_from_dict(COURSE)
        self.assertEqual(course.holes[0].features["precision_gate"].points_delta, 25)

    def test_duplicate_hole_rejected(self) -> None:
        bad = dict(COURSE)
        bad["holes"] = COURSE["holes"] * 2
        with self.assertRaises(Exception):
            course_from_dict(bad)


class SessionTests(unittest.TestCase):
    def test_guest_first_unique_assignment_and_booking_lookup(self) -> None:
        service = CheckInService(course_from_dict(COURSE), BALLS)
        session = service.create_session(["Alex", "Sam"], booking_code="BOOK-1")
        self.assertEqual(len({item.ball_id for item in session.assignments}), 2)
        self.assertFalse(session.to_public_dict()["players"][0]["account_linked"])
        self.assertEqual(service.lookup("BOOK-1").session_id, session.session_id)

    def test_ball_pool_capacity(self) -> None:
        service = CheckInService(course_from_dict(COURSE), BALLS[:1])
        with self.assertRaises(CheckInError):
            service.create_session(["A", "B"])


class RuntimeTests(unittest.TestCase):
    def make_runtime(self, temp_dir: str):
        service = CheckInService(course_from_dict(COURSE), BALLS)
        session = service.create_session(["Alex", "Sam"])
        return (
            LocalRoundRuntime(
                service.build_gameplay_state(session),
                audit_path=Path(temp_dir) / "audit.jsonl",
            ),
            session,
        )

    def test_detected_then_ready_and_flexible_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, session = self.make_runtime(temp_dir)
            sam = session.assignments[1]
            runtime.present_ball(
                sam.ball_id,
                event_id="tee-1",
                timestamp_ms=1000,
            )
            events = runtime.broker.after(0)
            self.assertEqual(
                [event.kind for event in events[:2]],
                ["ball_detected", "player_ready"],
            )
            self.assertEqual(runtime.presentation()["active_player"]["display_name"], "Sam")
            self.assertEqual(runtime.presentation()["cue"]["state"], "READY")

    def test_wrong_ball_gives_self_recovery_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, _ = self.make_runtime(temp_dir)
            with self.assertRaises(Exception):
                runtime.present_ball(
                    "wrong",
                    event_id="tee-x",
                    timestamp_ms=1,
                )
            self.assertEqual(runtime.broker.after(0)[-1].kind, "wrong_ball")

    def test_duplicate_event_does_not_double_score_and_audit_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, session = self.make_runtime(temp_dir)
            ball_id = session.assignments[0].ball_id
            runtime.present_ball(ball_id, event_id="tee", timestamp_ms=1)
            event = GameplayEvent(
                event_id="stroke",
                event_type=EventType.STROKE_CONFIRMED,
                timestamp_ms=2,
                hole_id="H01",
                ball_id=ball_id,
            )
            runtime.process_gameplay(event)
            runtime.process_gameplay(event)
            player_id = session.assignments[0].player_id
            self.assertEqual(runtime.state.stats[player_id].total_strokes, 1)
            audit = Path(temp_dir) / "audit.jsonl"
            self.assertTrue(audit.exists())
            self.assertGreater(len(audit.read_text().splitlines()), 1)


class PresentationSecurityTests(unittest.TestCase):
    def test_dynamic_player_and_ball_content_uses_text_content_not_inner_html(self) -> None:
        self.assertNotIn("innerHTML", TEE_SCREEN_HTML)
        self.assertIn("textContent", TEE_SCREEN_HTML)
        self.assertIn("createElement", TEE_SCREEN_HTML)


class HttpTests(unittest.TestCase):
    @staticmethod
    def request(port: int, method: str, path: str, data=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        body = None if data is None else json.dumps(data)
        headers = {"content-type": "application/json"} if body else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        status = response.status
        content_type = response.getheader("content-type", "")
        connection.close()
        if not payload:
            return status, None
        if "application/json" in content_type:
            return status, json.loads(payload)
        return status, payload.decode("utf-8")

    def test_end_to_end_one_hole_http(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = VenueApplication(
                course_from_dict(COURSE),
                BALLS,
                run_root=temp_dir,
            )
            server = build_server(app, "127.0.0.1", 0)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, session = self.request(
                    port,
                    "POST",
                    "/api/checkin",
                    {"players": ["Alex", "Sam"], "booking_code": "Q1"},
                )
                self.assertEqual(status, 201)
                self.assertEqual(
                    self.request(port, "GET", "/api/session?code=Q1")[1]["session_id"],
                    session["session_id"],
                )
                ball_id = session["players"][1]["ball_id"]
                self.assertEqual(
                    self.request(port, "POST", "/api/sim/tee", {"ball_id": ball_id})[0],
                    200,
                )
                self.assertEqual(
                    self.request(
                        port,
                        "POST",
                        "/api/operator/adjust",
                        {"ball_id": ball_id, "points_delta": 5, "reason": ""},
                    )[0],
                    409,
                )
                self.assertEqual(
                    self.request(
                        port,
                        "POST",
                        "/api/operator/adjust",
                        {
                            "ball_id": ball_id,
                            "points_delta": 5,
                            "reason": "verified demo correction",
                        },
                    )[0],
                    200,
                )
                self.assertEqual(
                    self.request(port, "POST", "/api/sim/stroke", {})[0],
                    200,
                )
                self.assertEqual(
                    self.request(
                        port,
                        "POST",
                        "/api/sim/feature",
                        {"feature_id": "precision_gate"},
                    )[0],
                    200,
                )
                self.assertEqual(
                    self.request(port, "POST", "/api/sim/cup", {})[0],
                    200,
                )
                state = self.request(port, "GET", "/api/state")[1]
                self.assertEqual(state["ranking"][0]["display_name"], "Sam")
                self.assertEqual(state["ranking"][0]["points"], 130)
                audit_files = list(Path(temp_dir).glob("*/round_audit.jsonl"))
                self.assertEqual(len(audit_files), 1)
                self.assertIn("verified demo correction", audit_files[0].read_text())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
