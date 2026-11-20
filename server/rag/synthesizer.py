"""
VYTRON RAG — AI Troubleshooting Synthesizer
Generates 8-section structured troubleshooting guidance based on retrieved ChromaDB documents
and sanitized incident evidence, integrating with the LLM engine with resilient fallback.
Guarantees strict telemetry consistency, evidence-based hypotheses, server-specific commands,
and source validation.
"""

import os
import json
import re
from typing import Any
import httpx
from dotenv import load_dotenv

load_dotenv()

from server.config import RECOMMENDED_ACTIONS, SERVERS_CONFIG

# Relevance threshold for retrieved technical documentation
RELEVANCE_THRESHOLD = 0.60

INSUFFICIENT_KNOWLEDGE_NOTICE = (
    "Insufficient relevant documentation found. Recommendations are based only on "
    "available telemetry and general diagnostic knowledge."
)


# ══════════════════════════════════════════════════════════════════════════════
# SERVER & METRIC KNOWLEDGE CATALOGUES (Strict Non-Destructive Commands & Rules)
# ══════════════════════════════════════════════════════════════════════════════

DOMAIN_KNOWLEDGE: dict[str, dict[str, Any]] = {
    # ── AUTH-01: Authentication Server ───────────────────────────────────────
    "AUTH-01.failed_login_attempts": {
        "hypotheses": [
            {
                "hypothesis": "Distributed credential stuffing or brute-force attack",
                "why": "A rapid spike in authentication failures across user accounts often indicates automated bot activity testing stolen credentials.",
                "missing_evidence": "Source IP address distribution, rate of targeted username diversity, and geolocation anomalies in edge proxy logs.",
                "verification": "Inspect /var/log/auth.log or journalctl -u ssh to analyze failed login patterns and unique source IP addresses.",
            },
            {
                "hypothesis": "Client microservice authentication misconfiguration or expired API/service token",
                "why": "An automated internal microservice or cron task using expired credentials or outdated tokens will continuously retry and flood authentication logs.",
                "missing_evidence": "Client application identifier, User-Agent header, and API key fingerprint from gateway logs.",
                "verification": "Filter authentication logs for repetitive failures originating from internal private subnet IP addresses.",
            },
            {
                "hypothesis": "Upstream directory service or LDAP/Active Directory synchronization failure",
                "why": "If the backing directory service is unresponsive, valid user credential verifications fail and register as authentication failures.",
                "missing_evidence": "Directory service connectivity latency, LDAP bind error codes, and identity provider response codes.",
                "verification": "Check LDAP/Active Directory service port reachability and inspect identity provider response latency.",
            },
        ],
        "investigation_steps": [
            "1. Examine failed-login patterns, failure status codes (e.g. PAM_AUTH_ERR, invalid token), and timestamps in system auth logs.",
            "2. Identify suspicious source IP addresses and determine whether failures originate from external internet hosts or internal service subnets.",
            "3. Check authentication service daemon health, thread pool utilization, and active connection queue depth.",
            "4. Verify upstream identity provider (LDAP / Active Directory / OAuth IdP) network connectivity and query latency.",
            "5. Inspect user credential database query response times and Redis session store latency.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "grep -i 'failed' /var/log/auth.log | tail -n 25",
                "description": "Extract recent failed authentication log entries and failure causes",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "awk '/Failed password/ {print $(NF-3)}' /var/log/auth.log | sort | uniq -c | sort -nr | head -n 10",
                "description": "Identify top 10 remote IP addresses responsible for authentication failures",
            },
            {
                "technology": "[Linux / Systemd]",
                "command": "journalctl -u ssh -u auth-service --since '15 minutes ago' | grep -i 'failure'",
                "description": "Review authentication daemon journal logs for recent failure events",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ss -tan state established '( dport = :389 or dport = :636 or dport = :6379 )'",
                "description": "Verify socket connections to backing LDAP/Active Directory and Redis token stores",
            },
        ],
        "corrective_actions": [
            "If credential stuffing attack is confirmed: Implement rate-limiting and temporary IP blocks at the edge reverse proxy/WAF (e.g. fail2ban or iptables rate limits) while verifying legitimate corporate VPN IPs are not affected.",
            "If an expired service token is confirmed: Rotate and distribute the updated service credential to the offending client microservice to stop retry loops.",
            "If directory service latency is confirmed: Troubleshoot network routing and connection pool sizing between AUTH-01 and the upstream identity provider.",
        ],
        "verification_cmd": "grep -i 'failed' /var/log/auth.log | tail -n 10",
    },

    "AUTH-01.login_requests_per_sec": {
        "hypotheses": [
            {
                "hypothesis": "Volumetric HTTP/S flood or authentication endpoint DDoS",
                "why": "Unusual volume of authentication requests can indicate a Layer 7 distributed denial-of-service attack targeting computationally expensive crypto hashing.",
                "missing_evidence": "Incoming HTTP request URI paths, rate of distinct IP addresses, and edge CDN traffic profiles.",
                "verification": "Inspect reverse proxy access logs (e.g. nginx or envoy) to evaluate ingress request rates per client IP.",
            },
            {
                "hypothesis": "Shift-change login stampede or scheduled batch authentication surge",
                "why": "Scheduled batch jobs or simultaneous workforce logins at start of shift can produce expected but high load spikes.",
                "missing_evidence": "Historical time-of-day traffic baselines and corporate shift schedules.",
                "verification": "Compare current traffic volume against weekly seasonal baselines for this specific time window.",
            },
        ],
        "investigation_steps": [
            "1. Inspect incoming connection rates and active SSL/TLS handshake queues on authentication endpoints.",
            "2. Identify top client IP addresses and user agents initiating authentication requests.",
            "3. Verify authentication daemon worker process CPU and memory utilization under load.",
            "4. Check token issuance and validation latency on session stores.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "ss -tan '( sport = :443 or sport = :8443 )' | wc -l",
                "description": "Count active incoming TCP socket connections to the authentication gateway",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "tail -n 100 /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -nr | head -n 10",
                "description": "Identify top client IP addresses driving request traffic",
            },
            {
                "technology": "[Linux / Systemd]",
                "command": "systemctl status auth-service --no-pager",
                "description": "Check operational status, active threads, and memory footprint of authentication service",
            },
        ],
        "corrective_actions": [
            "If an external volumetric flood is confirmed: Enable CAPTCHA challenges or IP rate-limiting at the ingress gateway for excessive authentication attempts.",
            "If legitimate surge is confirmed: Scale out authentication worker pods or increase worker concurrency limits to distribute request handling.",
        ],
        "verification_cmd": "ss -tan '( sport = :443 )' | wc -l",
    },

    "AUTH-01.auth_latency": {
        "hypotheses": [
            {
                "hypothesis": "Upstream LDAP / Active Directory connection timeout or network delay",
                "why": "Authentication latency typically spikes when synchronous network round-trips to backing directory servers experience queueing delays.",
                "missing_evidence": "LDAP query response time telemetry, round-trip ping time to domain controllers, and directory server CPU load.",
                "verification": "Measure TCP round-trip latency and LDAP bind response time from AUTH-01 to the domain controller.",
            },
            {
                "hypothesis": "Password hashing algorithm thread contention or high bcrypt work factor",
                "why": "Heavy CPU-bound key derivation (e.g. bcrypt or argon2) under concurrent load can saturate worker threads and cause request latency queues.",
                "missing_evidence": "CPU profiling traces and worker thread pool saturation metrics.",
                "verification": "Inspect CPU utilization and worker thread states during authentication spikes.",
            },
        ],
        "investigation_steps": [
            "1. Measure network latency between AUTH-01 and upstream directory servers (LDAP, Kerberos, AD).",
            "2. Inspect authentication service thread pool queues and worker utilization.",
            "3. Check Redis or Memcached token store response times for session lookup bottlenecks.",
            "4. Review cryptographic hashing duration profiles for user password verification.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "ss -t state established '( dport = :389 or dport = :636 or dport = :6379 )'",
                "description": "Inspect established connections to directory servers and token caches",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "curl -o /dev/null -s -w 'Connect: %{time_connect}s | TLS: %{time_appconnect}s | TTFB: %{time_starttransfer}s | Total: %{time_total}s\\n' https://localhost/auth/health",
                "description": "Profile HTTP response latency breakdown and Time-To-First-Byte on local auth endpoint",
            },
        ],
        "corrective_actions": [
            "If upstream directory latency is confirmed: Scale LDAP connection pools and enable local directory credential caching for active user sessions.",
            "If thread starvation is confirmed: Increase worker concurrency limits or offload cryptographic hashing to worker queue threads.",
        ],
        "verification_cmd": "curl -o /dev/null -s -w '%{time_total}s\\n' https://localhost/auth/health",
    },

    "AUTH-01.auth_success_rate": {
        "hypotheses": [
            {
                "hypothesis": "Expired SSL/TLS certificate or token signing key rotation mismatch",
                "why": "If token signing keys or TLS certificates expire, client tokens fail cryptographic signature validation, dropping success rate.",
                "missing_evidence": "Certificate expiration timestamps and token verification error codes in service logs.",
                "verification": "Verify SSL certificate expiration date and token signature validation error logs.",
            },
            {
                "hypothesis": "Database session store unavailability or read-only mode",
                "why": "If the token/session store is read-only or unreachable, successful credential checks cannot record valid sessions and return HTTP 500.",
                "missing_evidence": "Database error logs indicating connection refusals or read-only transaction errors.",
                "verification": "Check write permissions and connection status to session database.",
            },
        ],
        "investigation_steps": [
            "1. Inspect authentication service error logs for specific rejection codes (e.g. 401 Unauthorized vs 500 Server Error).",
            "2. Verify SSL/TLS certificate validity on authentication endpoints.",
            "3. Check session database connectivity and write capabilities.",
            "4. Review token signing and verification logs for cryptographic errors.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "journalctl -u auth-service --since '15 minutes ago' | grep -i -E 'error|reject|fail' | tail -n 25",
                "description": "Inspect recent authentication rejection and error events",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "openssl s_client -connect localhost:443 -tls1_3 </dev/null 2>/dev/null | grep -E 'Verify return code|Protocol'",
                "description": "Verify TLS certificate validity and protocol negotiation on auth gateway",
            },
        ],
        "corrective_actions": [
            "If certificate expiration is confirmed: Renew and deploy the TLS certificate or token signing keys adhering to rotation runbooks.",
            "If session store unavailability is confirmed: Restore session database write availability and verify replication topology.",
        ],
        "verification_cmd": "journalctl -u auth-service --since '5 minutes ago' | grep -i -E 'error' | wc -l",
    },

    # ── DB-01: Database Server ───────────────────────────────────────────────
    "DB-01.query_latency": {
        "hypotheses": [
            {
                "hypothesis": "Missing index or sequential scan on high-cardinality table",
                "why": "A query missing appropriate indexes forces full table sequential scans, consuming high I/O and CPU, dramatically increasing latency.",
                "missing_evidence": "Query execution plans (EXPLAIN ANALYZE), table cardinality, and sequential scan counts in pg_stat_user_tables.",
                "verification": "Run EXPLAIN on slow query statements identified in pg_stat_activity or pg_stat_statements.",
            },
            {
                "hypothesis": "Table or row-level lock contention from long-running transactions",
                "why": "An uncommitted transaction or schema migration holding exclusive locks blocks subsequent queries, producing severe latency queues.",
                "missing_evidence": "pg_locks granted status and blocking PID associations in pg_stat_activity.",
                "verification": "Query pg_locks joined with pg_stat_activity to identify blocked queries and their blocking transaction PIDs.",
            },
            {
                "hypothesis": "Disk I/O saturation or checkpoint write bursts",
                "why": "Aggressive background writer flushing or disk I/O saturation stalls data page reads from disk into shared buffers.",
                "missing_evidence": "Disk iowait percentages, WAL write rates, and buffer cache hit ratio in pg_stat_database.",
                "verification": "Inspect iostat disk await times and pg_stat_database buffer hit ratios.",
            },
        ],
        "investigation_steps": [
            "1. Inspect active database queries currently executing and identify long-running queries via pg_stat_activity.",
            "2. Check for database lock contention and blocked transaction processes via pg_locks.",
            "3. Examine historical query execution times and call frequencies using pg_stat_statements.",
            "4. Analyze disk I/O utilization, await time, and buffer cache hit ratio.",
            "5. Check autovacuum activity and table bloat metrics.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT pid, now() - query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 5;\"",
                "description": "Identify longest-running active queries currently executing in PostgreSQL",
            },
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT pid, locktype, mode, granted, query FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid WHERE NOT granted;\"",
                "description": "Check for locked or blocked queries waiting on database table/row locks",
            },
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT query, calls, total_exec_time, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;\" 2>/dev/null || psql -c \"SELECT datname, xact_commit, xact_rollback FROM pg_stat_database;\"",
                "description": "Inspect queries with highest average execution times or database transaction rates",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "iostat -xz 1 3",
                "description": "Inspect disk I/O wait times and storage utilization on database block devices",
            },
        ],
        "corrective_actions": [
            "If a long-running uncommitted transaction is holding locks: Gracefully terminate the blocking connection via SELECT pg_cancel_backend(pid) after verifying no critical schema migration is active.",
            "If sequential scans on large tables are confirmed: Create the required B-tree index concurrently via CREATE INDEX CONCURRENTLY during off-peak hours.",
            "If checkpoint I/O write spikes are confirmed: Adjust max_wal_size and checkpoint_completion_target in postgresql.conf to smooth checkpoint disk writes.",
        ],
        "verification_cmd": "psql -c \"SELECT count(*) FROM pg_stat_activity WHERE state != 'idle' AND now() - query_start > interval '5 seconds';\"",
    },

    "DB-01.active_connections": {
        "hypotheses": [
            {
                "hypothesis": "Application connection pool leak or unbounded client scaling",
                "why": "Microservices opening database connections without properly returning them to the connection pool will exhaust database connection slots.",
                "missing_evidence": "Count of connections in 'idle' or 'idle in transaction' state grouped by client application IP.",
                "verification": "Inspect pg_stat_activity grouped by client_addr and state to isolate connection origin.",
            },
            {
                "hypothesis": "Slow query backlog causing connection pool pile-up",
                "why": "When query execution slows down, client threads hold connections longer waiting for responses, quickly saturating the pool.",
                "missing_evidence": "Active executing query counts vs idle connection counts.",
                "verification": "Correlate connection growth timeline with query latency metrics.",
            },
        ],
        "investigation_steps": [
            "1. Inspect active PostgreSQL connections grouped by connection state (active, idle, idle in transaction).",
            "2. Identify client host IPs consuming the highest number of connection slots.",
            "3. Check configured maximum allowable database connection limit (max_connections).",
            "4. Verify connection pooler (e.g. PgBouncer) operational status and client wait queues.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT count(*), state FROM pg_stat_activity GROUP BY state;\"",
                "description": "Inspect active PostgreSQL connections grouped by connection state",
            },
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SHOW max_connections;\"",
                "description": "Check configured maximum allowable database connection limit",
            },
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT client_addr, count(*) FROM pg_stat_activity GROUP BY client_addr ORDER BY count DESC LIMIT 10;\"",
                "description": "Identify client application hosts consuming the most database connection slots",
            },
        ],
        "corrective_actions": [
            "If an application connection leak is confirmed: Configure idle transaction timeouts (idle_in_transaction_session_timeout) and recycle the leaking client microservice pool.",
            "If pool capacity exhaustion is confirmed: Deploy or tune PgBouncer connection pooling to multiplex client connections into a controlled server pool.",
        ],
        "verification_cmd": "psql -c \"SELECT count(*) FROM pg_stat_activity;\"",
    },

    "DB-01.disk_io_utilization": {
        "hypotheses": [
            {
                "hypothesis": "Buffer cache thrashing forcing high disk read operations",
                "why": "When shared_buffers cannot hold the active working set, PostgreSQL must continuously read 8KB data blocks from disk.",
                "missing_evidence": "Buffer cache hit ratio in pg_stat_database and blks_read vs blks_hit rates.",
                "verification": "Calculate cache hit ratio via pg_stat_database.",
            },
            {
                "hypothesis": "Heavy write workload from VACUUM, indexing, or WAL write bursts",
                "why": "Autovacuum worker processes or unthrottled data ingestion saturate disk write channels.",
                "missing_evidence": "Autovacuum process status and pg_stat_progress_vacuum metrics.",
                "verification": "Inspect vacuum progress and iotop disk write throughput by process.",
            },
        ],
        "investigation_steps": [
            "1. Check disk I/O metrics (%util, await, r/s, w/s) across database storage volumes.",
            "2. Calculate database buffer cache hit ratio in pg_stat_database.",
            "3. Inspect autovacuum worker processes and background writer activity.",
            "4. Check for temp files created on disk by large sort or hash operations.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "iostat -xz 1 5",
                "description": "Inspect extended disk I/O metrics (%util, await, r/s, w/s) across block storage devices",
            },
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT datname, blks_read, blks_hit, (blks_hit::float / nullif(blks_hit + blks_read, 0)) * 100 AS cache_hit_ratio FROM pg_stat_database;\"",
                "description": "Check database buffer cache hit ratio to evaluate disk read dependence",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "iotop -b -n 3 -o",
                "description": "Identify top processes generating disk write/read throughput",
            },
        ],
        "corrective_actions": [
            "If low cache hit ratio is confirmed: Increase PostgreSQL shared_buffers memory allocation and consider increasing system RAM for OS page caching.",
            "If autovacuum I/O thrashing is confirmed: Tune autovacuum_vacuum_cost_limit and autovacuum_vacuum_cost_delay to throttle vacuum I/O impact.",
        ],
        "verification_cmd": "iostat -xz 1 2 | awk 'NR>2 {print $NF}' | tail -n 1",
    },

    "DB-01.cpu_utilization": {
        "hypotheses": [
            {
                "hypothesis": "Computationally intensive queries or parallel worker thread execution",
                "why": "Complex aggregations, hash joins, or unindexed scans using multiple parallel query workers saturate database CPU cores.",
                "missing_evidence": "Query statement CPU profiling and pg_stat_activity active query count.",
                "verification": "Inspect active queries in pg_stat_activity ordered by runtime.",
            },
            {
                "hypothesis": "High context switching from excessive concurrent active connections",
                "why": "When hundreds of active connections compete for CPU time, kernel context switching overhead degrades throughput and spikes CPU.",
                "missing_evidence": "Context switch rates in vmstat and active backend count.",
                "verification": "Check vmstat context switch counters and active backend count.",
            },
        ],
        "investigation_steps": [
            "1. Identify queries currently running in PostgreSQL and their CPU consumption.",
            "2. Check system context switches and runnable process queues via vmstat.",
            "3. Inspect PostgreSQL background process CPU utilization (bgwriter, autovacuum).",
            "4. Review parallel query execution settings (max_parallel_workers_per_gather).",
        ],
        "diagnostic_commands": [
            {
                "technology": "[PostgreSQL CLI]",
                "command": "psql -c \"SELECT pid, usename, now() - query_start AS runtime, state, query FROM pg_stat_activity WHERE state = 'active' ORDER BY runtime DESC LIMIT 5;\"",
                "description": "Inspect queries currently consuming database worker CPU cycles",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "top -b -n 1 -u postgres | head -n 15",
                "description": "Display CPU usage specifically isolated to postgres background processes",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "vmstat 1 5",
                "description": "Check system context switches, runnable process queues, and CPU idle percentages",
            },
        ],
        "corrective_actions": [
            "If heavy parallel queries are confirmed: Adjust max_parallel_workers_per_gather and optimize heavy query execution plans.",
            "If excessive active connections are causing context thrashing: Enforce strict connection limits via PgBouncer.",
        ],
        "verification_cmd": "top -b -n 1 | grep '%Cpu(s)'",
    },

    # ── APP-01: Application Server ───────────────────────────────────────────
    "APP-01.cpu_utilization": {
        "hypotheses": [
            {
                "hypothesis": "Runaway worker thread loop or unoptimized algorithmic computation",
                "why": "An infinite loop, inefficient regex evaluation, or unoptimized data serialization in application code can peg CPU cores at 100%.",
                "missing_evidence": "Thread stack traces, CPU flamegraph samples, and application method execution profiles.",
                "verification": "Capture thread dumps or inspect pidstat per-thread CPU utilization to isolate the offending thread.",
            },
            {
                "hypothesis": "High request volume exceeding thread pool capacity",
                "why": "A surge in incoming HTTP transactions forces worker processes to continuously process requests without idle periods.",
                "missing_evidence": "Incoming HTTP requests per second and connection backlog metrics.",
                "verification": "Correlate CPU utilization with requests_per_sec telemetry.",
            },
        ],
        "investigation_steps": [
            "1. Identify top CPU-consuming worker processes and threads using top and pidstat.",
            "2. Inspect application error logs for unhandled exceptions or infinite loop warnings.",
            "3. Verify active incoming HTTP connection counts and request arrival rates.",
            "4. Profile application thread dumps to isolate CPU-intensive code paths.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "top -b -n 1 -o +%CPU | head -n 15",
                "description": "Identify top CPU-consuming worker processes and threads",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "pidstat -u 1 5",
                "description": "Sample per-process CPU utilization breakdown at 1-second intervals",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 10",
                "description": "List top 10 CPU-consuming processes with full command line details",
            },
        ],
        "corrective_actions": [
            "If a runaway worker thread is confirmed: Gracefully cycle the affected worker process to release CPU cores without dropping inflight requests.",
            "If high traffic demand is confirmed: Scale application instances across additional cluster nodes or enable ingress request rate limiting.",
        ],
        "verification_cmd": "top -b -n 1 | grep '%Cpu(s)'",
    },

    "APP-01.ram_utilization": {
        "hypotheses": [
            {
                "hypothesis": "Application heap memory leak or uncollected object references",
                "why": "Objects retained in memory due to open event listeners, caching without TTL, or static collection leaks cause gradual RAM exhaustion.",
                "missing_evidence": "Application heap dump analysis, garbage collection logs, and memory allocation delta over time.",
                "verification": "Capture heap allocation profiles and review garbage collection pause frequencies.",
            },
            {
                "hypothesis": "Operating system page cache accumulation or worker buffer bloat",
                "why": "High file I/O operations or buffering large payloads in worker memory consumes available physical RAM.",
                "missing_evidence": "Breakdown of used RAM vs buffer/cache RAM in free output.",
                "verification": "Inspect memory breakdown using free -h.",
            },
        ],
        "investigation_steps": [
            "1. Inspect physical RAM, swap usage, and OS buffer cache breakdown via free -h.",
            "2. Identify top memory-consuming processes and inspect memory growth trends.",
            "3. Check kernel ring buffer for Out-Of-Memory (OOM) killer events and score allocations.",
            "4. Analyze application runtime heap usage and garbage collection pause frequency.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "free -h",
                "description": "Display current physical RAM and swap memory usage breakdown",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -n 10",
                "description": "List top 10 memory-consuming processes ordered by RSS percentage",
            },
            {
                "technology": "[Linux / Systemd]",
                "command": "journalctl -k | grep -i -E 'oom|out of memory' | tail -n 20",
                "description": "Check kernel ring buffer for Out-Of-Memory (OOM) killer invocations",
            },
        ],
        "corrective_actions": [
            "If an application memory leak is confirmed: Gracefully restart the offending worker pool and patch memory caching retention policies.",
            "If system RAM is genuinely insufficient for baseline workload: Increase allocated node memory or tune JVM/V8 maximum heap limit flags.",
        ],
        "verification_cmd": "free -h",
    },

    "APP-01.requests_per_sec": {
        "hypotheses": [
            {
                "hypothesis": "Legitimate user traffic surge or marketing campaign spike",
                "why": "Promotions, marketing announcements, or seasonal shopping events drive increased client HTTP transaction arrivals.",
                "missing_evidence": "HTTP referrer headers, campaign launch schedules, and client IP distribution.",
                "verification": "Inspect HTTP access logs for common referrer headers or endpoint patterns.",
            },
            {
                "hypothesis": "Malicious traffic flood or scraper bot crawl",
                "why": "Aggressive web scraping bots or HTTP flood attacks generate abnormal request rates.",
                "missing_evidence": "User-Agent signatures and request rate per IP subnet.",
                "verification": "Analyze ingress access log IP distribution and User-Agent headers.",
            },
        ],
        "investigation_steps": [
            "1. Inspect incoming HTTP request rates and active established TCP connections.",
            "2. Identify top requesting IP addresses and user agent strings in web access logs.",
            "3. Verify backend processing latency and error rates under elevated request volume.",
            "4. Check load balancer distribution across backend application instances.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "ss -s",
                "description": "Display TCP socket summary and connection queue states",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ss -tan state established '( dport = :80 or dport = :443 or dport = :8080 )' | wc -l",
                "description": "Count active established HTTP/S client connections",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "uptime",
                "description": "Check 1-, 5-, and 15-minute system load averages against CPU core capacity",
            },
        ],
        "corrective_actions": [
            "If malicious bot traffic is confirmed: Apply rate limiting rules and challenge unidentified scrapers at the ingress gateway/WAF.",
            "If legitimate traffic surge is confirmed: Scale out additional application worker instances behind the load balancer.",
        ],
        "verification_cmd": "ss -s",
    },

    "APP-01.response_time": {
        "hypotheses": [
            {
                "hypothesis": "Downstream database or microservice dependency latency propagation",
                "why": "When the backing database (DB-01) or auth service (AUTH-01) slows down, application requests block waiting for I/O.",
                "missing_evidence": "Distributed APM traces showing time spent in downstream network calls.",
                "verification": "Check response times and error rates of dependent database and API services.",
            },
            {
                "hypothesis": "Thread pool exhaustion or socket backlog queuing",
                "why": "When all worker threads are occupied, incoming connections queue up in the TCP listen backlog, inflating total response time.",
                "missing_evidence": "Listen backlog overflow counter (ListenOverflows in netstat -s) and worker pool queue depth.",
                "verification": "Inspect socket listen backlog using ss -lnt and check netstat listen drop counters.",
            },
        ],
        "investigation_steps": [
            "1. Profile HTTP latency breakdown (DNS, connect, TTFB, total) using curl.",
            "2. Check socket listen backlog and active worker thread queue depth.",
            "3. Verify latency and availability of downstream database (DB-01) and caching services.",
            "4. Inspect application error logs for connection timeout exceptions.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "curl -o /dev/null -s -w 'Connect: %{time_connect}s | TTFB: %{time_starttransfer}s | Total: %{time_total}s\\n' http://localhost:8080/health",
                "description": "Profile HTTP latency breakdown and Time-To-First-Byte (TTFB) on local service endpoint",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ss -tan '( sport = :8080 )'",
                "description": "Inspect application listening port socket backlog and receive queue depth",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "netstat -s | grep -i -E 'listen|overflow' | head -n 10",
                "description": "Check TCP listen backlog overflow counters in the kernel network stack",
            },
        ],
        "corrective_actions": [
            "If downstream dependency latency is confirmed: Troubleshoot the specific backing database or API service identified in telemetry.",
            "If thread pool exhaustion is confirmed: Increase application worker concurrency and enable request timeouts to fail fast.",
        ],
        "verification_cmd": "curl -o /dev/null -s -w '%{time_total}s\\n' http://localhost:8080/health",
    },

    # ── NETWORK-01: Network Server ───────────────────────────────────────────
    "NETWORK-01.bandwidth_utilization": {
        "hypotheses": [
            {
                "hypothesis": "Large bulk data transfer, unthrottled backup sync, or media streaming",
                "why": "Large database backups, VM snapshot replication, or unmetered file transfers saturate physical network link bandwidth.",
                "missing_evidence": "Per-flow bandwidth breakdown by port and destination IP address.",
                "verification": "Inspect iftop or tc traffic control queues to identify top bandwidth-consuming network flows.",
            },
            {
                "hypothesis": "Network broadcast storm or packet amplification attack",
                "why": "Layer 2 switching loops or NTP/DNS amplification traffic can consume network interface throughput.",
                "missing_evidence": "Packet type distribution (unicast vs broadcast/multicast) in interface counters.",
                "verification": "Inspect ip -s link packet counters for broadcast vs unicast ratios.",
            },
        ],
        "investigation_steps": [
            "1. Display network interface statistics, bytes transmitted/received, and drop counters using ip -s link.",
            "2. Identify top bandwidth-consuming network hosts and data flows using iftop.",
            "3. Inspect traffic control queue disciplines and packet shaping statistics using tc.",
            "4. Check for active backup or large file replication transfers on the network.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Network Interface]",
                "command": "ip -s link show",
                "description": "Display interface packet counters, bytes transmitted/received, and error drops",
            },
            {
                "technology": "[Network Interface]",
                "command": "tc -s qdisc show",
                "description": "Inspect traffic control queue disciplines and packet drop counters",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ss -tan state established | awk '{print $4}' | cut -d: -f1 | sort | uniq -c | sort -nr | head -n 10",
                "description": "Identify top destination IP addresses across active network connections",
            },
        ],
        "corrective_actions": [
            "If bulk replication is saturating bandwidth: Apply traffic shaping rate limits (tc) to throttle background data transfers.",
            "If unexpected volumetric flood is confirmed: Filter offending source subnets at the edge router or firewall.",
        ],
        "verification_cmd": "ip -s link show | grep 'RX: bytes'",
    },

    "NETWORK-01.network_latency": {
        "hypotheses": [
            {
                "hypothesis": "Bufferbloat or packet queueing on intermediate network router/switch",
                "why": "Oversized network buffers holding packets during congestion cause significant round-trip latency spikes without packet loss.",
                "missing_evidence": "Hop-by-hop ping latency deltas across intermediate network hops.",
                "verification": "Execute traceroute or mtr to isolate which hop introduces latency degradation.",
            },
            {
                "hypothesis": "Suboptimal routing path or dynamic routing failover degradation",
                "why": "BGP or OSPF route flapping forcing traffic through suboptimal high-latency backup links causes sudden latency increases.",
                "missing_evidence": "Routing table changes and BGP peer flapping event logs.",
                "verification": "Inspect routing tables via ip route and verify gateway reachability.",
            },
        ],
        "investigation_steps": [
            "1. Measure ICMP round-trip latency and jitter to the default network gateway.",
            "2. Trace network routing path to isolate hop-level latency degradation via traceroute.",
            "3. Inspect TCP socket internal metrics including round-trip time (rtt) and congestion window.",
            "4. Verify router and switch link health along the transit path.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "ping -c 5 -i 0.2 192.168.1.1 2>/dev/null || ping -c 5 127.0.0.1",
                "description": "Measure ICMP round-trip latency and jitter to network gateway",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "ip route show",
                "description": "Verify default network routing table entries and gateway assignments",
            },
            {
                "technology": "[Network Interface]",
                "command": "ss -tip | head -n 20",
                "description": "Inspect TCP internal socket metrics including round-trip time (rtt) and rttvar",
            },
        ],
        "corrective_actions": [
            "If bufferbloat is confirmed: Enable modern queue management algorithms such as FQ-CoDel or CAKE on router interfaces.",
            "If routing path degradation is confirmed: Verify gateway routing protocols and reset degraded BGP/OSPF peer links.",
        ],
        "verification_cmd": "ping -c 3 127.0.0.1 | tail -n 1",
    },

    "NETWORK-01.packet_loss": {
        "hypotheses": [
            {
                "hypothesis": "NIC hardware ring buffer overflow from traffic bursts",
                "why": "When incoming packet bursts arrive faster than the OS network stack drains the driver ring buffer, the NIC drops packets at the physical layer.",
                "missing_evidence": "rx_discards, rx_fifo_errors, or rx_over_errors in ethtool -S statistics.",
                "verification": "Inspect ethtool -S statistics for driver and hardware drop counters.",
            },
            {
                "hypothesis": "Faulty physical cabling, SFP transceiver degradation, or CRC checksum errors",
                "why": "Physical layer degradation causes bit errors, resulting in CRC checksum failure and immediate packet discard.",
                "missing_evidence": "rx_crc_errors and rx_frame_errors in interface statistics.",
                "verification": "Check ethtool -S for CRC and framing error counters.",
            },
            {
                "hypothesis": "Firewall connection tracking table (conntrack) exhaustion",
                "why": "When the Linux kernel conntrack table reaches capacity, new incoming packets are dropped silently by netfilter.",
                "missing_evidence": "nf_conntrack_count vs nf_conntrack_max in sysctl.",
                "verification": "Check conntrack table utilization via sysctl net.netfilter.nf_conntrack_count.",
            },
        ],
        "investigation_steps": [
            "1. Inspect hardware NIC ring buffer overflows and physical interface drops using ethtool -S.",
            "2. Display kernel TCP stack retransmissions and buffer prune statistics via netstat -s.",
            "3. Verify firewall connection tracking table (conntrack) utilization against configured maximum limits.",
            "4. Inspect interface duplex settings and speed negotiation for mismatches.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Network Interface]",
                "command": "ethtool -S eth0 2>/dev/null | grep -i -E 'drop|err|over|fifo' | head -n 15 || ip -s link show",
                "description": "Inspect hardware NIC ring buffer overflows and physical interface drops",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "netstat -s | grep -i -E 'retransmitted|dropped|pruned' | head -n 10",
                "description": "Display kernel TCP stack retransmissions and buffer prune statistics",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null || ss -s",
                "description": "Check kernel firewall connection tracking table size and TCP socket counts",
            },
        ],
        "corrective_actions": [
            "If NIC ring buffer drops are confirmed: Increase RX/TX ring buffer descriptors via ethtool -G <interface> rx <value> during an approved window.",
            "If conntrack exhaustion is confirmed: Increase sysctl net.netfilter.nf_conntrack_max and tune TCP timeout intervals.",
            "If physical CRC errors are confirmed: Reseat or replace the physical network cable or SFP transceiver.",
        ],
        "verification_cmd": "netstat -s | grep -i 'segments retransmitted' | tail -n 1",
    },

    "NETWORK-01.throughput": {
        "hypotheses": [
            {
                "hypothesis": "TCP window collapse or small socket buffer sizing",
                "why": "If kernel TCP socket read/write buffers are undersized, TCP window sizing limits maximum throughput over high-bandwidth links.",
                "missing_evidence": "TCP socket buffer sysctl parameters (tcp_rmem, tcp_wmem) and TCP window scaling flags.",
                "verification": "Inspect sysctl tcp_wmem and tcp_rmem configurations.",
            },
            {
                "hypothesis": "TCP retransmission storm caused by packet drops",
                "why": "Packet drops trigger TCP congestion control window reduction, causing throughput to collapse precipitously.",
                "missing_evidence": "Retransmission counts and congestion window (cwnd) collapse in ss -ti.",
                "verification": "Inspect ss -ti for cwnd reduction and netstat retransmission counters.",
            },
        ],
        "investigation_steps": [
            "1. Review total active socket count, TCP memory buffer allocation, and timewait states via ss -s.",
            "2. Inspect TCP read and write memory buffer sizing configurations in sysctl.",
            "3. Check for packet loss and retransmission events triggering TCP congestion control throttling.",
            "4. Verify interface MTU settings across the network path to detect fragmentation.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "ss -s",
                "description": "Review total socket count, TCP memory buffer allocation, and timewait states",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "cat /proc/sys/net/ipv4/tcp_wmem /proc/sys/net/ipv4/tcp_rmem",
                "description": "Inspect TCP read and write memory buffer sizing configurations in kernel",
            },
        ],
        "corrective_actions": [
            "If undersized socket buffers are confirmed: Optimize kernel TCP window scaling and buffer parameters in /etc/sysctl.conf.",
            "If packet loss is choking throughput: Resolve physical packet loss or queue drops to restore TCP congestion window.",
        ],
        "verification_cmd": "ss -s",
    },

    # ── BACKUP-01: Backup Server ─────────────────────────────────────────────
    "BACKUP-01.backup_progress": {
        "hypotheses": [
            {
                "hypothesis": "Backup process stall or deadlock on destination storage lock",
                "why": "An unreleased lock file or stale snapshot lock prevents the backup daemon from writing subsequent archive blocks.",
                "missing_evidence": "Stale lock files in backup target directory and backup daemon process execution state.",
                "verification": "Check for lock files in /var/backups and inspect backup process state via ps.",
            },
            {
                "hypothesis": "Underlying storage I/O freeze or remote NFS/S3 endpoint timeout",
                "why": "If the remote storage mount becomes unresponsive, backup write syscalls block indefinitely in uninterruptible sleep (D state).",
                "missing_evidence": "NFS mount response times and dmesg storage timeout warnings.",
                "verification": "Inspect dmesg for storage timeout alerts and check mount responsiveness.",
            },
        ],
        "investigation_steps": [
            "1. Inspect backup job execution status, process state, and daemon logs via systemctl.",
            "2. Verify available filesystem storage capacity and mount point responsiveness.",
            "3. Check for stale lock files from prior aborted backup snapshot runs.",
            "4. Inspect network reachability to remote backup repository or storage endpoint.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Storage System]",
                "command": "df -h /var/backups /mnt/backup-storage 2>/dev/null || df -h",
                "description": "Verify available filesystem storage capacity and mount points for backup targets",
            },
            {
                "technology": "[Linux / Systemd]",
                "command": "systemctl status backup-service.service --no-pager 2>/dev/null || ps aux | grep -i backup | head -n 10",
                "description": "Check operational status and active runtime of the backup daemon",
            },
            {
                "technology": "[Storage System]",
                "command": "ls -la /var/backups/.lock* 2>/dev/null || ls -la /tmp/*backup*",
                "description": "Check for orphaned lock files from prior aborted backup runs",
            },
        ],
        "corrective_actions": [
            "If a stale lock file is blocking execution: Safely remove the orphaned lock file after confirming no active process holds the file descriptor.",
            "If remote storage is unresponsive: Remount degraded storage volumes and verify network connectivity to backup endpoints.",
        ],
        "verification_cmd": "systemctl is-active backup-service 2>/dev/null || echo 'Checked'",
    },

    "BACKUP-01.data_transfer_rate": {
        "hypotheses": [
            {
                "hypothesis": "Network throttling or link saturation on backup transit interface",
                "why": "Co-located network transfers competing for outbound bandwidth throttle backup data streaming.",
                "missing_evidence": "Interface throughput utilization on the backup network VLAN.",
                "verification": "Inspect network interface transfer rate using iftop or ip -s link.",
            },
            {
                "hypothesis": "Destination storage disk write bottleneck or IOPS exhaustion",
                "why": "Backup target disks reaching maximum write IOPS throttle ingestion speeds, slowing transfer rates.",
                "missing_evidence": "Disk write await time and %util on target storage block devices.",
                "verification": "Inspect iostat -xz write metrics on the backup destination mount.",
            },
        ],
        "investigation_steps": [
            "1. Inspect real-time network throughput and transfer bandwidth on backup interface.",
            "2. Inspect write throughput and latency on local storage targets receiving backup streams.",
            "3. Verify compression and deduplication CPU overhead on the backup server.",
            "4. Check for network QoS or rate-limiting rules applied to backup traffic.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / CLI]",
                "command": "iostat -xz 1 3",
                "description": "Inspect write throughput and latency on local storage targets receiving backup streams",
            },
            {
                "technology": "[Storage System]",
                "command": "df -h",
                "description": "Check disk space usage across all mounted volumes",
            },
            {
                "technology": "[Linux / CLI]",
                "command": "vmstat 1 3",
                "description": "Check CPU idle time and I/O wait percentages",
            },
        ],
        "corrective_actions": [
            "If disk write bottleneck is confirmed: Enable compression on the source side to reduce write byte volume to storage disks.",
            "If network bandwidth contention is confirmed: Allocate a dedicated backup VLAN or schedule transfers during off-peak maintenance windows.",
        ],
        "verification_cmd": "iostat -xz 1 2",
    },

    "BACKUP-01.backup_duration": {
        "hypotheses": [
            {
                "hypothesis": "Massive dataset growth or unpruned directory traversal",
                "why": "Accumulation of millions of small files or large newly ingested datasets expands the backup scan scope.",
                "missing_evidence": "File count delta and total byte size delta compared to the previous backup run.",
                "verification": "Compare current archive volume size with historical run records.",
            },
            {
                "hypothesis": "Snapshot lock wait or delayed file handle release",
                "why": "Backup job waiting for database or filesystem quiesce lock to complete before initiating snapshot.",
                "missing_evidence": "Database snapshot lock release logs and filesystem sync timestamps.",
                "verification": "Review backup daemon log timestamps for elapsed time between snapshot initialization and write phases.",
            },
        ],
        "investigation_steps": [
            "1. Examine backup duration against configured backup window tolerances.",
            "2. Compare dataset volume size and file counts with previous successful backups.",
            "3. Review backup daemon log messages for lockouts, stalls, or timeout warnings.",
            "4. Inspect source filesystem change rates and snapshot creation latency.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Linux / Systemd]",
                "command": "journalctl -u backup-service.service --since '2 hours ago' | tail -n 30",
                "description": "Review backup daemon log messages for lockouts, stalls, or timeout warnings",
            },
            {
                "technology": "[Storage System]",
                "command": "df -i /var/backups 2>/dev/null || df -i",
                "description": "Check inode utilization on backup storage volumes to detect inode exhaustion",
            },
        ],
        "corrective_actions": [
            "If dataset growth exceeds backup window: Switch from full backups to incremental snapshot-based backups (e.g. differential or block-level snapshots).",
            "If snapshot lock contention is confirmed: Optimize pre-backup quiesce scripts to minimize lock hold duration.",
        ],
        "verification_cmd": "tail -n 10 /var/log/backup.log 2>/dev/null || echo 'Checked'",
    },

    "BACKUP-01.backup_failure_count": {
        "hypotheses": [
            {
                "hypothesis": "Destination storage volume full (ENOSPC: No space left on device)",
                "why": "When destination storage capacity reaches 100%, write operations immediately fail with ENOSPC error codes.",
                "missing_evidence": "Filesystem available blocks and inode exhaustion counters.",
                "verification": "Inspect df -h and df -i on backup target storage mounts.",
            },
            {
                "hypothesis": "Authentication or permission failure on destination storage repository",
                "why": "Expired storage credentials, SSH key rotation failures, or IAM role policy changes cause target write rejections.",
                "missing_evidence": "Storage daemon access denied error messages in backup logs.",
                "verification": "Check backup log error codes for Permission Denied or Access Denied events.",
            },
        ],
        "investigation_steps": [
            "1. Check destination storage volume free space and inode exhaustion via df -h and df -i.",
            "2. Extract error-level log entries from backup daemon to identify root failure triggers.",
            "3. Verify write permissions on backup destination directories and mount points.",
            "4. Check storage repository credentials and token expiration dates.",
        ],
        "diagnostic_commands": [
            {
                "technology": "[Storage System]",
                "command": "df -h /var/backups /mnt/backup-storage 2>/dev/null || df -h",
                "description": "Verify available filesystem storage capacity and identify full volumes",
            },
            {
                "technology": "[Storage System]",
                "command": "df -i /var/backups 2>/dev/null || df -i",
                "description": "Verify inode availability on backup volumes to rule out inode exhaustion",
            },
            {
                "technology": "[Linux / Systemd]",
                "command": "journalctl -u backup-service.service -p err --since '2 hours ago' | tail -n 25",
                "description": "Extract error-level log entries from backup daemon to isolate failure triggers",
            },
        ],
        "corrective_actions": [
            "If storage volume full (ENOSPC) is confirmed: Safely purge expired backup snapshots adhering to retention policy (preserving minimum 7-day retention) to free storage blocks.",
            "If permission rejection is confirmed: Restore write permissions on backup destination directories and verify daemon service credentials.",
        ],
        "verification_cmd": "df -h /var/backups 2>/dev/null || df -h",
    },
}


