"""
Evaluation Harness for Multi-Agent Autonomous Customer Resolution System.
Runs 18 synthetic test cases covering happy paths, edge cases, disruption scenarios,
replanning loops, and strict policy guardrails.
Generates a complete benchmark report.
"""

import os
import json
import time
from datetime import datetime
from typing import Any, Dict, List
from backend.database import seed_db
from backend.orchestrator import create_case_from_email, run_case_to_completion

TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "benchmark_report.json")


def run_evaluation() -> Dict[str, Any]:
    """
    Execute all benchmark test cases and compile pass/fail report.
    """
    if not os.path.exists(TEST_CASES_PATH):
        raise FileNotFoundError(f"Test cases file not found at {TEST_CASES_PATH}")

    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        test_cases: List[Dict[str, Any]] = json.load(f)

    results = []
    passed_count = 0
    total_latency = 0.0

    print("=" * 70)
    print("STARTING AUTONOMOUS CUSTOMER RESOLUTION EVALUATION HARNESS")
    print(f"Total Synthetic Cases: {len(test_cases)}")
    print("=" * 70)

    for i, tc in enumerate(test_cases, 1):
        # 1. Reset database to fresh known state for each test
        seed_db(force=True)

        tc_id = tc.get("id", f"TC-{i:02d}")
        tc_name = tc.get("name", "Unnamed Case")
        print(f"[{i}/{len(test_cases)}] Running {tc_id}: {tc_name}...", end=" ", flush=True)

        start_time = time.time()
        try:
            email_record = {
                "sender_email": tc["sender_email"],
                "subject": tc["subject"],
                "body": tc["body"]
            }

            case = create_case_from_email(email_record)
            completed_case = run_case_to_completion(case)
            elapsed = time.time() - start_time
            total_latency += elapsed

            # Assertions
            expected_outcome = tc.get("expected_outcome")
            actual_outcome = "escalated" if completed_case.final_outcome == "escalated" else "resolved"

            outcome_match = (expected_outcome == actual_outcome)
            replan_check = True
            if tc.get("expect_replan"):
                replan_check = (completed_case.replan_count >= 1)

            chained_check = True
            if tc.get("expect_chained_failure"):
                chained_check = (len(completed_case.execution_history) >= 2 and actual_outcome == "escalated")

            email_sent = (completed_case.reply_email is not None and completed_case.reply_email.sent)
            threading_ok = (completed_case.reply_email is not None and completed_case.reply_email.subject.startswith("Re:"))

            passed = outcome_match and replan_check and chained_check and email_sent and threading_ok

            if passed:
                passed_count += 1
                print(f"PASSED ({elapsed:.2f}s)")
            else:
                print(f"FAILED ({elapsed:.2f}s)")
                print(f"   -> Expected: {expected_outcome}, Actual: {actual_outcome}")
                if not replan_check:
                    print(f"   -> Failed replan assertion (replans: {completed_case.replan_count})")
                if not email_sent:
                    print("   -> Outbound email was not sent")

            results.append({
                "id": tc_id,
                "name": tc_name,
                "passed": passed,
                "elapsed_seconds": round(elapsed, 3),
                "expected_outcome": expected_outcome,
                "actual_outcome": actual_outcome,
                "replan_count": completed_case.replan_count,
                "execution_attempts": len(completed_case.execution_history),
                "final_outcome": completed_case.final_outcome,
                "escalation_reason": completed_case.escalation_reason,
                "reply_sent": email_sent,
                "reply_subject": completed_case.reply_email.subject if completed_case.reply_email else None
            })

        except Exception as e:
            elapsed = time.time() - start_time
            total_latency += elapsed
            print(f"ERROR ({elapsed:.2f}s): {e}")
            results.append({
                "id": tc_id,
                "name": tc_name,
                "passed": False,
                "elapsed_seconds": round(elapsed, 3),
                "error": str(e)
            })

    total = len(test_cases)
    pass_rate = round((passed_count / total) * 100, 1)
    avg_latency = round(total_latency / total, 3)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": total,
        "passed_cases": passed_count,
        "failed_cases": total - passed_count,
        "pass_rate_percentage": pass_rate,
        "average_latency_seconds": avg_latency,
        "results": results
    }

    print("=" * 70)
    print(f"EVALUATION COMPLETE: {passed_count}/{total} Passed ({pass_rate}%)")
    print(f"Average Latency: {avg_latency}s per case")
    print("=" * 70)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    run_evaluation()
