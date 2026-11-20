"""
VYTRON — RAG Accuracy, Evidence Validation & Root Cause Analysis Test Suite
Validates 10 critical operational areas:
TEST 1: Telemetry consistency (single source of truth, exact value propagation)
TEST 2: Root cause evidence (evidence-based hypotheses, missing evidence, no unverified claims)
TEST 3: Authentication troubleshooting (AUTH-01 specific procedures and auth commands)
TEST 4: Database troubleshooting (DB-01 specific procedures and psql commands)
TEST 5: Network troubleshooting (NETWORK-01 specific procedures and interface commands)
TEST 6: Documentation citations (real titles and URLs from ChromaDB)
TEST 7: Missing evidence handling ('Not available' when unrecorded)
TEST 8: Low retrieval relevance (safety gate: 'Insufficient relevant documentation found')
TEST 9: Multi-server compatibility (APP-01, DB-01, AUTH-01, BACKUP-01, NETWORK-01)
TEST 10: Existing functionality regression (detection, incident manager, prioritization, resolution)
"""

import sys
import os
import asyncio
import traceback

# Ensure server package is discoverable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.config import SERVERS_CONFIG
from server.detector import ThresholdDetector
from server.incident_manager import IncidentManager
from server.rag.synthesizer import RAGSynthesizer, INSUFFICIENT_KNOWLEDGE_NOTICE
from server.rag.vector_store import VectorStore


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Telemetry Consistency
# ══════════════════════════════════════════════════════════════════════════════
async def test_1_telemetry_consistency():
    """
    TEST 1: Create an incident with known metric value.
    Verify every displayed occurrence in the RAG report matches the original incident data.
    Ensures observed_value, threshold_value, and issue signature never conflict.
    """
    synthesizer = RAGSynthesizer()
    known_val = 64.36
    known_thresh = 25.0
    incident = {
        "incident_id": "INC-2026-0042",
        "server_id": "AUTH-01",
        "server_name": "Authentication Server",
        "server_type": "Authentication",
        "metric_key": "failed_login_attempts",
        "metric_name": "Failed Login Attempts",
        "observed_value": known_val,
        "threshold_value": known_thresh,
        "warning_threshold": 15.0,
        "critical_threshold": 25.0,
        "unit": "fails/min",
        "severity": "CRITICAL",
        "priority": "P1",
        "direction": "above",
        "created_at_str": "14:23:05",
        "issue_description": f"AUTH-01 Failed Login Attempts breached critical threshold: {known_val} fails/min (>= {known_thresh} fails/min)",
    }

    report = await synthesizer.generate_troubleshooting(incident, [])

    # 1. Explanation must contain exact observed value
    assert str(known_val) in report["explanation"], f"Expected {known_val} in explanation"
    assert str(known_thresh) in report["explanation"], f"Expected {known_thresh} in explanation"

    # 2. Telemetry evidence must contain exact observed value
    evidence_str = " ".join(report["telemetry_evidence"])
    assert str(known_val) in evidence_str, f"Expected {known_val} in telemetry evidence"
    assert str(known_thresh) in evidence_str, f"Expected {known_thresh} in telemetry evidence"
    assert "INC-2026-0042" in evidence_str
    assert "AUTH-01" in evidence_str

    # 3. Issue signature in evidence must match observed value exactly
    signature_entry = next((e for e in report["telemetry_evidence"] if "Issue Signature:" in e), None)
    assert signature_entry is not None, "Missing Issue Signature in telemetry evidence"
    assert str(known_val) in signature_entry, f"Issue signature must contain observed value {known_val}"

    # 4. Root cause hypotheses must cite exact observed value as supporting evidence
    for hypo in report["possible_root_causes"]:
        if isinstance(hypo, dict):
            assert str(known_val) in hypo["evidence"], f"Hypothesis evidence must cite {known_val}"

    # 5. Incident Manager deduplication consistency check
    mgr = IncidentManager()
    breach1 = {
        "server_id": "AUTH-01",
        "server_name": "Authentication Server",
        "server_type": "Authentication",
        "metric_key": "failed_login_attempts",
        "metric_name": "Failed Login Attempts",
        "observed_value": 36.27,
        "threshold_value": 15.0,
        "breach_level": "warning",
        "unit": "fails/min",
        "severity": "MEDIUM",
        "priority": "P3",
        "direction": "above",
    }
    inc = mgr.process_breach(breach1)
    assert inc["observed_value"] == 36.27
    assert "36.27" in inc["issue_description"]

    # Deduplicate with new reading
    breach2 = {
        "server_id": "AUTH-01",
        "server_name": "Authentication Server",
        "server_type": "Authentication",
        "metric_key": "failed_login_attempts",
        "metric_name": "Failed Login Attempts",
        "observed_value": 64.36,
        "threshold_value": 25.0,
        "breach_level": "critical",
        "unit": "fails/min",
        "severity": "CRITICAL",
        "priority": "P1",
        "direction": "above",
    }
    updated_inc = mgr.process_breach(breach2)
    assert updated_inc["observed_value"] == 64.36
    assert "64.36" in updated_inc["issue_description"], "Updated incident description must reflect 64.36"
    assert "36.27" not in updated_inc["issue_description"], "Old 36.27 reading must NOT persist in issue description"
    return "Telemetry values consistent across explanation, evidence, signature, and manager deduplication."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Root Cause Evidence
