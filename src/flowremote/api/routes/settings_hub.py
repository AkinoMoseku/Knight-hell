"""AI-RPA management, controls and usage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from flowremote.api.deps import current_user, get_db
from flowremote.api.forms import read_form
from flowremote.api.rendering import render
from flowremote.contracts.models import User
from flowremote.control_plane.ai_settings import public_settings
from flowremote.control_plane.db import Database
from flowremote.control_plane.user_management import (
    ensure_rpa_connections,
    ensure_user_automation,
    save_automation_settings,
    usage_summary,
)

router = APIRouter()


def _context(db: Database, user: User, error: str | None = None, saved: bool = False) -> dict:
    return {
        "user": user,
        "ai": public_settings(db, user.id),
        "automation": ensure_user_automation(db, user.id),
        "connections": ensure_rpa_connections(db, user.id),
        "usage": usage_summary(db, user.id),
        "error": error,
        "saved": saved,
    }


def _number(form: dict[str, str], key: str, default: int) -> int:
    try:
        return int(form.get(key, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key.replace('_', ' ')} must be a number") from exc


@router.get("/settings", response_class=HTMLResponse)
def settings_hub(
    request: Request,
    saved: int = 0,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    if user is None:
        return RedirectResponse("/login?next=/settings", status_code=303)
    return render(request, "settings.html", _context(db, user, saved=bool(saved)))


@router.post("/settings/automation", response_class=HTMLResponse)
async def update_automation(
    request: Request,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    if user is None:
        return RedirectResponse("/login?next=/settings", status_code=303)
    form = await read_form(request)
    try:
        save_automation_settings(
            db,
            user_id=user.id,
            ai_enabled=form.get("ai_enabled") == "1",
            rpa_enabled=form.get("rpa_enabled") == "1",
            max_records_per_task=_number(form, "max_records_per_task", 10000),
            ai_daily_limit=_number(form, "ai_daily_limit", 100),
            rpa_daily_limit=_number(form, "rpa_daily_limit", 10),
            enabled_connections={
                value for value in ("local_excel", "local_http")
                if form.get("connection_" + value) == "1"
            },
        )
    except ValueError as exc:
        return render(request, "settings.html", _context(db, user, str(exc)), status_code=400)
    return RedirectResponse("/settings?saved=1", status_code=303)
