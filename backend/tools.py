"""
Enterprise sandbox tools and state-mutating endpoints.
All tools are genuinely stateful, read/write SQLite database, and log to audit_log.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.database import get_db, log_audit


def customer_db_lookup(identifier: str, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Look up customer record by email address or customer_id.
    Returns customer details and order history.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM customers WHERE email = ? OR customer_id = ?",
            (identifier, identifier)
        )
        row = cursor.fetchone()
        if not row:
            log_audit(case_id, "InvestigatorTool", "customer_db_lookup", {"identifier": identifier, "found": False}, conn=conn)
            return {"found": False, "error": f"No customer found with identifier {identifier}"}

        cust_id = row["customer_id"]
        # Fetch order history
        orders_cursor = conn.execute(
            "SELECT order_id, sku, item_name, status, order_date, delivery_date FROM orders WHERE customer_id = ? ORDER BY order_date DESC",
            (cust_id,)
        )
        orders = [dict(o) for o in orders_cursor.fetchall()]

        result = {
            "found": True,
            "customer_id": row["customer_id"],
            "name": row["name"],
            "email": row["email"],
            "tier": row["tier"],
            "created_at": row["created_at"],
            "order_history": orders
        }
        log_audit(case_id, "InvestigatorTool", "customer_db_lookup", {"identifier": identifier, "customer_id": cust_id, "tier": row["tier"]}, conn=conn)
        return result


def order_api_lookup(order_id: str, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Look up order record by order_id.
    Returns order status, items, payment method, dates, and calculated age.
    """
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if not row:
            log_audit(case_id, "OrderTool", "order_api_lookup", {"order_id": order_id, "found": False}, conn=conn)
            return {"found": False, "error": f"Order {order_id} not found"}

        order_data = dict(row)

        # Calculate days since delivery if delivered
        days_since_delivery = None
        if order_data.get("delivery_date"):
            try:
                deliv_dt = datetime.fromisoformat(order_data["delivery_date"])
                days_since_delivery = (datetime.now() - deliv_dt).days
            except Exception:
                pass

        order_data["days_since_delivery"] = days_since_delivery
        order_data["found"] = True
        log_audit(case_id, "OrderTool", "order_api_lookup", {"order_id": order_id, "status": order_data["status"], "days_since_delivery": days_since_delivery}, conn=conn)
        return order_data


def inventory_api_check(sku: str, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Check stock level for a SKU.
    """
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM inventory WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        if not row:
            log_audit(case_id, "InventoryTool", "inventory_api_check", {"sku": sku, "found": False}, conn=conn)
            return {"found": False, "sku": sku, "in_stock": False, "quantity": 0}

        qty = row["quantity"]
        result = {
            "found": True,
            "sku": row["sku"],
            "product_name": row["product_name"],
            "quantity": qty,
            "in_stock": qty > 0
        }
        log_audit(case_id, "InventoryTool", "inventory_api_check", {"sku": sku, "quantity": qty, "in_stock": qty > 0}, conn=conn)
        return result


def refund_action(order_id: str, reason: str, amount: Optional[float] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute refund action: mutates order status to 'refund_processing'.
    """
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found"}

        if order["status"] in ("refund_processing", "refunded"):
            return {
                "success": True,
                "already_refunded": True,
                "order_id": order_id,
                "new_order_status": order["status"],
                "message": "Refund was already in progress or completed."
            }

        new_status = "refund_processing"
        conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (new_status, order_id)
        )
        tx_id = f"tx_rf_{uuid.uuid4().hex[:8]}"

        result = {
            "success": True,
            "transaction_id": tx_id,
            "order_id": order_id,
            "new_order_status": new_status,
            "reason": reason,
            "amount": amount or "full"
        }
        log_audit(case_id, "ExecutionAgent", "refund_action", result, conn=conn)
        return result


