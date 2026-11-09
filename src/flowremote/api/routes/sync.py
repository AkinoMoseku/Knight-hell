"""Local-first synchronization API for browsers and installed PWAs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from flowremote.api.deps import current_user, get_db
from flowremote.contracts.models import User
from flowremote.control_plane.db import Database
from flowremote.control_plane.decisions import DecisionConflict, apply_review_decision
from flowremote.control_plane.order_validation import ValidationError
from flowremote.control_plane.review import DecisionRejected
from flowremote.control_plane.sync import (
    changes_since,
    current_cursor,
    register_device,
    snapshot,
)

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _require_user(user: User | None) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="sign in required")
    return user


@router.get("/bootstrap")
def bootstrap(
    request: Request,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    user = _require_user(user)
    device_id = request.headers.get("x-device-id", "")
    device_label = request.headers.get("x-device-label", "Browser")
    if device_id:
        register_device(db, user.id, device_id, device_label)
    payload = snapshot(db, user)
    payload["device_registered"] = bool(device_id)
    return JSONResponse(payload)


@router.get("/pull")
def pull(
    cursor: int = 0,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    user = _require_user(user)
    changes = changes_since(db, user, max(0, cursor))
    return JSONResponse(
        {
            "cursor": changes[-1]["sequence"] if changes else max(0, cursor),
            "server_cursor": current_cursor(db),
            "changes": changes,
        }
    )


@router.post("/operations")
async def push_operation(
    request: Request,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    user = _require_user(user)
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(payload, dict) or payload.get("type") != "decision":
        raise HTTPException(status_code=400, detail="unsupported sync operation")
    required = ("operation_id", "task_id", "record_id", "action")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        raise HTTPException(status_code=400, detail="missing sync operation fields")
    revision = payload.get("base_revision")
    expected_revision = int(revision) if isinstance(revision, int) and revision > 0 else None
    correction = payload.get("correction")
    if correction is not None and not isinstance(correction, dict):
        raise HTTPException(status_code=400, detail="correction must be an object")
    clean_correction = (
        {
            str(field): str(value)
            for field, value in correction.items()
            if isinstance(field, str) and isinstance(value, str)
        }
        if correction
        else None
    )
    try:
        outcome = apply_review_decision(
            db,
            user=user,
            task_id=payload["task_id"].strip(),
            record_id=payload["record_id"].strip(),
            action=payload["action"].strip(),
            value=payload.get("value"),
            decision_id=payload["operation_id"].strip(),
            expected_revision=expected_revision,
            correction=clean_correction,
        )
    except DecisionConflict as exc:
        return JSONResponse(
            {
                "ok": False,
                "error": "revision_conflict",
                "message": str(exc),
                "current_revision": exc.current_revision,
                "cursor": current_cursor(db),
            },
            status_code=409,
        )
    except (DecisionRejected, ValidationError) as exc:
        return JSONResponse(
            {
                "ok": False,
                "error": "operation_rejected",
                "message": str(exc),
                "cursor": current_cursor(db),
            },
            status_code=400,
        )
    return JSONResponse(
        {
            "ok": True,
            "operation_id": payload["operation_id"].strip(),
            "result": outcome.as_dict(),
            "cursor": current_cursor(db),
        }
    )
