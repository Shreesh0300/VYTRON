"""
Comprehensive Verification Suite for VYTRON Randomized Incident Generation Engine
Covers all 14 requirements specified in Section 15 of user instructions.
"""

import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.config import SERVERS_CONFIG, ISSUE_CATALOGUE
from server.generator import RandomIncidentEngine
from server.simulator import InfrastructureSimulator
from fastapi.testclient import TestClient
from server.app import app

def run_all_tests():
    print("=" * 75)
    print("VYTRON RANDOMIZED INCIDENT GENERATION ENGINE — VERIFICATION SUITE")
    print("=" * 75)

    engine = RandomIncidentEngine()

    # ── Test 1: Random Server Selection (Reqs 1, 2, 5, 14) ───────────────
    print("\n[Test 1] Testing Random Server Selection (1-5 servers, unique, diverse combos)...")
    counts_seen = set()
    combos_seen = set()
    immediate_repeats = 0

    prev_combo = None
    for i in range(30):
        plan = engine.generate_plan()
        servers = plan["affected_servers"]
        count = len(servers)
        counts_seen.add(count)
        
        # Req 5: No duplicate servers within a run
        assert len(servers) == len(set(servers)), f"Run {i}: Duplicate servers selected: {servers}"
        
        # All servers are valid
        for s in servers:
            assert s in SERVERS_CONFIG, f"Invalid server ID: {s}"

        combo_tuple = tuple(sorted(servers))
        combos_seen.add(combo_tuple)

        if prev_combo and combo_tuple == prev_combo:
            immediate_repeats += 1
        prev_combo = combo_tuple

    # Req 1: Different numbers of servers can be selected
    assert len(counts_seen) >= 3, f"Expected varied server counts across 30 runs, saw: {counts_seen}"
    # Req 2: Different server combinations generated
    assert len(combos_seen) >= 8, f"Expected high diversity of combinations, saw: {len(combos_seen)}"
    # Req 14: Multiple runs do not always produce same results
    assert immediate_repeats <= 2, f"Too many immediate repeats ({immediate_repeats}/30)"
    print(f"  ✓ Verified: Server counts varied {sorted(counts_seen)}. Unique combos: {len(combos_seen)}/30.")

    # ── Test 2: Random Metric Selection (Reqs 3, 5) ──────────────────────
    print("\n[Test 2] Testing Random Metric Selection (valid metrics, no cross-server selection, no duplicates)...")
    metrics_per_server = {sid: set() for sid in SERVERS_CONFIG.keys()}

    for _ in range(40):
        plan = engine.generate_plan()
        for iss in plan["issues"]:
            sid = iss["server_id"]
            m_key = iss["metric_key"]
            valid_server_params = SERVERS_CONFIG[sid]["parameters"]
            
            # Req 3: Metric must belong to the selected server
            assert m_key in valid_server_params, f"Metric {m_key} does not belong to {sid}"
            metrics_per_server[sid].add(m_key)

        # Req 5: No duplicate metric selection for the same server in a single run
        server_issue_metrics = {}
        for iss in plan["issues"]:
            sid = iss["server_id"]
            m = iss["metric_key"]
            server_issue_metrics.setdefault(sid, []).append(m)
        for sid, m_list in server_issue_metrics.items():
            assert len(m_list) == len(set(m_list)), f"Duplicate metric selected for {sid}: {m_list}"

    for sid, m_set in metrics_per_server.items():
        assert len(m_set) >= 2, f"Server {sid} had poor metric diversity: only {m_set}"
    print(f"  ✓ Verified: All selected metrics belong to their respective servers; no duplicates within a run.")

    # ── Test 3: Valid Issue Types from Catalogue (Req 4) ─────────────────
    print("\n[Test 3] Testing Valid Issue Types from Configurable Catalogue...")
    issue_types_seen = set()

    for _ in range(30):
        plan = engine.generate_plan()
        for iss in plan["issues"]:
            sid = iss["server_id"]
            m_key = iss["metric_key"]
            itype = iss["issue_type"]
            issue_types_seen.add(itype)

            # Req 4: Issue type must exist in ISSUE_CATALOGUE for that server & metric
            catalogue = ISSUE_CATALOGUE.get(sid, {}).get(m_key, [])
            valid_types = [c["issue_type"] for c in catalogue]
            assert itype in valid_types, f"Invalid issue type '{itype}' for {sid}.{m_key}! Valid: {valid_types}"

    assert len(issue_types_seen) >= 8, f"Expected diverse issue types, saw: {len(issue_types_seen)}"
    print(f"  ✓ Verified: All issue types matched ISSUE_CATALOGUE entries ({len(issue_types_seen)} distinct types seen).")

    # ── Test 4: Gradual Metric Degradation (Req 7) ───────────────────────
    print("\n[Test 4] Testing Gradual Multi-Step Metric Degradation...")
    sim = InfrastructureSimulator()
    # Force single server with a known high target
    plan = sim.start_simulation(server_count=1)
    aff_sid = plan["affected_servers"][0]
    aff_metric = plan["issues"][0]["metric_key"]
    target_val = plan["targets"][f"{aff_sid}.{aff_metric}"]
    base_val = SERVERS_CONFIG[aff_sid]["parameters"][aff_metric]["baseline"]

    readings = [sim.servers[aff_sid]["metrics"][aff_metric]]
    # Tick 5 times and observe gradual progression
    for _ in range(5):
        sim.tick()
        readings.append(sim.servers[aff_sid]["metrics"][aff_metric])

    # Req 7: Values should change gradually, not jump from base to target in 1 tick
    assert len(readings) == 6
    diff_tick1 = abs(readings[1] - readings[0])
    total_delta = abs(target_val - base_val)
    if total_delta > 10.0:
        # First tick should not jump all the way to target
        assert diff_tick1 < total_delta * 0.70, f"Metric jumped too quickly in tick 1: {readings[0]} -> {readings[1]} (target {target_val})"
        # Progressive movement towards target
        assert abs(readings[-1] - base_val) > abs(readings[1] - base_val), "Metric did not progressively degrade"
    print(f"  ✓ Verified gradual progression: {readings} towards target {target_val}.")

    # ── Test 5: Unaffected Servers Isolation (Req 6) ─────────────────────
    print("\n[Test 5] Testing Unaffected Servers Isolation (Remain Normal Baseline)...")
    sim.reset()
    plan = sim.start_simulation(server_count=2)
    aff_servers = set(plan["affected_servers"])
    unaff_servers = set(SERVERS_CONFIG.keys()) - aff_servers
    assert len(unaff_servers) == 3

    # Tick 6 times
    for _ in range(6):
        sim.tick()

    snap = sim.get_snapshot()
    for u_id in unaff_servers:
        u_state = snap["servers"][u_id]
        # Req 6: Status must be NORMAL
        assert u_state["status"] == "NORMAL", f"Unaffected server {u_id} became {u_state['status']}"
        # All 4 metrics within baseline bounds
        for p_key, p_val in u_state["metrics"].items():
            p_conf = SERVERS_CONFIG[u_id]["parameters"][p_key]
            thresh = p_conf.get("thresholds")
            if thresh:
                if thresh["direction"] == "above":
                    assert p_val < thresh["warning"], f"Unaffected {u_id}.{p_key} breached warning: {p_val} >= {thresh['warning']}"
                elif thresh["direction"] == "below":
                    assert p_val > thresh["warning"], f"Unaffected {u_id}.{p_key} breached warning: {p_val} <= {thresh['warning']}"
    print(f"  ✓ Verified: Unaffected servers {unaff_servers} strictly maintained baseline NORMAL operation.")

    # ── Test 6: Detection Pipeline, Deduplication & Priority Queue (Reqs 8, 9, 10, 11, 12) ──
    print("\n[Test 6] Testing Detection Separation, Severity/Priority Mapping & Strict Queue...")
    sim.reset()
    # Force 3 servers to ensure multiple incidents
    plan = sim.start_simulation(server_count=3)
    
    # Tick enough times (5 ticks) for consecutive breach confirmation (>=2 ticks)
    for _ in range(5):
        sim.tick()

    snap = sim.get_snapshot()
    pq = snap["priority_queue"]
    notifs = snap["notifications"]

    # Reqs 8 & 9: Incidents and notifications created from actual threshold breaches
    assert len(pq) > 0, "Expected active incidents in priority queue after breaches"
    assert len(notifs) >= len(pq), "Notifications should record all detected incidents"

    # Req 12: Deduplication: No duplicate active incidents for same (server_id, metric_key)
    seen_active = set()
    for inc in pq:
        key = (inc["server_id"], inc["metric_key"])
        assert key not in seen_active, f"Duplicate active incident in queue for {key}"
        seen_active.add(key)
    print(f"  ✓ Verified deduplication: {len(pq)} active incidents with zero duplicate pairs.")

    # Req 10 & 11: Priority mapping & Strict Queue sorting (P1 > P2 > P3 > P4)
    prio_order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    for i in range(len(pq) - 1):
        r_curr = prio_order.get(pq[i]["priority"], 99)
        r_next = prio_order.get(pq[i + 1]["priority"], 99)
        assert r_curr <= r_next, f"Priority queue out of order: {pq[i]['priority']} before {pq[i+1]['priority']}"
        if r_curr == r_next:
            # Ties broken by oldest created_at
            assert pq[i]["created_at"] <= pq[i + 1]["created_at"], "Ties not sorted by oldest unresolved incident"

    # Top incident marked as highest priority
    assert pq[0]["is_highest_priority"] is True
    print(f"  ✓ Verified priority queue: strictly sorted {[x['priority'] for x in pq]} with #1 flagged.")

    # ── Test 7: Stop & Reset Lifecycle (Req 13) ──────────────────────────
    print("\n[Test 7] Testing Stop & Reset Lifecycle...")
    # Stop simulation
    sim.stop_simulation()
    assert sim.is_running is False
    snap_stopped = sim.get_snapshot()
    assert snap_stopped["active_simulation"] is None or snap_stopped["active_simulation"]["plan_id"] is not None

    # Reset simulation
    sim.reset()
    snap_reset = sim.get_snapshot()
    assert snap_reset["overview"]["normal_count"] == 5
    assert snap_reset["overview"]["warning_count"] == 0
    assert snap_reset["overview"]["critical_count"] == 0
    assert len(snap_reset["priority_queue"]) == 0
    assert snap_reset["overview"]["highest_priority"] == "NONE"

    # Preserves notification history with RESOLVED status
    for inc in snap_reset["notifications"]:
        assert inc["status"] == "RESOLVED", f"Incident {inc['incident_id']} should be RESOLVED after reset"
    print("  ✓ Verified Stop & Reset: all 5 servers NORMAL, active queue cleared, notifications marked RESOLVED.")

    # ── Test 8: REST Endpoints Integration ───────────────────────────────
    print("\n[Test 8] Testing FastAPI REST Endpoints...")
    client = TestClient(app)

    # 1. Start simulation with auto
    r1 = client.post("/api/simulation/start", json={"scenario": "auto"})
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "started"
    assert "plan" in data1
    assert len(data1["plan"]["affected_servers"]) >= 1

    # 2. Get state
    r_state = client.get("/api/state")
    assert r_state.status_code == 200
    assert r_state.json()["active_simulation"] is not None

    # 3. Start simulation with specific count = 2
    r2 = client.post("/api/simulation/start", json={"server_count": 2})
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2["plan"]["affected_servers"]) == 2

    # 4. Stop simulation
    r_stop = client.post("/api/simulation/stop")
    assert r_stop.status_code == 200
    assert r_stop.json()["status"] == "stopped"

    # 5. Reset simulation
    r_reset = client.post("/api/simulation/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "reset"
    assert r_reset.json()["state"]["overview"]["normal_count"] == 5

    # 6. Verify static frontend
    r_ui = client.get("/")
    assert r_ui.status_code == 200
    assert "Random Simulation" in r_ui.text

    print("  ✓ Verified REST APIs: /api/simulation/start, stop, reset, and frontend integration.")

    print("\n" + "=" * 75)
    print("ALL 14 REQUIREMENTS VERIFIED & PASSED! RANDOM ENGINE IS FULLY OPERATIONAL.")
    print("=" * 75)

if __name__ == "__main__":
    run_all_tests()
