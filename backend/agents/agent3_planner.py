"""
Agent 3 — Resolution Planner Agent
Decides the resolution action given investigator's findings and case history.
Strict Policy Guardrail: Never invents an exception or justification.
If facts do not support automated resolution, chooses 'escalate' or 'request_more_info'.
"""

import json
from typing import Any, Dict, List, Optional
from backend.models import Agent2Output, Agent3Output, PlanTarget, ExecutionAttempt
from backend.database import log_audit
from backend.agents.base import call_llm_json
from backend.agents.agent6_policy_rag import run_agent6_policy_rag

SYSTEM_PROMPT = """You are Agent 3 (Resolution Planner Agent) for customer service.
Decide the resolution action given the investigator's findings and case history.
Valid actions: 'refund', 'replace', 'cancel', 'escalate', 'request_more_info'.

CRITICAL POLICY GUARDRAILS:
1. NEVER invent a policy exception. If policy findings do not clearly permit the action, choose 'escalate'.
2. Return Window: Regular customers have 30 days from delivery. Premium customers have 45 days.
3. Damaged/Defective items have an extended 60-day window and override non-returnable categories.
4. Non-returnable items (final sale, personalized) must be ESCALATED if the return is for buyer remorse, but can be replaced/refunded if damaged.
5. If an earlier attempt was BLOCKED (e.g. replacement blocked by 0 inventory), follow policy fallback order: offer alternate or fallback to refund.
6. If the order is already shipped, cancellation is NOT allowed; route to return upon delivery or escalate.

Output strictly valid JSON matching Agent3Output schema."""


