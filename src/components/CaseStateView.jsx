import React, { useState } from "react";

export default function CaseStateView({ caseState }) {
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!caseState) {
    return (
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title">📋 Case State &amp; Outbound Reply</span>
        </div>
        <div className="card-body" style={{ textAlign: "center", padding: "60px 20px", color: "var(--text-muted)" }}>
          <div style={{ fontSize: "36px", marginBottom: "12px" }}>📂</div>
          <div style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-secondary)" }}>
            Awaiting Active Case
          </div>
          <div style={{ fontSize: "12px", marginTop: "4px" }}>
            State object will update in real time as agents execute.
          </div>
        </div>
      </div>
    );
  }

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(caseState, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const inv = caseState.investigator_output;
  const planner = caseState.planner_output;
  const reply = caseState.reply_email;

  return (
    <div className="glass-card">
      <div className="card-header">
        <span className="card-title">
          📋 Case State: <span style={{ color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>{caseState.case_id}</span>
        </span>
        <button
          className="btn btn-secondary"
          style={{ fontSize: "11px", padding: "4px 8px" }}
          onClick={() => setShowRawJson(!showRawJson)}
        >
          {showRawJson ? "Visual Summary" : "{ } Raw JSON"}
        </button>
      </div>

      <div className="card-body">
        {showRawJson ? (
          <div>
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "8px" }}>
              <button className="btn btn-secondary" style={{ fontSize: "11px", padding: "4px 8px" }} onClick={copyJson}>
                {copied ? "✓ Copied!" : "📋 Copy JSON"}
              </button>
            </div>
            <pre className="trace-detail-pre" style={{ maxHeight: "500px" }}>
              {JSON.stringify(caseState, null, 2)}
            </pre>
          </div>
        ) : (
          <div>
            {/* Top Status Bar */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
              <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Status / State</div>
                <div style={{ fontSize: "13px", fontWeight: "600", color: caseState.state === "closed" ? "var(--accent-emerald)" : "var(--accent-cyan)", marginTop: "2px" }}>
                  {caseState.state.toUpperCase()}
                </div>
              </div>

              <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Customer Tier</div>
                <div style={{ fontSize: "13px", fontWeight: "600", color: inv?.customer?.tier === "premium" ? "var(--accent-violet)" : "var(--text-primary)", marginTop: "2px" }}>
                  {inv?.customer?.tier?.toUpperCase() || "REGULAR"}
                </div>
              </div>
            </div>

            {/* Goal */}
            {caseState.goal && (
              <div style={{ marginBottom: "14px", padding: "10px", background: "rgba(0, 240, 255, 0.04)", borderLeft: "3px solid var(--accent-cyan)", borderRadius: "4px" }}>
                <div style={{ fontSize: "10px", color: "var(--accent-cyan)", fontWeight: "600", textTransform: "uppercase" }}>Orchestrator Goal</div>
                <div style={{ fontSize: "12px", color: "var(--text-primary)", marginTop: "3px" }}>{caseState.goal}</div>
              </div>
            )}

            {/* Facts summary */}
            {inv?.order && (
              <div style={{ marginBottom: "14px", background: "rgba(255, 255, 255, 0.02)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "6px" }}>
                  📦 Order Facts &amp; Inventory Level:
                </div>
                <div style={{ fontSize: "12px", display: "flex", flexDirection: "column", gap: "3px" }}>
                  <div><strong>Order:</strong> <span style={{ fontFamily: "var(--font-mono)" }}>{inv.order.id}</span> ({inv.order.status})</div>
                  <div><strong>Item:</strong> {inv.order.items[0]?.name || "N/A"} (<span style={{ fontFamily: "var(--font-mono)" }}>{inv.order.items[0]?.sku}</span>)</div>
                  <div><strong>Age:</strong> {inv.order.dates?.days_since_delivery != null ? `${inv.order.dates.days_since_delivery} days since delivery` : "Not delivered / in transit"}</div>
                  <div><strong>Stock:</strong> {inv.inventory_status ? `${inv.inventory_status.quantity} units (${inv.inventory_status.in_stock ? "In Stock" : "OUT OF STOCK"})` : "N/A"}</div>
                </div>
              </div>
            )}

            {/* Execution History */}
            {caseState.execution_history && caseState.execution_history.length > 0 && (
              <div style={{ marginBottom: "14px" }}>
                <div style={{ fontSize: "11px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "6px" }}>
                  ⚡ Execution History:
                </div>
                {caseState.execution_history.map((att, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "8px 10px",
                      borderRadius: "6px",
                      marginBottom: "6px",
                      fontSize: "11px",
                      background: att.result === "success" ? "rgba(16, 185, 129, 0.08)" : "rgba(244, 63, 94, 0.08)",
                      border: `1px solid ${att.result === "success" ? "rgba(16, 185, 129, 0.2)" : "rgba(244, 63, 94, 0.2)"}`,
                    }}
                  >
                    <strong>Attempt {att.attempt}:</strong> {att.action} &rarr; <span style={{ fontWeight: "600" }}>{att.result}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Final Outcome */}
            {caseState.final_outcome && (
              <div
                style={{
                  padding: "10px 12px",
                  borderRadius: "8px",
                  background: caseState.final_outcome === "escalated" ? "rgba(244, 63, 94, 0.1)" : "rgba(16, 185, 129, 0.1)",
                  border: `1px solid ${caseState.final_outcome === "escalated" ? "rgba(244, 63, 94, 0.3)" : "rgba(16, 185, 129, 0.3)"}`,
                  marginBottom: "14px",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: "700", color: caseState.final_outcome === "escalated" ? "var(--accent-rose)" : "var(--accent-emerald)" }}>
                  {caseState.final_outcome === "escalated" ? "⚠️ CASE ESCALATED" : "✅ RESOLUTION CONFIRMED"}
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-primary)", marginTop: "4px" }}>
                  {caseState.final_outcome === "escalated" ? caseState.escalation_reason : caseState.final_outcome}
                </div>
              </div>
            )}

            {/* Outbound Customer Reply Email */}
            {reply && (
              <div className="email-preview-card">
                <div className="email-preview-header">
                  <span>✉️ Agent 7: Sent Customer Reply Email</span>
                  <span style={{ marginLeft: "auto", fontSize: "10px", padding: "2px 6px", borderRadius: "4px", background: "rgba(16, 185, 129, 0.2)", color: "var(--accent-emerald)" }}>
                    Tone: {reply.tone}
                  </span>
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "8px" }}>
                  <strong>Subject:</strong> {reply.subject}
                </div>
                <div className="email-preview-body">{reply.body}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
