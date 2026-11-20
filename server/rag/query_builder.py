"""
VYTRON RAG — Contextual Incident Query Builder
Extracts sanitized incident evidence to construct targeted semantic queries for vector retrieval.
"""

from typing import Any

METRIC_TOPIC_MAP = {
    "cpu_utilization": "CPU Performance and Thread Starvation",
    "ram_utilization": "Memory Exhaustion, Heap Leaks, and OOM killer",
    "requests_per_sec": "High Ingress HTTP Request Load and Rate Limiting",
    "response_time": "Application Latency Degradation and Thread Contention",
    "query_latency": "PostgreSQL Slow Query Optimization and Lock Contention",
    "active_connections": "Database Connection Pool Saturation and Connection Leaks",
    "disk_io_utilization": "Storage Disk I/O Saturation and High iowait",
    "login_requests_per_sec": "Authentication Traffic Surge and Rate Limiting",
    "failed_login_attempts": "Credential Stuffing, Failed Logins, and Security Defense",
    "auth_latency": "SSO Latency Spikes and LDAP Directory Delays",
    "auth_success_rate": "Authentication Failures and Token Validation Rejection",
    "backup_progress": "Stalled Backup Snapshots and Storage Freezes",
    "data_transfer_rate": "Storage Throughput Degradation and Network Transfer Throttle",
    "backup_duration": "Disaster Recovery Backup Delay and Window Overrun",
    "backup_failure_count": "Backup Archive Failures and ENOSPC Storage Quota",
    "bandwidth_utilization": "Network Bandwidth Saturation and Traffic Shaping",
    "network_latency": "Network Latency Spikes, Bufferbloat, and Routing Delays",
    "packet_loss": "Interface Packet Loss, CRC Errors, and Ring Buffer Overflows",
    "throughput": "Network Throughput Collapse and TCP Retransmissions",
}

class ContextualQueryBuilder:
    @staticmethod
    def build_query(incident: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Builds a semantic search query from sanitized incident evidence.
        Returns:
            - query_text: str (optimized for SentenceTransformer embedding)
            - metadata_hints: dict (topic, target_metric, server_id)
        """
        server_id = incident.get("server_id", "SERVER")
        server_name = incident.get("server_name", "Infrastructure Node")
        server_type = incident.get("server_type", "Server")
        metric_key = incident.get("metric_key", "")
        metric_name = incident.get("metric_name", "Metric")
        observed = incident.get("observed_value", "")
        threshold = incident.get("threshold_value", "")
        unit = incident.get("unit", "")
        issue_desc = incident.get("issue_description", "")
        severity = incident.get("severity", "MEDIUM")

        topic = METRIC_TOPIC_MAP.get(metric_key, f"{metric_name} Troubleshooting")

        # Construct dense semantic query
        query_text = (
            f"Troubleshooting and root cause diagnostics for {server_type} ({server_name} {server_id}). "
            f"{topic}. Observed {metric_name} reached {observed} {unit} breaching {severity.lower()} "
            f"threshold {threshold} {unit}. Diagnostic commands, system inspection, and remediation actions."
        )

        hints = {
            "server_id": server_id,
            "metric_key": metric_key,
            "topic": topic,
            "severity": severity,
        }

        return query_text, hints
