from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Iterable

from putttrack.gameplay import Player, SessionState

from .course import CourseDefinition


class CheckInError(ValueError):
    pass


@dataclass(frozen=True)
class BallAsset:
    ball_id: str
    label: str
    color: str
    number: str
    enabled: bool = True


@dataclass(frozen=True)
class PlayerAssignment:
    player_id: str
    display_name: str
    ball_id: str
    ball_label: str
    ball_color: str
    ball_number: str
    account_id: str | None = None


@dataclass
class CheckedInSession:
    session_id: str
    booking_code: str | None
    course_id: str
    assignments: tuple[PlayerAssignment, ...]
    created_at_ms: int
    metadata: dict[str, object] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "booking_code": self.booking_code,
            "course_id": self.course_id,
            "players": [
                {
                    "player_id": assignment.player_id,
                    "display_name": assignment.display_name,
                    "ball_id": assignment.ball_id,
                    "ball_label": assignment.ball_label,
                    "ball_color": assignment.ball_color,
                    "ball_number": assignment.ball_number,
                    "account_linked": assignment.account_id is not None,
                }
                for assignment in self.assignments
            ],
        }


class CheckInService:
    """Guest-first session and Ball assignment authority for the local vertical slice.

    Production persistence belongs to Venue Edge storage. Keeping this boundary
    separate means a later PostgreSQL-backed implementation does not need to
    change Gameplay Engine semantics.
    """

    def __init__(self, course: CourseDefinition, balls: Iterable[BallAsset]) -> None:
        self.course = course
        self._balls = {ball.ball_id: ball for ball in balls if ball.enabled}
        if not self._balls:
            raise CheckInError("at least one enabled Ball is required")
        self._ball_in_use: dict[str, str] = {}
        self._sessions: dict[str, CheckedInSession] = {}
        self._booking_index: dict[str, str] = {}

    @property
    def available_ball_count(self) -> int:
        return len(self._balls) - len(self._ball_in_use)

    def create_session(
        self,
        display_names: Iterable[str],
        *,
        booking_code: str | None = None,
        account_ids: Iterable[str | None] | None = None,
    ) -> CheckedInSession:
        names = [str(name).strip() for name in display_names]
        if not names or any(not name for name in names):
            raise CheckInError("at least one non-empty display name is required")
        if len(names) > self.available_ball_count:
            raise CheckInError("not enough available smart balls")

        normalized_booking = booking_code.strip() if booking_code else None
        if normalized_booking and normalized_booking in self._booking_index:
            raise CheckInError("booking code is already checked in")

        accounts = list(account_ids) if account_ids is not None else [None] * len(names)
        if len(accounts) != len(names):
            raise CheckInError("account_ids must match player count")

        free = [
            ball
            for ball_id, ball in self._balls.items()
            if ball_id not in self._ball_in_use
        ]
        free.sort(key=lambda ball: (ball.number, ball.ball_id))

        session_id = f"ses-{uuid.uuid4().hex[:12]}"
        assignments: list[PlayerAssignment] = []
        for index, (name, account, ball) in enumerate(
            zip(names, accounts, free), start=1
        ):
            player_id = f"{session_id}-p{index:02d}"
            assignment = PlayerAssignment(
                player_id=player_id,
                display_name=name,
                ball_id=ball.ball_id,
                ball_label=ball.label,
                ball_color=ball.color,
                ball_number=ball.number,
                account_id=account,
            )
            assignments.append(assignment)
            self._ball_in_use[ball.ball_id] = session_id

        session = CheckedInSession(
            session_id=session_id,
            booking_code=normalized_booking,
            course_id=self.course.course_id,
            assignments=tuple(assignments),
            created_at_ms=int(time.time() * 1000),
        )
        self._sessions[session_id] = session
        if normalized_booking:
            self._booking_index[normalized_booking] = session_id
        return session

    def lookup(self, code_or_session_id: str) -> CheckedInSession:
        key = str(code_or_session_id).strip()
        session_id = self._booking_index.get(key, key)
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise CheckInError("session/booking not found") from exc

    def release_session(self, session_id: str) -> None:
        session = self.lookup(session_id)
        for assignment in session.assignments:
            self._ball_in_use.pop(assignment.ball_id, None)
        self._sessions.pop(session.session_id, None)
        if session.booking_code:
            self._booking_index.pop(session.booking_code, None)

    def build_gameplay_state(self, session: CheckedInSession) -> SessionState:
        players = {
            assignment.player_id: Player(
                assignment.player_id,
                assignment.display_name,
                assignment.ball_id,
            )
            for assignment in session.assignments
        }
        return SessionState(
            session_id=session.session_id,
            players=players,
            course=list(self.course.holes),
            metadata={
                "course_id": self.course.course_id,
                "booking_code": session.booking_code,
                "ball_labels": {
                    assignment.ball_id: assignment.ball_label
                    for assignment in session.assignments
                },
            },
        )
