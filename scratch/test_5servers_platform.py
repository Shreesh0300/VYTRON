"""
End-to-End Verification Suite for VYTRON 5-Server Infrastructure Monitoring Platform
"""

import sys
import os

# Add root directory to sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.config import SERVERS_CONFIG, SCENARIOS_CONFIG
from server.simulator import InfrastructureSimulator
from fastapi.testclient import TestClient
from server.app import app

def run_tests():
    print("=" * 70)
    print("RUNNING VYTRON 5-SERVER PLATFORM VERIFICATION")
    print("=" * 70)

    # ── Test 1: Configuration Validation ─────────────────────────────────
    print("\n[Test 1] Validating 5-Server Configuration...")
    expected_servers = ["APP-01", "DB-01", "AUTH-01", "BACKUP-01", "NETWORK-01"]
    assert set(SERVERS_CONFIG.keys()) == set(expected_servers), "Server keys mismatch!"
    
    expected_params = {
        "APP-01": {"cpu_utilization", "ram_utilization", "requests_per_sec", "response_time"},
        "DB-01": {"query_latency", "active_connections", "disk_io_utilization", "cpu_utilization"},
        "AUTH-01": {"login_requests_per_sec", "failed_login_attempts", "auth_latency", "auth_success_rate"},
        "BACKUP-01": {"backup_progress", "data_transfer_rate", "backup_duration", "backup_failure_count"},
        "NETWORK-01": {"bandwidth_utilization", "network_latency", "packet_loss", "throughput"},
    }

    for sid, params in expected_params.items():
        actual_params = set(SERVERS_CONFIG[sid]["parameters"].keys())
        assert actual_params == params, f"Parameter mismatch for {sid}: {actual_params} != {params}"
    print("  ✓ All 5 servers and their 4 specific parameters verified.")

    # ── Test 2: Initial Normal Operation ─────────────────────────────────
    print("\n[Test 2] Testing Simulator Baseline & Normal Operation...")
    sim = InfrastructureSimulator()
    snapshot = sim.get_snapshot()

    assert snapshot["overview"]["total_servers"] == 5
    assert snapshot["overview"]["normal_count"] == 5
    assert snapshot["overview"]["warning_count"] == 0
    assert snapshot["overview"]["critical_count"] == 0
    assert snapshot["overview"]["active_incidents"] == 0
    assert snapshot["overview"]["highest_priority"] == "NONE"

    # Run 5 baseline ticks
    for _ in range(5):
        sim.tick()

    snap_after = sim.get_snapshot()
    assert snap_after["overview"]["normal_count"] == 5, "Baseline ticks should remain normal"
    assert len(snap_after["priority_queue"]) == 0, "No incidents should be triggered during baseline"
    print("  ✓ 5 servers operate normally with continuous baseline noise.")

    # ── Test 3: Scenario 01 (APP-01 & DB-01) ─────────────────────────────
    print("\n[Test 3] Testing Scenario 01: Application & Database Mutation...")
    sim.start_scenario("scenario_01")
    
    # Tick multiple times to allow consecutive breach confirmation
    for _ in range(4):
        sim.tick()

    snap_scen1 = sim.get_snapshot()
    assert snap_scen1["active_scenario"]["id"] == "scenario_01"
    
    # Affected servers: APP-01 and DB-01
    app_status = snap_scen1["servers"]["APP-01"]["status"]
    db_status = snap_scen1["servers"]["DB-01"]["status"]
    assert app_status in ("WARNING", "CRITICAL"), f"APP-01 status should be WARNING or CRITICAL, got {app_status}"
    assert db_status in ("WARNING", "CRITICAL"), f"DB-01 status should be WARNING or CRITICAL, got {db_status}"

    # Unaffected servers: AUTH-01, BACKUP-01, NETWORK-01 MUST remain NORMAL
    for unaffected_id in ["AUTH-01", "BACKUP-01", "NETWORK-01"]:
        un_status = snap_scen1["servers"][unaffected_id]["status"]
        assert un_status == "NORMAL", f"Server {unaffected_id} must remain NORMAL, but was {un_status}"
    print("  ✓ Exactly APP-01 & DB-01 affected. AUTH-01, BACKUP-01, NETWORK-01 remain baseline NORMAL.")

    # ── Test 4: Incident Deduplication & Priority Queue ──────────────────
    print("\n[Test 4] Testing Incident Deduplication & Strict P1-P4 Queue...")
    pq = snap_scen1["priority_queue"]
    assert len(pq) > 0, "Priority queue should contain active incidents"

    # Check deduplication: all (server_id, metric_key) pairs in pq must be unique
    seen_keys = set()
    for inc in pq:
        key = (inc["server_id"], inc["metric_key"])
        assert key not in seen_keys, f"Duplicate active incident found for {key}!"
        seen_keys.add(key)
    print("  ✓ Deduplication verified: No duplicate active incidents.")

    # Check priority sorting: P1 <= P2 <= P3 <= P4
    prio_order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    for i in range(len(pq) - 1):
        assert prio_order[pq[i]["priority"]] <= prio_order[pq[i + 1]["priority"]], "Priority queue not properly sorted!"

    assert pq[0]["is_highest_priority"] is True, "Top item must be marked as highest priority"
    print(f"  ✓ Priority queue sorted strictly P1-P4 ({[x['priority'] for x in pq]}). Top item marked highest priority.")

    # ── Test 5: Reset & Recovery ─────────────────────────────────────────
    print("\n[Test 5] Testing Reset & Normalization...")
    sim.reset()
    snap_reset = sim.get_snapshot()

    assert snap_reset["overview"]["normal_count"] == 5
    assert snap_reset["overview"]["warning_count"] == 0
    assert snap_reset["overview"]["critical_count"] == 0
    assert len(snap_reset["priority_queue"]) == 0
    assert snap_reset["overview"]["highest_priority"] == "NONE"

    # Check notification history retained with RESOLVED status
    notifs = snap_reset["notifications"]
    assert len(notifs) > 0, "Notification history should be preserved"
    for inc in notifs:
        assert inc["status"] == "RESOLVED", f"All incidents should be marked RESOLVED after reset, got {inc['status']}"
    print("  ✓ Reset verified: All servers NORMAL, active queue cleared, notifications marked RESOLVED.")

    # ── Test 6: Verify Other Scenarios (02, 03, 04) ───────────────────────
    print("\n[Test 6] Testing Scenarios 02, 03, 04 target exactly 2 servers...")
    for sc_id, sc_conf in SCENARIOS_CONFIG.items():
        if sc_id == "scenario_01":
            continue
        sim.reset()
        sim.start_scenario(sc_id)
        for _ in range(4):
            sim.tick()
        snap = sim.get_snapshot()
        
        affected = sc_conf["affected_servers"]
        assert len(affected) == 2, f"{sc_id} must affect exactly 2 servers"
        
        # Check that affected servers are non-normal
        for s_aff in affected:
            stat = snap["servers"][s_aff]["status"]
            assert stat in ("WARNING", "CRITICAL"), f"{s_aff} in {sc_id} should be non-normal, got {stat}"
        
        # Check that the 3 unaffected servers are NORMAL
        for s_unaff in SERVERS_CONFIG.keys():
            if s_unaff not in affected:
                stat = snap["servers"][s_unaff]["status"]
                assert stat == "NORMAL", f"{s_unaff} in {sc_id} should remain NORMAL, got {stat}"
        print(f"  ✓ {sc_id}: Exactly {affected} affected, remaining 3 remain NORMAL.")

    # ── Test 7: FastAPI Endpoints & Frontend Static Mount ────────────────
    print("\n[Test 7] Testing FastAPI Endpoints and Frontend Serving...")
    client = TestClient(app)

    # Test GET /api/state
    r_state = client.get("/api/state")
    assert r_state.status_code == 200
    assert "servers" in r_state.json()

    # Test GET /api/servers
    r_servers = client.get("/api/servers")
    assert r_servers.status_code == 200
    assert len(r_servers.json()["servers"]) == 5

    # Test GET /api/servers/APP-01
    r_app01 = client.get("/api/servers/APP-01")
    assert r_app01.status_code == 200
    assert r_app01.json()["id"] == "APP-01"

    # Test POST /api/simulation/start
    r_start = client.post("/api/simulation/start", json={"scenario": "scenario_02"})
    assert r_start.status_code == 200
    assert r_start.json()["status"] == "started"

    # Test POST /api/simulation/reset
    r_reset = client.post("/api/simulation/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "reset"

    # Test GET / (Frontend serving)
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "VYTRON" in r_index.text
    assert "chart.min.js" in r_index.text

    print("  ✓ All REST endpoints and Frontend serving successfully verified.")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! 5-Server Platform is fully operational and verified.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
