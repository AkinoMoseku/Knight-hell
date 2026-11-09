"""Record one review decision on one exception.

The endpoint is the only place that changes an exception's status. It applies
three rules in order: the task must be visible to the signed-in user, a replayed
decision id is a no-op, and the action itself must be legal (see
``review.decide``). The decision row and the exception update happen in one
transaction, so a failure cannot leave them out of step.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from flowremote.api.deps import current_user, get_db
from flowremote.api.forms import read_form
from flowremote.api.rendering import render
from flowremote.api.routes.tasks import load_task_page
from flowremote.contracts.models import User
from flowremote.control_plane.db import Database
from flowremote.control_plane.decisions import apply_review_decision
from flowremote.control_plane.order_validation import FIELDS, ValidationError
from flowremote.control_plane.review import DecisionRejected

router = APIRouter()


@router.post("/tasks/{task_id}/exceptions/{record_id}/decisions")
async def record_decision(
    task_id: str,
    record_id: str,
    request: Request,
    user: User | None = Depends(current_user),  # noqa: B008 - FastAPI dependency idiom.
    db: Database = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom.
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    context = load_task_page(db, user, task_id)
    if context is None:
        raise HTTPException(status_code=404, detail="task not found")
    if context["task"]["status"] != "review_required":
        context["error"] = "This task has already moved past review."
        return render(request, "task.html", context, status_code=400)

    form = await read_form(request)
    action = (form.get("action") or "").strip()
    value = form.get("value")
    decision_id = (form.get("decision_id") or "").strip()
    correction = {
        field: form["field_" + field] for field in FIELDS if "field_" + field in form
    }
    raw_revision = (form.get("base_revision") or "").strip()
    expected_revision = int(raw_revision) if raw_revision.isdigit() else None

    try:
        apply_review_decision(
            db,
            user=user,
            task_id=task_id,
            record_id=record_id,
            action=action,
            value=value,
            decision_id=decision_id,
            expected_revision=expected_revision,
            correction=correction,
        )
    except (DecisionRejected, ValidationError) as exc:
        context = load_task_page(db, user, task_id) or context
        context["error"] = str(exc)
        return render(request, "task.html", context, status_code=400)
    # Jump back to the row just decided, so the reviewer does not lose their place.
    return RedirectResponse(f"/tasks/{task_id}#exc-{record_id}", status_code=303)
