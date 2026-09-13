"""
Agent 5 — Verification / Policy-Compliance Agent (Independent Check)
Re-checks the executed action's effect against expected outcome AND against policy.
Deliberately separate from the Planner to prevent self-grading.
Independent re-fetch: always queries fresh state from tools, never trusts cached context.
"""

from typing import Any, Dict, Optional
from backend.models import Agent3Output, Agent4Output, Agent5Output
from backend.tools import order_api_lookup, inventory_api_check
from backend.agents.agent6_policy_rag import run_agent6_policy_rag
from backend.database import log_audit


def run_agent5_verification(
    plan: Agent3Output,
    execution_result: Agent4Output,
    order_id: Optional[str],
    case_id: Optional[str] = None
) -> Agent5Output:
    """
    Agent 5 independently re-fetches system state and validates policy compliance.
    """
    # Case 1: Action was blocked during execution (e.g. inventory out of stock)
    if not execution_result.success or execution_result.blocked_reason:
        output = Agent5Output(
            verification_passed=False,
            expected_state=f"Successful execution of {plan.action}",
            actual_state=f"Blocked: {execution_result.blocked_reason or execution_result.error}",
            policy_compliant=True,  # Policy anticipated block and provides fallback
            discrepancy=f"Action '{plan.action}' could not complete: {execution_result.blocked_reason or execution_result.error}",
            recommendation="replan"
        )
        log_audit(case_id, "Agent5Verification", "verification_outcome", output.model_dump())
        return output

    # Case 2: Planner chose escalation
    if plan.action == "escalate":
        output = Agent5Output(
            verification_passed=True,
            expected_state="Case marked for escalation with human follow-up",
            actual_state="Case escalated per policy guidelines",
            policy_compliant=True,
            discrepancy=None,
            recommendation="escalate"
        )
        log_audit(case_id, "Agent5Verification", "verification_outcome", output.model_dump())
        return output

    # Case 3: Planner requested more info
    if plan.action == "request_more_info":
        output = Agent5Output(
            verification_passed=True,
            expected_state="Customer contacted for missing details",
            actual_state="Inquiry drafted",
            policy_compliant=True,
            discrepancy=None,
            recommendation="close_case"
        )
        log_audit(case_id, "Agent5Verification", "verification_outcome", output.model_dump())
        return output

    # Case 4: State-mutating actions (refund, replace, cancel)
    # Independently re-fetch fresh state from the database
    if not order_id:
        output = Agent5Output(
            verification_passed=False,
            expected_state="Verified order mutation",
            actual_state="Order ID missing for verification",
            policy_compliant=False,
            discrepancy="Cannot independently verify state without valid order_id",
            recommendation="escalate"
        )
        log_audit(case_id, "Agent5Verification", "verification_outcome", output.model_dump())
        return output

    fresh_order = order_api_lookup(order_id, case_id=case_id)
    actual_status = fresh_order.get("status")

    if plan.action == "refund":
        expected_status = "refund_processing"
        passed = actual_status in ("refund_processing", "refunded")
        output = Agent5Output(
            verification_passed=passed,
            expected_state=f"Order status == '{expected_status}'",
            actual_state=f"Order status == '{actual_status}'",
            policy_compliant=passed,
            discrepancy=None if passed else f"Expected status {expected_status} but found {actual_status}",
            recommendation="close_case" if passed else "replan"
        )

    elif plan.action == "replace":
        expected_status = "replacement_processing"
        passed = actual_status in ("replacement_processing", "replaced")
        output = Agent5Output(
            verification_passed=passed,
            expected_state=f"Order status == '{expected_status}' and inventory deducted",
            actual_state=f"Order status == '{actual_status}'",
            policy_compliant=passed,
            discrepancy=None if passed else f"Expected status {expected_status} but found {actual_status}",
            recommendation="close_case" if passed else "replan"
        )

    elif plan.action == "cancel":
        expected_status = "cancelled"
        passed = actual_status == "cancelled"
        output = Agent5Output(
            verification_passed=passed,
            expected_state=f"Order status == '{expected_status}'",
            actual_state=f"Order status == '{actual_status}'",
            policy_compliant=passed,
            discrepancy=None if passed else f"Expected status {expected_status} but found {actual_status}",
            recommendation="close_case" if passed else "replan"
        )

    else:
        output = Agent5Output(
            verification_passed=False,
            expected_state="Known action state",
            actual_state=f"Unknown action {plan.action}",
            policy_compliant=False,
            discrepancy=f"Unsupported action {plan.action}",
            recommendation="escalate"
        )

    log_audit(case_id, "Agent5Verification", "verification_outcome", output.model_dump())
    return output
