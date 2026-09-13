import React from "react";

export default function AgentTraceViewer({ auditLogs = [], activeCase }) {
  const getBadgeClass = (agentName = "") => {
    const name = agentName.toLowerCase();
    if (name.includes("agent1") || name.includes("intake")) return "agent-badge a1";
    if (name.includes("agent2") || name.includes("investigator")) return "agent-badge a2";
    if (name.includes("agent3") || name.includes("planner")) return "agent-badge a3";
    if (name.includes("agent4") || name.includes("execution")) return "agent-badge a4";
    if (name.includes("agent5") || name.includes("verification")) return "agent-badge a5";
    if (name.includes("agent6") || name.includes("policyrag") || name.includes("rag")) return "agent-badge a6";
    if (name.includes("agent7") || name.includes("reply")) return "agent-badge a7";
    return "agent-badge orch";
  };

  const formatAgentName = (name = "") => {
    if (name.includes("Agent1")) return "🔍 Agent 1 (Intake)";
    if (name.includes("Agent2") || name.includes("Investigator")) return "🕵️ Agent 2 (Investigator)";
    if (name.includes("Agent3")) return "🧠 Agent 3 (Planner)";
    if (name.includes("Agent4")) return "⚡ Agent 4 (Execution)";
    if (name.includes("Agent5")) return "🛡️ Agent 5 (Verification)";
    if (name.includes("Agent6")) return "📚 Agent 6 (NVIDIA RAG)";
    if (name.includes("Agent7")) return "✉️ Agent 7 (Reply Notification)";
    if (name.includes("Orchestrator")) return "⚙️ Orchestrator (State Machine)";
    return name;
  };

  return (
    <div className="glass-card" style={{ flex: 1 }}>
      <div className="card-header">
        <span className="card-title">
          🔍 Live Agent &amp; Tool Trace Stream
        </span>
        <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          {auditLogs.length} Events Logged
        </span>
      </div>

      <div className="card-body">
        {auditLogs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--text-muted)" }}>
            <div style={{ fontSize: "36px", marginBottom: "12px" }}>📡</div>
            <div style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-secondary)" }}>
              No Active Trace Events
            </div>
            <div style={{ fontSize: "12px", marginTop: "4px" }}>
              Select a demo preset or submit an email on the left to start the multi-agent pipeline.
            </div>
          </div>
        ) : (
          <div>
            {auditLogs.map((item, idx) => (
              <div key={item.log_id || idx} className="trace-item">
                <div className="trace-item-header">
                  <span className={getBadgeClass(item.agent)}>
                    {formatAgentName(item.agent)}
                  </span>
                  <span className="trace-time">
                    {item.timestamp ? item.timestamp.split("T")[1]?.slice(0, 8) : ""}
                  </span>
                </div>

                <div className="trace-event">
                  &bull; <span style={{ color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>{item.event}</span>
                </div>

                {item.detail && (
                  <pre className="trace-detail-pre">
                    {typeof item.detail === "object"
                      ? JSON.stringify(item.detail, null, 2)
                      : String(item.detail)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
