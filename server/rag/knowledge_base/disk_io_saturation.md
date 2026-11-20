---
title: "Troubleshooting Disk I/O Saturation and Storage Subsystem Bottlenecks"
source: "Microsoft Learn & Red Hat Enterprise Linux Storage Administration Guide"
url: "https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/performance-storage-troubleshoot"
category: "Storage & I/O"
server_relevance: ["DB-01", "BACKUP-01"]
---

# Troubleshooting Disk I/O Saturation and Storage Latency

## 1. Overview
Disk I/O saturation occurs when read and write request queues to block storage devices exceed physical throughput or Input/Output Operations Per Second (IOPS) limits. On storage volumes hosting relational databases or backup repositories, high I/O wait (`%iowait`) stalls synchronous worker threads, causing dramatic response time spikes and request queue buildup.

## 2. Potential Root Causes
- **Excessive Sequential Disk Scans**: Relational database queries executing full table scans on multi-gigabyte tables without index coverage.
- **Heavy Checkpoint Flushing**: Database buffer engines writing thousands of dirty pages simultaneously to write-ahead logs (WAL).
- **Concurrent Backup and Production Workloads**: Backup snapshots streaming volume blocks concurrently during peak application hours.
- **Disk Queue Depth Saturation**: Cloud virtual disk or physical SAN IOPS bursting limits exhausted, triggering kernel disk request throttling.
- **Filesystem Journaling Locks**: Ext4/XFS filesystem metadata flush delays due to high inode creation rates.

## 3. Telemetry Indicators & Metrics
- `disk_io_utilization` > 75% (Warning) or > 85% (Critical).
- High `%iowait` in CPU summary (>15%).
- Disk request queue depth (`aqu-sz`) significantly greater than 1.0.
- Average read/write service time (`await`) spiking above 15–20 milliseconds.

## 4. Diagnostic Commands
Analyze storage device utilization, queue depth, and process-level I/O consumption:
```bash
# 1. Device-level utilization, await latency, and queue depth
iostat -xz 1 5

# 2. Identify top processes generating disk write and read traffic
iotop -b -n 3 -o

# 3. Inspect block device queue limits and scheduler type
cat /sys/block/sd*/queue/scheduler

# 4. Check disk free space and inode exhaustion
df -h; df -i
```

## 5. Investigation Procedures
1. Run `iostat -xz 1 5` and examine `%util` and `await`. If `%util` is near 100% and `await` is high (>20ms), the storage subsystem is hardware-bound.
2. Run `iotop -o` to determine whether application workers, background database cleaners, or backup snapshot processes are driving the I/O.
3. Check `dmesg -T` for SCSI timeout errors, kernel reset commands, or disk buffer allocation failures.
4. Verify if database write-ahead logging (WAL) resides on the same physical volume as table data partitions.

## 6. Recommended Corrective Actions
- **Isolate Workloads**: Separate database write-ahead logs (WAL) and backup destinations onto dedicated high-IOPS NVMe storage pools.
- **Query Optimization**: Create covering indexes to convert heavy disk-bound sequential scans into fast in-memory index scans.
- **I/O Throttling**: Configure cgroups blkio limits on backup daemons (`systemd-run --property=IOReadBandwidthMax=/dev/sda 20M`) to prevent backup processes from starving production traffic.
- **I/O Scheduler**: Switch virtual disk scheduler to `none` or `mq-deadline` for modern low-latency SSD/NVMe drives.