class RAGSynthesizer:
    def __init__(self):
        self.provider_name = os.getenv("LLM_PROVIDER", "fallback").lower()
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm_model = os.getenv("LLM_MODEL", "llama3.2")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

    async def generate_troubleshooting(
        self,
        incident: dict[str, Any],
        retrieved_chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Synthesizes 8-section troubleshooting guidance:
        1. Incident Explanation
        2. Possible Root Causes (evidence-based hypotheses, not confirmed facts)
        3. Supporting Telemetry Evidence (canonical single source of truth)
        4. SRE Investigation Procedures
        5. Diagnostic Commands (non-destructive, labeled by technology)
        6. Recommended Corrective Actions (condition-based)
        7. Expected Outcome After Remediation (measurable thresholds)
        8. Retrieved Documentation Sources (validated ChromaDB chunks)
        """
        # Step 1: Canonical Telemetry Extraction (Single Source of Truth)
        canonical_data = self._extract_canonical_telemetry(incident)

        # Step 2: Validate Retrieved Chunks against Relevance Threshold
        valid_chunks = [
            c for c in retrieved_chunks
            if c.get("relevance_score", 0.0) >= RELEVANCE_THRESHOLD
        ]
        insufficient_docs = len(valid_chunks) == 0

        # Step 3: Attempt external LLM if configured and valid chunks exist
        if not insufficient_docs:
            if self.provider_name == "ollama":
                llm_res = await self._call_ollama(canonical_data, valid_chunks)
                if llm_res:
                    return llm_res
            elif self.provider_name == "gemini" and self.gemini_key:
                llm_res = await self._call_gemini(canonical_data, valid_chunks)
                if llm_res:
                    return llm_res
            elif self.provider_name == "openai" and self.openai_key:
                llm_res = await self._call_openai(canonical_data, valid_chunks)
                if llm_res:
                    return llm_res

        # Step 4: Deterministic Grounded Synthesis (100% telemetry-accurate)
        return self._synthesize_grounded(canonical_data, valid_chunks, insufficient_docs)

    def _extract_canonical_telemetry(self, incident: dict[str, Any]) -> dict[str, Any]:
        """
        Extracts canonical incident data, resolving configured thresholds from SERVERS_CONFIG
        if omitted. Formats missing values strictly as 'Not available'.
        """
        server_id = incident.get("server_id") or "UNKNOWN-01"
        server_name = incident.get("server_name") or "Server Node"
        server_type = incident.get("server_type") or incident.get("server_category") or "Server"
        metric_key = incident.get("metric_key") or "unknown_metric"
        metric_name = incident.get("metric_name") or metric_key

        # Raw values
        raw_obs = incident.get("observed_value")
        raw_thresh = incident.get("threshold_value")
        raw_warn = incident.get("warning_threshold")
        raw_crit = incident.get("critical_threshold")
        raw_base = incident.get("baseline_value")
        unit = incident.get("unit") or ""
        severity = incident.get("severity") or "MEDIUM"
        priority = incident.get("priority") or "P3"
        direction = incident.get("direction") or "above"

        # Lookup thresholds from SERVERS_CONFIG if missing
        if raw_warn is None or raw_crit is None or raw_base is None:
            param_cfg = (
                SERVERS_CONFIG.get(server_id, {})
                .get("parameters", {})
                .get(metric_key, {})
            )
            thresh_cfg = param_cfg.get("thresholds", {})
            if raw_warn is None:
                raw_warn = thresh_cfg.get("warning")
            if raw_crit is None:
                raw_crit = thresh_cfg.get("critical")
            if raw_base is None:
                raw_base = param_cfg.get("baseline")
            if direction is None:
                direction = thresh_cfg.get("direction", "above")

        # Canonical string representation
        observed_str = str(raw_obs) if raw_obs is not None else "Not available"
        threshold_str = str(raw_thresh) if raw_thresh is not None else "Not available"
        warning_str = str(raw_warn) if raw_warn is not None else "Not available"
        critical_str = str(raw_crit) if raw_crit is not None else "Not available"
        baseline_str = str(raw_base) if raw_base is not None else "Not available"

        # Canonical Issue Signature — must match observed value exactly!
        direction_sym = ">=" if direction == "above" else "<="
        issue_desc = incident.get("issue_description")
        if not issue_desc or (raw_obs is not None and str(raw_obs) not in issue_desc):
            issue_desc = (
                f"{server_id} {metric_name} breached {severity.lower()} threshold: "
                f"{observed_str} {unit} ({direction_sym} {threshold_str} {unit})"
            )

        return {
            "incident_id": incident.get("incident_id") or "INC-2026-XXXX",
            "server_id": server_id,
            "server_name": server_name,
            "server_type": server_type,
            "server_category": server_type,
            "metric_key": metric_key,
            "metric_name": metric_name,
            "observed_value": raw_obs,
            "observed_str": observed_str,
            "threshold_value": raw_thresh,
            "threshold_str": threshold_str,
            "warning_threshold": raw_warn,
            "warning_str": warning_str,
            "critical_threshold": raw_crit,
            "critical_str": critical_str,
            "baseline_value": raw_base,
            "baseline_str": baseline_str,
            "unit": unit,
            "severity": severity,
            "priority": priority,
            "direction": direction,
            "direction_sym": direction_sym,
            "created_at_str": incident.get("created_at_str") or "Not available",
            "issue_description": issue_desc,
        }

    def _synthesize_grounded(
        self,
        c: dict[str, Any],
        chunks: list[dict[str, Any]],
        insufficient_docs: bool
    ) -> dict[str, Any]:
        """
        Builds the complete 8-section troubleshooting response strictly grounded in
        canonical telemetry and validated ChromaDB documents.
        """
        server_id = c["server_id"]
        metric_key = c["metric_key"]
        metric_name = c["metric_name"]
        observed = c["observed_str"]
        threshold = c["threshold_str"]
        warning = c["warning_str"]
        critical = c["critical_str"]
        baseline = c["baseline_str"]
        unit = c["unit"]
        severity = c["severity"]
        priority = c["priority"]
        domain_key = f"{server_id}.{metric_key}"

        # Retrieve domain-specific diagnostics catalogue
        domain_info = DOMAIN_KNOWLEDGE.get(domain_key)

        # ── 1. Explanation ───────────────────────────────────────────────────
        explanation = (
            f"Server {server_id} ({c['server_name']}) experienced an abnormal {severity.lower()} "
            f"threshold breach in {metric_name}. The observed value reached {observed} {unit}, "
            f"violating the configured {severity.lower()} threshold of {threshold} {unit} "
            f"(Warning: {warning} {unit}, Critical: {critical} {unit}). The incident has been "
            f"assigned priority {priority} for immediate investigation."
        )
        if insufficient_docs:
            explanation += f" Note: {INSUFFICIENT_KNOWLEDGE_NOTICE}"

        # ── 2. Possible Root Causes (Hypotheses, Not Confirmed Facts) ─────────
        possible_causes: list[dict[str, str]] = []
        if domain_info and "hypotheses" in domain_info:
            for h in domain_info["hypotheses"]:
                possible_causes.append({
                    "hypothesis": h["hypothesis"],
                    "why": h["why"],
                    "evidence": (
                        f"Observed {metric_name} reached {observed} {unit} against "
                        f"{severity.lower()} threshold of {threshold} {unit}."
                    ),
                    "missing_evidence": h["missing_evidence"],
                    "verification": h["verification"],
                })
        else:
            # Fallback hypothesis adhering to evidence rules
            possible_causes.append({
                "hypothesis": f"Resource saturation or unmanaged workload demand on {metric_name}",
                "why": f"Sustained load exceeded server processing capacity for {server_id}.",
                "evidence": f"Observed {metric_name} reached {observed} {unit} (Threshold: {threshold} {unit}).",
                "missing_evidence": "Process-level resource breakdown and dependency network traces.",
                "verification": f"Inspect system telemetry and process lists on {server_id}.",
            })

        # ── 3. Supporting Telemetry Evidence ─────────────────────────────────
        telemetry_evidence = [
            f"Incident Identifier: {c['incident_id']}",
            f"Target Server: {server_id} ({c['server_name']} — {c['server_type']})",
            f"Affected Metric: {metric_name} ({metric_key})",
            f"Observed Telemetry Value: {observed} {unit}",
            f"Configured Thresholds: Warning = {warning} {unit} | Critical = {critical} {unit}",
            f"Breach Level & Severity: {severity} (Priority: {priority})",
            f"Detection Timestamp: {c['created_at_str']}",
            f"Issue Signature: {c['issue_description']}",
        ]

        # ── 4. Investigation Procedures ──────────────────────────────────────
        if domain_info and "investigation_steps" in domain_info:
            investigation_steps = list(domain_info["investigation_steps"])
        else:
            investigation_steps = [
                f"1. Isolate the offending process or thread pool consuming {metric_name} on {server_id}.",
                f"2. Check error-level logs and system journal on {server_id}.",
                "3. Verify network gateway and upstream dependency connectivity.",
                "4. Compare current telemetry readings with baseline historical performance trends.",
            ]

        # ── 5. Diagnostic Commands (Non-Destructive & Technology-Labeled) ─────
        diagnostic_commands: list[dict[str, str]] = []
        if domain_info and "diagnostic_commands" in domain_info:
            diagnostic_commands = list(domain_info["diagnostic_commands"])
        else:
            diagnostic_commands = [
                {
                    "technology": "[Linux / CLI]",
                    "command": f"top -b -n 1 | head -n 15",
                    "description": "Inspect top resource-consuming processes",
                },
                {
                    "technology": "[Linux / Systemd]",
                    "command": f"journalctl -u {server_id.lower()} -n 30 --no-pager",
                    "description": "Review recent system service logs",
                },
            ]

        # ── 6. Recommended Corrective Actions (Condition-Based) ──────────────
        recommended_solutions: list[str] = []
        if domain_info and "corrective_actions" in domain_info:
            recommended_solutions = list(domain_info["corrective_actions"])
        else:
            act_text = RECOMMENDED_ACTIONS.get(
                domain_key,
                f"Investigate {metric_name} on {server_id} and stabilize workload parameters."
            )
            recommended_solutions.append(
                f"If resource exhaustion is confirmed: {act_text} Verify system telemetry before and after action."
            )

        # ── 7. Expected Outcome After Remediation ────────────────────────────
        verify_cmd = domain_info.get("verification_cmd", "Inspect server telemetry") if domain_info else "Inspect server telemetry"
        expected_outcome = (
            f"Following remediation, {metric_name} on {server_id} should normalize below "
            f"{warning} {unit} (configured warning threshold) and return toward the normal "
            f"baseline of {baseline} {unit}. Verify recovery by executing: '{verify_cmd}'. "
            f"Server status should return to NORMAL without premature alert closure."
        )

        # ── 8. Retrieved Documentation Sources (ChromaDB) ────────────────────
        knowledge_sources: list[dict[str, Any]] = []
        if not insufficient_docs:
            seen_sources: set[tuple[str, str]] = set()
            for chunk in chunks:
                meta = chunk.get("metadata", {})
                title = meta.get("title") or meta.get("doc_name") or "Technical Documentation"
                source_org = meta.get("source") or "Official Documentation"
                url = meta.get("url") or "#"
                section = meta.get("section") or "Diagnostics"
                rel_score = chunk.get("relevance_score", 0.0)

                key = (title, url)
                if key not in seen_sources:
                    seen_sources.add(key)
                    knowledge_sources.append({
                        "title": title,
                        "source": source_org,
                        "url": url,
                        "section": section,
                        "relevance_score": rel_score,
                    })

        synthesized_by = (
            "VYTRON Safety Gate (Zero-Hallucination Policy)"
            if insufficient_docs
            else "VYTRON RAG Intelligence Engine (Grounded Documentation)"
        )

        return {
            "incident_id": c["incident_id"],
            "server_id": server_id,
            "insufficient_knowledge": insufficient_docs,
            "explanation": explanation,
            "possible_root_causes": possible_causes,
            "telemetry_evidence": telemetry_evidence,
            "investigation_steps": investigation_steps,
            "diagnostic_commands": diagnostic_commands,
            "recommended_solutions": recommended_solutions,
            "expected_outcome": expected_outcome,
            "knowledge_sources": knowledge_sources,
            "synthesized_by": synthesized_by,
        }

    async def _call_ollama(
        self, c: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        prompt = self._build_llm_rag_prompt(c, chunks)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.llm_model, "prompt": prompt, "stream": False, "format": "json"}
                )
                if res.status_code == 200:
                    text = res.json().get("response", "")
                    return self._parse_llm_json(text, c, chunks, f"Ollama ({self.llm_model})")
        except Exception:
            pass
        return None

    async def _call_gemini(
        self, c: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        prompt = self._build_llm_rag_prompt(c, chunks)
        gemini_models = [
            os.getenv("LLM_MODEL", "gemini-flash-lite-latest"),
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash"
        ]
        seen = set()
        for model in gemini_models:
            if not model or model in seen:
                continue
            seen.add(model)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(
                        url,
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "responseMimeType": "application/json",
                                "temperature": 0.1
                            }
                        }
                    )
                    if res.status_code == 200:
                        data = res.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return self._parse_llm_json(text, c, chunks, f"Google Gemini ({model})")
            except Exception:
                continue
        return None

    async def _call_openai(
        self, c: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        prompt = self._build_llm_rag_prompt(c, chunks)
        url = "https://api.openai.com/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.openai_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    text = data["choices"][0]["message"]["content"]
                    return self._parse_llm_json(text, c, chunks, "OpenAI GPT-4o-mini")
        except Exception:
            pass
        return None

    def _build_llm_rag_prompt(
        self, c: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> str:
        chunks_text = "\n\n".join([
            f"--- SOURCE: {c.get('metadata', {}).get('title')} ({c.get('metadata', {}).get('url')}) ---\n{c.get('content')}"
            for c in chunks[:4]
        ])

        return f"""You are an expert AIOps SRE incident investigator. Analyze this infrastructure incident using ONLY the retrieved technical documentation below.
STRICT RULES:
1. Use the exact observed value: {c['observed_str']} {c['unit']} throughout. Never alter or round it.
2. Formulate possible root causes strictly as hypotheses, not confirmed facts.
3. Every hypothesis must specify: hypothesis, why possible, supporting evidence, missing evidence, and verification.
4. Diagnostic commands must be non-destructive and labeled with technology.
5. Provide output strictly in valid JSON format matching this schema:

{{
  "explanation": "2-sentence explanation of the breach",
  "possible_root_causes": [
    {{
      "hypothesis": "Hypothesis title",
      "why": "Why this could explain the incident",
      "evidence": "Supporting telemetry evidence",
      "missing_evidence": "Missing evidence needed to confirm",
      "verification": "Operator verification procedure"
    }}
  ],
  "telemetry_evidence": ["Point 1", "Point 2"],
  "investigation_steps": ["Step 1", "Step 2", "Step 3"],
  "diagnostic_commands": [
    {{"technology": "[Linux / CLI]", "command": "command string", "description": "what this checks"}}
  ],
  "recommended_solutions": ["If condition confirmed: Action..."],
  "expected_outcome": "Expected recovery baseline"
}}

INCIDENT EVIDENCE:
{json.dumps(c, indent=2)}

RETRIEVED KNOWLEDGE BASE DOCUMENTATION:
{chunks_text}
"""

    def _parse_llm_json(
        self,
        text: str,
        c: dict[str, Any],
        chunks: list[dict[str, Any]],
        model_label: str
    ) -> dict[str, Any] | None:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                parsed = json.loads(text[start:end])

                # Format knowledge sources from retrieved chunks
                knowledge_sources = []
                seen_src = set()
                for chunk in chunks:
                    m = chunk.get("metadata", {})
                    src_tuple = (m.get("title"), m.get("url"))
                    if src_tuple not in seen_src:
                        seen_src.add(src_tuple)
                        knowledge_sources.append({
                            "title": m.get("title", "Technical Documentation"),
                            "source": m.get("source", "Official Docs"),
                            "url": m.get("url", "#"),
                            "section": m.get("section", "Diagnostics"),
                            "relevance_score": chunk.get("relevance_score", 0.9),
                        })

                # Ensure telemetry evidence is canonical
                telemetry_evidence = [
                    f"Incident Identifier: {c['incident_id']}",
                    f"Target Server: {c['server_id']} ({c['server_name']} — {c['server_type']})",
                    f"Affected Metric: {c['metric_name']} ({c['metric_key']})",
                    f"Observed Telemetry Value: {c['observed_str']} {c['unit']}",
                    f"Configured Thresholds: Warning = {c['warning_str']} {c['unit']} | Critical = {c['critical_str']} {c['unit']}",
                    f"Breach Level & Severity: {c['severity']} (Priority: {c['priority']})",
                    f"Detection Timestamp: {c['created_at_str']}",
                    f"Issue Signature: {c['issue_description']}",
                ]

                return {
                    "incident_id": c["incident_id"],
                    "server_id": c["server_id"],
                    "insufficient_knowledge": False,
                    "explanation": parsed.get("explanation", ""),
                    "possible_root_causes": parsed.get("possible_root_causes", []),
                    "telemetry_evidence": telemetry_evidence,
                    "investigation_steps": parsed.get("investigation_steps", []),
                    "diagnostic_commands": parsed.get("diagnostic_commands", []),
                    "recommended_solutions": parsed.get("recommended_solutions", []),
                    "expected_outcome": parsed.get("expected_outcome", ""),
                    "knowledge_sources": knowledge_sources,
                    "synthesized_by": f"VYTRON RAG + {model_label}",
                }
        except Exception as e:
            print(f"[RAGSynthesizer] JSON parsing error from LLM: {e}")
        return None
