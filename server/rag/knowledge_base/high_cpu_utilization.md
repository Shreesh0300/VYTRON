---
title: "Troubleshooting High CPU Utilization and Thread Starvation in Linux Systems"
source: "Ubuntu Server Documentation & Red Hat Enterprise Linux 9 Performance Tuning Guide"
url: "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/"
category: "CPU Performance"
server_relevance: ["APP-01", "DB-01"]
---

# Troubleshooting High CPU Utilization and Processor Starvation

## 1. Overview
High CPU utilization occurs when compute demand exceeds available core processing capacity, leading to execution run-queue saturation, elevated scheduler latency, thread starvation, and response time degradation. On production application and database servers, CPU saturation is frequently caused by runaway application loops, thread pool exhaustion, unindexed database queries, or inefficient garbage collection sweeps.

## 2. Potential Root Causes
- **Thread Contention & Concurrency Starvation**: Excess worker threads competing for CPU cores or lock synchronization barriers (futex locks).
- **Application Runaway Computation**: Infinite loops, unthrottled cryptographic hashing, or unoptimized recursive functions.
- **Garbage Collection (GC) Pressure**: High allocation rate triggering frequent stop-the-world JVM or V8 heap sweeps.
- **Unindexed Database Scans**: Relational database queries executing full sequential scans across millions of disk blocks.
- **Interrupt Overload (SoftIRQs)**: High network packet volume causing excessive software interrupt handling on core 0.

## 3. Telemetry Indicators & Metrics
- `cpu_utilization` > 80% (Warning) or > 90% (Critical).
- System load averages (1m, 5m, 15m) exceeding the total number of physical CPU cores.
- Application `response_time` increasing proportionally with CPU usage.
- High system-time `%sys` vs user-time `%us` indicating excessive context switching.

## 4. Diagnostic Commands
Inspect running processes and per-thread CPU consumption:
```bash
# 1. Real-time process breakdown sorted by CPU
top -b -n 1 -o %CPU | head -n 25

# 2. Detailed thread-level CPU utilization for application processes
pidstat -u -p ALL 1 3

# 3. Check scheduler context switching and CPU run queue length
vmstat 1 5

# 4. Identify kernel stack traces of heavy threads
perf top --sort comm,dso
```

## 5. Investigation Procedures
1. Run `pidstat -u 1 5` to isolate whether CPU time is consumed by user space (`%usr`) or kernel space (`%system`).
2. If `%system` is elevated (>30%), investigate hardware interrupt handling using `cat /proc/interrupts` and check lock contention with `perf record -g`.
3. If `%usr` is dominant, inspect application thread dumps (e.g. `jstack <pid>` for Java, or `py-spy` for Python).
4. Verify if database query threads (`postgres`, `mysqld`) correlate with the CPU spike.

## 6. Recommended Corrective Actions
- **Immediate Workaround**: Scale out horizontal application replicas (HPA) or temporarily rate-limit ingress HTTP request concurrency.
- **Thread Management**: Adjust application thread pool size to match available core count ($N_{\text{threads}} = N_{\text{cores}} \times 2$).
- **Process Restart**: Gracefully restart worker nodes exhibiting runaway memory allocation or stuck threads.
- **CPU Affinity**: Pin critical processing daemons to dedicated CPU cores using `taskset -c 2,3 <pid>`.
