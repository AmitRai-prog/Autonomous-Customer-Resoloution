"""
Agent 7 — Reply / Notification Agent
Composes and sends a final email reply to the customer once the case reaches
'resolved' or 'escalated'.
Tools: send_email only.
Rules:
- Never claim success if verification failed.
- If escalated, state clearly that a human team member will follow up.
- Prefix subject with 'Re: ' for email threading.
- Accurate, empathetic, professional customer tone.
"""

from typing import Any, Dict, Optional
from backend.models import CaseState, Agent7Output
from backend.email_service import send_email
from backend.database import log_audit
from backend.agents.base import call_llm_json

SYSTEM_PROMPT = """You are Agent 7 (Reply/Notification Agent) for customer service.
Compose a clear, compassionate, and professional email reply to the customer.

RULES:
1. Subject line MUST start with 'Re: ' followed by original subject.
2. Tone must be one of: 'apologetic', 'neutral', 'reassuring'.
3. ACCURACY: Strictly reflect what actually happened:
   - If case resolved with refund: confirm refund has been initiated to original payment method.
   - If case resolved with replacement: confirm replacement has been processed and will ship shortly.
   - If case resolved with cancellation: confirm order was cancelled and inventory released.
   - If case was escalated: clearly inform the customer that a human specialist is actively reviewing their case and will follow up within 1 business day. Do NOT fabricate a resolution.
4. Plain language: no internal jargon (e.g. do not say 'Agent 4 executed tool').

Output strictly valid JSON matching Agent7Output schema."""


def _compose_rule_based(case_state: CaseState) -> Agent7Output:
    """Deterministic fallback email composition."""
    orig_sub = case_state.original_email.get("subject", "Your Customer Support Request")
    subject = f"Re: {orig_sub}" if not orig_sub.lower().startswith("re:") else orig_sub

    cust_email = case_state.customer_email
    order_id = case_state.investigator_output.order.id if case_state.investigator_output and case_state.investigator_output.order else "your order"

    if case_state.state == "escalated" or case_state.final_outcome == "escalated":
        tone = "apologetic"
        reason = case_state.escalation_reason or "specialist review required"
        body = (
            f"Dear Customer,\n\n"
            f"Thank you for contacting customer support regarding {order_id}.\n\n"
            f"Due to specific policy considerations ({reason}), we have escalated your case to our senior support team for individual review. "
            f"A dedicated team member will follow up with you directly within one business day with next steps.\n\n"
            f"We sincerely apologize for any inconvenience caused and appreciate your patience.\n\n"
            f"Warm regards,\nCustomer Resolution Team"
        )

    elif case_state.planner_output and case_state.planner_output.action == "refund":
        tone = "reassuring"
        # Check if replanned from replacement
        replanned_note = ""
        if len(case_state.execution_history) > 1:
            replanned_note = "As the requested replacement item is currently out of stock, we have automatically converted your request to a full refund as per our customer policy.\n\n"

        body = (
            f"Dear Customer,\n\n"
            f"Thank you for contacting customer support regarding {order_id}.\n\n"
            f"{replanned_note}"
            f"We are pleased to inform you that your refund has been successfully initiated. "
            f"Please allow 3 to 5 business days for the funds to reflect on your original payment method depending on your bank's processing schedule.\n\n"
            f"If you have any questions, please reply directly to this email.\n\n"
            f"Best regards,\nCustomer Resolution Team"
        )

    elif case_state.planner_output and case_state.planner_output.action == "replace":
        tone = "reassuring"
        body = (
            f"Dear Customer,\n\n"
            f"Thank you for reaching out regarding {order_id}.\n\n"
            f"We have processed your replacement request! A brand new replacement item has been reserved and is being prepared for dispatch. "
            f"You will receive a separate shipment notification with tracking details as soon as it ships.\n\n"
            f"Thank you for choosing us, and please let us know if you need anything else.\n\n"
            f"Best regards,\nCustomer Resolution Team"
        )

    elif case_state.planner_output and case_state.planner_output.action == "cancel":
        tone = "neutral"
        body = (
            f"Dear Customer,\n\n"
            f"This email confirms that your order {order_id} has been successfully cancelled as requested prior to dispatch. "
            f"Any pending payment hold has been released.\n\n"
            f"Thank you,\nCustomer Resolution Team"
        )

    else:
        tone = "neutral"
        body = (
            f"Dear Customer,\n\n"
            f"Thank you for contacting customer support regarding {order_id}. Your request has been reviewed by our team.\n\n"
            f"If you have any additional questions or details to share, please reply directly to this message.\n\n"
            f"Warm regards,\nCustomer Resolution Team"
        )

    return Agent7Output(
        subject=subject,
        body=body,
        tone=tone,
        sent=False,
        email_id=None
    )


def run_agent7_reply(case_state: CaseState) -> Agent7Output:
    """
    Agent 7 composes and sends the final resolution email.
    """
    orig_sub = case_state.original_email.get("subject", "Your Order Support Request")
    context_str = (
        f"Original Email Subject: {orig_sub}\n"
        f"Original Email Body: {case_state.original_email.get('body', '')}\n"
        f"Case State: {case_state.state}\n"
        f"Final Outcome: {case_state.final_outcome}\n"
        f"Escalation Reason: {case_state.escalation_reason}\n"
        f"Planned Action: {case_state.planner_output.action if case_state.planner_output else 'none'}\n"
        f"Execution Attempts: {len(case_state.execution_history)}\n"
        f"Customer Email: {case_state.customer_email}\n"
    )

    llm_res = call_llm_json(context_str, SYSTEM_PROMPT)

    if llm_res and "subject" in llm_res and "body" in llm_res:
        try:
            draft = Agent7Output(**llm_res)
        except Exception:
            draft = _compose_rule_based(case_state)
    else:
        draft = _compose_rule_based(case_state)

    # Enforce Re: in subject
    if not draft.subject.lower().startswith("re:"):
        draft.subject = f"Re: {draft.subject}"

    # Actually call send_email tool
    orig_msg_id = case_state.original_email.get("email_id")
    send_res = send_email(
        to=case_state.customer_email,
        subject=draft.subject,
        body=draft.body,
        case_id=case_state.case_id,
        in_reply_to=orig_msg_id,
        tone=draft.tone
    )

    draft.sent = True
    draft.email_id = send_res.get("email_id")

    log_audit(case_state.case_id, "Agent7Reply", "reply_sent", draft.model_dump())
    return draft
