"""
VYTRON — 5-Server Infrastructure Configuration
Defines the 5 servers, their parameters, units, baselines, and detection thresholds.
"""

from typing import Any

# ── 5 Server Profiles ───────────────────────────────────────────────────

SERVERS_CONFIG: dict[str, dict[str, Any]] = {
    "APP-01": {
        "id": "APP-01",
        "name": "Application Server",
        "type": "Application",
        "description": "Main transaction processing & application workloads",
        "parameters": {
            "cpu_utilization": {
                "name": "CPU Utilization",
                "unit": "%",
                "baseline": 34.0,
                "noise_std": 1.8,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 80.0, "critical": 90.0, "direction": "above"},
            },
            "ram_utilization": {
                "name": "RAM Utilization",
                "unit": "%",
                "baseline": 48.0,
                "noise_std": 1.2,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 80.0, "critical": 90.0, "direction": "above"},
            },
            "requests_per_sec": {
                "name": "Requests Per Second",
                "unit": "req/s",
                "baseline": 145.0,
                "noise_std": 8.0,
                "min": 0.0,
                "max": 2000.0,
                "thresholds": {"warning": 600.0, "critical": 900.0, "direction": "above"},
            },
            "response_time": {
                "name": "Application Response Time",
                "unit": "ms",
                "baseline": 42.0,
                "noise_std": 3.0,
                "min": 1.0,
                "max": 10000.0,
                "thresholds": {"warning": 500.0, "critical": 1000.0, "direction": "above"},
            },
        },
    },
    "DB-01": {
        "id": "DB-01",
        "name": "Database Server",
        "type": "Database",
        "description": "Relational database operations & query execution",
        "parameters": {
            "query_latency": {
                "name": "Query Latency",
                "unit": "ms",
                "baseline": 18.0,
                "noise_std": 2.2,
                "min": 1.0,
                "max": 10000.0,
                "thresholds": {"warning": 500.0, "critical": 1000.0, "direction": "above"},
            },
            "active_connections": {
                "name": "Active Connections",
                "unit": "conns",
                "baseline": 35.0,
                "noise_std": 2.5,
                "min": 0.0,
                "max": 200.0,
                "thresholds": {"warning": 160.0, "critical": 180.0, "direction": "above"},  # 80% & 90% of 200
            },
            "disk_io_utilization": {
                "name": "Disk I/O Utilization",
                "unit": "%",
                "baseline": 28.0,
                "noise_std": 1.5,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 75.0, "critical": 85.0, "direction": "above"},
            },
            "cpu_utilization": {
                "name": "CPU Utilization",
                "unit": "%",
                "baseline": 24.0,
                "noise_std": 1.6,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 75.0, "critical": 85.0, "direction": "above"},
            },
        },
    },
    "AUTH-01": {
        "id": "AUTH-01",
        "name": "Authentication Server",
        "type": "Authentication",
        "description": "Token issuance, SSO verification & identity management",
        "parameters": {
            "login_requests_per_sec": {
                "name": "Login Requests",
                "unit": "req/s",
                "baseline": 48.0,
                "noise_std": 3.5,
                "min": 0.0,
                "max": 2000.0,
                "thresholds": {"warning": 250.0, "critical": 400.0, "direction": "above"},
            },
            "failed_login_attempts": {
                "name": "Failed Login Attempts",
                "unit": "fails/min",
                "baseline": 0.5,
                "noise_std": 0.3,
                "min": 0.0,
                "max": 500.0,
                "thresholds": {"warning": 10.0, "critical": 25.0, "direction": "above"},
            },
            "auth_latency": {
                "name": "Authentication Latency",
                "unit": "ms",
                "baseline": 22.0,
                "noise_std": 1.8,
                "min": 1.0,
                "max": 10000.0,
                "thresholds": {"warning": 500.0, "critical": 1000.0, "direction": "above"},
            },
            "auth_success_rate": {
                "name": "Success Rate",
                "unit": "%",
                "baseline": 99.5,
                "noise_std": 0.2,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 90.0, "critical": 75.0, "direction": "below"},
            },
        },
    },
    "BACKUP-01": {
        "id": "BACKUP-01",
        "name": "Backup Server",
        "type": "Backup",
        "description": "Snapshot archival, disaster recovery & volume backups",
        "parameters": {
            "backup_progress": {
                "name": "Backup Progress",
                "unit": "%",
                "baseline": 45.0,
                "noise_std": 0.0,
                "min": 0.0,
                "max": 100.0,
                "thresholds": None,
            },
            "data_transfer_rate": {
                "name": "Transfer Rate",
                "unit": "MB/s",
                "baseline": 48.0,
                "noise_std": 2.5,
                "min": 0.0,
                "max": 500.0,
                "thresholds": {"warning": 10.0, "critical": 3.0, "direction": "below"},
            },
            "backup_duration": {
                "name": "Backup Duration",
                "unit": "sec",
                "baseline": 110.0,
                "noise_std": 2.0,
                "min": 0.0,
                "max": 3600.0,
                "thresholds": {"warning": 300.0, "critical": 600.0, "direction": "above"},
            },
            "backup_failure_count": {
                "name": "Failure Count",
                "unit": "errors",
                "baseline": 0.0,
                "noise_std": 0.0,
                "min": 0.0,
                "max": 50.0,
                "thresholds": {"warning": 1.0, "critical": 2.0, "direction": "above"},
            },
        },
    },
    "NETWORK-01": {
        "id": "NETWORK-01",
        "name": "Network Server",
        "type": "Network",
        "description": "Core routing, packet switching & traffic distribution",
        "parameters": {
            "bandwidth_utilization": {
                "name": "Bandwidth Utilization",
                "unit": "%",
                "baseline": 34.0,
                "noise_std": 1.8,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 75.0, "critical": 90.0, "direction": "above"},
            },
            "network_latency": {
                "name": "Network Latency",
                "unit": "ms",
                "baseline": 12.0,
                "noise_std": 1.4,
                "min": 0.5,
                "max": 5000.0,
                "thresholds": {"warning": 150.0, "critical": 300.0, "direction": "above"},
            },
            "packet_loss": {
                "name": "Packet Loss",
                "unit": "%",
                "baseline": 0.02,
                "noise_std": 0.01,
                "min": 0.0,
                "max": 100.0,
                "thresholds": {"warning": 3.0, "critical": 5.0, "direction": "above"},
            },
            "throughput": {
                "name": "Throughput",
                "unit": "Mbps",
                "baseline": 680.0,
                "noise_std": 25.0,
                "min": 0.0,
                "max": 5000.0,
                "thresholds": {"warning": 200.0, "critical": 80.0, "direction": "below"},
            },
        },
    },
}

