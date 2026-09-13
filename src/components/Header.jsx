import React from "react";

export default function Header({ onOpenEval, onResetDatabase }) {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo">⚡</div>
        <div>
          <div className="brand-title">AUTONOMOUS CUSTOMER RESOLUTION</div>
          <div className="brand-subtitle">Multi-Agent System &bull; Problem Statement 5 &bull; Tech Zephyr Hackathon</div>
        </div>
      </div>

      <div className="header-badges">
        <div className="tech-badge">
          <span className="badge-dot emerald"></span>
          <span>7 Logical Agents</span>
        </div>
        <div className="tech-badge">
          <span className="badge-dot"></span>
          <span>Deterministic Orchestrator</span>
        </div>
        <div className="tech-badge">
          <span className="badge-dot violet"></span>
          <span>NVIDIA Policy RAG (nv-embedqa-e5-v5)</span>
        </div>

        <button className="btn btn-secondary" onClick={onOpenEval} style={{ marginLeft: "12px" }}>
          📊 Evaluation Harness (18 Cases)
        </button>
        <button className="btn btn-danger" onClick={onResetDatabase} title="Reset DB to fresh seed data">
          🔄 Reset DB
        </button>
      </div>
    </header>
  );
}
