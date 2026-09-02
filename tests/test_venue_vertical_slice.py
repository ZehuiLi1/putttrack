from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from putttrack.contracts import (
    MotionObservation,
    PhysicalSensorObservation,
    record_to_dict,
)
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

    def test_motion_impact_stays_pending_and_cannot_increment_strokes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, session = self.make_runtime(temp_dir)
            assignment = session.assignments[0]
            runtime.present_ball(
                assignment.ball_id,
                event_id="tee-motion",
                timestamp_ms=1000,
            )
            motion = MotionObservation(
                event_id="motion-impact-1",
                event_type="ball.motion_observed",
                source_device_id="tag-hardware-1",
                source_boot_id="boot-1",
                sequence=20,
                source_monotonic_ns=2_000_000_000,
                edge_received_ns=2_010_000_000,
                trace_id="trace-motion-1",
                hole_id="H01",
                ball_id=assignment.ball_id,
                firmware_version="0.1.5",
                model_version="motion-v0",
                raw_evidence_refs=("runs/impact-001.jsonl",),
                motion_state="IMPACT_CANDIDATE",
                confidence=0.8,
                raw_window_ref="runs/impact-001.jsonl",
            )

            decision = runtime.process_motion_observation(motion)
            repeated = runtime.process_motion_observation(motion)

            self.assertEqual(decision.status, "pending")
            self.assertEqual(decision.candidate_type, "stroke.candidate")
            self.assertIs(decision, repeated)
            self.assertEqual(runtime.state.stats[assignment.player_id].total_strokes, 0)
            self.assertEqual(runtime.presentation()["cue"]["state"], "READY")
            self.assertEqual(runtime.broker.after(0)[-1].kind, "evidence_pending")
            audit_lines = (Path(temp_dir) / "audit.jsonl").read_text().splitlines()
            self.assertEqual(
                sum("motion_candidate_decision" in line for line in audit_lines),
                1,
            )

    def test_physical_tee_and_two_stage_cup_complete_one_hole(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, session = self.make_runtime(temp_dir)
            assignment = session.assignments[0]

            tee = self.physical_observation(
                "physical-tee-1",
                sensor_kind="tee_presence",
                transition="occupied",
                source_device_id="tee-node",
                ball_id=assignment.ball_id,
                edge_received_ns=1_000_000_000,
            )
            tee_decision = runtime.process_physical_sensor_observation(tee)
            self.assertEqual(tee_decision.status, "accepted")
            self.assertEqual(runtime.presentation()["cue"]["state"], "READY")

            runtime.process_gameplay(
                GameplayEvent(
                    event_id="independent-stroke-1",
                    event_type=EventType.STROKE_CONFIRMED,
                    timestamp_ms=1_500,
                    hole_id="H01",
                    ball_id=assignment.ball_id,
                )
            )
            entry = self.physical_observation(
                "physical-cup-entry-1",
                sensor_kind="cup_entry",
                transition="entered",
                source_device_id="cup-entry-node",
                ball_id=assignment.ball_id,
                edge_received_ns=2_000_000_000,
            )
            presence = self.physical_observation(
                "physical-cup-presence-1",
                sensor_kind="cup_presence",
                transition="occupied",
                source_device_id="cup-presence-node",
                ball_id=assignment.ball_id,
                edge_received_ns=2_400_000_000,
            )
            self.assertEqual(
                runtime.process_physical_sensor_observation(entry).status,
                "pending",
            )
            cup_decision = runtime.process_physical_sensor_observation(presence)
            repeated = runtime.process_physical_sensor_observation(presence)

            self.assertEqual(cup_decision.status, "accepted")
            self.assertIs(repeated, cup_decision)
            self.assertEqual(
                runtime.state.stats[assignment.player_id].total_strokes,
                1,
            )
            self.assertEqual(
                runtime.state.current_runtime.players[assignment.player_id].status.value,
                "complete",
            )
            self.assertEqual(runtime.state.status.value, "active")
            audit_lines = (Path(temp_dir) / "audit.jsonl").read_text().splitlines()
            self.assertEqual(
                sum("physical_sensor_decision" in line for line in audit_lines),
                3,
            )

    @staticmethod
    def physical_observation(
        event_id: str,
        *,
        sensor_kind: str,
        transition: str,
        source_device_id: str,
        ball_id: str,
        edge_received_ns: int,
    ) -> PhysicalSensorObservation:
        return PhysicalSensorObservation(
            event_id=event_id,
            event_type="sensor.edge_observed",
            source_device_id=source_device_id,
            source_boot_id="boot-1",
            sequence=1,
            source_monotonic_ns=edge_received_ns - 1_000_000,
            edge_received_ns=edge_received_ns,
            trace_id=f"trace-{event_id}",
            hole_id="H01",
            ball_id=ball_id,
            sensor_id=f"sensor-{source_device_id}",
            sensor_kind=sensor_kind,
            transition=transition,
            value=True,
            health="ok",
            debounce_version="debounce-v1",
        )


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
                motion = MotionObservation(
                    event_id="http-motion-impact-1",
                    event_type="ball.motion_observed",
                    source_device_id="tag-http-1",
                    source_boot_id="boot-http-1",
                    sequence=1,
                    source_monotonic_ns=100,
                    edge_received_ns=200,
                    trace_id="trace-http-motion",
                    hole_id="H01",
                    ball_id=ball_id,
                    firmware_version="0.1.5",
                    model_version="motion-v0",
                    motion_state="IMPACT_CANDIDATE",
                    confidence=0.8,
                )
                motion_status, motion_result = self.request(
                    port,
                    "POST",
                    "/api/evidence/motion",
                    record_to_dict(motion),
                )
                self.assertEqual(motion_status, 202)
                self.assertEqual(motion_result["decision"]["status"], "pending")
                self.assertEqual(
                    motion_result["state"]["player_hole_state"][
                        session["players"][1]["player_id"]
                    ]["strokes"],
                    0,
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

    def test_physical_evidence_http_ingress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = VenueApplication(course_from_dict(COURSE), BALLS, run_root=temp_dir)
            server = build_server(app, "127.0.0.1", 0)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                _, session = self.request(
                    port,
                    "POST",
                    "/api/checkin",
                    {"players": ["Alex"]},
                )
                ball_id = session["players"][0]["ball_id"]
                tee = RuntimeTests.physical_observation(
                    "http-physical-tee",
                    sensor_kind="tee_presence",
                    transition="occupied",
                    source_device_id="http-tee-node",
                    ball_id=ball_id,
                    edge_received_ns=1_000_000_000,
                )
                status, response = self.request(
                    port,
                    "POST",
                    "/api/evidence/physical",
                    record_to_dict(tee),
                )
                self.assertEqual(status, 202)
                self.assertEqual(response["decision"]["status"], "accepted")
                self.assertEqual(response["state"]["cue"]["state"], "READY")

                self.assertEqual(
                    self.request(port, "POST", "/api/sim/stroke", {})[0],
                    200,
                )
                for event in (
                    RuntimeTests.physical_observation(
                        "http-cup-entry",
                        sensor_kind="cup_entry",
                        transition="entered",
                        source_device_id="http-cup-entry-node",
                        ball_id=ball_id,
                        edge_received_ns=2_000_000_000,
                    ),
                    RuntimeTests.physical_observation(
                        "http-cup-presence",
                        sensor_kind="cup_presence",
                        transition="occupied",
                        source_device_id="http-cup-presence-node",
                        ball_id=ball_id,
                        edge_received_ns=2_500_000_000,
                    ),
                ):
                    status, response = self.request(
                        port,
                        "POST",
                        "/api/evidence/physical",
                        record_to_dict(event),
                    )
                    self.assertEqual(status, 202)
                self.assertEqual(response["decision"]["status"], "accepted")
                self.assertEqual(response["state"]["session_status"], "complete")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
