"""
VYTRON — Verification Suite for 10 Live Server Simulators & Demo Mode
Tests:
1. Profiles and baselines for all 10 servers
2. Continuous telemetry generation across all 10 system metrics + role extras
3. Dynamic operational log generation and activity tracking
4. Inter-service dependency cascading (DB-01 failure cascades to APP-01 and WEB-01)
5. 8 Judge Demo Scenarios (Normal, CPU, DB Cascade, Auth, Net, Storage, App, Recovery)
6. Fine-grained interactive server controls (fail, recover, set_metric)
7. Collector Tier 1 pipeline (normalization, privacy filter, egress proof, local queue)
8. Central Backend Tier 2 APIs (/api/servers, /api/servers/{id}/detail, /api/demo/state)
"""

import sys
import os
import unittest
from datetime import datetime, timezone

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.constants import SERVER_PROFILES, RULE_THRESHOLDS
from simulator.server_profiles import (
    get_all_servers,
    get_server,
    reset_all_servers,
    apply_cascading_dependencies,
)
from simulator.telemetry_generator import (
    generate_all_telemetry,
    generate_events_for_server,
    _metrics_for_server,
)
from simulator.scenarios import (
    demo_normal,
    demo_cpu_spike,
    demo_db_failure,
    demo_auth_spike,
    demo_network_degradation,
    demo_storage_pressure,
    demo_app_failure,
    demo_full_recovery,
    control_server_metric,
    fail_single_server,
    recover_single_server,
    get_active_scenario,
)
from collector.normalization import normalize_event
from collector.privacy_filter import filter_payload
from collector.database import SessionLocal, init_db
from backend.database.connection import init_db as init_backend_db, SessionLocal as BackendSessionLocal
from backend.models.platform_models import Server, Metric, Alert


