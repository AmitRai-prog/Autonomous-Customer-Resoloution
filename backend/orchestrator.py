"""
Deterministic State Machine Orchestrator (NOT an LLM).
Owns CaseState, drives sequential agent execution, detects blocked/failed actions,
manages replanning loops (max 2 retries), and enforces policy guardrails.

State transitions:
email_received -> intake -> investigating -> planning -> executing -> verifying
  -> if verified -> resolved -> replying -> closed
  -> if blocked / unverified & retries < max -> replanning -> planning -> executing ...
  -> if retries >= max or unresolvable -> escalated -> replying -> closed
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.models import (
    CaseState,
    CaseStateEnum,
    ExecutionAttempt,
    VerificationAttempt,
)
from backend.database import get_db, log_audit, get_audit_trail
from backend.agents.agent1_intake import run_agent1_intake
from backend.agents.agent2_investigator import run_agent2_investigator
from backend.agents.agent3_planner import run_agent3_planner
from backend.agents.agent4_execution import run_agent4_execution
from backend.agents.agent5_verification import run_agent5_verification
from backend.agents.agent7_reply import run_agent7_reply
from backend.email_service import mark_email_processed


def save_case_to_db(case: CaseState):
    """Persist or update case record in SQLite database."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO cases 
               (case_id, customer_id, order_id, channel, state, goal, final_outcome, escalation_reason, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(case_id) DO UPDATE SET
                   customer_id = excluded.customer_id,
                   order_id = excluded.order_id,
                   state = excluded.state,
                   goal = excluded.goal,
                   final_outcome = excluded.final_outcome,
                   escalation_reason = excluded.escalation_reason,
                   updated_at = excluded.updated_at""",
            (
                case.case_id,
                case.customer_id,
                case.investigator_output.order.id if case.investigator_output and case.investigator_output.order else None,
                "email",
                case.state,
                case.goal,
                case.final_outcome,
                case.escalation_reason,
                datetime.now().isoformat()
            )
        )


def create_case_from_email(email_record: Dict[str, Any]) -> CaseState:
    """
    Initialize a new CaseState from an ingested email record.
    """
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    sender_email = email_record["sender_email"]

    case = CaseState(
        case_id=case_id,
        customer_email=sender_email,
        original_email=email_record,
        state="email_received",
        goal="Resolve customer email inquiry adhering to company policies.",
        audit_log=[]
    )

    save_case_to_db(case)
    if email_record.get("email_id"):
        mark_email_processed(email_record["email_id"], case_id)

    log_audit(case_id, "Orchestrator", "case_created", {"email": sender_email, "subject": email_record.get("subject")})
    return case


def step_case(case: CaseState) -> CaseState:
    """
    Executes exactly one discrete transition in the state machine.
    Allows step-by-step UI visualization and fine-grained control.
    """
    case_id = case.case_id
    current_state = case.state

    # 1. email_received -> intake (Agent 1)
    if current_state == "email_received":
        case.state = "intake"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": "email_received", "to": "intake"})
        agent1_out = run_agent1_intake(
            subject=case.original_email.get("subject", ""),
            body=case.original_email.get("body", ""),
            customer_email=case.customer_email,
            case_id=case_id
        )
        case.intake_output = agent1_out
        case.goal = f"Resolve {agent1_out.intent}: {agent1_out.reason}"
        # Advance state to investigating
        case.state = "investigating"
        save_case_to_db(case)
        return case

    # 2. investigating (Agent 2)
    elif current_state == "investigating":
        # Need Agent 1 output from previous step or re-run
        agent1_out = case.intake_output or run_agent1_intake(
            subject=case.original_email.get("subject", ""),
            body=case.original_email.get("body", ""),
            customer_email=case.customer_email,
            case_id=case_id
        )
        case.intake_output = agent1_out
        agent2_out = run_agent2_investigator(
            intent_data=agent1_out,
            customer_email=case.customer_email,
            case_id=case_id
        )
        case.investigator_output = agent2_out
        if agent2_out.customer:
            case.customer_id = agent2_out.customer.id

        # Advance state to planning
        case.state = "planning"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": "investigating", "to": "planning"})
        save_case_to_db(case)
        return case

    # 3. planning (Agent 3)
    elif current_state == "planning":
        if not case.investigator_output:
            case.state = "investigating"
            return case

        agent3_out = run_agent3_planner(
            investigator=case.investigator_output,
            execution_history=case.execution_history,
            intent=case.intake_output,
            case_id=case_id
        )
        case.planner_output = agent3_out

        if agent3_out.action == "escalate":
            case.state = "escalated"
            case.final_outcome = "escalated"
            case.escalation_reason = agent3_out.justification
            log_audit(case_id, "Orchestrator", "state_transition", {"from": "planning", "to": "escalated", "reason": agent3_out.justification})
        elif agent3_out.action == "request_more_info":
            case.state = "escalated"
            case.final_outcome = "escalated"
            case.escalation_reason = "Customer contact needed for missing order information"
        else:
            case.state = "executing"
            log_audit(case_id, "Orchestrator", "state_transition", {"from": "planning", "to": "executing", "action": agent3_out.action})

        save_case_to_db(case)
        return case

    # 4. executing (Agent 4)
    elif current_state == "executing":
        order_id = case.investigator_output.order.id if case.investigator_output and case.investigator_output.order else None
        agent4_out = run_agent4_execution(
            plan=case.planner_output,
            order_id=order_id,
            case_id=case_id
        )

        # Record execution attempt in history
        attempt_num = len(case.execution_history) + 1
        case.execution_history.append(
            ExecutionAttempt(
                attempt=attempt_num,
                action=agent4_out.action_attempted,
                result="success" if agent4_out.success else f"blocked - {agent4_out.blocked_reason or agent4_out.error}",
                blocked_reason=agent4_out.blocked_reason
            )
        )

        # Advance to verifying
        case.state = "verifying"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": "executing", "to": "verifying"})
        save_case_to_db(case)
        return case

    # 5. verifying (Agent 5)
    elif current_state == "verifying":
        order_id = case.investigator_output.order.id if case.investigator_output and case.investigator_output.order else None
        last_attempt = case.execution_history[-1] if case.execution_history else None

        from backend.models import Agent4Output
        dummy_exec_res = Agent4Output(
            action_attempted=last_attempt.action if last_attempt else "unknown",
            success=last_attempt.result == "success" if last_attempt else False,
            blocked_reason=last_attempt.blocked_reason if last_attempt else None
        )

        agent5_out = run_agent5_verification(
            plan=case.planner_output,
            execution_result=dummy_exec_res,
            order_id=order_id,
            case_id=case_id
        )

        # Record verification history
        case.verification_history.append(
            VerificationAttempt(
                attempt=len(case.verification_history) + 1,
                passed=agent5_out.verification_passed,
                expected=agent5_out.expected_state,
                actual=agent5_out.actual_state,
                discrepancy=agent5_out.discrepancy
            )
        )

        # Route based on verification recommendation
        if agent5_out.recommendation == "close_case" and agent5_out.verification_passed:
            case.state = "resolved"
            case.final_outcome = f"Resolved successfully via {case.planner_output.action}."
            log_audit(case_id, "Orchestrator", "state_transition", {"from": "verifying", "to": "resolved"})
        elif agent5_out.recommendation == "escalate":
            case.state = "escalated"
            case.final_outcome = "escalated"
            case.escalation_reason = agent5_out.discrepancy or "Verification failed policy compliance check"
            log_audit(case_id, "Orchestrator", "state_transition", {"from": "verifying", "to": "escalated", "reason": case.escalation_reason})
        else:
            # replan recommended
            case.replan_count += 1
            if case.replan_count > case.max_replans:
                # Force escalation due to retry limit guardrail
                case.state = "escalated"
                case.final_outcome = "escalated"
                case.escalation_reason = f"Exceeded maximum replanning attempts ({case.max_replans}). Consecutive failures blocked."
                log_audit(case_id, "Orchestrator", "state_transition", {"from": "verifying", "to": "escalated", "reason": case.escalation_reason})
            else:
                case.state = "replanning"
                log_audit(case_id, "Orchestrator", "state_transition", {"from": "verifying", "to": "replanning", "attempt": case.replan_count})

        save_case_to_db(case)
        return case

    # 6. replanning -> planning (routes back to Agent 3 with accumulated execution history)
    elif current_state == "replanning":
        case.state = "planning"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": "replanning", "to": "planning", "replan_count": case.replan_count})
        save_case_to_db(case)
        return case

    # 7. resolved or escalated -> replying (Agent 7)
    elif current_state in ("resolved", "escalated"):
        case.state = "replying"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": current_state, "to": "replying"})
        agent7_out = run_agent7_reply(case)
        case.reply_email = agent7_out
        case.state = "closed"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": "replying", "to": "closed", "reply_sent": agent7_out.sent})
        save_case_to_db(case)
        return case

    elif current_state == "replying":
        agent7_out = run_agent7_reply(case)
        case.reply_email = agent7_out
        case.state = "closed"
        log_audit(case_id, "Orchestrator", "state_transition", {"from": "replying", "to": "closed"})
        save_case_to_db(case)
        return case

    # Already closed
    return case


def run_case_to_completion(case: CaseState, max_steps: int = 15) -> CaseState:
    """
    Drive the state machine continuously until reaching terminal state 'closed'.
    """
    steps = 0
    while case.state != "closed" and steps < max_steps:
        case = step_case(case)
        steps += 1

    # Load fresh audit logs into case object for convenience
    case.audit_log = get_audit_trail(case.case_id)
    save_case_to_db(case)
    return case


def get_case_state(case_id: str) -> Optional[CaseState]:
    """Retrieve current case from database."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Fetch original email
        email_cursor = conn.execute("SELECT * FROM inbound_emails WHERE case_id = ?", (case_id,))
        email_row = email_cursor.fetchone()
        orig_email = dict(email_row) if email_row else {}

        # Fetch audit logs
        logs = get_audit_trail(case_id)

        case = CaseState(
            case_id=row["case_id"],
            customer_id=row["customer_id"],
            customer_email=orig_email.get("sender_email", ""),
            original_email=orig_email,
            state=row["state"],
            goal=row["goal"],
            final_outcome=row["final_outcome"],
            escalation_reason=row["escalation_reason"],
            audit_log=logs,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
        return case