# ══════════════════════════════════════════════════════════════════════════════
async def test_2_root_cause_evidence():
    """
    TEST 2: Verify root cause hypotheses are structured with:
    - hypothesis
    - why it could explain
    - supporting telemetry evidence
    - missing evidence needed to confirm
    - operator verification procedure
    Verify hypotheses are NOT presented as confirmed facts without evidence.
    """
    synthesizer = RAGSynthesizer()
    incident = {
        "incident_id": "INC-2026-0043",
        "server_id": "AUTH-01",
        "server_name": "Authentication Server",
        "server_type": "Authentication",
        "metric_key": "failed_login_attempts",
        "metric_name": "Failed Login Attempts",
        "observed_value": 55.0,
        "threshold_value": 25.0,
        "unit": "fails/min",
        "severity": "CRITICAL",
        "priority": "P1",
    }

    report = await synthesizer.generate_troubleshooting(incident, [])
    causes = report["possible_root_causes"]
    assert len(causes) >= 2, "Must generate at least 2 hypotheses"

    for c in causes:
        assert isinstance(c, dict), "Hypothesis must be a structured dictionary"
        assert "hypothesis" in c and len(c["hypothesis"]) > 5
        assert "why" in c and len(c["why"]) > 10
        assert "evidence" in c and "55.0" in c["evidence"]
        assert "missing_evidence" in c and len(c["missing_evidence"]) > 10
        assert "verification" in c and len(c["verification"]) > 10

        # Verify not claimed as absolute confirmed truth
        assert "confirmed" not in c["hypothesis"].lower()
    return f"{len(causes)} evidence-based hypotheses verified with why, evidence, missing evidence, and verification."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Authentication Troubleshooting
# ══════════════════════════════════════════════════════════════════════════════
async def test_3_auth_troubleshooting():
    """
    TEST 3: Verify authentication incidents receive relevant investigation steps
    and authentication-specific commands (auth.log, journalctl, ssh, ss auth ports).
    """
    synthesizer = RAGSynthesizer()
    incident = {
        "incident_id": "INC-2026-0044",
        "server_id": "AUTH-01",
        "server_name": "Authentication Server",
        "server_type": "Authentication",
        "metric_key": "failed_login_attempts",
        "metric_name": "Failed Login Attempts",
        "observed_value": 72.0,
        "threshold_value": 25.0,
        "unit": "fails/min",
        "severity": "CRITICAL",
        "priority": "P1",
    }

    report = await synthesizer.generate_troubleshooting(incident, [])

    # Procedures must be auth-specific
    steps_text = " ".join(report["investigation_steps"]).lower()
    assert "failed-login" in steps_text or "ip address" in steps_text or "identity provider" in steps_text

    # Diagnostic commands must be auth-specific
    commands = [c["command"] for c in report["diagnostic_commands"]]

    assert any("auth.log" in cmd or "ssh" in cmd or "auth-service" in cmd for cmd in commands)
    # Ensure commands are read-only (non-destructive)
    assert not any("kill" in cmd or "rm " in cmd or "reboot" in cmd for cmd in commands)
    return f"Auth-specific investigation steps and non-destructive commands verified ({len(commands)} commands)."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Database Troubleshooting
