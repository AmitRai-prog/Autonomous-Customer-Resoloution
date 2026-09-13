import React, { useState } from "react";

const DEMO_PRESETS = [
  {
    title: "1. Standard Refund (In Window)",
    tag: "Happy Path",
    email: "alice.morgan@example.com",
    subject: "Refund request for ord_101 headphones",
    body: "Hi Support,\nI would like to return the Aura Wireless Headphones from ord_101. Delivered 10 days ago, in perfect condition.\nPlease process a refund to my card.",
  },
  {
    title: "2. Disruption: Inventory Block & Replan",
    tag: "Disruption 1",
    isDisruption: true,
    email: "david.miller@example.com",
    subject: "Replacement request for speaker ord_104",
    body: "Hello,\nI need a replacement for my SonicBoom Portable Speaker in ord_104. The unit has a buzzing sound.\nPlease send a new unit as soon as possible.",
  },
  {
    title: "3. Disruption: Chained Failure Escalation",
    tag: "Disruption 3",
    isDisruption: true,
    email: "bob.chen@example.com",
    subject: "Replacement for drone ord_110",
    body: "Hi,\nMy SkyFalcon drone in ord_110 has a rotor issue. Please dispatch a replacement unit or alternate color.",
  },
  {
    title: "4. Disruption: Return Outside 30 Days",
    tag: "Disruption 4",
    isDisruption: true,
    email: "carol.davis@example.com",
    subject: "Return hiking boots ord_103",
    body: "Hello,\nI would like to return the hiking boots from ord_103 and get a refund. They arrived 42 days ago.",
  },
  {
    title: "5. Damaged Item Override (60 Days)",
    tag: "Policy Override",
    email: "grace.hopper@example.com",
    subject: "Action camera defective ord_107",
    body: "Hi team,\nThe Apex 4K action camera in ord_107 arrived with a cracked sensor and is defective. Delivered 50 days ago.\nPlease replace it under the damaged goods policy.",
  },
  {
    title: "6. Non-Returnable Final Sale Remorse",
    tag: "Guardrail",
    email: "henry.ford@example.com",
    subject: "Return engraved tumbler ord_108",
    body: "I changed my mind and no longer want the engraved tumbler in ord_108. Please refund.",
  },
];

export default function EmailIntakePanel({
  onDispatch,
  onStep,
  activeCase,
  loading,
  onTriggerDisruption,
}) {
  const [senderEmail, setSenderEmail] = useState(DEMO_PRESETS[0].email);
  const [subject, setSubject] = useState(DEMO_PRESETS[0].subject);
  const [body, setBody] = useState(DEMO_PRESETS[0].body);

  const applyPreset = (preset) => {
    setSenderEmail(preset.email);
    setSubject(preset.subject);
    setBody(preset.body);
  };

  const handleDispatch = () => {
    onDispatch({ sender_email: senderEmail, subject, body });
  };

  return (
    <div className="glass-card">
      <div className="card-header">
        <span className="card-title">📥 Customer Email Intake</span>
        <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          IMAP Poller / Virtual Ingest
        </span>
      </div>

      <div className="card-body">
        <div style={{ marginBottom: "12px", fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)" }}>
          Demo Scenarios &amp; Disruption Presets:
        </div>

        <div className="presets-group">
          {DEMO_PRESETS.map((p, idx) => (
            <button
              key={idx}
              className="preset-btn"
              onClick={() => applyPreset(p)}
              type="button"
            >
              <span>{p.title}</span>
              <span className={`preset-tag ${p.isDisruption ? "disruption" : ""}`}>
                {p.tag}
              </span>
            </button>
          ))}
        </div>

        <hr style={{ borderColor: "var(--border-subtle)", margin: "16px 0" }} />

        <div className="form-group">
          <label className="form-label">Customer Email Address</label>
          <input
            className="form-input"
            type="email"
            value={senderEmail}
            onChange={(e) => setSenderEmail(e.target.value)}
            placeholder="e.g. alice.morgan@example.com"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Email Subject</label>
          <input
            className="form-input"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject of customer complaint"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Customer Email Body</label>
          <textarea
            className="form-textarea"
            rows="5"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Customer message details..."
          />
        </div>

        <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
          <button
            className="btn btn-primary"
            style={{ flex: 1 }}
            onClick={handleDispatch}
            disabled={loading}
          >
            {loading ? "⚙️ Processing..." : "⚡ Dispatch & Auto-Resolve"}
          </button>

          {activeCase && activeCase.state !== "closed" && (
            <button
              className="btn btn-secondary"
              onClick={onStep}
              disabled={loading}
              title="Advance one discrete state machine step"
            >
              ⏯️ Next Step
            </button>
          )}
        </div>

        <div style={{ marginTop: "20px", paddingTop: "14px", borderTop: "1px solid var(--border-subtle)" }}>
          <div style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            ⚖️ Judge Live Disruption Levers:
          </div>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            <button
              className="btn btn-warning"
              style={{ fontSize: "11px", padding: "5px 10px" }}
              onClick={() => onTriggerDisruption("inventory_block")}
            >
              Zero Stock (Speaker)
            </button>
            <button
              className="btn btn-danger"
              style={{ fontSize: "11px", padding: "5px 10px" }}
              onClick={() => onTriggerDisruption("chained_failure")}
            >
              Zero Both SKUs (Drone)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