def _plan_rule_based(
    investigator: Agent2Output,
    execution_history: List[ExecutionAttempt],
    intent: Optional[Any] = None,
    case_id: Optional[str] = None
) -> Agent3Output:
    """Deterministic, policy-compliant resolution planner adhering strictly to handbook."""
    customer = investigator.customer
    order = investigator.order
    inventory = investigator.inventory_status
    conflicts = investigator.conflicts_or_gaps

    # Check for unresolvable identity or order conflict
    if not customer:
        return Agent3Output(
            action="escalate",
            target=PlanTarget(reason="Customer identification failed"),
            justification="Escalation Criteria Policy Section 2(e): Customer identity cannot be verified against database.",
            confidence="high",
            fallback_plan="Human support representative to contact sender for verification."
        )

    if any("Security Conflict" in c for c in conflicts):
        return Agent3Output(
            action="escalate",
            target=PlanTarget(reason="Order ownership mismatch"),
            justification="Escalation Criteria Policy Section 2(e): Mismatch between email identity and order record customer_id.",
            confidence="high",
            fallback_plan="Route to fraud prevention & security team."
        )

    if not order:
        return Agent3Output(
            action="request_more_info",
            target=PlanTarget(reason="Missing order identification"),
            justification="Cannot formulate resolution without valid order record.",
            confidence="high",
            fallback_plan="Escalate to human agent if customer does not respond within 48 hours."
        )

    sku = order.items[0]["sku"] if order.items else "UNKNOWN"
    item_name = order.items[0]["name"] if order.items else ""
    days_deliv = order.dates.get("days_since_delivery")
    tier = customer.tier

    # Check for replanning after previous blocked attempts
    blocked_attempts = [a for a in execution_history if "blocked" in a.result.lower() or a.blocked_reason]
    if blocked_attempts:
        last_blocked = blocked_attempts[-1]
        # Check if chained failure limit reached (e.g. 2nd consecutive failure)
        if len(blocked_attempts) >= 2:
            return Agent3Output(
                action="escalate",
                target=PlanTarget(reason="Chained execution failure threshold exceeded"),
                justification="Escalation Criteria Section 2(d) & Replacement Rules Section 2a: Two consecutive replacement failures occurred on the same case.",
                confidence="high",
                fallback_plan="Manual inventory allocation and supervisor intervention."
            )

        # Check if an alternate SKU should be attempted first (Section 2a)
        if len(blocked_attempts) == 1 and (sku == "SKU-DRONE-X" or "alternate" in investigator.conflicts_or_gaps or "drone" in item_name.lower()):
            alt_sku = "SKU-DRONE-X-BLU" if sku == "SKU-DRONE-X" else f"{sku}-ALT"
            return Agent3Output(
                action="replace",
                target=PlanTarget(
                    sku=alt_sku,
                    reason=f"Primary SKU '{sku}' out of stock; attempting alternate SKU '{alt_sku}' per Section 2(a)"
                ),
                justification="Replacement Rules Policy Section 2(a): Offer equivalent alternate SKU if primary is out of stock.",
                confidence="medium",
                fallback_plan="Escalate or fallback to refund if alternate SKU is also out of stock."
            )

        # Replanning after single blocked replacement: fallback to refund per policy
        if "replace" in last_blocked.action.lower() or "stock" in str(last_blocked.blocked_reason).lower():
            return Agent3Output(
                action="refund",
                target=PlanTarget(
                    amount="full",
                    reason=f"Replacement blocked due to inventory exhaustion; fallback to full refund per policy."
                ),
                justification="Replacement Rules Policy Section 2(b): When requested replacement SKU has 0 stock and no alternate is available, convert to standard refund.",
                confidence="high",
                fallback_plan="Escalate if refund processing encounters payment gateway error."
            )


    # 1. Cancellation intent
    is_cancellation = (intent and intent.intent == "cancellation")
    if is_cancellation and order.status in ("placed", "processing"):
        return Agent3Output(
            action="cancel",
            target=PlanTarget(sku=sku, reason="Pre-shipment customer cancellation"),
            justification="Cancellation Rules Policy Section 1: Order may be cancelled with no fee at any time before status changes to 'shipped'.",
            confidence="high",
            fallback_plan="Escalate if cancellation fails."
        )
    elif is_cancellation and order.status in ("shipped", "delivered"):
        return Agent3Output(
            action="escalate",
            target=PlanTarget(reason="Post-shipment cancellation requested"),
            justification="Cancellation Rules Policy Section 2: Once order status is 'shipped', it can no longer be cancelled outright; customer must return after delivery.",
            confidence="high",
            fallback_plan="Instruct customer to initiate return once delivery is complete."
        )

    # 2. Defective or Damaged items (60-day window, overrides non-returnable)
    reason_text = (intent.reason or "") if intent else ""
    if intent and intent.item_reference:
        reason_text += " " + intent.item_reference
    is_damaged = any(k in reason_text.lower() for k in ["damaged", "defective", "broken", "cracked", "not working", "faulty", "malfunctioning", "shattered"])

    if is_damaged:
        if days_deliv is not None and days_deliv <= 60:
            # Check customer preference
            if intent and intent.intent == "refund":
                return Agent3Output(
                    action="refund",
                    target=PlanTarget(amount="full", reason="Damaged item refund requested within 60-day defect window"),
                    justification="Damaged and Defective Items Policy Section 2: Damaged items are eligible for refund within 60 days of delivery, overriding standard return window.",
                    confidence="high",
                    fallback_plan="Escalate to customer support specialist."
                )
            else:
                # Replacement requested
                if inventory and inventory.in_stock:
                    return Agent3Output(
                        action="replace",
                        target=PlanTarget(sku=sku, reason="Damaged item replacement within 60-day defect window"),
                        justification="Damaged and Defective Items Policy Section 2 & 5: Damaged items are eligible for replacement within 60 days.",
                        confidence="high",
                        fallback_plan="Fallback to full refund if replacement execution is blocked."
                    )
                else:
                    return Agent3Output(
                        action="refund",
                        target=PlanTarget(amount="full", reason="Damaged item refund (replacement SKU out of stock)"),
                        justification="Damaged and Defective Items Policy Section 2 & Replacement Rules Section 2(b): Defective item eligible, falling back to refund due to stock unavailability.",
                        confidence="high",
                        fallback_plan="Escalate to customer support specialist."
                    )
        else:
            return Agent3Output(
                action="escalate",
                target=PlanTarget(reason="Defect reported past 60-day defect window"),
                justification="Damaged and Defective Items Policy Section 2: Defect report made outside the 60-day window from delivery.",
                confidence="high",
                fallback_plan="Human supervisor review for discretionary courtesy."
            )

    # 3. Non-returnable items (final sale, personalized)
    is_non_returnable = "final sale" in item_name.lower() or "custom" in item_name.lower() or "personalized" in item_name.lower()
    if is_non_returnable:
        return Agent3Output(
            action="escalate",
            target=PlanTarget(reason="Non-returnable item return requested (final sale / personalized)"),
            justification="Return Window Policy Section 4 & Escalation Criteria Section 2(b): Personalized and final sale items are excluded from standard return window.",
            confidence="high",
            fallback_plan="Explain policy to customer and offer store credit discount."
        )

    # 4. Standard Return Window evaluation
    max_days = 45 if tier == "premium" else 30
    if days_deliv is not None and days_deliv > max_days:
        return Agent3Output(
            action="escalate",
            target=PlanTarget(reason=f"Return requested {days_deliv} days after delivery (limit: {max_days} days for {tier} tier)"),
            justification=f"Return Window Policy Section 1 & 3: Return requested at {days_deliv} days, which exceeds the {max_days}-day window for {tier}-tier customers.",
            confidence="high",
            fallback_plan="Escalate to human support to check for annual courtesy exception."
        )

    # 5. Within window: Replacement vs Refund
    wants_replacement = (intent and intent.intent == "replacement")
    if wants_replacement:
        if inventory and inventory.in_stock:
            return Agent3Output(
                action="replace",
                target=PlanTarget(sku=sku, reason="Product exchange/replacement within return window"),
                justification=f"Replacement Rules Policy Section 1: Customer is within {max_days}-day return window and replacement SKU is in stock.",
                confidence="high",
                fallback_plan="Fallback to refund if inventory deduction fails."
            )
        else:
            return Agent3Output(
                action="replace",
                target=PlanTarget(sku=sku, reason="Replacement requested by customer"),
                justification=f"Replacement Rules Policy Section 1: Customer requested replacement within {max_days}-day window.",
                confidence="medium",
                fallback_plan="Fallback to refund under Section 2(b) if inventory check blocks execution."
            )
    else:
        # Standard Refund
        return Agent3Output(
            action="refund",
            target=PlanTarget(amount="full", reason="Standard return within policy window"),
            justification=f"Refund Eligibility Policy Section 1: Return initiated within {max_days}-day window for {tier} tier.",
            confidence="high",
            fallback_plan="Escalate if payment refund gateway is unreachable."
        )