# ══════════════════════════════════════════════════════════════════════════════
async def test_4_database_troubleshooting():
    """
    TEST 4: Verify database incidents receive PostgreSQL-specific commands
    (psql, pg_stat_activity, pg_locks) and query investigation steps.
    """
    synthesizer = RAGSynthesizer()
    incident = {
        "incident_id": "INC-2026-0045",
        "server_id": "DB-01",
        "server_name": "Database Server",
        "server_type": "Database",
        "metric_key": "query_latency",
        "metric_name": "Query Latency",
        "observed_value": 1450.0,
        "threshold_value": 1000.0,
        "unit": "ms",
        "severity": "CRITICAL",
        "priority": "P1",
    }

    report = await synthesizer.generate_troubleshooting(incident, [])

    steps_text = " ".join(report["investigation_steps"]).lower()
    assert "pg_stat_activity" in steps_text or "query" in steps_text or "lock" in steps_text

    commands = [c["command"] for c in report["diagnostic_commands"]]
    assert any("psql" in cmd for cmd in commands), "Must provide PostgreSQL CLI diagnostic commands"
    assert any("pg_stat_activity" in cmd for cmd in commands), "Must inspect pg_stat_activity"
    return f"PostgreSQL psql and pg_stat_activity inspection commands verified ({len(commands)} commands)."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Network Troubleshooting
# ══════════════════════════════════════════════════════════════════════════════
async def test_5_network_troubleshooting():
    """
    TEST 5: Verify network incidents receive network-specific investigation steps
    and interface commands (ip -s link, ethtool, tc, netstat -s).
    """
    synthesizer = RAGSynthesizer()
    incident = {
        "incident_id": "INC-2026-0046",
        "server_id": "NETWORK-01",
        "server_name": "Network Server",
        "server_type": "Network",
        "metric_key": "packet_loss",
        "metric_name": "Packet Loss",
        "observed_value": 5.4,
        "threshold_value": 2.0,
        "unit": "%",
        "severity": "CRITICAL",
        "priority": "P1",
    }

    report = await synthesizer.generate_troubleshooting(incident, [])

    steps_text = " ".join(report["investigation_steps"]).lower()
    assert "packet" in steps_text or "interface" in steps_text or "ethtool" in steps_text

    commands = [c["command"] for c in report["diagnostic_commands"]]
    assert any("ethtool" in cmd or "ip -s link" in cmd or "netstat" in cmd for cmd in commands)
    return f"Network-specific commands (ethtool, ip -s link, netstat) verified ({len(commands)} commands)."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Documentation Citations
# ══════════════════════════════════════════════════════════════════════════════
async def test_6_documentation_citations():
    """
    TEST 6: Verify source titles and URLs originate from actual retrieved documents
    and avoid fabrication.
    """
    vs = VectorStore()
    results = vs.search("PostgreSQL query latency performance and locks", n_results=3)
    assert len(results) > 0, "Vector store must return search results"

    for r in results:
        meta = r.get("metadata", {})
        assert "title" in meta or "doc_name" in meta
        assert "url" in meta
        assert meta.get("url").startswith("http") or meta.get("url") == "#"
    return f"ChromaDB document citations verified ({len(results)} chunks validated)."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: Missing Evidence Handling
# ══════════════════════════════════════════════════════════════════════════════
async def test_7_missing_evidence_handling():
    """
    TEST 7: Verify the system explicitly reports 'Not available' for unrecorded
    or missing attributes instead of inventing values.
    """
    synthesizer = RAGSynthesizer()
    sparse_incident = {
        "incident_id": "INC-2026-0047",
        "server_id": "APP-01",
        "metric_key": "unknown_metric",
        "metric_name": "Custom Metric",
        "observed_value": None,
        "threshold_value": None,
        "warning_threshold": None,
        "critical_threshold": None,
        "created_at_str": None,
    }

    report = await synthesizer.generate_troubleshooting(sparse_incident, [])
    evidence = " ".join(report["telemetry_evidence"])

    assert "Not available" in evidence, "Missing fields must explicitly display 'Not available'"
    return "Explicit 'Not available' fallback verified for unrecorded telemetry fields."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8: Low Retrieval Relevance (Safety Gate)
