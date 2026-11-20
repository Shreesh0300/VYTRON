"""
VYTRON — In-Memory Incident Management & Prioritization Engine
Maintains active and historical incident records.
Ensures incident deduplication, P1-P4 priority queues, and automatic resolution.
Zero database dependencies.
"""

import time
from datetime import datetime
from typing import Any
from server.config import RECOMMENDED_ACTIONS

PRIORITY_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

class IncidentManager:
    def __init__(self):
        self._seq = 0
        # Active open incidents: key is f"{server_id}:{metric_key}" -> incident dict
        self._active_incidents: dict[str, dict[str, Any]] = {}
        # Historical log of all notifications (both active and resolved, newest first)
        self._notifications: list[dict[str, Any]] = []

    def _next_incident_id(self) -> str:
        self._seq += 1
        year = datetime.now().year
        return f"INC-{year}-{self._seq:04d}"

    def process_breach(self, breach: dict[str, Any]) -> dict[str, Any]:
        """
        Processes a confirmed threshold breach.
        If an open incident already exists for this server & metric, updates it (deduplication).
        Otherwise, creates a new incident and logs it.
        """
        server_id = breach["server_id"]
        metric_key = breach["metric_key"]
        dedup_key = f"{server_id}:{metric_key}"
        now = time.time()
        now_str = datetime.fromtimestamp(now).strftime("%H:%M:%S")

        action_key = f"{server_id}.{metric_key}"
        action_text = RECOMMENDED_ACTIONS.get(
            action_key,
            f"Inspect {breach['metric_name']} on {server_id} and stabilize workload parameters."
        )

        direction_sym = ">=" if breach.get("direction") == "above" else "<="
        issue_desc = (
            f"{server_id} {breach['metric_name']} breached {breach['breach_level']} threshold: "
            f"{breach['observed_value']} {breach['unit']} ({direction_sym} {breach['threshold_value']} {breach['unit']})"
        )

        if dedup_key in self._active_incidents:
            # Deduplicate: update existing open incident with latest values
            inc = self._active_incidents[dedup_key]
            inc["observed_value"] = breach["observed_value"]
            inc["last_updated_at"] = now
            inc["last_updated_at_str"] = now_str
            # Upgrade severity/priority if it worsened from warning to critical
            if PRIORITY_ORDER.get(breach["priority"], 99) < PRIORITY_ORDER.get(inc["priority"], 99):
                inc["severity"] = breach["severity"]
                inc["priority"] = breach["priority"]
                inc["threshold_value"] = breach["threshold_value"]
                inc["issue_description"] = issue_desc
            return inc

        # Create new incident
        inc_id = self._next_incident_id()
        incident = {
            "incident_id": inc_id,
            "server_id": server_id,
            "server_name": breach["server_name"],
            "server_type": breach["server_type"],
            "metric_key": metric_key,
            "metric_name": breach["metric_name"],
            "issue_description": issue_desc,
            "observed_value": breach["observed_value"],
            "threshold_value": breach["threshold_value"],
            "unit": breach["unit"],
            "severity": breach["severity"],
            "priority": breach["priority"],
            "status": "OPEN",
            "created_at": now,
            "created_at_str": now_str,
            "resolved_at": None,
            "resolved_at_str": None,
            "recommended_action": action_text,
        }

        self._active_incidents[dedup_key] = incident
        self._notifications.insert(0, incident)

        # Cap notification history at 100 entries
        if len(self._notifications) > 100:
            self._notifications = self._notifications[:100]

        return incident

    def resolve_metric(self, server_id: str, metric_key: str):
        """
        Marks an open incident for this server and metric as RESOLVED.
        """
        dedup_key = f"{server_id}:{metric_key}"
        if dedup_key in self._active_incidents:
            inc = self._active_incidents.pop(dedup_key)
            now = time.time()
            now_str = datetime.fromtimestamp(now).strftime("%H:%M:%S")
            inc["status"] = "RESOLVED"
            inc["resolved_at"] = now
            inc["resolved_at_str"] = now_str

    def get_priority_queue(self) -> list[dict[str, Any]]:
        """
        Returns active open incidents sorted strictly by:
        1. Priority: P1 > P2 > P3 > P4
        2. Ties broken by oldest unresolved incident (earliest created_at).
        Sets 'is_highest_priority' on the top incident.
        """
        active_list = list(self._active_incidents.values())
        if not active_list:
            return []

        sorted_incidents = sorted(
            active_list,
            key=lambda x: (PRIORITY_ORDER.get(x["priority"], 99), x["created_at"])
        )

        result = []
        for idx, inc in enumerate(sorted_incidents):
            item = dict(inc)
            item["is_highest_priority"] = (idx == 0)
            item["rank"] = idx + 1
            result.append(item)

        return result

    def get_notifications(self, limit: int = 50) -> list[dict[str, Any]]:
        """Returns recent notifications list (both active and resolved)."""
        return self._notifications[:limit]

    def reset(self):
        """Resolves all open incidents and clears queues."""
        now = time.time()
        now_str = datetime.fromtimestamp(now).strftime("%H:%M:%S")
        for inc in list(self._active_incidents.values()):
            inc["status"] = "RESOLVED"
            inc["resolved_at"] = now
            inc["resolved_at_str"] = now_str
        self._active_incidents.clear()