def run_agent3_planner(
    investigator: Agent2Output,
    execution_history: Optional[List[ExecutionAttempt]] = None,
    intent: Optional[Any] = None,
    case_id: Optional[str] = None
) -> Agent3Output:
    """
    Execute Agent 3: formulate resolution plan with strict guardrails.
    """
    execution_history = execution_history or []

    # Prepare prompt for LLM
    context_data = {
        "customer": investigator.customer.model_dump() if investigator.customer else None,
        "order": investigator.order.model_dump() if investigator.order else None,
        "inventory": investigator.inventory_status.model_dump() if investigator.inventory_status else None,
        "policy_findings": investigator.policy_findings,
        "conflicts_or_gaps": investigator.conflicts_or_gaps,
        "execution_history": [e.model_dump() for e in execution_history],
        "customer_intent": intent.model_dump() if intent and hasattr(intent, "model_dump") else None
    }

    user_prompt = f"Case Facts & Policy Findings:\n{json.dumps(context_data, indent=2)}"
    llm_res = call_llm_json(user_prompt, SYSTEM_PROMPT)

    if llm_res and "action" in llm_res and "justification" in llm_res:
        try:
            output = Agent3Output(**llm_res)
        except Exception:
            output = _plan_rule_based(investigator, execution_history, intent=intent, case_id=case_id)
    else:
        output = _plan_rule_based(investigator, execution_history, intent=intent, case_id=case_id)

    log_audit(case_id, "Agent3Planner", "resolution_planned", output.model_dump())
    return output