def replace_action(order_id: str, sku: str, alternate_sku: Optional[str] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute replacement action:
    Checks inventory for primary SKU. If stock is 0 and alternate_sku is provided,
    checks alternate SKU. If stock is 0, returns a structured BLOCKED response.
    Never fails silently!
    """
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found", "blocked_reason": "order_not_found"}

        # 1. Check primary SKU inventory
        inv_cursor = conn.execute("SELECT * FROM inventory WHERE sku = ?", (sku,))
        inv_row = inv_cursor.fetchone()
        stock = inv_row["quantity"] if inv_row else 0

        target_sku = sku
        if stock <= 0:
            # Check if alternate SKU was passed and has stock
            if alternate_sku:
                alt_cursor = conn.execute("SELECT * FROM inventory WHERE sku = ?", (alternate_sku,))
                alt_row = alt_cursor.fetchone()
                alt_stock = alt_row["quantity"] if alt_row else 0
                if alt_stock > 0:
                    target_sku = alternate_sku
                    stock = alt_stock
                else:
                    blocked_res = {
                        "success": False,
                        "blocked": True,
                        "sku": sku,
                        "alternate_sku": alternate_sku,
                        "blocked_reason": f"Out of stock for primary SKU '{sku}' and alternate SKU '{alternate_sku}'.",
                        "stock_level": 0
                    }
                    log_audit(case_id, "ExecutionAgent", "replace_action_blocked", blocked_res, conn=conn)
                    return blocked_res
            else:
                blocked_res = {
                    "success": False,
                    "blocked": True,
                    "sku": sku,
                    "blocked_reason": f"Out of stock for SKU '{sku}'. Available quantity is 0.",
                    "stock_level": 0
                }
                log_audit(case_id, "ExecutionAgent", "replace_action_blocked", blocked_res, conn=conn)
                return blocked_res

        # Deduct 1 item from stock
        new_qty = stock - 1
        conn.execute("UPDATE inventory SET quantity = ?, last_updated = ? WHERE sku = ?", (new_qty, datetime.now().isoformat(), target_sku))

        new_status = "replacement_processing"
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))

        tx_id = f"tx_rep_{uuid.uuid4().hex[:8]}"
        result = {
            "success": True,
            "blocked": False,
            "transaction_id": tx_id,
            "order_id": order_id,
            "replacement_sku": target_sku,
            "new_order_status": new_status,
            "new_inventory_level": new_qty
        }
        log_audit(case_id, "ExecutionAgent", "replace_action_success", result, conn=conn)
        return result


def cancel_action(order_id: str, reason: str, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute order cancellation:
    Checks if order is shipped or delivered (cannot cancel outright post-shipment).
    If eligible, marks cancelled and restores reserved stock.
    """
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found"}

        current_status = order["status"]
        if current_status in ("shipped", "delivered"):
            blocked_res = {
                "success": False,
                "blocked": True,
                "blocked_reason": f"Cannot cancel order with status '{current_status}'. Policy dictates return process after delivery.",
                "current_status": current_status
            }
            log_audit(case_id, "ExecutionAgent", "cancel_action_blocked", blocked_res, conn=conn)
            return blocked_res

        new_status = "cancelled"
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))

        # Restore inventory
        sku = order["sku"]
        conn.execute("UPDATE inventory SET quantity = quantity + 1, last_updated = ? WHERE sku = ?", (datetime.now().isoformat(), sku))

        tx_id = f"tx_cnl_{uuid.uuid4().hex[:8]}"
        result = {
            "success": True,
            "transaction_id": tx_id,
            "order_id": order_id,
            "new_order_status": new_status,
            "reason": reason
        }
        log_audit(case_id, "ExecutionAgent", "cancel_action_success", result, conn=conn)
        return result


def set_inventory_stock(sku: str, quantity: int) -> Dict[str, Any]:
    """
    Admin / Judge disruption endpoint helper to change stock level live.
    """
    with get_db() as conn:
        conn.execute(
            "UPDATE inventory SET quantity = ?, last_updated = ? WHERE sku = ?",
            (quantity, datetime.now().isoformat(), sku)
        )
        return {"sku": sku, "quantity": quantity, "updated": True}
