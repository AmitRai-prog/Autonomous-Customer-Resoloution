-- Schema for Autonomous Customer Resolution System
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    tier            TEXT CHECK (tier IN ('regular', 'premium')) DEFAULT 'regular',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id        TEXT PRIMARY KEY,
    customer_id     TEXT REFERENCES customers(customer_id),
    sku             TEXT NOT NULL,
    item_name       TEXT NOT NULL,
    status          TEXT CHECK (status IN
                      ('placed','shipped','delivered','refund_processing',
                       'replacement_processing','cancelled','refunded','replaced')),
    payment_method  TEXT,
    order_date      TIMESTAMP,
    delivery_date   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    sku             TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 0,
    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_documents (
    doc_id          TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    category        TEXT,
    version         TEXT,
    ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cases (
    case_id             TEXT PRIMARY KEY,
    customer_id         TEXT REFERENCES customers(customer_id),
    order_id            TEXT REFERENCES orders(order_id),
    channel             TEXT DEFAULT 'email',
    state               TEXT CHECK (state IN
                          ('email_received','intake','investigating','planning',
                           'executing','verifying','replanning','resolved',
                           'escalated','replying','closed')),
    goal                TEXT,
    final_outcome       TEXT,
    escalation_reason   TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inbound_emails (
    email_id        TEXT PRIMARY KEY,
    case_id         TEXT REFERENCES cases(case_id),
    sender_email    TEXT NOT NULL,
    subject         TEXT,
    body            TEXT,
    received_at     TIMESTAMP,
    processed       BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS outbound_emails (
    email_id        TEXT PRIMARY KEY,
    case_id         TEXT REFERENCES cases(case_id),
    recipient_email TEXT NOT NULL,
    subject         TEXT,
    body            TEXT,
    tone            TEXT,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         TEXT REFERENCES cases(case_id),
    agent_name      TEXT,
    event_type      TEXT,
    detail          TEXT,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
