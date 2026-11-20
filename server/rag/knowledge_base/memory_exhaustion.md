---
title: "Troubleshooting Linux Memory Exhaustion and Out-Of-Memory (OOM) Conditions"
source: "Red Hat Enterprise Linux Kernel Memory Management Guide & Linux Kernel Docs"
url: "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/assembly_monitoring-memory-usage"
category: "Memory Management"
server_relevance: ["APP-01", "DB-01", "AUTH-01"]
---

# Troubleshooting Memory Exhaustion and Resident Memory Pressure

## 1. Overview
Memory exhaustion occurs when operating system resident memory (RSS), slab cache, or swap space becomes depleted. When available physical memory drops below the kernel watermark (`min_free_kbytes`), the Linux Out-Of-Memory (OOM) killer activates and forcefully terminates processes with the highest `oom_score`, leading to unexpected service termination and service unavailability.

## 2. Potential Root Causes
- **Application Heap Memory Leaks**: Objects retained in persistent references preventing garbage collector reclamation.
- **Unbounded In-Memory Buffers**: Caches lacking eviction policies (LRU/TTL) growing indefinitely under high request loads.
- **Database Buffer Cache Bloat**: Relational database shared buffers or query work memory (`work_mem`) configured higher than physical RAM.
- **Kernel Slab Allocation Leakage**: Dentry and inode caches not reclaiming space under high filesystem inode turnover.
- **Zombie Process Leakage**: Abandoned child processes holding allocated virtual memory pages.

## 3. Telemetry Indicators & Metrics
- `ram_utilization` exceeding 80% (Warning) or 90% (Critical).
- Swap utilization increasing above 20% accompanied by elevated page-in/page-out rates (`si`/`so` in `vmstat`).
- Kernel dmesg logs reporting `Out of Memory: Kill process <pid> (<process_name>) score <score>`.
- Latency spikes caused by major page faults reading memory segments from secondary disk storage.

## 4. Diagnostic Commands
Inspect physical memory, slab allocations, and OOM killer scores:
```bash
# 1. Summary of physical memory, swap, and buffer cache
free -h

# 2. Detailed memory consumption breakdown
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|Slab"

# 3. Top 15 memory-consuming processes by RSS
ps aux --sort=-%mem | awk 'NR<=15 {print $1, $2, $3, $4, $6/1024 "MB", $11}'

# 4. Check system ring buffer for OOM killer events
dmesg -T | grep -i -E "oom-killer|out of memory"
```

## 5. Investigation Procedures
1. Run `free -m` and inspect the `available` column (not just `free`, as buffers/cache are reclaimable).
2. If `SwapFree` is rapidly depleting and `vmstat 1` shows non-zero `so` (swap-out), the system is actively swapping memory to disk.
3. Check `dmesg -T | grep -i oom` to identify if any background service has already been terminated by the kernel.
4. For Java or Python applications, capture a heap profile snapshot (`jcmd <pid> GC.heap_dump` or `tracemalloc`).

## 6. Recommended Corrective Actions
- **Immediate Workaround**: Trigger an emergency page cache and slab cache flush:
  `sync; echo 3 > /proc/sys/vm/drop_caches`
- **Application Memory Sizing**: Constrain container heap memory limits (`-Xmx` / `--memory`) to ensure headroom for operating system buffers.
- **Restart Starved Service**: Restart leaking application worker containers to reclaim locked RSS memory.
- **Swap Tuning**: Configure `vm.swappiness=10` on production servers to prevent premature memory paging to disk.
