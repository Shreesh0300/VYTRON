"""
Verification Suite for VYTRON Egress Proof & Privacy Audit Feature
Tests actual collector.db integration, API endpoints, safe secret masking, and frontend serving.
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
from server.app import app

def run_egress_tests():
    print("=" * 75)
    print("VYTRON EGRESS PROOF & PRIVACY AUDIT — VERIFICATION SUITE")
    print("=" * 75)

    client = TestClient(app)

    # ── Test 1: Egress Statistics from collector.db ──────────────────────
    print("\n[Test 1] Testing /api/egress/stats with real collector.db data...")
    r_stats = client.get("/api/egress/stats")
    assert r_stats.status_code == 200, f"Expected 200, got {r_stats.status_code}"
    stats = r_stats.json()
    print("  Stats returned:", stats)

    # Actual data checks (no hardcoded zero values)
    assert stats["payloads_sent"] > 0, "payloads_sent should be > 0"
    assert stats["pending_transfers"] > 0, "pending_transfers should be > 0"
    assert stats["total_audits"] > 1000, "total_audits should reflect collector.db records"
    assert stats["sensitive_fields_blocked"] > 0, "sensitive_fields_blocked should be > 0"
    assert "Strict Allow-List" in stats["trust_boundary"]
    print("  ✓ Egress statistics verified: Real live data loaded from collector.db.")

    # ── Test 2: Payload Audit Records ────────────────────────────────────
    print("\n[Test 2] Testing /api/egress records query & prioritization...")
    r_records = client.get("/api/egress?limit=25")
    assert r_records.status_code == 200
    records = r_records.json()
    assert len(records) > 0, "Expected audit records"
    
    # Verify redacted records appear first for demonstration impact
    first_record = records[0]
    print(f"  First audit record: {first_record['payload_id']} ({first_record['policy_result']}, blocked: {first_record['blocked_count']})")
    assert first_record["policy_result"] == "redacted", "Redacted audit should be prioritized on top"
    assert first_record["blocked_count"] > 0, "Top record should demonstrate blocked fields"

    # Verify server filtering
    r_filtered = client.get("/api/egress?limit=10&server=AUTH-01")
    assert r_filtered.status_code == 200
    for r in r_filtered.json():
        assert r["server_id"] == "AUTH-01", f"Expected AUTH-01, got {r['server_id']}"
    print("  ✓ Audit trail verified: Proper structure, sorting, and server filtering.")

    # ── Test 3: Before vs After Comparison & Zero Secret Leakage ─────────
    print("\n[Test 3] Testing /api/egress/{payload_id} Before vs After & safe secret masking...")
    target_pid = first_record["payload_id"]
    r_detail = client.get(f"/api/egress/{target_pid}")
    assert r_detail.status_code == 200
    detail = r_detail.json()

    print("  Detail payload ID:", detail["payload_id"])
    print("  Approved fields:", detail["approved_fields"])
    print("  Blocked fields:", detail["blocked_fields"])

    # Verify blocked fields
    assert "metadata.password" in detail["blocked_fields"]
    assert "metadata.api_key" in detail["blocked_fields"]

    # Verify ZERO password or API key exists in outgoing approved payload
    outgoing_str = detail["outgoing_serialized_json"].lower()
    assert "hackathonpassword" not in outgoing_str, "CRITICAL: Plaintext password leaked in outgoing payload!"
    assert "sk-secret-key" not in outgoing_str, "CRITICAL: Plaintext API key leaked in outgoing payload!"
    assert "supersecrettoken" not in outgoing_str, "CRITICAL: Plaintext raw token leaked in outgoing payload!"

    # Verify safe masking in the Before raw display view
    raw_str = str(detail["raw_original_telemetry"]).lower()
    assert "hackathonpassword" not in raw_str, "CRITICAL: Plaintext password exposed in Before viewer!"
    assert "sk-secret-key" not in raw_str, "CRITICAL: Plaintext API key exposed in Before viewer!"
    assert "blocked_secret" in raw_str or "••••••••" in raw_str, "Secrets should be safely masked in Before viewer"

    # Verify field classifications (green vs red)
    classifications = {item["field"]: item["classification"] for item in detail["field_analysis"]}
    assert classifications.get("metadata.password") == "blocked"
    assert classifications.get("payload_id") == "allowed"

    print("  ✓ Before vs After verified: Zero raw secrets exposed; strict allow-list enforcement validated.")

    # ── Test 4: Frontend HTML, CSS, and JS Serving ───────────────────────
    print("\n[Test 4] Testing Frontend Egress Proof Serving...")
    # Main dashboard with Egress Proof tab
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "Egress Proof &amp; Privacy Audit" in r_index.text
    assert "data-flow-container" in r_index.text
    assert "code-comparison-grid" in r_index.text
    assert "egress.js" in r_index.text

    # Dedicated egress.html page
    r_egress_page = client.get("/egress.html")
    assert r_egress_page.status_code == 200
    assert "TIER 1 TRUST BOUNDARY" in r_egress_page.text
    assert "egressAuditTbody" in r_egress_page.text

    # Egress CSS and JS
    r_css = client.get("/css/egress.css")
    assert r_css.status_code == 200
    r_js = client.get("/js/egress.js")
    assert r_js.status_code == 200

    print("  ✓ Frontend assets verified: Integrated tab, dedicated egress.html, CSS and JS properly served.")

    print("\n" + "=" * 75)
    print("ALL EGRESS PROOF TESTS PASSED! Real data verified with zero secret leaks.")
    print("=" * 75)

if __name__ == "__main__":
    run_egress_tests()
