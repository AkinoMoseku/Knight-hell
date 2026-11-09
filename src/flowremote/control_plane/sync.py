"""Server-authoritative snapshots, revisions and device cursors."""

from __future__ import annotations

import json
from typing import Any

from flowremote.contracts.enums import Role
from flowremote.contracts.models import User
from flowremote.control_plane.db import Database, utc_now


def current_cursor(db: Database) -> int:
    return int(db.scalar("SELECT next_sequence - 1 FROM sync_clock WHERE id = 'global'", default=0))


def record_change(
    db: Database,
    *,
    user_id: str,
    entity_type: str,
    entity_id: str,
    task_id: str,
    revision: int,
) -> int:
    """Append one change inside the caller's transaction and return its cursor."""
    row = db.execute(
        "UPDATE sync_clock SET next_sequence = next_sequence + 1"
        " WHERE id = 'global' RETURNING next_sequence"
    ).fetchone()
    sequence = int(row["next_sequence"]) - 1
    db.execute(
        "INSERT INTO sync_changes (sequence, user_id, entity_type, entity_id,"
        " task_id, revision, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sequence, user_id, entity_type, entity_id, task_id, revision, utc_now()),
    )
    return sequence


def touch_task(db: Database, task_id: str) -> int:
    """Increment the task revision and append a change record."""
    rows = db.query("SELECT owner_id, revision FROM tasks WHERE id = ?", (task_id,))
    if not rows:
        return 0
    owner_id = rows[0]["owner_id"]
    revision = int(rows[0]["revision"] or 1) + 1
    db.execute(
        "UPDATE tasks SET revision = ?, updated_at = ? WHERE id = ?",
        (revision, utc_now(), task_id),
    )
    if owner_id:
        record_change(
            db,
            user_id=owner_id,
            entity_type="task",
            entity_id=task_id,
            task_id=task_id,
            revision=revision,
        )
    return revision


def touch_exception(db: Database, task_id: str, record_id: str) -> int:
    rows = db.query(
        "SELECT e.id, e.revision, t.owner_id FROM exceptions e"
        " JOIN tasks t ON t.id = e.task_id WHERE e.task_id = ? AND e.record_id = ?",
        (task_id, record_id),
    )
    if not rows:
        return 0
    row = rows[0]
    revision = int(row["revision"] or 1) + 1
    db.execute(
        "UPDATE exceptions SET revision = ? WHERE id = ?",
        (revision, row["id"]),
    )
    if row["owner_id"]:
        record_change(
            db,
            user_id=row["owner_id"],
            entity_type="exception",
            entity_id=row["id"],
            task_id=task_id,
            revision=revision,
        )
    return revision


def _visible_task_ids(db: Database, user: User) -> list[str]:
    if user.role is Role.ADMIN:
        rows = db.query("SELECT id FROM tasks ORDER BY updated_at DESC")
    else:
        rows = db.query(
            "SELECT id FROM tasks WHERE owner_id = ? ORDER BY updated_at DESC",
            (user.id,),
        )
    return [row["id"] for row in rows]


def snapshot(db: Database, user: User) -> dict[str, Any]:
    """Return the authoritative state needed by the local cache.

    This intentionally includes every visible exception rather than only the
    current HTML page. Demo batches and the 10,000-row validator bound make this
    practical for the promotional build.
    """
    task_ids = _visible_task_ids(db, user)
    if not task_ids:
        return {
            "cursor": current_cursor(db),
            "server_time": utc_now(),
            "tasks": [],
        }
    placeholders = ", ".join("?" for _ in task_ids)
    tasks = db.query(
        "SELECT id, workflow, batch_size, status, source_file, source_location,"
        " primary_target, secondary_target, owner_id, revision, created_at, updated_at"
        f" FROM tasks WHERE id IN ({placeholders}) ORDER BY updated_at DESC",
        task_ids,
    )
    task_map = {task["id"]: {**task, "exceptions": [], "run": None} for task in tasks}

    exceptions = db.query(
        "SELECT id, task_id, record_id, issue, flagged_fields, original_value,"
        " suggestion, confidence, reason, status, resolved_value, revision, created_at"
        f" FROM exceptions WHERE task_id IN ({placeholders}) ORDER BY record_id",
        task_ids,
    )
    for item in exceptions:
        task_map[item["task_id"]]["exceptions"].append(item)

    runs = db.query(
        "SELECT r.* FROM execution_runs r"
        f" WHERE r.task_id IN ({placeholders}) AND r.attempt ="
        " (SELECT MAX(r2.attempt) FROM execution_runs r2 WHERE r2.task_id = r.task_id)",
        task_ids,
    )
    for run in runs:
        task_map[run["task_id"]]["run"] = run

    completed = db.query(
        "SELECT r.* FROM ai_suggestion_runs r"
        " WHERE r.status = 'completed' AND r.task_id IN"
        f" ({placeholders}) AND r.created_at ="
        " (SELECT MAX(r2.created_at) FROM ai_suggestion_runs r2"
        "  WHERE r2.exception_id = r.exception_id AND r2.status = 'completed')",
        task_ids,
    )
    completed_by_exception = {row["exception_id"]: row for row in completed}
    if completed_by_exception:
        run_ids = [row["id"] for row in completed_by_exception.values()]
        item_marks = ", ".join("?" for _ in run_ids)
        items = db.query(
            "SELECT run_id, field, value, confidence, reason, evidence_json"
            f" FROM ai_suggestion_items WHERE run_id IN ({item_marks}) ORDER BY field",
            run_ids,
        )
        items_by_run: dict[str, list[dict]] = {}
        for item in items:
            try:
                item["evidence"] = json.loads(item.pop("evidence_json"))
            except (TypeError, ValueError):
                item["evidence"] = []
            items_by_run.setdefault(item["run_id"], []).append(item)
        for exception in exceptions:
            run = completed_by_exception.get(exception["id"])
            exception["ai_items"] = items_by_run.get(run["id"], []) if run else []

    return {
        "cursor": current_cursor(db),
        "server_time": utc_now(),
        "tasks": list(task_map.values()),
    }


def changes_since(db: Database, user: User, cursor: int) -> list[dict]:
    if user.role is Role.ADMIN:
        rows = db.query(
            "SELECT sequence, entity_type, entity_id, task_id, revision, changed_at"
            " FROM sync_changes WHERE sequence > ? ORDER BY sequence LIMIT 500",
            (cursor,),
        )
    else:
        rows = db.query(
            "SELECT sequence, entity_type, entity_id, task_id, revision, changed_at"
            " FROM sync_changes WHERE user_id = ? AND sequence > ?"
            " ORDER BY sequence LIMIT 500",
            (user.id, cursor),
        )
    return rows


def register_device(db: Database, user_id: str, device_id: str, label: str) -> None:
    device_id = device_id.strip()[:80]
    label = label.strip()[:120] or "Browser"
    if not device_id:
        return
    now = utc_now()
    with db.transaction():
        rows = db.query("SELECT id FROM devices WHERE id = ?", (device_id,))
        if rows:
            db.execute(
                "UPDATE devices SET label = ?, last_seen_at = ? WHERE id = ? AND user_id = ?",
                (label, now, device_id, user_id),
            )
        else:
            db.execute(
                "INSERT INTO devices (id, user_id, label, last_seen_at, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (device_id, user_id, label, now, now),
            )
