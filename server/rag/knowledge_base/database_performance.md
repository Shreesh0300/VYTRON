---
title: "Troubleshooting Database Performance, Connection Saturation, and Slow Queries"
source: "PostgreSQL Official Documentation (v16) — Routine Vacuuming & Performance Monitoring"
url: "https://www.postgresql.org/docs/current/monitoring-stats.html"
category: "Database Performance"
server_relevance: ["DB-01"]
---

# Troubleshooting Database Performance, Query Latency, and Lock Saturation

## 1. Overview
Database degradation directly degrades application tier performance. When database queries experience lock contention, missing indexes, connection pool exhaustion, or transaction bloat, downstream services experience exponential response time surges and connection timeouts.

## 2. Potential Root Causes
- **Unindexed Heavy Queries**: Relational queries scanning entire table heaps instead of utilizing B-tree or GiST indexes.
- **Connection Pool Exhaustion**: Applications opening non-pooled connections, exhausting `max_connections` and queuing incoming requests.
- **Exclusive Lock Contention**: DDL operations or uncommitted row-level locks (`SELECT FOR UPDATE`) blocking subsequent read and write transactions.
- **Dead Tuples and Table Bloat**: Autovacuum falling behind on high-update tables, requiring sequential reads of thousands of dead page blocks.
- **Work Memory Starvation**: Queries falling back to on-disk temporary merge sorts because query `work_mem` is insufficient.

## 3. Telemetry Indicators & Metrics
- `query_latency` > 500ms (Warning) or > 1000ms (Critical).
- `active_connections` > 80% (Warning) or > 90% (Critical) of `max_connections` (e.g. >160/180).
- Application `response_time` increasing proportionally with database latency.
- Connection timeout errors (`503 Service Unavailable`, `psycopg2.OperationalError: server closed the connection unexpectedly`).

## 4. Diagnostic Commands
Inspect active database queries, lock contention, and connection pool state:
```sql
-- 1. Check currently active long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND (now() - pg_stat_activity.query_start) > interval '5 seconds'
ORDER BY duration DESC;

-- 2. Detect queries waiting on exclusive locks
SELECT blocked_locks.pid AS blocked_pid, blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_statement, blocking_activity.query AS current_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- 3. Terminate runaway blocking query by PID
SELECT pg_cancel_backend(<blocking_pid>);
-- Or forcibly disconnect:
SELECT pg_terminate_backend(<blocking_pid>);
```

## 5. Investigation Procedures
1. Query `pg_stat_activity` to inspect state: if dozens of connections are in `idle in transaction`, the application client opened transactions without committing.
2. Check `pg_stat_statements` for top queries sorted by `total_exec_time` to identify the most resource-intensive queries.
3. Review `pg_locks` to determine if an uncommitted schema migration or batch update holds table-level exclusive locks.
4. Verify connection pooler health (e.g., PgBouncer status and queue depth).

## 6. Recommended Corrective Actions
- **Immediate Workaround**: Cancel long-running blocking queries using `SELECT pg_cancel_backend(pid)` and terminate idle client connections.
- **Connection Pooling**: Deploy and enforce connection pooling (PgBouncer or HikariCP) in `transaction` mode to cap connection churn.
- **Index Optimization**: Run `EXPLAIN (ANALYZE, BUFFERS) <query>` on slow statements and create missing compound B-tree indexes.
- **Vacuum Maintenance**: Trigger manual vacuum analyze on bloated tables (`VACUUM ANALYZE <table_name>;`).
