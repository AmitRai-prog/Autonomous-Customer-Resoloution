"""
Agent 1 — Intake / Understanding Agent
Parses raw customer email into structured intent.
Tools: None (Pure extraction/parsing agent).
LLM: Google Gemini 2.0 Flash with deterministic fallback parser.
"""

import re
from typing import Any, Dict, Optional
from backend.models import Agent1Input, Agent1Output
from backend.database import log_audit
from backend.agents.base import call_llm_json


SYSTEM_PROMPT = """You are Agent 1 (Intake/Understanding Agent) for customer support.
Your role is to parse incoming raw customer emails into structured intent.
Extract:
- intent: one of 'refund', 'replacement', 'cancellation', 'status_inquiry', 'complaint', 'other'
- order_id: string like 'ord_101' if mentioned, or null
- item_reference: product name or SKU if mentioned, or null
- reason: brief summary of why customer is contacting
- urgency: 'low', 'medium', or 'high'
- missing_info: list of missing fields (e.g. ['order_id']) if customer did not provide them

Output strictly valid JSON matching this schema."""


def _fallback_parse(subject: str, body: str, customer_email: str) -> Agent1Output:
    """Deterministic extraction fallback when LLM is offline or not configured."""
    text = f"{subject}\n{body}".lower()

    # Extract order_id if present
    order_match = re.search(r"\b(ord_\d{3,4}|order\s*#?\s*(\d{3,4}))\b", text)
    order_id = None
    if order_match:
        order_id = order_match.group(1).replace("order #", "ord_").replace("order ", "ord_").replace("#", "ord_").strip()
        if not order_id.startswith("ord_"):
            order_id = f"ord_{order_id}"

    # Extract item reference
    item_reference = None
    skus = re.findall(r"\b(sku-[\w-]+)\b", text)
    if skus:
        item_reference = skus[0].upper()
    else:
        for product in ["headphones", "watch", "boots", "speaker", "parka", "keyboard", "camera", "tumbler", "drone", "monitor", "tablet", "earbuds", "lamp", "backpack"]:
            if product in text:
                item_reference = product.title()
                break

    # Determine intent
    if any(k in text for k in ["cancel", "cancellation", "stop order", "do not ship"]):
        intent = "cancellation"
    elif any(k in text for k in ["replace", "replacement", "exchange", "broken", "defective", "damaged", "cracked", "not working", "different color"]):
        intent = "replacement"
    elif any(k in text for k in ["refund", "return", "money back", "reimburse", "send back"]):
        intent = "refund"
    elif any(k in text for k in ["status", "tracking", "where is", "delivered yet", "shipment update"]):
        intent = "status_inquiry"
    elif any(k in text for k in ["unacceptable", "terrible", "frustrated", "angry", "complaint"]):
        intent = "complaint"
    else:
        intent = "other"

    # Urgency
    if any(k in text for k in ["urgent", "immediately", "asap", "emergency", "right now", "ridiculous"]):
        urgency = "high"
    elif any(k in text for k in ["soon", "waiting", "disappointed"]):
        urgency = "medium"
    else:
        urgency = "low"

    # Missing info
    missing = []
    if not order_id and intent in ("refund", "replacement", "cancellation"):
        missing.append("order_id")

    reason = subject if len(subject) > 10 else body[:100]

    return Agent1Output(
        intent=intent,
        order_id=order_id,
        item_reference=item_reference,
        reason=reason.strip(),
        urgency=urgency,
        missing_info=missing
    )


def run_agent1_intake(
    subject: str,
    body: str,
    customer_email: str,
    prior_history: Optional[str] = None,
    case_id: Optional[str] = None
) -> Agent1Output:
    """
    Execute Agent 1 on the incoming email.
    """
    user_prompt = f"Subject: {subject}\nSender: {customer_email}\nBody: {body}"
    if prior_history:
        user_prompt += f"\nPrior History: {prior_history}"

    llm_result = call_llm_json(user_prompt, SYSTEM_PROMPT)

    if llm_result and "intent" in llm_result and "urgency" in llm_result:
        try:
            output = Agent1Output(**llm_result)
        except Exception:
            output = _fallback_parse(subject, body, customer_email)
    else:
        output = _fallback_parse(subject, body, customer_email)

    log_audit(case_id, "Agent1Intake", "parsed_intent", output.model_dump())
    return output