# ══════════════════════════════════════════════════════════════════════════════
async def test_8_low_retrieval_relevance():
    """
    TEST 8: Verify low relevance (< 0.60) chunks are not presented as citations.
    The system must output the explicit fallback safety message:
    'Insufficient relevant documentation found. Recommendations are based only on available telemetry and general diagnostic knowledge.'
    and keep knowledge_sources empty.
    """
    synthesizer = RAGSynthesizer()
    incident = {
        "incident_id": "INC-2026-0048",
        "server_id": "APP-01",
        "server_name": "Application Server",
        "server_type": "Application",
        "metric_key": "cpu_utilization",
        "metric_name": "CPU Utilization",
        "observed_value": 94.2,
        "threshold_value": 90.0,
        "unit": "%",
        "severity": "CRITICAL",
        "priority": "P1",
    }

    # Simulate low relevance chunk (below 0.60 threshold)
    low_relevance_chunks = [
        {
            "chunk_id": "fake_1",
            "content": "Cooking recipe for chocolate chip cookies.",
            "metadata": {"title": "Cookie Guide", "url": "http://cookies.com"},
            "relevance_score": 0.35,
        }
    ]

    report = await synthesizer.generate_troubleshooting(incident, low_relevance_chunks)

    assert report["insufficient_knowledge"] is True
    assert INSUFFICIENT_KNOWLEDGE_NOTICE in report["explanation"]
    assert report["knowledge_sources"] == [], "Knowledge sources must be empty when below threshold"
    return "Safety gate correctly triggered; zero fabricated sources returned."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9: Multi-Server Compatibility
