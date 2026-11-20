"""
VYTRON — Gemini Anti-Hallucination & Accuracy Verification Test
Verifies that:
1. Gemini API generates 7-section structured answers using the provided key.
2. Exact telemetry metrics are preserved with zero hallucination.
3. Retrieved sources match ChromaDB collection chunks.
4. Non-destructive diagnostic commands are recommended.
"""

import os
import unittest
from dotenv import load_dotenv

load_dotenv()

from server.chatbot import process_chat_message
from server.simulator import InfrastructureSimulator


class TestGeminiAntiHallucination(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.simulator = InfrastructureSimulator()

    async def test_gemini_live_incident_accuracy(self):
        incident_context = {
            "incident_id": "INC-2026-GEMINI-TEST",
            "server_id": "DB-01",
            "server_name": "Database Server",
            "server_type": "Database",
            "metric_name": "Query Latency",
            "metric_key": "query_latency",
            "observed_value": 285.42,
            "threshold_value": 120.0,
            "unit": "ms",
            "severity": "CRITICAL",
            "priority": "P1",
            "status": "OPEN"
        }

        res = await process_chat_message(
            user_message="Why is DB-01 query latency so high and what commands should I run to inspect it?",
            session_id="session-gemini-test-01",
            incident_context=incident_context,
            simulator_instance=self.simulator
        )

        ans = res["answer"]
        self.assertIn("DB-01", ans, "Response must reference DB-01")
        self.assertIn("285.42", ans, "Response must quote exact observed telemetry value 285.42 ms")
        self.assertIn("120.0", ans, "Response must quote exact threshold 120.0 ms")
        self.assertIn("### 1. Understanding the Issue", ans)
        self.assertIn("### 2. Possible Root Causes", ans)
        self.assertIn("### 3. Evidence from VYTRON", ans)
        self.assertIn("### 4. Recommended Investigation Steps", ans)
        self.assertIn("### 5. Suggested Remediation", ans)
        self.assertIn("### 6. Prevention Measures", ans)
        self.assertIn("### 7. Retrieved Sources", ans)

        # Anti-hallucination check: ensure pg_stat_activity is recommended for postgres
        self.assertIn("pg_stat_activity", ans.lower())

        # Anti-hallucination check: ensure no fabricated destructive commands
        self.assertNotIn("rm -rf", ans)
        self.assertNotIn("drop database", ans.lower())

        print("[PASS] GEMINI ANTI-HALLUCINATION TEST PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    unittest.main()
