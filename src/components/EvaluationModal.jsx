import React, { useState, useEffect } from "react";

export default function EvaluationModal({ isOpen, onClose }) {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchLatestReport();
    }
  }, [isOpen]);

  const fetchLatestReport = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/eval/report");
      const data = await res.json();
      if (data.results) {
        setReport(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunEvaluation = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/eval/run", { method: "POST" });
      const data = await res.json();
      setReport(data);
    } catch (e) {
      console.error("Eval run failed:", e);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="card-header">
          <span className="card-title">📊 Multi-Agent Evaluation &amp; Robustness Harness</span>
          <button className="btn btn-secondary" style={{ padding: "4px 8px" }} onClick={onClose}>
            ✕ Close
          </button>
        </div>

        <div className="card-body">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: "600", color: "#fff" }}>
                18 Synthetic Benchmark Cases
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Tests happy paths, inventory blocks, chained failure guards, out-of-window returns, and policy overrides.
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleRunEvaluation}
              disabled={loading}
            >
              {loading ? "⚙️ Running 18 Cases..." : "🚀 Run Full Test Suite"}
            </button>
          </div>

          {/* Stats Bar */}
          {report && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px", marginBottom: "16px" }}>
              <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Pass Rate</div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: "var(--accent-emerald)", marginTop: "2px" }}>
                  {report.pass_rate_percentage}%
                </div>
              </div>

              <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Passed / Total</div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: "var(--accent-cyan)", marginTop: "2px" }}>
                  {report.passed_cases} / {report.total_cases}
                </div>
              </div>

              <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Avg Latency</div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: "var(--accent-violet)", marginTop: "2px" }}>
                  {report.average_latency_seconds}s
                </div>
              </div>

              <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-subtle)", textAlign: "center" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Failed Cases</div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: report.failed_cases > 0 ? "var(--accent-rose)" : "var(--accent-emerald)", marginTop: "2px" }}>
                  {report.failed_cases}
                </div>
              </div>
            </div>
          )}

          {/* Test Case Table */}
          {report && report.results && (
            <div style={{ maxHeight: "360px", overflowY: "auto", border: "1px solid var(--border-subtle)", borderRadius: "8px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px", textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "rgba(255, 255, 255, 0.04)", borderBottom: "1px solid var(--border-subtle)" }}>
                    <th style={{ padding: "8px 10px" }}>ID</th>
                    <th style={{ padding: "8px 10px" }}>Scenario Name</th>
                    <th style={{ padding: "8px 10px" }}>Expected</th>
                    <th style={{ padding: "8px 10px" }}>Actual</th>
                    <th style={{ padding: "8px 10px" }}>Replans</th>
                    <th style={{ padding: "8px 10px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {report.results.map((r) => (
                    <tr key={r.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.03)" }}>
                      <td style={{ padding: "8px 10px", fontFamily: "var(--font-mono)", color: "var(--accent-cyan)" }}>{r.id}</td>
                      <td style={{ padding: "8px 10px", color: "var(--text-primary)" }}>{r.name}</td>
                      <td style={{ padding: "8px 10px", color: "var(--text-secondary)" }}>{r.expected_outcome}</td>
                      <td style={{ padding: "8px 10px", color: r.actual_outcome === "escalated" ? "var(--accent-amber)" : "var(--accent-emerald)" }}>
                        {r.actual_outcome}
                      </td>
                      <td style={{ padding: "8px 10px", fontFamily: "var(--font-mono)" }}>{r.replan_count || 0}</td>
                      <td style={{ padding: "8px 10px" }}>
                        <span
                          style={{
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontSize: "10px",
                            fontWeight: "600",
                            background: r.passed ? "rgba(16, 185, 129, 0.15)" : "rgba(244, 63, 94, 0.15)",
                            color: r.passed ? "var(--accent-emerald)" : "var(--accent-rose)",
                          }}
                        >
                          {r.passed ? "✓ PASS" : "✗ FAIL"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
