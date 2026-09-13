"""
Unit tests for Agent 6 (Policy RAG Agent).
Tests retrieval accuracy, confidence threshold guardrails, citation formatting,
and audit logging across standard policy scenarios and edge cases.
"""

import unittest
from backend.models import Agent6Output
from backend.database import seed_db, get_audit_trail
from backend.agents.agent6_policy_rag import run_agent6_policy_rag, _local_policy_search


class TestAgent6PolicyRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_db(force=True)
        from backend.database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO cases (case_id, customer_id, state) "
                "VALUES ('case_test_agent6_audit', 'cust_001', 'investigating')"
            )

    def test_standard_return_regular_customer(self):
        question = "What is the return window policy for a regular customer where delivery was 10 days ago?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Return Window Policy" in src for src in res.source_documents))
        self.assertTrue(any("30 days" in snip or "30-day" in snip or "30" in snip for snip in res.supporting_snippets + [res.answer]))
        self.assertGreaterEqual(len(res.supporting_snippets), 1)

    def test_premium_customer_extended_window(self):
        question = "What is the return and refund policy for a premium customer where delivery was 38 days ago?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Return Window Policy" in src for src in res.source_documents))
        self.assertTrue(any("Premium-Tier Extension" in src for src in res.source_documents))
        self.assertIn("45", res.answer)

    def test_damaged_defective_item_override(self):
        question = "What is the return and replacement policy for a regular customer where delivery was 50 days ago? What is the damaged or defective item policy?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Damaged and Defective Items Policy" in src for src in res.source_documents))
        self.assertIn("60", res.answer)

    def test_replacement_out_of_stock_fallback(self):
        question = "What is the fallback rule when a replacement SKU is out of stock?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Replacement Rules Policy" in src for src in res.source_documents))
        self.assertTrue(any("Stock-Dependent Fallback" in src for src in res.source_documents))
        self.assertTrue("fallback" in res.answer.lower() or "refund" in res.answer.lower() or "alternate" in res.answer.lower())

    def test_pre_shipment_cancellation(self):
        question = "Can a customer cancel an order if its status is placed?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Cancellation Rules Policy" in src for src in res.source_documents))
        self.assertTrue(any("Pre-Shipment Cancellation" in src for src in res.source_documents))

    def test_post_shipment_cancellation(self):
        question = "Can a customer cancel an order if its status is shipped?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Cancellation Rules Policy" in src for src in res.source_documents))
        self.assertTrue(any("Post-Shipment Cancellation" in src for src in res.source_documents))

    def test_non_returnable_final_sale_items(self):
        question = "What is the return and refund policy for a regular customer where delivery was 10 days ago? Is a personalized or final-sale item returnable?"
        res = run_agent6_policy_rag(question)

        self.assertIsInstance(res, Agent6Output)
        self.assertEqual(res.confidence, "high")
        self.assertTrue(any("Non-Returnable Items" in src for src in res.source_documents))

    def test_irrelevant_query_guardrail_low_confidence(self):
        nonsense_questions = [
            "What is the weather in Paris?",
            "Can I bring my pet dog to the moon?",
            "How do I bake a chocolate cake?",
        ]
        for q in nonsense_questions:
            res = run_agent6_policy_rag(q)
            self.assertEqual(res.confidence, "low", f"Expected low confidence for: {q}")
            self.assertEqual(res.supporting_snippets, [])
            self.assertEqual(res.source_documents, [])
            self.assertIn("No relevant company policy found with sufficient confidence", res.answer)

    def test_audit_logging_events(self):
        case_id = "case_test_agent6_audit"
        run_agent6_policy_rag("What is the standard return window?", case_id=case_id)

        trail = get_audit_trail(case_id)
        events = [log["event"] for log in trail if log.get("agent") == "Agent6PolicyRAG"]
        self.assertIn("pinecone_query", events)
        self.assertIn("policy_response", events)


if __name__ == "__main__":
    unittest.main()
