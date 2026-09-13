"""
Database connection, schema management, and seeding for
Autonomous Customer Resolution Multi-Agent System.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.environ.get("DATABASE_PATH", "./data/customer_resolution.db")


def get_db_path() -> str:
    # Ensure directory exists
    dir_name = os.path.dirname(DB_PATH)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
    return DB_PATH


@contextmanager
def get_db(timeout: float = 30.0):
    """Context manager for SQLite database connection with row factory and foreign keys enabled."""
    conn = sqlite3.connect(get_db_path(), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



def init_db():
    """Create all tables according to the required schema."""
    schema_sql_path = os.path.join(os.path.dirname(__file__), "..", "data", "db_init.sql")
    if os.path.exists(schema_sql_path):
        with open(schema_sql_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
    else:
        # Fallback inline schema
        schema_sql = """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            tier TEXT CHECK (tier IN ('regular', 'premium')) DEFAULT 'regular',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT REFERENCES customers(customer_id),
            sku TEXT NOT NULL,
            item_name TEXT NOT NULL,
            status TEXT CHECK (status IN ('placed','shipped','delivered','refund_processing','replacement_processing','cancelled','refunded','replaced')),
            payment_method TEXT,
            order_date TIMESTAMP,
            delivery_date TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS inventory (
            sku TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS policy_documents (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            category TEXT,
            version TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            customer_id TEXT REFERENCES customers(customer_id),
            order_id TEXT REFERENCES orders(order_id),
            channel TEXT DEFAULT 'email',
            state TEXT CHECK (state IN ('email_received','intake','investigating','planning','executing','verifying','replanning','resolved','escalated','replying','closed')),
            goal TEXT,
            final_outcome TEXT,
            escalation_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS inbound_emails (
            email_id TEXT PRIMARY KEY,
            case_id TEXT REFERENCES cases(case_id),
            sender_email TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            received_at TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS outbound_emails (
            email_id TEXT PRIMARY KEY,
            case_id TEXT REFERENCES cases(case_id),
            recipient_email TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            tone TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT REFERENCES cases(case_id),
            agent_name TEXT,
            event_type TEXT,
            detail TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

    with get_db() as conn:
        conn.executescript(schema_sql)


def seed_db(force: bool = False):
    """Seed initial records for customers, orders, inventory, and policy docs."""
    init_db()

    with get_db() as conn:
        # Check if already seeded
        cursor = conn.execute("SELECT COUNT(*) FROM customers")
        if cursor.fetchone()[0] > 0 and not force:
            return

        if force:
            conn.execute("DELETE FROM audit_log;")
            conn.execute("DELETE FROM outbound_emails;")
            conn.execute("DELETE FROM inbound_emails;")
            conn.execute("DELETE FROM cases;")
            conn.execute("DELETE FROM orders;")
            conn.execute("DELETE FROM customers;")
            conn.execute("DELETE FROM inventory;")
            conn.execute("DELETE FROM policy_documents;")

        now = datetime.now()

        # 1. Customers (Regular & Premium tiers)
        customers = [
            ("cust_001", "Alice Morgan", "alice.morgan@example.com", "regular", (now - timedelta(days=120)).isoformat()),
            ("cust_002", "Bob Chen", "bob.chen@example.com", "premium", (now - timedelta(days=200)).isoformat()),
            ("cust_003", "Carol Davis", "carol.davis@example.com", "regular", (now - timedelta(days=90)).isoformat()),
            ("cust_004", "David Miller", "david.miller@example.com", "premium", (now - timedelta(days=365)).isoformat()),
            ("cust_005", "Elena Rostova", "elena.rostova@example.com", "regular", (now - timedelta(days=45)).isoformat()),
            ("cust_006", "Frank Wright", "frank.wright@example.com", "regular", (now - timedelta(days=150)).isoformat()),
            ("cust_007", "Grace Hopper", "grace.hopper@example.com", "premium", (now - timedelta(days=400)).isoformat()),
            ("cust_008", "Henry Ford", "henry.ford@example.com", "regular", (now - timedelta(days=30)).isoformat()),
        ]
        conn.executemany(
            "INSERT INTO customers (customer_id, name, email, tier, created_at) VALUES (?, ?, ?, ?, ?)",
            customers
        )

        # 2. Inventory (with 0 quantity disruption levers)
        inventory_items = [
            ("SKU-HEADPHONES-BLK", "Aura Wireless Headphones", 25),
            ("SKU-WATCH-PRO", "Chronos Smart Watch Pro", 8),
            ("SKU-BOOTS-BRN", "Alpine Leather Hiking Boots", 12),
            ("SKU-SPEAKER-PORT", "SonicBoom Portable Speaker", 0),          # Stock = 0 (Disruption Lever: Single Block)
            ("SKU-SPEAKER-PORT-BLK", "SonicBoom Portable Speaker (Black)", 0), # Alternate also 0
            ("SKU-JACKET-RED", "Polar Winter Parka", 14),
            ("SKU-KEYBOARD-MECH", "Tactile Pro Mechanical Keyboard", 30),
            ("SKU-CAM-4K", "Apex 4K Action Camera", 6),
            ("SKU-MUG-CUSTOM", "Personalized Laser Engraved Tumbler", 50),
            ("SKU-DRONE-X", "SkyFalcon Quadcopter Drone", 0),              # Stock = 0 (Disruption Lever: Chained Failure)
            ("SKU-DRONE-X-BLU", "SkyFalcon Quadcopter Drone (Blue)", 0),    # Alternate Stock = 0 (Triggers Chained Failure Escalation)
            ("SKU-MONITOR-32", "UltraVision 32-inch 4K Monitor", 4),
            ("SKU-TABLET-AIR", "Nexus Slim Tablet 10", 15),
            ("SKU-EARBUDS-WHT", "TrueTone Wireless Earbuds", 40),
            ("SKU-DESK-LAMP", "Lumina Smart LED Desk Lamp", 22),
            ("SKU-BACKPACK-GREY", "Voyager Anti-Theft Travel Backpack", 18),
        ]
        conn.executemany(
            "INSERT INTO inventory (sku, product_name, quantity, last_updated) VALUES (?, ?, ?, ?)",
            [(sku, name, qty, now.isoformat()) for sku, name, qty in inventory_items]
        )

        # 3. Orders
        orders = [
            # ord_101: Alice Morgan (regular) - 10 days ago (within 30d) -> standard refund/replacement eligible
            ("ord_101", "cust_001", "SKU-HEADPHONES-BLK", "Aura Wireless Headphones", "delivered", "credit_card",
             (now - timedelta(days=15)).isoformat(), (now - timedelta(days=10)).isoformat()),

            # ord_102: Bob Chen (premium) - 38 days ago (within 45d premium window, outside 30d regular) -> premium exception applies
            ("ord_102", "cust_002", "SKU-WATCH-PRO", "Chronos Smart Watch Pro", "delivered", "credit_card",
             (now - timedelta(days=42)).isoformat(), (now - timedelta(days=38)).isoformat()),

            # ord_103: Carol Davis (regular) - 42 days ago (outside 30d regular window, no exception) -> should escalate
            ("ord_103", "cust_003", "SKU-BOOTS-BRN", "Alpine Leather Hiking Boots", "delivered", "paypal",
             (now - timedelta(days=48)).isoformat(), (now - timedelta(days=42)).isoformat()),

            # ord_104: David Miller (premium) - 15 days ago, replacement requested, but stock is 0 -> replans to refund
            ("ord_104", "cust_004", "SKU-SPEAKER-PORT", "SonicBoom Portable Speaker", "delivered", "credit_card",
             (now - timedelta(days=18)).isoformat(), (now - timedelta(days=15)).isoformat()),

            # ord_105: Elena Rostova (regular) - placed, not shipped yet -> pre-shipment cancellation eligible
            ("ord_105", "cust_005", "SKU-JACKET-RED", "Polar Winter Parka", "placed", "credit_card",
             (now - timedelta(days=1)).isoformat(), None),

            # ord_106: Frank Wright (regular) - 12 days ago, paid via cash_on_delivery -> refund must be store credit
            ("ord_106", "cust_006", "SKU-KEYBOARD-MECH", "Tactile Pro Mechanical Keyboard", "delivered", "cash_on_delivery",
             (now - timedelta(days=16)).isoformat(), (now - timedelta(days=12)).isoformat()),

            # ord_107: Grace Hopper (premium) - 50 days ago, defective camera -> covered by 60-day defect policy
            ("ord_107", "cust_007", "SKU-CAM-4K", "Apex 4K Action Camera", "delivered", "credit_card",
             (now - timedelta(days=55)).isoformat(), (now - timedelta(days=50)).isoformat()),

            # ord_108: Henry Ford (regular) - 8 days ago, personalized item, buyer remorse -> non-returnable, must escalate
            ("ord_108", "cust_008", "SKU-MUG-CUSTOM", "Personalized Laser Engraved Tumbler", "delivered", "credit_card",
             (now - timedelta(days=12)).isoformat(), (now - timedelta(days=8)).isoformat()),

            # ord_109: Alice Morgan (regular) - 14 days ago, personalized item arriving broken -> defect overrides non-returnable!
            ("ord_109", "cust_001", "SKU-MUG-CUSTOM", "Personalized Laser Engraved Tumbler", "delivered", "credit_card",
             (now - timedelta(days=18)).isoformat(), (now - timedelta(days=14)).isoformat()),

            # ord_110: Bob Chen (premium) - 20 days ago, replacement requested, drone stock=0, alt stock=0 -> chained failure escalation
            ("ord_110", "cust_002", "SKU-DRONE-X", "SkyFalcon Quadcopter Drone", "delivered", "credit_card",
             (now - timedelta(days=25)).isoformat(), (now - timedelta(days=20)).isoformat()),

            # ord_111: Carol Davis (regular) - shipped, cancellation attempted -> cannot cancel once shipped
            ("ord_111", "cust_003", "SKU-MONITOR-32", "UltraVision 32-inch 4K Monitor", "shipped", "credit_card",
             (now - timedelta(days=3)).isoformat(), None),

            # ord_112: David Miller (premium) - 55 days ago (past 45d window even for premium) -> must escalate
            ("ord_112", "cust_004", "SKU-TABLET-AIR", "Nexus Slim Tablet 10", "delivered", "credit_card",
             (now - timedelta(days=60)).isoformat(), (now - timedelta(days=55)).isoformat()),

            # ord_113: Elena Rostova (regular) - 5 days ago, replacement requested -> stock available (40) -> replacement succeeds
            ("ord_113", "cust_005", "SKU-EARBUDS-WHT", "TrueTone Wireless Earbuds", "delivered", "credit_card",
             (now - timedelta(days=8)).isoformat(), (now - timedelta(days=5)).isoformat()),

            # ord_114: Frank Wright (regular) - 18 days ago, standard refund -> success
            ("ord_114", "cust_006", "SKU-DESK-LAMP", "Lumina Smart LED Desk Lamp", "delivered", "debit_card",
             (now - timedelta(days=22)).isoformat(), (now - timedelta(days=18)).isoformat()),

            # ord_115: Grace Hopper (premium) - shipped recently
            ("ord_115", "cust_007", "SKU-BACKPACK-GREY", "Voyager Anti-Theft Travel Backpack", "shipped", "credit_card",
             (now - timedelta(days=2)).isoformat(), None),
        ]
        conn.executemany(
            """INSERT INTO orders 
               (order_id, customer_id, sku, item_name, status, payment_method, order_date, delivery_date) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            orders
        )

        # 4. Policy Documents Metadata
        policy_docs = [
            ("doc_001", "combined_policies.md", "return_window", "1.0"),
            ("doc_002", "combined_policies.md", "refund_eligibility", "1.0"),
            ("doc_003", "combined_policies.md", "replacement_rules", "1.0"),
            ("doc_004", "combined_policies.md", "loyalty_tier_exceptions", "1.0"),
            ("doc_005", "combined_policies.md", "cancellation_rules", "1.0"),
            ("doc_006", "combined_policies.md", "escalation_criteria", "1.0"),
            ("doc_007", "combined_policies.md", "damaged_and_defective_items", "1.0"),
            ("doc_008", "combined_policies.md", "payment_method", "1.0"),
        ]
        conn.executemany(
            "INSERT INTO policy_documents (doc_id, filename, category, version, ingested_at) VALUES (?, ?, ?, ?, ?)",
            [(d_id, fn, cat, ver, now.isoformat()) for d_id, fn, cat, ver in policy_docs]
        )

        print("Database seeded successfully with customers, inventory, orders, and policy metadata.")


def log_audit(case_id: Optional[str], agent_name: str, event_type: str, detail: Any, conn: Optional[sqlite3.Connection] = None):
    """Log an agent decision or tool invocation to the audit_log table."""
    detail_json = json.dumps(detail, default=str) if not isinstance(detail, str) else detail
    query = "INSERT INTO audit_log (case_id, agent_name, event_type, detail, timestamp) VALUES (?, ?, ?, ?, ?)"
    params = (case_id, agent_name, event_type, detail_json, datetime.now().isoformat())

    if conn is not None:
        conn.execute(query, params)
    else:
        with get_db() as new_conn:
            new_conn.execute(query, params)


def get_audit_trail(case_id: str) -> List[Dict[str, Any]]:
    """Retrieve full chronological audit trail for a case."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT log_id, case_id, agent_name, event_type, detail, timestamp FROM audit_log WHERE case_id = ? ORDER BY log_id ASC",
            (case_id,)
        )
        logs = []
        for row in cursor.fetchall():
            try:
                detail_parsed = json.loads(row["detail"])
            except Exception:
                detail_parsed = row["detail"]
            logs.append({
                "log_id": row["log_id"],
                "case_id": row["case_id"],
                "agent": row["agent_name"],
                "event": row["event_type"],
                "detail": detail_parsed,
                "timestamp": row["timestamp"]
            })
        return logs


if __name__ == "__main__":
    seed_db(force=True)
