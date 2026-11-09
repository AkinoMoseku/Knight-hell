"""First-run setup, automation controls and usage summaries."""

from __future__ import annotations

import json
from typing import Any

from flowremote.control_plane.db import Database, new_id, utc_now

DEFAULT_RPA_CONNECTIONS = (
    ("local_excel", "Local Excel Output", json.dumps({"output": "targets/latest"})),
    ("local_http", "Local HTTP Target", json.dumps({"base_url": "http://127.0.0.1:8770"})),
)


def ensure_user_automation(db: Database, user_id: str) -> dict[str, Any]:
    rows = db.query(
        "SELECT * FROM user_automation_settings WHERE user_id = ?", (user_id,)
    )
    if not rows:
        now = utc_now()
        db.execute(
            "INSERT INTO user_automation_settings (user_id, ai_enabled, rpa_enabled,"
            " max_records_per_task, ai_daily_limit, rpa_daily_limit, updated_at)"
            " VALUES (?, 1, 1, 10000, 100, 10, ?)",
            (user_id, now),
        )
        rows = db.query(
            "SELECT * FROM user_automation_settings WHERE user_id = ?", (user_id,)
        )
    return rows[0]


def ensure_rpa_connections(db: Database, user_id: str) -> list[dict[str, Any]]:
    rows = db.query(
        "SELECT * FROM rpa_connections WHERE user_id = ? ORDER BY kind", (user_id,)
    )
    if rows:
        return rows
    now = utc_now()
    with db.transaction():
        for kind, name, config in DEFAULT_RPA_CONNECTIONS:
            db.execute(
                "INSERT INTO rpa_connections (id, user_id, kind, name, enabled,"
                " config_json, health, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, ?, 'available', ?, ?)",
                (new_id("RPA"), user_id, kind, name, config, now, now),
            )
    return db.query(
        "SELECT * FROM rpa_connections WHERE user_id = ? ORDER BY kind", (user_id,)
    )


def save_automation_settings(
    db: Database,
    *,
    user_id: str,
    ai_enabled: bool,
    rpa_enabled: bool,
    max_records_per_task: int,
    ai_daily_limit: int,
    rpa_daily_limit: int,
    enabled_connections: set[str],
) -> None:
    if not 1 <= max_records_per_task <= 10000:
        raise ValueError("max records per task must be between 1 and 10000")
    if not 0 <= ai_daily_limit <= 100000:
        raise ValueError("AI daily limit must be between 0 and 100000")
    if not 0 <= rpa_daily_limit <= 10000:
        raise ValueError("RPA daily limit must be between 0 and 10000")
    ensure_user_automation(db, user_id)
    ensure_rpa_connections(db, user_id)
    now = utc_now()
    with db.transaction():
        db.execute(
            "UPDATE user_automation_settings SET ai_enabled = ?, rpa_enabled = ?,"
            " max_records_per_task = ?, ai_daily_limit = ?, rpa_daily_limit = ?,"
            " updated_at = ? WHERE user_id = ?",
            (
                int(ai_enabled),
                int(rpa_enabled),
                max_records_per_task,
                ai_daily_limit,
                rpa_daily_limit,
                now,
                user_id,
            ),
        )
        for row in db.query(
            "SELECT id, kind FROM rpa_connections WHERE user_id = ?", (user_id,)
        ):
            db.execute(
                "UPDATE rpa_connections SET enabled = ?, updated_at = ? WHERE id = ?",
                (int(row["kind"] in enabled_connections), now, row["id"]),
            )


def complete_onboarding(db: Database, user_id: str) -> None:
    now = utc_now()
    rows = db.query("SELECT user_id FROM user_onboarding WHERE user_id = ?", (user_id,))
    if rows:
        db.execute(
            "UPDATE user_onboarding SET current_step = 'complete', completed_at = ?,"
            " updated_at = ? WHERE user_id = ?",
            (now, now, user_id),
        )
    else:
        db.execute(
            "INSERT INTO user_onboarding (user_id, current_step, completed_at,"
            " created_at, updated_at) VALUES (?, 'complete', ?, ?, ?)",
            (user_id, now, now, now),
        )


def onboarding_complete(db: Database, user_id: str) -> bool:
    value = db.scalar(
        "SELECT completed_at FROM user_onboarding WHERE user_id = ?", (user_id,)
    )
    return bool(value)


def record_usage(
    db: Database,
    *,
    user_id: str,
    event_type: str,
    success: bool,
    provider: str | None = None,
    model: str | None = None,
    record_count: int = 0,
    duration_ms: int = 0,
) -> None:
    db.execute(
        "INSERT INTO usage_events (id, user_id, event_type, provider, model,"
        " record_count, duration_ms, success, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            new_id("USE"),
            user_id,
            event_type,
            provider,
            model,
            max(0, record_count),
            max(0, duration_ms),
            int(success),
            utc_now(),
        ),
    )


def usage_summary(db: Database, user_id: str) -> dict[str, int]:
    rows = db.query(
        "SELECT event_type, COUNT(*) AS events, SUM(record_count) AS records,"
        " SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures"
        " FROM usage_events WHERE user_id = ? GROUP BY event_type",
        (user_id,),
    )
    summary = {
        "ai_requests": 0,
        "rpa_runs": 0,
        "records_processed": 0,
        "failures": 0,
    }
    for row in rows:
        if row["event_type"].startswith("ai_"):
            summary["ai_requests"] += int(row["events"] or 0)
        if row["event_type"] == "rpa_step":
            summary["rpa_runs"] += int(row["events"] or 0)
        summary["records_processed"] += int(row["records"] or 0)
        summary["failures"] += int(row["failures"] or 0)
    summary["tasks"] = int(
        db.scalar("SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (user_id,), 0)
    )
    day_prefix = utc_now()[:10] + "%"
    summary["ai_today"] = int(
        db.scalar(
            "SELECT COUNT(*) FROM usage_events WHERE user_id = ?"
            " AND event_type = 'ai_suggestion' AND created_at LIKE ?",
            (user_id, day_prefix),
            0,
        )
    )
    summary["rpa_today"] = int(
        db.scalar(
            "SELECT COUNT(*) FROM usage_events WHERE user_id = ?"
            " AND event_type = 'rpa_step' AND created_at LIKE ?",
            (user_id, day_prefix),
            0,
        )
    )
    return summary
