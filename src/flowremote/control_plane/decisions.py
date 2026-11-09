"""Atomic review decisions shared by HTML forms and offline sync."""

from __future__ import annotations

import json
from dataclasses import dataclass

from flowremote.agent.service import accepted_changes
from flowremote.contracts.enums import Role
from flowremote.contracts.models import ExceptionItem, User
from flowremote.control_plane.activity import log_event
from flowremote.control_plane.db import Database, new_id, utc_now
from flowremote.control_plane.order_validation import apply_correction
from flowremote.control_plane.review import DecisionRejected, decide
from flowremote.control_plane.sync import record_change, touch_task


class DecisionConflict(DecisionRejected):
    """The client tried to apply a stale version of an exception."""

    def __init__(self, current_revision: int) -> None:
        super().__init__(
            f"This exception changed on another device. Reload revision {current_revision}."
        )
        self.current_revision = current_revision


@dataclass(frozen=True)
class DecisionOutcome:
    record_id: str
    status: str
    resolved_value: str | None
    exception_revision: int
    task_revision: int
    replayed: bool = False

    def as_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "status": self.status,
            "resolved_value": self.resolved_value,
            "exception_revision": self.exception_revision,
            "task_revision": self.task_revision,
            "replayed": self.replayed,
        }


def apply_review_decision(
    db: Database,
    *,
    user: User,
    task_id: str,
    record_id: str,
    action: str,
    value: str | None,
    decision_id: str,
    expected_revision: int | None = None,
    correction: dict[str, str] | None = None,
) -> DecisionOutcome:
    """Apply one human review action and append all related sync changes."""
    with db.transaction():
        task = db.query(
            "SELECT id, owner_id, status, revision FROM tasks WHERE id = ?", (task_id,)
        )
        if not task or (user.role is not Role.ADMIN and task[0]["owner_id"] != user.id):
            raise DecisionRejected("task not found")
        if task[0]["status"] != "review_required":
            raise DecisionRejected("This task has already moved past review.")

        if decision_id:
            replay = db.query(
                "SELECT d.action, d.new_value, e.record_id, e.status, e.resolved_value,"
                " e.revision FROM decisions d JOIN exceptions e ON e.id = d.exception_id"
                " WHERE d.decision_id = ? AND e.task_id = ?",
                (decision_id, task_id),
            )
            if replay:
                current_task = db.query("SELECT revision FROM tasks WHERE id = ?", (task_id,))[0]
                row = replay[0]
                return DecisionOutcome(
                    record_id=row["record_id"],
                    status=row["status"],
                    resolved_value=row["resolved_value"],
                    exception_revision=int(row["revision"] or 1),
                    task_revision=int(current_task["revision"] or 1),
                    replayed=True,
                )

        rows = db.query(
            "SELECT * FROM exceptions WHERE task_id = ? AND record_id = ?",
            (task_id, record_id),
        )
        if not rows:
            raise DecisionRejected("exception not found")
        exception = ExceptionItem.from_row(rows[0])
        if expected_revision is not None and int(rows[0]["revision"] or 1) != expected_revision:
            raise DecisionConflict(int(rows[0]["revision"] or 1))

        real_order = db.scalar(
            "SELECT 1 FROM order_inputs WHERE task_id = ? AND record_id = ?",
            (task_id, record_id),
        )
        changes = dict(correction or {})
        if real_order and action == "edit":
            if not changes:
                fields = exception.flagged_fields.split(", ")
                if len(fields) != 1:
                    raise DecisionRejected("Use Edit order to correct all flagged fields.")
                changes = {fields[0]: value or ""}
            value = json.dumps(changes, ensure_ascii=False)

        result = decide(exception, action, value)
        if real_order and action == "accept":
            suggested = accepted_changes(db, exception)
            if not suggested:
                raise DecisionRejected(
                    "this AI suggestion cannot be verified as a complete correction"
                )
            changes = suggested
        if real_order and action != "skip":
            apply_correction(db, task_id, record_id, changes)

        now = utc_now()
        exception_revision = int(rows[0]["revision"] or 1) + 1
        db.execute(
            "INSERT INTO decisions (id, exception_id, decision_id, action, new_value,"
            " by_user, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                new_id("DEC"),
                exception.id,
                decision_id or new_id("K"),
                result.action.value,
                result.resolved_value,
                user.id,
                now,
            ),
        )
        db.execute(
            "UPDATE exceptions SET status = ?, resolved_value = ?, reviewed_by = ?,"
            " reviewed_at = ?, revision = ? WHERE id = ?",
            (
                result.status.value,
                result.resolved_value,
                user.id,
                now,
                exception_revision,
                exception.id,
            ),
        )
        log_event(
            db,
            task_id=task_id,
            kind="exception_decided",
            actor=user.name,
            occurred_at=now,
            description={
                "accept": f"Accepted the suggestion for {record_id}",
                "edit": f"Corrected {record_id} by hand",
                "skip": f"Skipped {record_id}",
            }[result.action.value],
            payload={
                "record_id": record_id,
                "action": result.action.value,
                "value": result.resolved_value,
                "decision_id": decision_id,
            },
        )
        if task[0]["owner_id"]:
            record_change(
                db,
                user_id=task[0]["owner_id"],
                entity_type="exception",
                entity_id=exception.id,
                task_id=task_id,
                revision=exception_revision,
            )
        task_revision = touch_task(db, task_id)
        return DecisionOutcome(
            record_id=record_id,
            status=result.status.value,
            resolved_value=result.resolved_value,
            exception_revision=exception_revision,
            task_revision=task_revision,
        )