# ══════════════════════════════════════════════════════════════════════════════
async def test_9_multi_server_compatibility():
    """
    TEST 9: Verify RAG works for all 5 server categories:
    APP-01, DB-01, AUTH-01, BACKUP-01, NETWORK-01.
    """
    synthesizer = RAGSynthesizer()
    servers_to_test = [
        ("APP-01", "Application", "cpu_utilization", "CPU Utilization", 95.0, 90.0, "%"),
        ("DB-01", "Database", "active_connections", "Active Connections", 185.0, 180.0, "conns"),
        ("AUTH-01", "Authentication", "failed_login_attempts", "Failed Login Attempts", 45.0, 25.0, "fails/min"),
        ("BACKUP-01", "Backup", "backup_duration", "Backup Duration", 350.0, 300.0, "min"),
        ("NETWORK-01", "Network", "bandwidth_utilization", "Bandwidth Utilization", 96.0, 90.0, "%"),
    ]

    results = []
    for s_id, s_type, m_key, m_name, obs, thresh, unit in servers_to_test:
        inc = {
            "incident_id": f"INC-TEST-{s_id}",
            "server_id": s_id,
            "server_name": f"{s_type} Server",
            "server_type": s_type,
            "metric_key": m_key,
            "metric_name": m_name,
            "observed_value": obs,
            "threshold_value": thresh,
            "unit": unit,
            "severity": "CRITICAL",
            "priority": "P1",
        }

        report = await synthesizer.generate_troubleshooting(inc, [])
        assert report["server_id"] == s_id
        assert len(report["possible_root_causes"]) >= 1
        assert len(report["diagnostic_commands"]) >= 1
        assert len(report["investigation_steps"]) >= 1
        assert s_id in report["explanation"]
        results.append(s_id)
    return f"Successfully generated targeted guidance across all 5 servers: {', '.join(results)}."


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10: Existing Functionality Regression
# ══════════════════════════════════════════════════════════════════════════════
def test_10_existing_functionality_regression():
    """
    TEST 10: Verify detection, prioritization (P1 > P2 > P3 > P4), and auto-resolution
    continue functioning without breaking existing platform logic.
    """
    detector = ThresholdDetector(consecutive_required=1)
    mgr = IncidentManager()

    # Step A: Detect warning breach on DB-01 (warning threshold is 500.0 ms)
    status, breaches_warn, _ = detector.evaluate_server("DB-01", {
        "query_latency": 650.0,
        "active_connections": 35.0,
        "disk_io_utilization": 28.0,
        "cpu_utilization": 24.0,
    })
    assert len(breaches_warn) >= 1
    warn_breach = next(b for b in breaches_warn if b["metric_key"] == "query_latency")
    assert warn_breach["breach_level"] == "warning"
    assert warn_breach["priority"] == "P3"

    inc_warn = mgr.process_breach(warn_breach)
    assert inc_warn["priority"] == "P3"
    assert inc_warn["status"] == "OPEN"

    # Step B: Detect critical breach on DB-01 (critical threshold is 1000.0 ms)
    status, breaches_crit, _ = detector.evaluate_server("DB-01", {
        "query_latency": 1200.0,
        "active_connections": 35.0,
        "disk_io_utilization": 28.0,
        "cpu_utilization": 24.0,
    })
    crit_breach = next(b for b in breaches_crit if b["metric_key"] == "query_latency")
    assert crit_breach["breach_level"] == "critical"
    assert crit_breach["priority"] == "P1"

    inc_crit = mgr.process_breach(crit_breach)
    # Must upgrade in-place
    assert inc_crit["priority"] == "P1"
    assert inc_crit["observed_value"] == 1200.0
    assert "1200.0" in inc_crit["issue_description"]

    # Step C: Priority queue ordering check
    queue = mgr.get_priority_queue()
    assert len(queue) == 1
    assert queue[0]["priority"] == "P1"
    assert queue[0]["is_highest_priority"] is True

    # Step D: Auto-resolution when metrics normalize
    status, _, recoveries = detector.evaluate_server("DB-01", {
        "query_latency": 15.0,
        "active_connections": 35.0,
        "disk_io_utilization": 28.0,
        "cpu_utilization": 24.0,
    })
    assert "query_latency" in recoveries
    mgr.resolve_metric("DB-01", "query_latency")

    queue_after = mgr.get_priority_queue()
    assert len(queue_after) == 0, "Queue should be empty after resolution"
    return "Detection, P1-P4 escalation, priority queue, and auto-resolution regression verified."


# ══════════════════════════════════════════════════════════════════════════════
# Master Test Runner
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    print("=" * 78)
    print("VYTRON AIOps — 10 Automated RAG Accuracy & Root Cause Validation Tests")
    print("=" * 78)

    tests = [
        ("TEST 1: Telemetry Consistency", test_1_telemetry_consistency, True),
        ("TEST 2: Root Cause Evidence", test_2_root_cause_evidence, True),
        ("TEST 3: Authentication Troubleshooting", test_3_auth_troubleshooting, True),
        ("TEST 4: Database Troubleshooting", test_4_database_troubleshooting, True),
        ("TEST 5: Network Troubleshooting", test_5_network_troubleshooting, True),
        ("TEST 6: Documentation Citations", test_6_documentation_citations, True),
        ("TEST 7: Missing Evidence Handling", test_7_missing_evidence_handling, True),
        ("TEST 8: Low Retrieval Relevance (Safety Gate)", test_8_low_retrieval_relevance, True),
        ("TEST 9: Multi-Server Compatibility", test_9_multi_server_compatibility, True),
        ("TEST 10: Existing Functionality Regression", test_10_existing_functionality_regression, False),
    ]

    passed = 0
    failed = 0

    for name, test_fn, is_async in tests:
        try:
            if is_async:
                res_msg = await test_fn()
            else:
                res_msg = test_fn()
            print(f"[PASS] {name}")
            print(f"       -> {res_msg}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}")
            print(f"       Error: {e}")
            traceback.print_exc()
            failed += 1

    print("=" * 78)
    print(f"RESULTS: {passed} PASSED | {failed} FAILED | Total: {len(tests)}")
    print("=" * 78)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
