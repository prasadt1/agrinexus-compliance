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

from .cases import CaseStore
from .cohort import build_cohort_summary, nudge_message_for_case
from .interpreter import interpret
from .planner import plan
from .receipt import build_receipt_files, build_receipt_payload

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
    applicator_name: Optional[str] = "You (pilot applicator)"
    phone: Optional[str] = "+1 (515) 555-0100"


class ConfirmRequest(BaseModel):
    text: str = Field(min_length=1)
    bedrock: bool = False


class NudgeRequest(BaseModel):
    which: str = "T+24"


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
    try:
        result = plan(offline=not body.bedrock, windy=body.windy)
    except Exception as exc:
        if body.bedrock:
            raise _bedrock_http_error(exc) from exc
        raise
    out: dict[str, Any] = {"plan": result}
    if body.create_case:
        case = store.create(
            result,
            planned_spray_date=body.planned_spray_date,
            applicator_name=body.applicator_name,
            phone=body.phone,
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
    if store.get(case_id) is None:
        raise HTTPException(status_code=404, detail="case not found")
    try:
        confirmation = interpret(body.text, offline=not body.bedrock)
    except Exception as exc:
        if body.bedrock:
            raise _bedrock_http_error(exc) from exc
        raise
    try:
        case = store.confirm(case_id, confirmation)
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found") from None
    return case.as_dict()


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


if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
