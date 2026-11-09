"""First-run registration setup for AI and RPA."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from flowremote.api.deps import current_user, get_db
from flowremote.api.forms import read_form
from flowremote.api.rendering import render
from flowremote.contracts.models import User
from flowremote.control_plane.ai_settings import (
    AISettingsError,
    public_settings,
    save_settings,
)
from flowremote.control_plane.db import Database
from flowremote.control_plane.user_management import (
    complete_onboarding,
    ensure_rpa_connections,
    ensure_user_automation,
    save_automation_settings,
    usage_summary,
)

router = APIRouter()


def _context(db: Database, user: User, error: str | None = None) -> dict:
    return {
        "user": user,
        "ai": public_settings(db, user.id),
        "automation": ensure_user_automation(db, user.id),
        "connections": ensure_rpa_connections(db, user.id),
        "usage": usage_summary(db, user.id),
        "error": error,
    }


def _number(form: dict[str, str], key: str, default: int) -> int:
    raw = (form.get(key) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError as exc:
        raise ValueError(f"{key.replace('_', ' ')} must be a number") from exc


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding(
    request: Request,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    if user is None:
        return RedirectResponse("/login?next=/onboarding", status_code=303)
    return render(request, "onboarding.html", _context(db, user))


@router.post("/onboarding", response_class=HTMLResponse)
async def complete_setup(
    request: Request,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    if user is None:
        return RedirectResponse("/login?next=/onboarding", status_code=303)
    form = await read_form(request)
    try:
        save_settings(
            db,
            request.app.state.ai_settings_cipher,
            user_id=user.id,
            provider=form.get("provider", "offline"),
            model=form.get("model", ""),
            base_url=form.get("base_url", ""),
            api_key=form.get("api_key", ""),
            clear_key=form.get("clear_key") == "1",
        )
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
        complete_onboarding(db, user.id)
    except (AISettingsError, ValueError) as exc:
        return render(
            request,
            "onboarding.html",
            _context(db, user, str(exc)),
            status_code=400,
        )
    return RedirectResponse("/?guide=start", status_code=303)