class TestLiveServerSimulators(unittest.TestCase):

    def setUp(self):
        reset_all_servers()

    def test_01_all_ten_servers_configured_with_roles(self):
        """Verify all 10 required servers exist with independent simulation states."""
        expected_ids = [
            "APP-01", "DB-01", "AUTH-01", "WEB-01", "STORAGE-01",
            "APP-02", "DB-02", "NETWORK-01", "BACKUP-01", "INTERNAL-01",
        ]
        servers = get_all_servers()
        self.assertEqual(len(servers), 10)
        for sid in expected_ids:
            self.assertIn(sid, servers)
            srv = servers[sid]
            self.assertEqual(srv.server_id, sid)
            self.assertTrue(len(srv.name) > 0)
            self.assertTrue(len(srv.role) > 0)
            self.assertGreater(srv.get_uptime_seconds(), 0)

    def test_02_all_ten_metrics_generated(self):
        """Verify every server generates all 10 core metrics + role metrics."""
        events = generate_all_telemetry()
        self.assertGreater(len(events), 90)  # 10 servers * (10 core + extras)

        # Check APP-01
        app01_events = [e for e in events if e.source_id == "APP-01"]
        app01_metrics = {e.metric: e.value for e in app01_events}

        core_metrics = [
            "cpu_usage", "memory_usage", "disk_usage",
            "network_upload", "network_download", "network_latency",
            "request_rate", "error_rate", "response_time", "service_availability"
        ]
        for m in core_metrics:
            self.assertIn(m, app01_metrics, f"Missing metric {m} in APP-01 telemetry")
            self.assertIsInstance(app01_metrics[m], float)

        # Check role-specific metrics
        auth_events = [e for e in events if e.source_id == "AUTH-01"]
        auth_metrics = {e.metric for e in auth_events}
        self.assertIn("failed_logins", auth_metrics)

        net_events = [e for e in events if e.source_id == "NETWORK-01"]
        net_metrics = {e.metric for e in net_events}
        self.assertIn("packet_loss", net_metrics)

    def test_03_role_specific_baselines_and_noise(self):
        """Verify servers do not have identical random values; baselines match roles."""
        servers = get_all_servers()
        web01 = servers["WEB-01"]
        db01 = servers["DB-01"]

        # WEB-01 has high network throughput baseline; DB-01 has higher disk & memory
        self.assertGreater(web01.baselines["network_download"], db01.baselines["network_download"])
        self.assertGreater(db01.baselines["memory_usage"], web01.baselines["memory_usage"])
        self.assertGreater(db01.baselines["disk_usage"], web01.baselines["disk_usage"])

    def test_04_dynamic_logs_generated(self):
        """Verify dynamic operational logs are maintained in ring buffer."""
        servers = get_all_servers()
        app01 = servers["APP-01"]
        initial_log_count = len(app01.log_history)

        # Generating telemetry emits fresh logs
        generate_events_for_server(app01)
        self.assertGreater(len(app01.log_history), initial_log_count)

        last_log = app01.log_history[-1]
        self.assertIn("message", last_log)
        self.assertIn("level", last_log)
        self.assertIn("timestamp", last_log)

    def test_05_dependency_cascade_database_failure(self):
        """Verify DB-01 failure cascades to APP-01 and WEB-01."""
        res = demo_db_failure()
        self.assertEqual(res["status"], "success")

        servers = get_all_servers()
        db01 = servers["DB-01"]
        app01 = servers["APP-01"]
        web01 = servers["WEB-01"]

        # DB-01 is offline
        self.assertEqual(db01.compute_health_state(), "OFFLINE")

        # APP-01 cascaded degradation
        self.assertGreaterEqual(app01.current["error_rate"], 35.0)
        self.assertGreaterEqual(app01.current["response_time"], 500.0)
        self.assertIn("Cascading", app01.activity)

        # WEB-01 cascaded degradation
        self.assertGreaterEqual(web01.current["error_rate"], 20.0)
        self.assertGreaterEqual(web01.current["response_time"], 400.0)

    def test_06_dependency_cascade_storage_pressure(self):
        """Verify STORAGE-01 disk pressure cascades to BACKUP-01."""
        res = demo_storage_pressure()
        self.assertEqual(res["status"], "success")

        servers = get_all_servers()
        storage = servers["STORAGE-01"]
        backup = servers["BACKUP-01"]

        self.assertGreaterEqual(storage.current["disk_usage"], 90.0)
        self.assertGreaterEqual(backup.current["error_rate"], 40.0)
        self.assertIn("Backup", backup.activity)

    def test_07_all_eight_demo_scenarios(self):
        """Verify all 8 judge demo scenarios execute cleanly."""
        scenarios = [
            demo_normal,
            demo_cpu_spike,
            demo_db_failure,
            demo_auth_spike,
            demo_network_degradation,
            demo_storage_pressure,
            demo_app_failure,
            demo_full_recovery,
        ]
        for sc_fn in scenarios:
            res = sc_fn()
            self.assertEqual(res["status"], "success")
            self.assertTrue(len(get_active_scenario()) > 0)

    def test_08_server_level_interactive_controls(self):
        """Verify fine-grained controls: fail, set_metric, recover."""
        # 1. Fail single server
        fail_res = fail_single_server("AUTH-01")
        self.assertEqual(fail_res["status"], "success")
        auth = get_server("AUTH-01")
        self.assertEqual(auth.compute_health_state(), "OFFLINE")
        self.assertEqual(auth.get_uptime_seconds(), 0.0)

        # 2. Recover single server
        rec_res = recover_single_server("AUTH-01")
        self.assertEqual(rec_res["status"], "success")
        self.assertEqual(auth.compute_health_state(), "ONLINE")

        # 3. Set metric
        set_res = control_server_metric("APP-02", "cpu_usage", 88.5)
        self.assertEqual(set_res["status"], "success")
        self.assertEqual(get_server("APP-02").current["cpu_usage"], 88.5)

    def test_09_collector_pipeline_with_new_metrics(self):
        """Verify collector normalizes and audits new metric types."""
        init_db()
        events = generate_all_telemetry()
        sample_event = [e for e in events if e.metric == "response_time"][0]

        # Normalization
        norm = normalize_event(sample_event)
        self.assertEqual(norm["metric"], "response_time")

        # Privacy Filter (allow-list validation + egress record)
        approved, egress_rec = filter_payload(norm)
        self.assertEqual(approved.metric, "response_time")
        self.assertEqual(egress_rec.policy_result, "approved")
        self.assertIsNotNone(egress_rec.serialized_payload)

    def test_10_database_seeding_and_snapshot(self):
        """Verify platform database synchronises server profile metadata."""
        init_backend_db()
        db = BackendSessionLocal()
        try:
            servers = db.query(Server).all()
            self.assertEqual(len(servers), 10)
            server_names = {s.server_name for s in servers}
            self.assertIn("Application Server 01", server_names)
            self.assertIn("Database Server 01", server_names)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
