import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import StateTimeline from "./components/StateTimeline";
import EmailIntakePanel from "./components/EmailIntakePanel";
import AgentTraceViewer from "./components/AgentTraceViewer";
import CaseStateView from "./components/CaseStateView";
import EvaluationModal from "./components/EvaluationModal";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [activeCase, setActiveCase] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotification = (msg, type = "info") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchCaseDetails = async (caseId) => {
    try {
      const res = await fetch(`${API_BASE}/api/cases/${caseId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveCase(data);
        setAuditLogs(data.audit_log || []);
      }
    } catch (e) {
      console.error("Failed to fetch case details:", e);
    }
  };

  const handleDispatch = async (emailPayload) => {
    setLoading(true);
    try {
      // 1. Create case from email
      const createRes = await fetch(`${API_BASE}/api/cases/create-from-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(emailPayload),
      });
      if (!createRes.ok) {
        throw new Error(`Server returned error ${createRes.status} on case creation`);
      }
      const newCase = await createRes.json();
      setActiveCase(newCase);
      setAuditLogs(newCase.audit_log || []);

      // 2. Run to completion
      const runRes = await fetch(`${API_BASE}/api/cases/${newCase.case_id}/run-to-completion`, {
        method: "POST",
      });
      if (!runRes.ok) {
        throw new Error(`Server returned error ${runRes.status} while executing agents`);
      }
      const completed = await runRes.json();
      setActiveCase(completed);
      setAuditLogs(completed.audit_log || []);

      showNotification(
        `Case ${completed.case_id} completed: ${completed.final_outcome || completed.state}`,
        completed.state === "closed" ? "success" : "info"
      );
    } catch (e) {
      console.error("Dispatch failed:", e);
      const isNetwork = e.name === "TypeError" || (e.message && e.message.includes("fetch"));
      const errorMsg = isNetwork
        ? "Cannot connect to backend at http://localhost:8000. Is the backend server running?"
        : `Failed to dispatch case: ${e.message}`;
      showNotification(errorMsg, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleStep = async () => {
    if (!activeCase) return;
    setLoading(true);
    try {
      const stepRes = await fetch(`${API_BASE}/api/cases/${activeCase.case_id}/step`, {
        method: "POST",
      });
      if (!stepRes.ok) {
        throw new Error(`Server returned status ${stepRes.status}`);
      }
      const updated = await stepRes.json();
      setActiveCase(updated);
      setAuditLogs(updated.audit_log || []);
    } catch (e) {
      console.error("Step execution failed:", e);
      showNotification(`Step failed: ${e.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerDisruption = async (scenario) => {
    try {
      const res = await fetch(`${API_BASE}/api/disruptions/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario }),
      });
      const data = await res.json();
      showNotification(`Disruption Triggered: ${data.message}`, "warning");
    } catch (e) {
      console.error("Disruption trigger failed:", e);
      showNotification("Failed to trigger disruption", "error");
    }
  };

  const handleResetDatabase = async () => {
    await handleTriggerDisruption("reset_stock");
    setActiveCase(null);
    setAuditLogs([]);
    showNotification("Database reset to initial clean state with fresh seeds.", "info");
  };

  return (
    <div className="app-container">
      <Header
        onOpenEval={() => setEvalModalOpen(true)}
        onResetDatabase={handleResetDatabase}
      />

      {/* State Machine Visual Progression */}
      <StateTimeline
        currentState={activeCase ? activeCase.state : "email_received"}
        replanCount={activeCase ? activeCase.replan_count : 0}
      />

      {/* Notification Banner */}
      {notification && (
        <div
          style={{
            background:
              notification.type === "warning"
                ? "rgba(245, 158, 11, 0.2)"
                : notification.type === "error"
                ? "rgba(244, 63, 94, 0.2)"
                : "rgba(0, 240, 255, 0.15)",
            borderBottom: "1px solid var(--border-subtle)",
            padding: "8px 24px",
            fontSize: "12px",
            fontWeight: "500",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>ℹ️</span>
          <span>{notification.msg}</span>
        </div>
      )}

      {/* 3-Column Cyber Grid Dashboard */}
      <div className="dashboard-grid">
        {/* Left Column: Email Intake & Presets */}
        <EmailIntakePanel
          onDispatch={handleDispatch}
          onStep={handleStep}
          activeCase={activeCase}
          loading={loading}
          onTriggerDisruption={handleTriggerDisruption}
        />

        {/* Center Column: Live Agent & Tool Trace Stream */}
        <AgentTraceViewer
          auditLogs={auditLogs}
          activeCase={activeCase}
        />

        {/* Right Column: Case State Object & Outbound Email */}
        <CaseStateView caseState={activeCase} />
      </div>

      {/* Evaluation Test Suite Modal */}
      <EvaluationModal
        isOpen={evalModalOpen}
        onClose={() => setEvalModalOpen(false)}
      />
    </div>
  );
}
