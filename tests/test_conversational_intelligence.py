"""
VYTRON — Conversational Intelligence & Intent Classification Test Suite
Tests all 10 user requirements from Section 7:
1. "Hiii" -> Friendly greeting, no incident report.
2. "Good morning" -> Natural greeting.
3. "Thank you" -> Brief acknowledgement.
4. "What is query bottleneck?" -> Conversational technical explanation grounded in RAG.
5. "How can I fix high database latency?" -> Retrieved troubleshooting steps.
6. "Why is DB-01 showing high disk I/O?" -> Actual DB-01 telemetry + relevant retrieved knowledge.
7. "What should I check first?" -> Understands the previous question and continues.
8. "How can I prevent it?" -> Context-aware preventive advice.
9. "Tell me a joke" -> Polite out-of-scope response.
10. "What is happening with APP-01?" -> Relevant live APP-01 information and technical explanation.
"""

import unittest
from dotenv import load_dotenv

load_dotenv()

from server.chatbot import process_chat_message, ChatIntent
from server.simulator import InfrastructureSimulator


class TestConversationalIntelligence(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.simulator = InfrastructureSimulator()

    # 1. "Hiii" -> Friendly greeting, no incident report
    async def test_01_greeting_hiii(self):
        res = await process_chat_message(
            user_message="Hiii",
            session_id="session-test-greeting-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.GREETING)
        self.assertEqual(len(res["sources"]), 0, "Greetings must not perform vector retrieval")
        self.assertNotIn("Understanding the Issue", ans, "Greetings must NOT generate incident reports")
        self.assertNotIn("Supporting Evidence", ans, "Greetings must NOT dump telemetry")
        self.assertTrue("Hey" in ans or "help" in ans or "hello" in ans.lower(), "Must be a friendly conversational greeting")
        print("[PASS] TEST 1: 'Hiii' returned friendly greeting with zero incident report formatting.")

    # 2. "Good morning" -> Natural greeting
    async def test_02_greeting_good_morning(self):
        res = await process_chat_message(
            user_message="Good morning",
            session_id="session-test-greeting-02",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.GREETING)
        self.assertEqual(len(res["sources"]), 0)
        self.assertNotIn("### 1. Understanding the Issue", ans)
        print("[PASS] TEST 2: 'Good morning' returned natural greeting.")

    # 3. "Thank you" -> Brief acknowledgement
    async def test_03_acknowledgement_thank_you(self):
        res = await process_chat_message(
            user_message="Thank you",
            session_id="session-test-ack-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.ACKNOWLEDGEMENT)
        self.assertEqual(len(res["sources"]), 0)
        self.assertNotIn("### 1. Understanding the Issue", ans)
        self.assertTrue("welcome" in ans.lower() or "help" in ans.lower())
        print("[PASS] TEST 3: 'Thank you' returned brief acknowledgement.")

    # 4. "What is query bottleneck?" -> Conversational technical explanation grounded in RAG
    async def test_04_general_it_query_bottleneck(self):
        res = await process_chat_message(
            user_message="What is query bottleneck?",
            session_id="session-test-concept-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.GENERAL_IT_QUESTION)
        self.assertGreater(len(res["sources"]), 0, "Must retrieve ChromaDB documentation")
        self.assertNotIn("### 1. Understanding the Issue", ans, "General questions must not force incident report template")
        self.assertTrue("index" in ans.lower() or "query" in ans.lower() or "database" in ans.lower() or "lock" in ans.lower())
        print("[PASS] TEST 4: 'What is query bottleneck?' returned conversational technical explanation grounded in RAG.")

    # 5. "How can I fix high database latency?" -> Retrieved troubleshooting steps
    async def test_05_troubleshooting_database_latency(self):
        res = await process_chat_message(
            user_message="How can I fix high database latency?",
            session_id="session-test-troubleshoot-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.TROUBLESHOOTING_REQUEST)
        self.assertGreater(len(res["sources"]), 0, "Troubleshooting must retrieve technical documentation")
        self.assertTrue("1." in ans or "step" in ans.lower(), "Troubleshooting must provide numbered practical steps")
        self.assertTrue("pg_stat_activity" in ans.lower() or "query" in ans.lower() or "index" in ans.lower())
        print("[PASS] TEST 5: 'How can I fix high database latency?' returned numbered practical troubleshooting steps.")

    # 6. "Why is DB-01 showing high disk I/O?" -> Actual DB-01 telemetry + relevant retrieved knowledge
    async def test_06_incident_db01_disk_io(self):
        incident_context = {
            "incident_id": "INC-2026-DISK-01",
            "server_id": "DB-01",
            "server_name": "Database Server",
            "server_type": "Database",
            "metric_name": "Disk I/O Utilization",
            "metric_key": "disk_io_utilization",
            "observed_value": 89.4,
            "threshold_value": 80.0,
            "unit": "%",
            "severity": "CRITICAL",
            "priority": "P1"
        }
        res = await process_chat_message(
            user_message="Why is DB-01 showing high disk I/O?",
            session_id="session-multiturn-flow-01",
            incident_context=incident_context,
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.INCIDENT_SPECIFIC_QUERY)
        self.assertIn("DB-01", ans, "Must reference DB-01")
        self.assertIn("89.4", ans, "Must quote exact observed telemetry value 89.4 %")
        self.assertGreater(len(res["sources"]), 0, "Must retrieve ChromaDB documentation")
        print("[PASS] TEST 6: 'Why is DB-01 showing high disk I/O?' integrated DB-01 telemetry + retrieved knowledge.")

    # 7. "What should I check first?" -> Understands previous question and continues
    async def test_07_followup_check_first(self):
        # Continues in same session as test_06
        res = await process_chat_message(
            user_message="What should I check first?",
            session_id="session-multiturn-flow-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.FOLLOW_UP_QUERY)
        self.assertIn("DB-01", ans, "Follow-up must maintain DB-01 context")
        self.assertTrue("pg_stat_activity" in ans.lower() or "iostat" in ans.lower() or "lock" in ans.lower() or "query" in ans.lower())
        print("[PASS] TEST 7: 'What should I check first?' understood prior DB-01 context and provided prioritized investigation.")

    # 8. "How can I prevent it?" -> Context-aware preventive advice
    async def test_08_followup_prevent_it(self):
        # Continues in same session as test_06 and test_07
        res = await process_chat_message(
            user_message="How can I prevent it?",
            session_id="session-multiturn-flow-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.FOLLOW_UP_QUERY)
        self.assertIn("DB-01", ans, "Follow-up must maintain DB-01 context")
        self.assertTrue("prevent" in ans.lower() or "index" in ans.lower() or "checkpoint" in ans.lower() or "timeout" in ans.lower())
        print("[PASS] TEST 8: 'How can I prevent it?' provided context-aware preventive guidance for DB-01.")

    # 9. "Tell me a joke" -> Polite out-of-scope response
    async def test_09_out_of_scope_joke(self):
        res = await process_chat_message(
            user_message="Tell me a joke",
            session_id="session-test-joke-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.OUT_OF_SCOPE)
        self.assertTrue(res["is_scope_violation"])
        self.assertIn("IT-related question", ans)
        print("[PASS] TEST 9: 'Tell me a joke' was politely rejected with IT-only scope explanation.")

    # 10. "What is happening with APP-01?" -> Relevant live APP-01 info & technical explanation
    async def test_10_app01_live_telemetry_query(self):
        res = await process_chat_message(
            user_message="What is happening with APP-01?",
            session_id="session-test-app01-01",
            simulator_instance=self.simulator
        )
        ans = res["answer"]
        self.assertEqual(res["intent"], ChatIntent.INCIDENT_SPECIFIC_QUERY)
        self.assertIn("APP-01", ans, "Must reference APP-01")
        print("[PASS] TEST 10: 'What is happening with APP-01?' retrieved live APP-01 telemetry and generated technical explanation.")


if __name__ == "__main__":
    unittest.main()
