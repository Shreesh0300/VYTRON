"""
VYTRON — 5-Server Infrastructure Telemetry Simulator
Powered by the dynamic Randomized Incident Generation Engine.
Generates realistic baseline telemetry, gradual multi-step degradation,
rule-based metric relationships, and smooth recovery without any database reliance.
"""

import time
import random
from collections import deque
from typing import Any
from server.config import SERVERS_CONFIG, RECOMMENDED_ACTIONS
from server.detector import ThresholdDetector
from server.incident_manager import IncidentManager
from server.generator import RandomIncidentEngine
from server.privacy import EgressProofEngine

HISTORY_MAX_POINTS = 60

class InfrastructureSimulator:
    def __init__(self):
        self.detector = ThresholdDetector(consecutive_required=2)
        self.incident_manager = IncidentManager()
        self.engine = RandomIncidentEngine()
        self.egress_engine = EgressProofEngine()

        self.active_plan: dict[str, Any] | None = None
        self.is_running: bool = False
        self.start_time = time.time()
        self.ticks = 0

        # In-memory server telemetry state:
        # server_id -> {
        #   "metrics": {param: float},
        #   "status": "NORMAL",
        #   "uptime_seconds": int,
        #   "history": {param: deque of {"time": str, "value": float}}
        # }
        self.servers: dict[str, dict[str, Any]] = {}
        self._init_servers()

    def _init_servers(self):
        now_str = time.strftime("%H:%M:%S")
        for server_id, conf in SERVERS_CONFIG.items():
            metrics = {}
            history = {}
            for param_key, p_conf in conf["parameters"].items():
                base = p_conf["baseline"]
                metrics[param_key] = base
                d = deque(maxlen=HISTORY_MAX_POINTS)
                # Seed with 10 baseline points
                for _ in range(10):
                    val = base + random.gauss(0, p_conf.get("noise_std", 1.0))
                    val = max(p_conf["min"], min(p_conf["max"], val))
                    d.append({"time": now_str, "value": round(val, 2)})
                history[param_key] = d

            self.servers[server_id] = {
                "id": server_id,
                "name": conf["name"],
                "type": conf["type"],
                "description": conf["description"],
                "status": "NORMAL",
                "health_state": "EXCELLENT",
                "health_reason": "Optimal baseline health; zero metric anomalies",
                "uptime_seconds": 1240,
                "metrics": metrics,
                "history": history,
            }

    def start_simulation(self, server_count: int | None = None) -> dict[str, Any]:
        """
        Starts a new randomized simulation run:
        Selects random servers (1-5), random metrics, random issue types,
        and starts gradual multi-step metric degradation.
        """
        self.active_plan = self.engine.generate_plan(server_count=server_count)
        self.is_running = True
        return self.active_plan

    def start_scenario(self, scenario_id: str = "auto") -> bool:
        """Compatibility wrapper for scenario-based triggers."""
        count = None
        if scenario_id in ("1", "2", "3", "4", "5"):
            count = int(scenario_id)
        elif scenario_id == "scenario_01" or scenario_id == "scenario_02" or scenario_id == "scenario_03" or scenario_id == "scenario_04":
            count = 2
        self.start_simulation(server_count=count)
        return True

    def stop_simulation(self):
        """Stops active simulation, freezing current degradation targets."""
        self.is_running = False

    def stop_scenario(self):
        """Compatibility alias for stop_simulation."""
        self.stop_simulation()

    def reset(self):
        """
        Resets all 5 servers to baseline, clears simulation plan,
        resets detector breach states, and resolves active incidents.
        """
        self.active_plan = None
        self.is_running = False
        self.detector.reset()
        self.incident_manager.reset()

        now_str = time.strftime("%H:%M:%S")
        for server_id, conf in SERVERS_CONFIG.items():
            s_state = self.servers[server_id]
            s_state["status"] = "NORMAL"
            for param_key, p_conf in conf["parameters"].items():
                base = p_conf["baseline"]
                s_state["metrics"][param_key] = base
                s_state["history"][param_key].append({
                    "time": now_str,
                    "value": round(base, 2)
                })

    def tick(self):
        """
        Executes one simulation step (called every ~1.5s).
        1. Checks auto-recovery duration timers.
        2. Generates realistic telemetry:
           - Unaffected servers/metrics: baseline + gaussian noise.
           - Affected servers/metrics: gradual step degradation toward target values.
           - Rule-based metric relationships: secondary nudges on correlated metrics.
        3. Independently feeds telemetry into ThresholdDetector.
        4. Detects breaches (consecutive confirmed) and creates/updates incidents.
        5. Resolves incidents when metrics return to normal baseline.
        """
        self.ticks += 1
        now = time.time()
        now_str = time.strftime("%H:%M:%S")

        plan = self.active_plan if self.is_running else None
        affected_servers = plan["affected_servers"] if plan else []
        plan_targets = plan["targets"] if plan else {}
        plan_durations = plan["durations"] if plan else {}

        # 1. Check auto-recovery timers
        if plan and plan_durations:
            for t_key, dur_info in plan_durations.items():
                if dur_info.get("auto_recover") and not dur_info.get("is_recovering"):
                    elapsed = now - dur_info["start_time"]
                    if elapsed >= dur_info["duration_seconds"]:
                        dur_info["is_recovering"] = True

        # 2. Update telemetry for all 5 servers
        for server_id, conf in SERVERS_CONFIG.items():
            s_state = self.servers[server_id]
            s_state["uptime_seconds"] += 2
            is_affected = server_id in affected_servers

            for param_key, p_conf in conf["parameters"].items():
                current_val = s_state["metrics"][param_key]
                base = p_conf["baseline"]
                noise_std = p_conf.get("noise_std", 1.0)
                t_key = f"{server_id}.{param_key}"

                if is_affected and t_key in plan_targets:
                    dur_info = plan_durations.get(t_key, {})
                    if dur_info.get("is_recovering"):
                        # Auto-recovering: gradual step back to baseline
                        step = 0.32 * (base - current_val)
                        new_val = current_val + step + random.gauss(0, noise_std * 0.5)
                    else:
                        # Gradual metric degradation toward target value
                        target_val = plan_targets[t_key]
                        # Lerp factor 0.28 produces authentic 4-6 step progression
                        step = 0.28 * (target_val - current_val)
                        new_val = current_val + step + random.gauss(0, noise_std * 0.25)
                else:
                    # Normal baseline operation (or recovering back to baseline after reset)
                    if abs(current_val - base) > 2.0:
                        step = 0.35 * (base - current_val)
                        new_val = current_val + step + random.gauss(0, noise_std)
                    else:
                        new_val = base + random.gauss(0, noise_std)

                # Clamp within physically meaningful limits
                new_val = max(p_conf["min"], min(p_conf["max"], new_val))
                new_val = round(new_val, 2)

                s_state["metrics"][param_key] = new_val
                s_state["history"][param_key].append({
                    "time": now_str,
                    "value": new_val
                })

            # 3. Independent Detection Engine Pipeline
            # Evaluates server metrics against configured warning & critical thresholds
            server_status, confirmed_breaches, confirmed_recoveries = self.detector.evaluate_server(
                server_id, s_state["metrics"]
            )
            s_state["status"] = server_status

            # Map the Four Official Hackathon Health States (Excellent, Good, Fair, Poor)
            if server_status == "CRITICAL":
                health_state = "POOR"
                health_reason = f"Critical threshold breach on {server_id} requiring immediate response"
            elif server_status == "WARNING":
                health_state = "FAIR"
                health_reason = f"Warning threshold elevated on {server_id}; requires SRE monitoring"
            else:
                has_minor_drift = any(
                    abs(s_state["metrics"][pk] - conf["parameters"][pk]["baseline"]) > conf["parameters"][pk].get("noise_std", 1.0) * 1.5
                    for pk in conf["parameters"]
                )
                if has_minor_drift:
                    health_state = "GOOD"
                    health_reason = "Nominal baseline variance within standard operating noise"
                else:
                    health_state = "EXCELLENT"
                    health_reason = "Optimal baseline performance; zero anomalies detected"

            s_state["health_state"] = health_state
            s_state["health_reason"] = health_reason

            # 4. Incident Management: process confirmed breaches (with deduplication)
            for breach in confirmed_breaches:
                self.incident_manager.process_breach(breach)

            # 5. Incident Management: resolve recovered metrics
            for recovered_param in confirmed_recoveries:
                self.incident_manager.resolve_metric(server_id, recovered_param)

            # 6. Tier 1 Privacy Filtering & Egress Proof Logging
            self.egress_engine.process_telemetry(
                server_id=server_id,
                server_name=s_state["name"],
                server_type=s_state["type"],
                health_state=health_state,
                health_reason=health_reason,
                metrics=s_state["metrics"],
                severity=s_state["status"],
                status=s_state["status"],
            )

    def get_snapshot(self) -> dict[str, Any]:
        """Returns the complete platform snapshot for UI / WebSocket."""
        servers_data = {}
        normal_count = 0
        warning_count = 0
        critical_count = 0

        excellent_count = 0
        good_count = 0
        fair_count = 0
        poor_count = 0

        for server_id, s_state in self.servers.items():
            conf = SERVERS_CONFIG[server_id]
            status = s_state["status"]
            h_state = s_state.get("health_state", "EXCELLENT")

            if status == "CRITICAL":
                critical_count += 1
            elif status == "WARNING":
                warning_count += 1
            else:
                normal_count += 1

            if h_state == "POOR":
                poor_count += 1
            elif h_state == "FAIR":
                fair_count += 1
            elif h_state == "GOOD":
                good_count += 1
            else:
                excellent_count += 1

            hist_formatted = {}
            for p_key, d in s_state["history"].items():
                hist_formatted[p_key] = list(d)

            up_sec = s_state["uptime_seconds"]
            hrs, rem = divmod(up_sec, 3600)
            mins, secs = divmod(rem, 60)
            uptime_str = f"{hrs:02d}h {mins:02d}m {secs:02d}s"

            servers_data[server_id] = {
                "id": server_id,
                "name": s_state["name"],
                "type": s_state["type"],
                "description": s_state["description"],
                "status": status,
                "health_state": h_state,
                "health_reason": s_state.get("health_reason", "Optimal health"),
                "uptime_seconds": up_sec,
                "uptime_str": uptime_str,
                "metrics": dict(s_state["metrics"]),
                "parameters_meta": conf["parameters"],
                "history": hist_formatted,
            }

        priority_queue = self.incident_manager.get_priority_queue()
        notifications = self.incident_manager.get_notifications(40)

        highest_prio_str = "NONE"
        highest_prio_item = None
        if priority_queue:
            highest_prio_item = priority_queue[0]
            highest_prio_str = highest_prio_item["priority"]

        cluster_health = "EXCELLENT"
        if poor_count > 0:
            cluster_health = "POOR"
        elif fair_count > 0:
            cluster_health = "FAIR"
        elif good_count > 0:
            cluster_health = "GOOD"

        active_simulation_info = None
        if self.active_plan and self.is_running:
            active_simulation_info = {
                "plan_id": self.active_plan["plan_id"],
                "title": f"Dynamic Simulation ({len(self.active_plan['affected_servers'])} Servers Affected)",
                "summary": self.active_plan["summary"],
                "description": f"Randomized incident generation across: {', '.join(self.active_plan['affected_servers'])}",
                "affected_servers": self.active_plan["affected_servers"],
                "issues": self.active_plan["issues"],
            }

        now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return {
            "timestamp": time.time(),
            "timestamp_str": time.strftime("%H:%M:%S"),
            "timestamp_utc": now_utc,
            "overview": {
                "total_servers": len(self.servers),
                "normal_count": normal_count,
                "warning_count": warning_count,
                "critical_count": critical_count,
                "excellent_count": excellent_count,
                "good_count": good_count,
                "fair_count": fair_count,
                "poor_count": poor_count,
                "cluster_health": cluster_health,
                "active_incidents": len(priority_queue),
                "highest_priority": highest_prio_str,
                "highest_priority_incident": highest_prio_item,
            },
            "data_freshness": {
                "status": "REAL-TIME",
                "latency_seconds": 1.2,
                "ingest_latency_seconds": 1.2,
                "dashboard_latency_seconds": 1.2,
                "alert_latency_seconds": 2.1,
                "target_seconds": 10.0,
                "alert_target_seconds": 15.0,
                "stale_threshold_seconds": 60.0,
                "is_stale": False,
                "tenant_id": self.egress_engine.tenant_id,
                "collector_id": self.egress_engine.collector_id,
                "region": "us-east-1 (UTC)",
                "timestamp_utc": now_utc,
            },
            "egress_proof": {
                "latest": self.egress_engine.get_latest_proof(),
                "history": self.egress_engine.get_history(6),
                "stats": self.egress_engine.get_stats(),
            },
            "servers": servers_data,
            "priority_queue": priority_queue,
            "notifications": notifications,
            "active_scenario": active_simulation_info,
            "active_simulation": active_simulation_info,
        }
