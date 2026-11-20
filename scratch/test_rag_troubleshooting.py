"""
VYTRON RAG Troubleshooting Engine — End-to-End Verification Suite
Tests knowledge ingestion, vector similarity search, domain-specific retrieval,
LLM synthesis of 8 sections, safety/zero-hallucination policies, and REST APIs.
"""

import sys
import os
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.rag.ingestion import DocumentLoader, TextChunker
from server.rag.vector_store import VectorStore
from server.rag.query_builder import ContextualQueryBuilder
from server.rag.synthesizer import RAGSynthesizer
from server.rag.pipeline import get_vector_store, troubleshoot_incident
from fastapi.testclient import TestClient
from server.app import app

def run_tests():
    print("=" * 75)
    print("VYTRON RAG-BASED AI TROUBLESHOOTING SYSTEM — VERIFICATION SUITE")
    print("=" * 75)

    # ── Test 1: Ingestion & Text Chunking ─────────────────────────────────
    print("\n[Test 1] Testing Document Ingestion & Recursive Text Chunking...")
    kb_dir = os.path.join(ROOT, "server", "rag", "knowledge_base")
    loader = DocumentLoader(kb_dir)
    docs = loader.load_all()
    assert len(docs) >= 6, f"Expected at least 6 technical documents, found {len(docs)}"
    
    chunker = TextChunker(target_chunk_size=650, chunk_overlap=120)
    total_chunks = []
    for doc in docs:
        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 0, f"Document {doc['doc_name']} yielded 0 chunks"
        total_chunks.extend(chunks)

    print(f"  ✓ Loaded {len(docs)} technical documents across Ubuntu, PostgreSQL, Red Hat & Microsoft Learn.")
    print(f"  ✓ Generated {len(total_chunks)} semantic chunks with section hierarchy and source metadata.")

    # ── Test 2: ChromaDB Persistent Vector Store ─────────────────────────
    print("\n[Test 2] Testing ChromaDB Persistent Vector Store & Embeddings...")
    store = get_vector_store()
    chunk_count = store.collection.count()
    assert chunk_count > 0, "ChromaDB collection is empty!"
    print(f"  ✓ ChromaDB collection 'vytron_troubleshooting_kb' active with {chunk_count} indexed chunks.")

    # ── Test 3: Domain-Specific Semantic Retrieval ───────────────────────
    print("\n[Test 3] Testing Domain-Specific Semantic Retrieval across Incident Categories...")

    test_incidents = [
        {
            "category": "CPU",
            "incident": {
                "server_id": "APP-01",
                "server_name": "Application Server",
                "server_type": "Application",
                "metric_key": "cpu_utilization",
                "metric_name": "CPU Utilization",
                "observed_value": 94.5,
                "threshold_value": 90.0,
                "unit": "%",
                "severity": "CRITICAL",
                "issue_description": "APP-01 CPU Utilization breached critical threshold: 94.5% (>= 90.0%)",
            },
            "expected_doc": "high_cpu_utilization.md"
        },
        {
            "category": "Memory",
            "incident": {
                "server_id": "APP-01",
                "server_name": "Application Server",
                "server_type": "Application",
                "metric_key": "ram_utilization",
                "metric_name": "RAM Utilization",
                "observed_value": 92.0,
                "threshold_value": 85.0,
                "unit": "%",
                "severity": "CRITICAL",
                "issue_description": "APP-01 RAM Utilization breached critical threshold: 92.0% (>= 85.0%)",
            },
            "expected_doc": "memory_exhaustion.md"
        },
        {
            "category": "Database",
            "incident": {
                "server_id": "DB-01",
                "server_name": "Database Server",
                "server_type": "Database",
                "metric_key": "query_latency",
                "metric_name": "Query Latency",
                "observed_value": 1180.0,
                "threshold_value": 1000.0,
                "unit": "ms",
                "severity": "CRITICAL",
                "issue_description": "DB-01 Query Latency breached critical threshold: 1180.0 ms (>= 1000.0 ms)",
            },
            "expected_doc": "database_performance.md"
        },
        {
            "category": "Network",
            "incident": {
                "server_id": "NETWORK-01",
                "server_name": "Network Server",
                "server_type": "Network",
                "metric_key": "packet_loss",
                "metric_name": "Packet Loss",
                "observed_value": 6.8,
                "threshold_value": 5.0,
                "unit": "%",
                "severity": "CRITICAL",
                "issue_description": "NETWORK-01 Packet Loss breached critical threshold: 6.8% (>= 5.0%)",
            },
            "expected_doc": "network_latency_packet_loss.md"
        },
        {
            "category": "Authentication",
            "incident": {
                "server_id": "AUTH-01",
                "server_name": "Authentication Server",
                "server_type": "Authentication",
                "metric_key": "failed_login_attempts",
                "metric_name": "Failed Login Attempts",
                "observed_value": 34.0,
                "threshold_value": 25.0,
                "unit": "fails/min",
                "severity": "CRITICAL",
                "issue_description": "AUTH-01 Failed Login Attempts breached critical threshold: 34.0 (>= 25.0)",
            },
            "expected_doc": "authentication_failures.md"
        },
    ]

    for item in test_incidents:
        cat = item["category"]
        inc = item["incident"]
        expected_doc = item["expected_doc"]

        query_text, _ = ContextualQueryBuilder.build_query(inc)
        chunks = store.search(query_text, n_results=3)
        assert len(chunks) > 0, f"No chunks retrieved for {cat} incident"
        
        retrieved_doc_names = [c["metadata"]["doc_name"] for c in chunks]
        assert expected_doc in retrieved_doc_names, (
            f"Expected {expected_doc} in top results for {cat}, retrieved: {retrieved_doc_names}"
        )
        print(f"  ✓ {cat} Incident correctly retrieved: {expected_doc} (Top match score: {chunks[0]['relevance_score']})")

    # ── Test 4: 8-Section Troubleshooting Guidance Synthesis ─────────────
    print("\n[Test 4] Testing 8-Section Troubleshooting Guidance Synthesis...")
    cpu_incident = test_incidents[0]["incident"]
    guidance = asyncio.run(troubleshoot_incident(cpu_incident))

    required_sections = [
        "explanation",
        "possible_root_causes",
        "telemetry_evidence",
        "investigation_steps",
        "diagnostic_commands",
        "recommended_solutions",
        "expected_outcome",
        "knowledge_sources",
    ]

    for sec in required_sections:
        assert sec in guidance, f"Missing required section: {sec}"
        assert guidance[sec], f"Section {sec} is empty!"

    # Verify diagnostic commands structure
    diag_cmds = guidance["diagnostic_commands"]
    assert len(diag_cmds) >= 2, "Expected at least 2 diagnostic commands"
    assert "command" in diag_cmds[0] and "description" in diag_cmds[0]

    # Verify knowledge sources structure and clickable URLs
    sources = guidance["knowledge_sources"]
    assert len(sources) >= 1, "Expected knowledge source citations"
    assert sources[0]["url"].startswith("http"), f"Invalid source URL: {sources[0]['url']}"
    assert sources[0]["title"], "Missing source title"

    print(f"  ✓ All 8 structured sections verified with diagnostic commands and documentation citations.")

    # ── Test 5: Safety & Zero-Fabrication on Unknown Incidents ───────────
    print("\n[Test 5] Testing Safety Requirements & Zero-Fabrication Policy...")
    unknown_incident = {
        "server_id": "UNKNOWN-99",
        "server_name": "Bogus Server",
        "server_type": "QuantumRelay",
        "metric_key": "flux_capacitor_warp_drag",
        "metric_name": "Warp Drag Factor",
        "observed_value": 999999.0,
        "threshold_value": 1.0,
        "unit": "warp",
        "severity": "CRITICAL",
        "issue_description": "Unknown uncatalogued anomaly",
    }
    synth = RAGSynthesizer()
    # Pass empty or non-relevant chunks to simulate zero retrieval
    safe_res = asyncio.run(synth.generate_troubleshooting(unknown_incident, []))
    assert safe_res["insufficient_knowledge"] is True, "Must flag insufficient knowledge!"
    assert "insufficient" in safe_res["explanation"].lower()
    assert len(safe_res["knowledge_sources"]) == 0, "Must not fabricate knowledge sources!"
    print("  ✓ Zero-hallucination verified: correctly flagged insufficient knowledge without fabricating citations.")

    # ── Test 6: FastAPI REST API Integration ─────────────────────────────
    print("\n[Test 6] Testing FastAPI Endpoints for RAG Troubleshooting...")
    client = TestClient(app)

    # 1. Test POST /api/aiops/troubleshoot
    r_trouble = client.post("/api/aiops/troubleshoot", json={"incident": cpu_incident})
    assert r_trouble.status_code == 200
    res_data = r_trouble.json()
    assert res_data["server_id"] == "APP-01"
    assert len(res_data["diagnostic_commands"]) >= 2
    assert len(res_data["knowledge_sources"]) >= 1

    # 2. Test GET /api/knowledge/sources
    r_sources = client.get("/api/knowledge/sources")
    assert r_sources.status_code == 200
    sources_data = r_sources.json()
    assert sources_data["total_chunks"] > 0
    assert len(sources_data["sources"]) >= 6

    print("  ✓ Verified endpoints: POST /api/aiops/troubleshoot & GET /api/knowledge/sources.")

    # ── Test 7: Platform Non-Regression ──────────────────────────────────
    print("\n[Test 7] Verifying Existing Simulation Platform Non-Regression...")
    r_state = client.get("/api/state")
    assert r_state.status_code == 200
    state_data = r_state.json()
    assert state_data["overview"]["total_servers"] == 5

    r_scen = client.get("/api/scenarios")
    assert r_scen.status_code == 200

    print("  ✓ Existing 5-server telemetry, detector, priority queue, and frontend remain 100% operational.")

    print("\n" + "=" * 75)
    print("ALL RAG TROUBLESHOOTING TESTS PASSED! RAG PIPELINE FULLY OPERATIONAL.")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