# ── 4 Predefined Scenarios ──────────────────────────────────────────────

SCENARIOS_CONFIG: dict[str, dict[str, Any]] = {
    "scenario_01": {
        "id": "scenario_01",
        "title": "Scenario 01: Application & Database",
        "description": "APP-01 experiences heavy CPU & response time surge; DB-01 query latency spikes and connections surge.",
        "affected_servers": ["APP-01", "DB-01"],
        "mutations": {
            "APP-01": {
                "cpu_utilization": 94.5,
                "ram_utilization": 74.0,
                "response_time": 1250.0,
                "requests_per_sec": 85.0,
            },
            "DB-01": {
                "query_latency": 1150.0,
                "active_connections": 178.0,
                "disk_io_utilization": 89.0,
                "cpu_utilization": 82.0,
            },
        },
    },
    "scenario_02": {
        "id": "scenario_02",
        "title": "Scenario 02: Authentication & Network",
        "description": "AUTH-01 experiences credential brute force; NETWORK-01 experiences high packet loss & latency.",
        "affected_servers": ["AUTH-01", "NETWORK-01"],
        "mutations": {
            "AUTH-01": {
                "login_requests_per_sec": 380.0,
                "failed_login_attempts": 32.0,
                "auth_latency": 1180.0,
                "auth_success_rate": 68.0,
            },
            "NETWORK-01": {
                "packet_loss": 6.8,
                "network_latency": 340.0,
                "bandwidth_utilization": 94.0,
                "throughput": 120.0,
            },
        },
    },
    "scenario_03": {
        "id": "scenario_03",
        "title": "Scenario 03: Backup & Application",
        "description": "BACKUP-01 duration explodes and transfers stall; APP-01 response time climbs with moderate CPU.",
        "affected_servers": ["BACKUP-01", "APP-01"],
        "mutations": {
            "BACKUP-01": {
                "backup_duration": 480.0,
                "data_transfer_rate": 2.4,
                "backup_failure_count": 3.0,
                "backup_progress": 22.0,
            },
            "APP-01": {
                "response_time": 1050.0,
                "cpu_utilization": 84.5,
                "ram_utilization": 62.0,
            },
        },
    },
    "scenario_04": {
        "id": "scenario_04",
        "title": "Scenario 04: Database & Network",
        "description": "DB-01 connection pool exhausts and CPU spikes; NETWORK-01 latency surges and drops packets.",
        "affected_servers": ["DB-01", "NETWORK-01"],
        "mutations": {
            "DB-01": {
                "active_connections": 188.0,
                "query_latency": 1080.0,
                "cpu_utilization": 88.5,
                "disk_io_utilization": 78.0,
            },
            "NETWORK-01": {
                "network_latency": 360.0,
                "packet_loss": 5.8,
                "bandwidth_utilization": 82.0,
            },
        },
    },
}

