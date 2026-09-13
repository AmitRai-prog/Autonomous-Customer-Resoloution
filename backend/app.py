"""
FastAPI Server for Autonomous Customer Resolution Multi-Agent System.
Exposes case lifecycle management, live step-by-step agent driving,
audit log queries, disruption injection controls, and evaluation harness triggers.
"""

import os
import sys

# Ensure repository root is in sys.path when running python backend/app.py
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.database import get_db, seed_db, get_audit_trail
from backend.models import CaseState
from backend.tools import set_inventory_stock
from backend.email_service import fetch_new_emails, simulate_inbound_email
from backend.orchestrator import (
    create_case_from_email,
    step_case,
    run_case_to_completion,
    get_case_state,
    save_case_to_db,
)
from evaluation.harness import run_evaluation, REPORT_PATH
import json

app = FastAPI(
    title="Autonomous Customer Resolution Multi-Agent API",
    description="Deterministic orchestrator and 7 logical agents for enterprise customer resolution.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    seed_db(force=False)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "customer-resolution-agent-backend"}


class EmailSubmission(BaseModel):
    sender_email: str
    subject: str
    body: str


@app.post("/api/cases/create-from-email")
def create_case(email_data: EmailSubmission):
    """Ingest an email and initialize a new CaseState in state 'email_received'."""
    raw_email = simulate_inbound_email(
        sender_email=email_data.sender_email,
        subject=email_data.subject,
        body=email_data.body
    )
    case = create_case_from_email(raw_email)
    return case.model_dump()


@app.post("/api/cases/{case_id}/step")
def step_case_endpoint(case_id: str):
    """Execute one discrete transition in the deterministic state machine."""
    case = get_case_state(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    updated_case = step_case(case)
    updated_case.audit_log = get_audit_trail(case_id)
    return updated_case.model_dump()


@app.post("/api/cases/{case_id}/run-to-completion")
def run_case_endpoint(case_id: str):
    """Drive case through all agents to terminal state 'closed'."""
    case = get_case_state(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    completed = run_case_to_completion(case)
    return completed.model_dump()


@app.get("/api/cases/{case_id}")
def get_case_endpoint(case_id: str):
    """Get complete live case state and audit trail."""
    case = get_case_state(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.model_dump()


@app.get("/api/cases")
def list_cases():
    """List recent cases from the database."""
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT c.case_id, c.customer_id, c.order_id, c.state, c.goal, 
                      c.final_outcome, c.escalation_reason, c.created_at, c.updated_at,
                      e.sender_email, e.subject 
               FROM cases c 
               LEFT JOIN inbound_emails e ON c.case_id = e.case_id 
               ORDER BY c.created_at DESC LIMIT 50"""
        )
        cases = [dict(row) for row in cursor.fetchall()]
        return {"cases": cases}


@app.get("/api/audit-logs/{case_id}")
def get_audit_logs(case_id: str):
    """Get chronological audit log for case."""
    logs = get_audit_trail(case_id)
    return {"case_id": case_id, "logs": logs}


@app.get("/api/inventory")
def list_inventory():
    """List all inventory items and stock levels."""
    with get_db() as conn:
        cursor = conn.execute("SELECT sku, product_name, quantity, last_updated FROM inventory ORDER BY sku ASC")
        return {"inventory": [dict(r) for r in cursor.fetchall()]}


class StockUpdate(BaseModel):
    sku: str
    quantity: int


@app.post("/api/inventory/set-stock")
def update_stock(req: StockUpdate):
    """Admin / Judge control to modify inventory stock level live."""
    res = set_inventory_stock(req.sku, req.quantity)
    return res


class DisruptionTrigger(BaseModel):
    scenario: str  # 'inventory_block', 'chained_failure', 'reset_stock'


@app.post("/api/disruptions/trigger")
def trigger_disruption(req: DisruptionTrigger):
    """Live judge scenario injection endpoint."""
    scenario = req.scenario.lower()

    if scenario == "inventory_block":
        set_inventory_stock("SKU-SPEAKER-PORT", 0)
        return {
            "status": "triggered",
            "scenario": "inventory_block",
            "message": "Set 'SKU-SPEAKER-PORT' stock to 0. Next replacement for ord_104 will be blocked and replanned to refund."
        }

    elif scenario == "chained_failure":
        set_inventory_stock("SKU-DRONE-X", 0)
        set_inventory_stock("SKU-DRONE-X-BLU", 0)
        return {
            "status": "triggered",
            "scenario": "chained_failure",
            "message": "Set 'SKU-DRONE-X' and alternate 'SKU-DRONE-X-BLU' stock to 0. Next replacement for ord_110 will encounter consecutive blocks and force escalation."
        }

    elif scenario == "reset_stock":
        seed_db(force=True)
        return {
            "status": "reset",
            "scenario": "reset_stock",
            "message": "Database and inventory stock levels restored to initial seed state."
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown disruption scenario '{req.scenario}'")


@app.post("/api/eval/run")
def run_evaluation_endpoint():
    """Trigger the 18-case synthetic test suite and return pass rate & metrics."""
    summary = run_evaluation()
    return summary


@app.get("/api/eval/report")
def get_eval_report():
    """Retrieve the latest evaluation report."""
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "not_run", "message": "Evaluation has not been executed yet."}


@app.get("/api/inbound-emails")
def get_inbound_emails():
    """List all ingested inbound emails."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM inbound_emails ORDER BY received_at DESC LIMIT 50")
        return {"inbound_emails": [dict(r) for r in cursor.fetchall()]}


@app.get("/api/outbound-emails")
def get_outbound_emails():
    """List all outbound reply emails sent by Agent 7."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM outbound_emails ORDER BY sent_at DESC LIMIT 50")
        return {"outbound_emails": [dict(r) for r in cursor.fetchall()]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)


