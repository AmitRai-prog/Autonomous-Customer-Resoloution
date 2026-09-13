import React from "react";

const PIPELINE_STATES = [
  { key: "email_received", label: "Email Intake", icon: "📥" },
  { key: "intake", label: "Agent 1: Understanding", icon: "🔍" },
  { key: "investigating", label: "Agent 2: Investigator", icon: "🕵️" },
  { key: "planning", label: "Agent 3: Planner", icon: "🧠" },
  { key: "executing", label: "Agent 4: Execution", icon: "⚡" },
  { key: "verifying", label: "Agent 5: Verification", icon: "🛡️" },
  { key: "replanning", label: "Replanning Loop", icon: "🔄" },
  { key: "resolved", label: "Resolved", icon: "✅" },
  { key: "escalated", label: "Escalated", icon: "⚠️" },
  { key: "replying", label: "Agent 7: Customer Reply", icon: "✉️" },
  { key: "closed", label: "Closed", icon: "🏁" },
];

export default function StateTimeline({ currentState, replanCount = 0 }) {
  const getStepClass = (stepKey) => {
    if (currentState === stepKey) {
      if (stepKey === "replanning") return "timeline-step active replan";
      if (stepKey === "escalated") return "timeline-step active escalated";
      return "timeline-step active";
    }

    const stateOrder = [
      "email_received",
      "intake",
      "investigating",
      "planning",
      "executing",
      "verifying",
      "resolved",
      "escalated",
      "replying",
      "closed",
    ];

    const currentIdx = stateOrder.indexOf(currentState);
    const stepIdx = stateOrder.indexOf(stepKey);

    if (currentIdx > stepIdx && stepIdx !== -1) {
      return "timeline-step completed";
    }

    return "timeline-step";
  };

  return (
    <div className="timeline-container">
      <div className="timeline-nodes">
        {PIPELINE_STATES.map((step, idx) => (
          <React.Fragment key={step.key}>
            <div className={getStepClass(step.key)}>
              <span>{step.icon}</span>
              <span>{step.label}</span>
              {step.key === "replanning" && replanCount > 0 && (
                <span style={{ fontSize: "10px", padding: "1px 5px", background: "rgba(245, 158, 11, 0.3)", borderRadius: "4px" }}>
                  x{replanCount}
                </span>
              )}
            </div>
            {idx < PIPELINE_STATES.length - 1 && (
              <span className="timeline-arrow">&rarr;</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