# ── Recommended Actions Catalog ─────────────────────────────────────────

RECOMMENDED_ACTIONS: dict[str, str] = {
    "APP-01.cpu_utilization": "Scale out application container replicas (HPA) or restart starved thread pool worker executors.",
    "APP-01.ram_utilization": "Investigate application memory leak in heap space; trigger garbage collection or resize JVM metaspace.",
    "APP-01.response_time": "Inspect upstream slow database calls and throttle incoming HTTP client concurrency.",
    "DB-01.query_latency": "Kill long-running queries; examine missing indexes and analyze query execution plan.",
    "DB-01.active_connections": "Increase database connection pool size or terminate orphaned idle connections (pg_terminate_backend).",
    "DB-01.disk_io_utilization": "Optimize heavy sequential table scans; re-route read operations to read-replicas.",
    "DB-01.cpu_utilization": "Check for unindexed full table scans or runaway stored procedures.",
    "AUTH-01.failed_login_attempts": "Enforce IP rate-limiting, activate Cloudflare bot protection, and block suspicious subnet.",
    "AUTH-01.auth_latency": "Scale authentication Redis cache cluster and inspect SSO LDAP token verification delay.",
    "AUTH-01.auth_success_rate": "Check token validation service endpoint and investigate identity provider availability.",
    "BACKUP-01.backup_failure_count": "Verify storage volume quota (ENOSPC), check mount point permissions and retry snapshot.",
    "BACKUP-01.data_transfer_rate": "Inspect storage network bandwidth throttle and check backup volume I/O congestion.",
    "BACKUP-01.backup_duration": "Abort stalled snapshot process and verify snapshot consistency before rescheduling.",
    "NETWORK-01.packet_loss": "Inspect switch interface CRC checksum errors, replace faulty patch cable, and check duplex mode.",
    "NETWORK-01.network_latency": "Reroute traffic around congested transit link and verify BGP routing table convergence.",
    "NETWORK-01.bandwidth_utilization": "Activate egress traffic shaping and throttle high-bandwidth video/file transfer consumers.",
}
