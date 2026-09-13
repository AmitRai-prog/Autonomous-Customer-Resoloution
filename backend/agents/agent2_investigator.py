"""
Agent 2 — Investigator Agent
Retrieves and reconciles all facts needed to make a resolution decision.
Calls customer_db_lookup, order_api_lookup, inventory_api_check.
Calls Agent 6 (Policy RAG Agent) as a sub-step for policy findings.
"""

from typing import Any, Dict, List, Optional
from backend.models import (
    Agent1Output,
    Agent2Output,
    CustomerSummary,
    OrderSummary,
    InventorySummary,
)
from backend.tools import customer_db_lookup, order_api_lookup, inventory_api_check
from backend.agents.agent6_policy_rag import run_agent6_policy_rag
from backend.database import log_audit


def run_agent2_investigator(
    intent_data: Agent1Output,
    customer_email: str,
    case_id: Optional[str] = None
) -> Agent2Output:
    """
    Agent 2 retrieves enterprise facts and queries Agent 6 for policy findings.
    """
    conflicts_or_gaps = []
    policy_findings = []

    # 1. Customer lookup
    cust_res = customer_db_lookup(customer_email, case_id=case_id)
    customer_summary = None

    if not cust_res.get("found"):
        conflicts_or_gaps.append(f"Customer with email '{customer_email}' does not exist in customer database.")
    else:
        order_count = len(cust_res.get("order_history", []))
        tier = cust_res.get("tier", "regular")
        customer_summary = CustomerSummary(
            id=cust_res["customer_id"],
            tier=tier,
            history_summary=f"Customer since {cust_res.get('created_at', '')[:10]} with {order_count} past orders. Tier: {tier}."
        )

    # 2. Order lookup
    order_id = intent_data.order_id
    # If no order_id provided, look up customer's most recent order
    if not order_id and cust_res.get("order_history"):
        order_id = cust_res["order_history"][0]["order_id"]
        conflicts_or_gaps.append(f"No order ID specified in email. Auto-associated with most recent order: {order_id}")
    elif not order_id:
        conflicts_or_gaps.append("Missing order ID; unable to locate relevant order record.")

    order_summary = None
    order_data = {}
    if order_id:
        order_data = order_api_lookup(order_id, case_id=case_id)
        if not order_data.get("found"):
            conflicts_or_gaps.append(f"Order '{order_id}' not found in order database.")
        else:
            # Check ownership
            if customer_summary and order_data.get("customer_id") != customer_summary.id:
                conflicts_or_gaps.append(f"Security Conflict: Order '{order_id}' belongs to customer {order_data.get('customer_id')}, not {customer_summary.id}.")

            order_summary = OrderSummary(
                id=order_data["order_id"],
                status=order_data["status"],
                items=[{"sku": order_data["sku"], "name": order_data["item_name"]}],
                dates={
                    "order_date": order_data.get("order_date"),
                    "delivery_date": order_data.get("delivery_date"),
                    "days_since_delivery": order_data.get("days_since_delivery")
                },
                payment_method=order_data.get("payment_method")
            )

    # 3. Inventory lookup
    sku = order_data.get("sku")
    inv_summary = None
    if sku:
        inv_data = inventory_api_check(sku, case_id=case_id)
        inv_summary = InventorySummary(
            sku=inv_data["sku"],
            in_stock=inv_data["in_stock"],
            quantity=inv_data["quantity"]
        )
        if not inv_data["in_stock"]:
            conflicts_or_gaps.append(f"Inventory Alert: Requested SKU '{sku}' is out of stock (quantity=0).")

    # 4. Policy findings via Agent 6 sub-call
    # Construct targeted policy question based on intent and facts
    tier_str = customer_summary.tier if customer_summary else "regular"
    days_deliv = order_summary.dates.get("days_since_delivery") if order_summary else None
    item_name = order_data.get("item_name", "")

    if intent_data.intent in ("refund", "replacement"):
        q = f"What is the return and {intent_data.intent} policy for a {tier_str} customer where delivery was {days_deliv or 10} days ago?"
        if "final sale" in item_name.lower() or "custom" in item_name.lower():
            q += " Is a personalized or final-sale item returnable?"
        if any(d in intent_data.reason.lower() for d in ["broken", "defective", "damaged"]):
            q += " What is the damaged or defective item policy?"

        rag_res = run_agent6_policy_rag(q, case_id=case_id)
        policy_findings.append(rag_res.answer)
        if rag_res.supporting_snippets:
            policy_findings.extend(rag_res.supporting_snippets[:2])

        if inv_summary and not inv_summary.in_stock and intent_data.intent == "replacement":
            rag_stock = run_agent6_policy_rag("What is the fallback rule when a replacement SKU is out of stock?", case_id=case_id)
            policy_findings.append(f"Stock Fallback Policy: {rag_stock.answer}")

    elif intent_data.intent == "cancellation":
        order_status = order_summary.status if order_summary else "placed"
        q = f"Can a customer cancel an order if its status is {order_status}?"
        rag_res = run_agent6_policy_rag(q, case_id=case_id)
        policy_findings.append(rag_res.answer)

    output = Agent2Output(
        customer=customer_summary,
        order=order_summary,
        inventory_status=inv_summary,
        policy_findings=policy_findings,
        conflicts_or_gaps=conflicts_or_gaps
    )

    log_audit(case_id, "Agent2Investigator", "investigation_completed", output.model_dump())
    return output
