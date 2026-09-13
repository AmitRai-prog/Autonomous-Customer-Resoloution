"""
Agent 4 — Execution Agent
Calls the state-changing enterprise endpoints and captures results.
Tools: refund_action, replace_action, cancel_action.
Low creative latitude — focuses strictly on reliable tool execution and outcome packaging.
"""

from typing import Any, Dict, Optional
from backend.models import Agent3Output, Agent4Output, ExecutionResult
from backend.tools import refund_action, replace_action, cancel_action
from backend.database import log_audit


def run_agent4_execution(
    plan: Agent3Output,
    order_id: str,
    case_id: Optional[str] = None
) -> Agent4Output:
    """
    Agent 4 executes the state-changing action decided by the planner.
    """
    action = plan.action
    target = plan.target

    if action == "refund":
        tool_res = refund_action(
            order_id=order_id,
            reason=target.reason or "Approved customer refund",
            amount=target.amount if isinstance(target.amount, (int, float)) else None,
            case_id=case_id
        )
        if tool_res.get("success"):
            exec_res = ExecutionResult(
                new_order_status=tool_res.get("new_order_status", "refund_processing"),
                transaction_id=tool_res.get("transaction_id"),
                details={"amount": tool_res.get("amount", "full")}
            )
            output = Agent4Output(
                action_attempted="refund",
                success=True,
                result=exec_res,
                error=None,
                blocked_reason=None
            )
        else:
            output = Agent4Output(
                action_attempted="refund",
                success=False,
                result=None,
                error=tool_res.get("error", "Refund failed"),
                blocked_reason=tool_res.get("blocked_reason")
            )

    elif action == "replace":
        tool_res = replace_action(
            order_id=order_id,
            sku=target.sku or "UNKNOWN",
            alternate_sku=target.alternate_sku,
            case_id=case_id
        )
        if tool_res.get("success") and not tool_res.get("blocked"):
            exec_res = ExecutionResult(
                new_order_status=tool_res.get("new_order_status", "replacement_processing"),
                new_inventory_level=tool_res.get("new_inventory_level"),
                transaction_id=tool_res.get("transaction_id"),
                details={"replacement_sku": tool_res.get("replacement_sku")}
            )
            output = Agent4Output(
                action_attempted="replace",
                success=True,
                result=exec_res,
                error=None,
                blocked_reason=None
            )
        else:
            # Action was blocked (e.g. stock level was 0)
            output = Agent4Output(
                action_attempted="replace",
                success=False,
                result=None,
                error=tool_res.get("error"),
                blocked_reason=tool_res.get("blocked_reason", "Replacement blocked: out of stock")
            )

    elif action == "cancel":
        tool_res = cancel_action(
            order_id=order_id,
            reason=target.reason or "Pre-shipment customer cancellation",
            case_id=case_id
        )
        if tool_res.get("success") and not tool_res.get("blocked"):
            exec_res = ExecutionResult(
                new_order_status=tool_res.get("new_order_status", "cancelled"),
                transaction_id=tool_res.get("transaction_id")
            )
            output = Agent4Output(
                action_attempted="cancel",
                success=True,
                result=exec_res,
                error=None,
                blocked_reason=None
            )
        else:
            output = Agent4Output(
                action_attempted="cancel",
                success=False,
                result=None,
                error=tool_res.get("error"),
                blocked_reason=tool_res.get("blocked_reason", "Cancellation blocked")
            )

    elif action in ("escalate", "request_more_info"):
        # Non-mutating actions pass through execution directly to verification/reply
        output = Agent4Output(
            action_attempted=action,
            success=True,
            result=ExecutionResult(new_order_status=None, details={"action": action}),
            error=None,
            blocked_reason=None
        )

    else:
        output = Agent4Output(
            action_attempted=action,
            success=False,
            result=None,
            error=f"Unrecognized action '{action}'",
            blocked_reason=None
        )

    log_audit(case_id, "Agent4Execution", "action_result", output.model_dump())
    return output
