"""
VYTRON — 5-Server Infrastructure Configuration & Issue Catalogue
Defines server profiles, baseline parameters, detection thresholds,
extensible issue types catalogue, and lightweight metric relationship rules.
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
                "thresholds": {"warning": 160.0, "critical": 180.0, "direction": "above"},
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

# ── Configurable Issue Catalogue ─────────────────────────────────────────
# Maps each (server_id, metric_key) to realistic, valid issue profiles.
# Easily extensible without modifying engine mechanics.

ISSUE_CATALOGUE: dict[str, dict[str, list[dict[str, Any]]]] = {
    "APP-01": {
        "cpu_utilization": [
            {
                "issue_type": "CPU Spike",
                "description": "Sudden compute spike due to high transaction volume or heavy unoptimized thread tasks.",
                "warn_range": (82.0, 89.0),
                "crit_range": (91.0, 97.0),
                "recommended_action": "Scale out application container replicas (HPA) or restart starved thread pool worker executors.",
            },
            {
                "issue_type": "Sustained High CPU",
                "description": "Continuous elevated processor load caused by infinite recursion or unoptimized computation.",
                "warn_range": (83.0, 88.0),
                "crit_range": (92.0, 96.0),
                "recommended_action": "Profile application CPU flamegraph to detect hotspots and balance incoming request distribution.",
            },
        ],
        "ram_utilization": [
            {
                "issue_type": "Memory Pressure",
                "description": "Moderate memory leak or accumulation of unevicted cache entries consuming resident memory.",
                "warn_range": (81.0, 88.0),
                "crit_range": (91.0, 96.0),
                "recommended_action": "Trigger manual garbage collection sweep and purge expired in-memory cache partitions.",
            },
            {
                "issue_type": "Memory Exhaustion",
                "description": "Severe heap memory consumption approaching Out-Of-Memory (OOM) threshold.",
                "warn_range": (84.0, 89.0),
                "crit_range": (93.0, 98.0),
                "recommended_action": "Investigate application memory heap dump; resize JVM metaspace and restart leak-prone worker nodes.",
            },
        ],
        "requests_per_sec": [
            {
                "issue_type": "Request Surge",
                "description": "Unexpected spike in user traffic exceeding capacity projections.",
                "warn_range": (620.0, 780.0),
                "crit_range": (920.0, 1350.0),
                "recommended_action": "Enable API gateway rate limiting and divert incoming traffic to standby edge nodes.",
            },
            {
                "issue_type": "Request Overload",
                "description": "Massive ingress HTTP request flood saturating application ingestion thread capacity.",
                "warn_range": (650.0, 820.0),
                "crit_range": (980.0, 1500.0),
                "recommended_action": "Enforce WAF rate-limiting quotas and apply circuit breaker patterns on edge proxies.",
            },
        ],
        "response_time": [
            {
                "issue_type": "Slow Response",
                "description": "Processing latency degradation in upstream dependencies or thread starvation.",
                "warn_range": (550.0, 850.0),
                "crit_range": (1100.0, 2200.0),
                "recommended_action": "Inspect upstream slow database calls and throttle incoming HTTP client concurrency.",
            },
            {
                "issue_type": "Request Timeout",
                "description": "Severe request latency causing client-side HTTP 504 timeouts and connection drops.",
                "warn_range": (600.0, 900.0),
                "crit_range": (1250.0, 3200.0),
                "recommended_action": "Abort stalled synchronous requests, enable async messaging queue, and scale worker pool.",
            },
        ],
    },
    "DB-01": {
        "query_latency": [
            {
                "issue_type": "Slow Queries",
                "description": "Complex sequential table scans causing query queue accumulation.",
                "warn_range": (520.0, 800.0),
                "crit_range": (1050.0, 2400.0),
                "recommended_action": "Kill long-running queries; examine missing indexes and analyze query execution plan.",
            },
            {
                "issue_type": "Query Bottleneck",
                "description": "Lock contention on relational transaction tables blocking read/write workers.",
                "warn_range": (580.0, 880.0),
                "crit_range": (1150.0, 2800.0),
                "recommended_action": "Terminate blocking lock transactions (pg_cancel_backend) and enforce query timeout thresholds.",
            },
        ],
        "active_connections": [
            {
                "issue_type": "Connection Saturation",
                "description": "Client connection pool exhaustion approaching server max_connections limit.",
                "warn_range": (162.0, 175.0),
                "crit_range": (182.0, 196.0),
                "recommended_action": "Increase database connection pool size or terminate orphaned idle connections (pg_terminate_backend).",
            },
            {
                "issue_type": "Connection Leak",
                "description": "Applications opening pooled connections without returning them to the pool.",
                "warn_range": (164.0, 176.0),
                "crit_range": (184.0, 198.0),
                "recommended_action": "Enforce aggressive idle client timeout and verify connection release in application ORM layers.",
            },
        ],
        "disk_io_utilization": [
            {
                "issue_type": "Disk I/O Bottleneck",
                "description": "Heavy swap activity and unindexed disk read operations throttling IOPS throughput.",
                "warn_range": (76.0, 82.0),
                "crit_range": (86.0, 95.0),
                "recommended_action": "Optimize heavy sequential table scans; re-route read operations to read-replicas.",
            },
            {
                "issue_type": "Disk I/O Saturation",
                "description": "Storage volume write queue depth saturating physical SSD IOPS limit.",
                "warn_range": (78.0, 83.0),
                "crit_range": (87.0, 96.0),
                "recommended_action": "Flush dirty write buffers, enable write-ahead log compression, and migrate tables to fast SSD storage.",
            },
        ],
        "cpu_utilization": [
            {
                "issue_type": "Database CPU Spike",
                "description": "Database server processor overloaded by simultaneous complex aggregation queries.",
                "warn_range": (76.0, 83.0),
                "crit_range": (86.0, 95.0),
                "recommended_action": "Check for unindexed full table scans or runaway stored procedures.",
            },
            {
                "issue_type": "Query Engine Overload",
                "description": "Internal query planner thread pool starved by concurrent joins and sorting tasks.",
                "warn_range": (77.0, 84.0),
                "crit_range": (88.0, 96.0),
                "recommended_action": "Tune work_mem parameter and throttle concurrent analytical background jobs.",
            },
        ],
    },
    "AUTH-01": {
        "login_requests_per_sec": [
            {
                "issue_type": "Login Surge",
                "description": "High influx of user login operations during morning shift or marketing campaign launch.",
                "warn_range": (260.0, 360.0),
                "crit_range": (420.0, 750.0),
                "recommended_action": "Scale authentication Redis cache cluster and inspect SSO LDAP token verification delay.",
            },
            {
                "issue_type": "Authentication Traffic Surge",
                "description": "Rapid succession of authentication tokens verification requests from API consumers.",
                "warn_range": (270.0, 380.0),
                "crit_range": (440.0, 850.0),
                "recommended_action": "Deploy additional stateless authentication token verification nodes behind load balancer.",
            },
        ],
        "failed_login_attempts": [
            {
                "issue_type": "Failed Login Spike",
                "description": "Elevated invalid password and credential rejections across multiple accounts.",
                "warn_range": (11.0, 22.0),
                "crit_range": (27.0, 75.0),
                "recommended_action": "Enforce IP rate-limiting, activate Cloudflare bot protection, and block suspicious subnet.",
            },
            {
                "issue_type": "Suspicious Login Activity",
                "description": "Distributed credential stuffing attack targeting enterprise authentication endpoints.",
                "warn_range": (12.0, 24.0),
                "crit_range": (30.0, 95.0),
                "recommended_action": "Trigger adaptive MFA step-up authentication and block malicious IP range via firewall.",
            },
        ],
        "auth_latency": [
            {
                "issue_type": "Authentication Slowdown",
                "description": "Delay in JWT signing operations or LDAP directory response latency.",
                "warn_range": (520.0, 850.0),
                "crit_range": (1080.0, 2400.0),
                "recommended_action": "Check upstream LDAP/Active Directory domain controller latency and warm up Redis token caches.",
            },
            {
                "issue_type": "SSO Latency Spike",
                "description": "Single Sign-On SAML/OIDC identity provider handshake timeout.",
                "warn_range": (550.0, 900.0),
                "crit_range": (1150.0, 2600.0),
                "recommended_action": "Switch to redundant secondary identity provider endpoint and inspect token signing key cache.",
            },
        ],
        "auth_success_rate": [
            {
                "issue_type": "Authentication Failure Increase",
                "description": "Significant portion of authentication sessions failing due to credential rejection or token expiry.",
                "warn_range": (82.0, 89.0),
                "crit_range": (55.0, 74.0),
                "recommended_action": "Check token validation service endpoint and investigate identity provider availability.",
            },
            {
                "issue_type": "Identity Provider Degradation",
                "description": "Downstream identity directory rejecting or failing to validate enterprise login tokens.",
                "warn_range": (80.0, 88.0),
                "crit_range": (45.0, 72.0),
                "recommended_action": "Inspect directory service health, verify signing certificates, and restart Auth SSO gateway.",
            },
        ],
    },
    "BACKUP-01": {
        "backup_progress": [
            {
                "issue_type": "Backup Stalled",
                "description": "Snapshot archival task frozen at intermediate percentage without advancing.",
                "warn_range": (20.0, 35.0),
                "crit_range": (10.0, 25.0),
                "recommended_action": "Check disk write locks, inspect NFS mount connectivity, and restart snapshot worker thread.",
            },
            {
                "issue_type": "Snapshot Delay",
                "description": "Volume snapshot checkpoint creation taking abnormally long to persist blocks.",
                "warn_range": (22.0, 38.0),
                "crit_range": (12.0, 28.0),
                "recommended_action": "Verify storage volume quota (ENOSPC), check mount point permissions and retry snapshot.",
            },
        ],
        "data_transfer_rate": [
            {
                "issue_type": "Slow Data Transfer",
                "description": "Archival data streaming speed severely degraded due to storage bandwidth throttling.",
                "warn_range": (5.0, 9.5),
                "crit_range": (0.8, 2.8),
                "recommended_action": "Inspect storage network bandwidth throttle and check backup volume I/O congestion.",
            },
            {
                "issue_type": "Storage Throughput Drop",
                "description": "Network storage protocol throughput collapsed under remote SAN congestion.",
                "warn_range": (6.0, 9.8),
                "crit_range": (0.5, 2.5),
                "recommended_action": "Reroute storage replication to secondary iSCSI link and verify target SAN array health.",
            },
        ],
        "backup_duration": [
            {
                "issue_type": "Backup Delay",
                "description": "Scheduled archival job exceeded typical execution window.",
                "warn_range": (320.0, 520.0),
                "crit_range": (650.0, 1400.0),
                "recommended_action": "Abort stalled snapshot process and verify snapshot consistency before rescheduling.",
            },
            {
                "issue_type": "Snapshot Window Overrun",
                "description": "Disaster recovery snapshot running into production business hours window.",
                "warn_range": (350.0, 580.0),
                "crit_range": (700.0, 1800.0),
                "recommended_action": "Split backup into parallel incremental shards and exclude non-critical staging partitions.",
            },
        ],
        "backup_failure_count": [
            {
                "issue_type": "Backup Failures",
                "description": "Archival daemon logged repeated CRC validation or write failure errors.",
                "warn_range": (1.0, 1.0),
                "crit_range": (2.0, 6.0),
                "recommended_action": "Verify storage volume quota (ENOSPC), check mount point permissions and retry snapshot.",
            },
            {
                "issue_type": "Disaster Recovery Error",
                "description": "Critical snapshot volume block corrupted during replication.",
                "warn_range": (1.0, 1.0),
                "crit_range": (2.0, 5.0),
                "recommended_action": "Perform storage volume filesystem check (fsck), rebuild parity blocks, and trigger fresh volume clone.",
            },
        ],
    },
    "NETWORK-01": {
        "bandwidth_utilization": [
            {
                "issue_type": "Bandwidth Saturation",
                "description": "Core interface traffic reaching maximum NIC link throughput.",
                "warn_range": (78.0, 88.0),
                "crit_range": (92.0, 98.0),
                "recommended_action": "Activate egress traffic shaping and throttle high-bandwidth video/file transfer consumers.",
            },
            {
                "issue_type": "Transit Pipe Congestion",
                "description": "Backbone uplink bandwidth fully consumed by concurrent synchronization streams.",
                "warn_range": (79.0, 87.0),
                "crit_range": (91.0, 97.0),
                "recommended_action": "Enable QoS traffic classification and prioritize control plane and transactional packets.",
            },
        ],
        "network_latency": [
            {
                "issue_type": "Latency Spike",
                "description": "Packet transit round-trip-time (RTT) elevated due to queue buildup at gateway router.",
                "warn_range": (160.0, 270.0),
                "crit_range": (320.0, 650.0),
                "recommended_action": "Reroute traffic around congested transit link and verify BGP routing table convergence.",
            },
            {
                "issue_type": "Network Congestion",
                "description": "Bufferbloat on internal switch ports causing severe transmission delay.",
                "warn_range": (170.0, 280.0),
                "crit_range": (340.0, 750.0),
                "recommended_action": "Clear network buffer queues, adjust TCP congestion algorithm to BBR, and inspect switch logs.",
            },
        ],
        "packet_loss": [
            {
                "issue_type": "Packet Loss Spike",
                "description": "Dropped frames on interface due to transmission collisions or MTU mismatch.",
                "warn_range": (3.2, 4.8),
                "crit_range": (5.5, 12.0),
                "recommended_action": "Inspect switch interface CRC checksum errors, replace faulty patch cable, and check duplex mode.",
            },
            {
                "issue_type": "Interface Packet Drop",
                "description": "Physical NIC receive ring buffer overflow discarding incoming frames.",
                "warn_range": (3.4, 4.9),
                "crit_range": (6.0, 15.0),
                "recommended_action": "Increase NIC ring buffer size (ethtool -G) and inspect hardware link negotiation status.",
            },
        ],
        "throughput": [
            {
                "issue_type": "Throughput Drop",
                "description": "Effective transmission rate collapsed due to retransmissions and window shrinking.",
                "warn_range": (120.0, 190.0),
                "crit_range": (30.0, 75.0),
                "recommended_action": "Inspect TCP window scaling parameters and verify MTU consistency across all network hops.",
            },
            {
                "issue_type": "Egress Throttle",
                "description": "Upstream ISP or cloud provider policing mechanism artificially capping throughput.",
                "warn_range": (130.0, 195.0),
                "crit_range": (25.0, 70.0),
                "recommended_action": "Review cloud bandwidth egress quota and distribute outbound traffic across multi-region VPC peering links.",
            },
        ],
    },
}

# ── Metric Relationship Rules ───────────────────────────────────────────
# Defines lightweight rule-based secondary correlations on affected servers.
# If a primary metric is abnormal, secondary metrics on the same server receive logical nudges.

METRIC_RELATIONSHIPS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "APP-01": {
        "cpu_utilization": [
            {"target_metric": "response_time", "factor": 12.0, "noise_scale": 15.0},
            {"target_metric": "ram_utilization", "factor": 0.25, "noise_scale": 1.5},
        ],
        "requests_per_sec": [
            {"target_metric": "cpu_utilization", "factor": 0.045, "noise_scale": 2.0},
            {"target_metric": "response_time", "factor": 0.85, "noise_scale": 10.0},
        ],
        "response_time": [
            {"target_metric": "cpu_utilization", "factor": 0.02, "noise_scale": 1.5},
        ],
    },
    "DB-01": {
        "query_latency": [
            {"target_metric": "active_connections", "factor": 0.075, "noise_scale": 3.0},
            {"target_metric": "cpu_utilization", "factor": 0.04, "noise_scale": 2.0},
            {"target_metric": "disk_io_utilization", "factor": 0.045, "noise_scale": 2.0},
        ],
        "active_connections": [
            {"target_metric": "query_latency", "factor": 3.5, "noise_scale": 15.0},
            {"target_metric": "cpu_utilization", "factor": 0.25, "noise_scale": 2.0},
        ],
        "disk_io_utilization": [
            {"target_metric": "query_latency", "factor": 8.0, "noise_scale": 20.0},
        ],
    },
    "AUTH-01": {
        "login_requests_per_sec": [
            {"target_metric": "auth_latency", "factor": 1.8, "noise_scale": 5.0},
        ],
        "failed_login_attempts": [
            {"target_metric": "auth_latency", "factor": 14.0, "noise_scale": 8.0},
            {"target_metric": "auth_success_rate", "factor": -0.85, "noise_scale": 1.0},
        ],
        "auth_latency": [
            {"target_metric": "auth_success_rate", "factor": -0.015, "noise_scale": 0.5},
        ],
    },
    "BACKUP-01": {
        "data_transfer_rate": [
            {"target_metric": "backup_duration", "factor": -4.0, "noise_scale": 5.0},
        ],
        "backup_failure_count": [
            {"target_metric": "backup_duration", "factor": 60.0, "noise_scale": 10.0},
        ],
    },
    "NETWORK-01": {
        "bandwidth_utilization": [
            {"target_metric": "network_latency", "factor": 2.2, "noise_scale": 5.0},
            {"target_metric": "packet_loss", "factor": 0.04, "noise_scale": 0.1},
        ],
        "packet_loss": [
            {"target_metric": "network_latency", "factor": 25.0, "noise_scale": 8.0},
            {"target_metric": "throughput", "factor": -45.0, "noise_scale": 15.0},
        ],
        "network_latency": [
            {"target_metric": "throughput", "factor": -1.2, "noise_scale": 10.0},
        ],
    },
}

# ── Recommended Actions Catalog (Fallback & Lookup) ──────────────────────

RECOMMENDED_ACTIONS: dict[str, str] = {
    "APP-01.cpu_utilization": "Scale out application container replicas (HPA) or restart starved thread pool worker executors.",
    "APP-01.ram_utilization": "Investigate application memory leak in heap space; trigger garbage collection or resize JVM metaspace.",
    "APP-01.requests_per_sec": "Enable API gateway rate limiting and divert incoming traffic to standby edge nodes.",
    "APP-01.response_time": "Inspect upstream slow database calls and throttle incoming HTTP client concurrency.",
    "DB-01.query_latency": "Kill long-running queries; examine missing indexes and analyze query execution plan.",
    "DB-01.active_connections": "Increase database connection pool size or terminate orphaned idle connections (pg_terminate_backend).",
    "DB-01.disk_io_utilization": "Optimize heavy sequential table scans; re-route read operations to read-replicas.",
    "DB-01.cpu_utilization": "Check for unindexed full table scans or runaway stored procedures.",
    "AUTH-01.login_requests_per_sec": "Scale authentication Redis cache cluster and inspect SSO LDAP token verification delay.",
    "AUTH-01.failed_login_attempts": "Enforce IP rate-limiting, activate Cloudflare bot protection, and block suspicious subnet.",
    "AUTH-01.auth_latency": "Check upstream LDAP/Active Directory domain controller latency and warm up Redis token caches.",
    "AUTH-01.auth_success_rate": "Check token validation service endpoint and investigate identity provider availability.",
    "BACKUP-01.backup_progress": "Check disk write locks, inspect NFS mount connectivity, and restart snapshot worker thread.",
    "BACKUP-01.data_transfer_rate": "Inspect storage network bandwidth throttle and check backup volume I/O congestion.",
    "BACKUP-01.backup_duration": "Abort stalled snapshot process and verify snapshot consistency before rescheduling.",
    "BACKUP-01.backup_failure_count": "Verify storage volume quota (ENOSPC), check mount point permissions and retry snapshot.",
    "NETWORK-01.bandwidth_utilization": "Activate egress traffic shaping and throttle high-bandwidth video/file transfer consumers.",
    "NETWORK-01.network_latency": "Reroute traffic around congested transit link and verify BGP routing table convergence.",
    "NETWORK-01.packet_loss": "Inspect switch interface CRC checksum errors, replace faulty patch cable, and check duplex mode.",
    "NETWORK-01.throughput": "Inspect TCP window scaling parameters and verify MTU consistency across all network hops.",
}
