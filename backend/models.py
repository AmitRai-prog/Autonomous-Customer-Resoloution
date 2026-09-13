"""
Pydantic data models and schemas for the Multi-Agent Customer Resolution System.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# --- EMAIL MODELS ---
class RawEmail(BaseModel):
    sender_email: str
    subject: str
    body: str
    received_at: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())


# --- AGENT 1: INTAKE SCHEMAS ---
class Agent1Input(BaseModel):
    subject: str
    body: str
    customer_email: str
    prior_history: Optional[str] = None


class Agent1Output(BaseModel):
    intent: Literal["refund", "replacement", "cancellation", "status_inquiry", "complaint", "other"]
    order_id: Optional[str] = None
    item_reference: Optional[str] = None
    reason: str
    urgency: Literal["low", "medium", "high"]
    missing_info: List[str] = Field(default_factory=list)


# --- AGENT 2: INVESTIGATOR SCHEMAS ---
class CustomerSummary(BaseModel):
    id: str
    tier: str
    history_summary: str


class OrderSummary(BaseModel):
    id: str
    status: str
    items: List[Dict[str, Any]] = Field(default_factory=list)
    dates: Dict[str, Any] = Field(default_factory=dict)
    payment_method: Optional[str] = None


class InventorySummary(BaseModel):
    sku: str
    in_stock: bool
    quantity: int


class Agent2Output(BaseModel):
    customer: Optional[CustomerSummary] = None
    order: Optional[OrderSummary] = None
    inventory_status: Optional[InventorySummary] = None
    policy_findings: List[str] = Field(default_factory=list)
    conflicts_or_gaps: List[str] = Field(default_factory=list)


# --- AGENT 3: RESOLUTION PLANNER SCHEMAS ---
class PlanTarget(BaseModel):
    sku: Optional[str] = None
    amount: Optional[Union[float, str]] = None
    reason: Optional[str] = None
    alternate_sku: Optional[str] = None


class Agent3Output(BaseModel):
    action: Literal["refund", "replace", "cancel", "escalate", "request_more_info"]
    target: PlanTarget = Field(default_factory=PlanTarget)
    justification: str
    confidence: Literal["high", "medium", "low"]
    fallback_plan: str


# --- AGENT 4: EXECUTION SCHEMAS ---
class ExecutionResult(BaseModel):
    new_order_status: Optional[str] = None
    new_inventory_level: Optional[Union[int, str]] = None
    transaction_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class Agent4Output(BaseModel):
    action_attempted: str
    success: bool
    result: Optional[ExecutionResult] = None
    error: Optional[str] = None
    blocked_reason: Optional[str] = None


# --- AGENT 5: VERIFICATION SCHEMAS ---
class Agent5Output(BaseModel):
    verification_passed: bool
    expected_state: str
    actual_state: str
    policy_compliant: bool
    discrepancy: Optional[str] = None
    recommendation: Literal["close_case", "replan", "escalate"]


# --- AGENT 6: POLICY RAG SCHEMAS ---
class Agent6Output(BaseModel):
    answer: str
    supporting_snippets: List[str] = Field(default_factory=list)
    source_documents: List[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


# --- AGENT 7: REPLY / NOTIFICATION SCHEMAS ---
class Agent7Output(BaseModel):
    subject: str
    body: str
    tone: Literal["apologetic", "neutral", "reassuring"]
    sent: bool = False
    email_id: Optional[str] = None


# --- COMPLETE CASE STATE OBJECT ---
CaseStateEnum = Literal[
    "email_received",
    "intake",
    "investigating",
    "planning",
    "executing",
    "verifying",
    "replanning",
    "resolved",
    "escalated",
    "replying",
    "closed",
]


class ExecutionAttempt(BaseModel):
    attempt: int
    action: str
    result: str
    blocked_reason: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class VerificationAttempt(BaseModel):
    attempt: int
    passed: bool
    expected: str
    actual: str
    discrepancy: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class CaseState(BaseModel):
    case_id: str
    customer_id: Optional[str] = None
    customer_email: str
    original_email: Dict[str, Any]
    state: CaseStateEnum = "email_received"
    goal: Optional[str] = None
    intake_output: Optional[Agent1Output] = None
    investigator_output: Optional[Agent2Output] = None
    planner_output: Optional[Agent3Output] = None
    execution_history: List[ExecutionAttempt] = Field(default_factory=list)
    verification_history: List[VerificationAttempt] = Field(default_factory=list)
    final_outcome: Optional[str] = None
    escalation_reason: Optional[str] = None
    reply_email: Optional[Agent7Output] = None
    replan_count: int = 0
    max_replans: int = 2
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
