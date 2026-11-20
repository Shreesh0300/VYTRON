"""
VYTRON — 5-Server Infrastructure Telemetry Simulator
Maintains independent in-memory state and rolling history for all 5 servers.
Simulates realistic baseline telemetry, controlled 2-server scenario abnormalities,
and smooth recovery without any database reliance.
"""

import time
import random
from collections import deque
from typing import Any
from server.config import SERVERS_CONFIG, SCENARIOS_CONFIG
from server.detector import ThresholdDetector
from server.incident_manager import IncidentManager

HISTORY_MAX_POINTS = 60

class InfrastructureSimulator:
    def __init__(self):
        self.detector = ThresholdDetector(consecutive_required=2)
        self.incident_manager = IncidentManager()

        self.active_scenario_id: str | None = None
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
                # Seed with a few baseline points
                for i in range(10):
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
                "uptime_seconds": 1240,
                "metrics": metrics,
                "history": history,
            }

    def start_scenario(self, scenario_id: str) -> bool:
        """Starts one of the 4 predefined scenarios."""
        if scenario_id in SCENARIOS_CONFIG:
            self.active_scenario_id = scenario_id
            return True
        return False

    def stop_scenario(self):
        """Stops active scenario, allowing servers to return to baseline."""
        self.active_scenario_id = None

    def reset(self):
        """Resets all 5 servers to baseline, clears detector and resolves incidents."""
        self.active_scenario_id = None
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
        Generates telemetry for all 5 servers:
        - If unaffected by active scenario: baseline + gaussian noise.
        - If affected by active scenario: mutated parameters towards scenario targets.
        - Evaluates thresholds and updates incidents.
        """
        self.ticks += 1
        now_str = time.strftime("%H:%M:%S")

        scenario = SCENARIOS_CONFIG.get(self.active_scenario_id) if self.active_scenario_id else None
        affected_servers = scenario["affected_servers"] if scenario else []
        scenario_mutations = scenario["mutations"] if scenario else {}

        for server_id, conf in SERVERS_CONFIG.items():
            s_state = self.servers[server_id]
            s_state["uptime_seconds"] += 2
            is_affected = server_id in affected_servers

            # Update metrics
            for param_key, p_conf in conf["parameters"].items():
                current_val = s_state["metrics"][param_key]
                base = p_conf["baseline"]
                noise_std = p_conf.get("noise_std", 1.0)

                if is_affected and param_key in scenario_mutations.get(server_id, {}):
                    # Affected parameter in active scenario: smooth ramp toward target + noise
                    target_val = scenario_mutations[server_id][param_key]
                    step = 0.45 * (target_val - current_val)
                    new_val = current_val + step + random.gauss(0, noise_std * 0.3)
                else:
                    # Normal baseline operation (or recovering back to baseline)
                    if abs(current_val - base) > 2.0:
                        # Smooth recovery back to baseline
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

            # Evaluate thresholds using detection engine
            server_status, confirmed_breaches, confirmed_recoveries = self.detector.evaluate_server(
                server_id, s_state["metrics"]
            )
            s_state["status"] = server_status

            # Process breach incidents
            for breach in confirmed_breaches:
                self.incident_manager.process_breach(breach)

            # Process metric recoveries
            for recovered_param in confirmed_recoveries:
                self.incident_manager.resolve_metric(server_id, recovered_param)

    def get_snapshot(self) -> dict[str, Any]:
        """Returns the complete current platform snapshot for UI / WebSocket."""
        servers_data = {}
        normal_count = 0
        warning_count = 0
        critical_count = 0

        for server_id, s_state in self.servers.items():
            conf = SERVERS_CONFIG[server_id]
            status = s_state["status"]
            if status == "CRITICAL":
                critical_count += 1
            elif status == "WARNING":
                warning_count += 1
            else:
                normal_count += 1

            # Format history for frontend charts
            hist_formatted = {}
            for p_key, d in s_state["history"].items():
                hist_formatted[p_key] = list(d)

            # Format uptime
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

        active_scenario_info = None
        if self.active_scenario_id and self.active_scenario_id in SCENARIOS_CONFIG:
            sc = SCENARIOS_CONFIG[self.active_scenario_id]
            active_scenario_info = {
                "id": sc["id"],
                "title": sc["title"],
                "description": sc["description"],
                "affected_servers": sc["affected_servers"],
            }

        return {
            "timestamp": time.time(),
            "timestamp_str": time.strftime("%H:%M:%S"),
            "overview": {
                "total_servers": len(self.servers),
                "normal_count": normal_count,
                "warning_count": warning_count,
                "critical_count": critical_count,
                "active_incidents": len(priority_queue),
                "highest_priority": highest_prio_str,
                "highest_priority_incident": highest_prio_item,
            },
            "servers": servers_data,
            "priority_queue": priority_queue,
            "notifications": notifications,
            "active_scenario": active_scenario_info,
            "scenarios": [
                {
                    "id": k,
                    "title": v["title"],
                    "description": v["description"],
                    "affected_servers": v["affected_servers"],
                }
                for k, v in SCENARIOS_CONFIG.items()
            ],
        }
