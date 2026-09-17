"""
FastAPI app: cohort board → plan → confirm → receipt. Serves static web UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .cases import CaseStore, ConflictError
from .clock import advance_hours, clear_file_override, now_iso, set_now, status as clock_status
from .cohort import build_cohort_summary, nudge_message_for_case
from .interpreter import interpret
from .planner import plan
from .receipt import build_receipt_files, build_receipt_payload
from .verify import checklist_to_interpretation, verify_against_plan

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

app = FastAPI(
    title="AgriNexus Compliance",
    description=(
        "Closed-loop ESA pesticide-label mitigation: plan, remind, confirm, record. "
        "Decision-support / education. Not legal advice. The product label controls."
    ),
    version="0.3.0",
)

store = CaseStore()


class PlanRequest(BaseModel):
    windy: bool = False
    bedrock: bool = False
    planned_spray_date: Optional[str] = None
    create_case: bool = True
    applicator_name: Optional[str] = None
    phone: Optional[str] = None
    is_example: bool = False
    # Fixture pack: boone_liberty (default) or mchenry_stryax_pula (Item 2)
    pack: Optional[str] = None


class ConfirmRequest(BaseModel):
    mode: str = "free_text"
    text: Optional[str] = None
    items: Optional[dict[str, Any]] = None
    bedrock: bool = False


class NudgeRequest(BaseModel):
    which: str = "T+24"


class DemoClockRequest(BaseModel):
    set: Optional[str] = None
    advance_hours: Optional[float] = None
    clear: bool = False


def _bedrock_http_error(exc: Exception) -> HTTPException:
    name = type(exc).__name__
    msg = str(exc)
    if "AccessDenied" in name or "AccessDenied" in msg:
        return HTTPException(
            status_code=502,
            detail=(
                "Bedrock model access denied (IAM / AWS Marketplace subscription). "
                "Uncheck Bedrock to use the offline stub, or enable model access "
                "in the Bedrock console for this account/region."
            ),
        )
    return HTTPException(
        status_code=502,
        detail=f"Bedrock call failed ({name}): {msg}",
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/cohort")
def api_cohort() -> dict[str, Any]:
    return build_cohort_summary(store)


@app.post("/api/plan")
def api_plan(body: PlanRequest) -> dict[str, Any]:
    if body.create_case and not (body.applicator_name or "").strip():
        raise HTTPException(status_code=400, detail="applicator_name is required")
    pack = (body.pack or "").strip() or None
    if pack and pack not in {"boone_liberty", "mchenry_stryax_pula", "dupage_stryax_pula"}:
        raise HTTPException(status_code=400, detail=f"unknown pack: {pack}")
    try:
        result = plan(
            offline=not body.bedrock,
            windy=body.windy,
            pack=pack,
            planned_spray_date=body.planned_spray_date,
        )
    except Exception as exc:
        if body.bedrock:
            raise _bedrock_http_error(exc) from exc
        raise
    out: dict[str, Any] = {"plan": result}
    if body.create_case:
        case = store.create(
            result,
            planned_spray_date=body.planned_spray_date,
            applicator_name=(body.applicator_name or "").strip(),
            phone=body.phone,
            is_example=bool(body.is_example),
        )
        out["case"] = case.as_dict()
    return out


@app.get("/api/cases")
def api_list_cases() -> dict[str, Any]:
    return {"cases": [c.as_dict() for c in store.list_cases()]}


@app.get("/api/cases/{case_id}")
def api_get_case(case_id: str) -> dict[str, Any]:
    case = store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    data = case.as_dict()
    # Attach latest outbound SMS preview for the message UI
    outbound = None
    for ev in reversed(case.events or []):
        if ev.get("outbound_message"):
            outbound = ev["outbound_message"]
            break
    if outbound is None and case.status in {"PLANNED", "NUDGED"}:
        outbound = nudge_message_for_case(case, which="T+24")
    data["outbound_preview"] = outbound
    return data


@app.post("/api/cases/{case_id}/nudge")
def api_nudge(case_id: str, body: Optional[NudgeRequest] = None) -> dict:
    which = (body.which if body else "T+24") or "T+24"
    try:
        case = store.simulate_reminder(case_id, which=which)
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found") from None
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    data = case.as_dict()
    data["outbound_preview"] = None
    for ev in reversed(case.events or []):
        if ev.get("outbound_message"):
            data["outbound_preview"] = ev["outbound_message"]
            break
    return data


@app.post("/api/cases/{case_id}/confirm")
def api_confirm(case_id: str, body: ConfirmRequest) -> dict[str, Any]:
    case = store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    mode = (body.mode or "free_text").strip()
    try:
        if mode == "checklist":
            if not body.items:
                raise HTTPException(status_code=400, detail="checklist items required")
            confirmation = checklist_to_interpretation(body.items, case.plan or {})
            case = store.confirm(case_id, confirmation, mode="checklist")
            verdict = verify_against_plan(confirmation, case.plan or {})
            case = store.apply_verification(
                case_id, verdict, next_status=verdict["next_status"]
            )
            return case.as_dict()

        if not body.text or not str(body.text).strip():
            raise HTTPException(status_code=400, detail="text required for free_text mode")
        try:
            confirmation = interpret(
                body.text, offline=not body.bedrock, plan=case.plan or {}
            )
        except Exception as exc:
            if body.bedrock:
                # Stay confirmable: record error without stack, leave status unchanged
                from .clock import now_iso

                c = store.get(case_id)
                assert c is not None
                c.events.append(
                    {
                        "at": now_iso(),
                        "type": "error",
                        "actor": "system",
                        "detail": "Interpretation failed; reply not stored.",
                        "data": {"message": str(exc)[:200]},
                    }
                )
                store._update(c)  # noqa: SLF001
                raise _bedrock_http_error(exc) from exc
            raise
        case = store.confirm(case_id, confirmation, mode="free_text")
        # Offline free-text: store only (CONFIRMED). Model path: verify.
        if confirmation.get("layer") == "model":
            verdict = verify_against_plan(confirmation, case.plan or {})
            case = store.apply_verification(
                case_id, verdict, next_status=verdict["next_status"]
            )
        return case.as_dict()
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found") from None


class ReviewRequest(BaseModel):
    decision: str
    note: str = Field(min_length=1)
    actor: str = "partner"


class CloseRequest(BaseModel):
    outcome: Optional[str] = None


class ReplanRequest(BaseModel):
    windy: bool = False
    bedrock: bool = False
    planned_spray_date: Optional[str] = None


@app.post("/api/cases/{case_id}/review")
def api_review(case_id: str, body: ReviewRequest) -> dict[str, Any]:
    try:
        case = store.review(
            case_id, decision=body.decision, note=body.note, actor=body.actor
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found") from None
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return case.as_dict()


@app.post("/api/cases/{case_id}/close")
def api_close(case_id: str, body: Optional[CloseRequest] = None) -> dict[str, Any]:
    outcome = body.outcome if body else None
    try:
        case = store.close(case_id, outcome=outcome)
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found") from None
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return case.as_dict()


@app.post("/api/cases/{case_id}/replan")
def api_replan(case_id: str, body: ReplanRequest) -> dict[str, Any]:
    try:
        result = plan(offline=not body.bedrock, windy=body.windy)
        case = store.replan(
            case_id, result, planned_spray_date=body.planned_spray_date
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found") from None
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception as exc:
        if body.bedrock:
            raise _bedrock_http_error(exc) from exc
        raise
    return {"plan": result, "case": case.as_dict()}


@app.get("/api/cases/{case_id}/receipt")
def api_receipt_json(case_id: str) -> dict[str, Any]:
    case = store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    paths = build_receipt_files(case)
    payload = build_receipt_payload(case)
    payload["_files"] = paths
    return payload


@app.get("/api/cases/{case_id}/receipt.pdf")
def api_receipt_pdf(case_id: str) -> FileResponse:
    case = store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    paths = build_receipt_files(case)
    return FileResponse(
        paths["pdf"],
        media_type="application/pdf",
        filename=f"agrinexus-compliance-{case_id}.pdf",
    )


@app.get("/api/cases/{case_id}/receipt.json")
def api_receipt_json_file(case_id: str) -> FileResponse:
    case = store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    paths = build_receipt_files(case)
    return FileResponse(
        paths["json"],
        media_type="application/json",
        filename=f"agrinexus-compliance-{case_id}.json",
    )


def _run_tick() -> dict[str, Any]:
    """Run scheduler if present (added in ladder commit); otherwise no-op."""
    try:
        from .scheduler import tick
    except ImportError:
        return {"ticked": False, "reason": "scheduler not loaded"}
    return tick(store)


@app.get("/api/demo/clock")
def api_demo_clock() -> dict[str, Any]:
    return clock_status()


@app.post("/api/demo/clock")
def api_demo_clock_set(body: DemoClockRequest) -> dict[str, Any]:
    if body.clear:
        clear_file_override()
        return {"clock": clock_status(), "tick": _run_tick()}
    if body.set:
        set_now(body.set)
    elif body.advance_hours is not None:
        advance_hours(body.advance_hours)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide set (ISO), advance_hours, or clear=true",
        )
    return {"clock": clock_status(), "tick": _run_tick()}


@app.post("/api/demo/tick")
def api_demo_tick() -> dict[str, Any]:
    return {"clock": clock_status(), "tick": _run_tick()}


@app.post("/api/demo/reset")
def api_demo_reset() -> dict[str, Any]:
    # Import here so scripts/ stays the single reset implementation.
    sys_path_root = str(ROOT)
    if sys_path_root not in __import__("sys").path:
        __import__("sys").path.insert(0, sys_path_root)
    from scripts.demo_reset import reset_demo

    result = reset_demo(seed=True)
    result["clock"] = clock_status()
    return result


if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
