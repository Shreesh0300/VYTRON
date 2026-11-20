---
title: "Troubleshooting Backup Failures, Stalled Snapshots, and Disaster Recovery Delays"
source: "Ubuntu Server Documentation — Storage Backup and Disaster Recovery Procedures"
url: "https://ubuntu.com/server/docs/backup-and-disaster-recovery"
category: "Disaster Recovery"
server_relevance: ["BACKUP-01"]
---

# Troubleshooting Backup Failures, Storage Transfer Drops, and Snapshot Timeouts

## 1. Overview
Backup server abnormalities threaten disaster recovery (DR) preparedness and Point-In-Time Recovery (PITR) service level agreements (SLAs). Storage throughput collapse, stalled backup progress, and mounting backup failure counts typically indicate destination storage volume exhaustion (ENOSPC), NFS/iSCSI mount disconnection, volume snapshot lock timeouts, or network link saturation.

## 2. Potential Root Causes
- **Destination Storage Quota Exhaustion (ENOSPC)**: The backup repository volume running out of available disk space or filesystem inodes (`df -h`, `df -i`).
- **NFS / iSCSI Network Storage Mount Timeout**: Intermittent packet loss or network congestion causing remote SAN/NAS storage mount stalls.
- **Volume Shadow / Snapshot Lock Contention**: The target volume holding open read locks or failing to quiesce databases before snapshot creation.
- **Storage Bandwidth Throttling**: Cloud storage bucket egress limits or local backup agent bandwidth throttling misconfiguration.
- **File Integrity and CRC Checksum Failures**: Corrupted source blocks or hardware transfer bitflips causing archive validation rejection.

## 3. Telemetry Indicators & Metrics
- `backup_failure_count` >= 1 (Warning) or >= 2 (Critical).
- `data_transfer_rate` < 10.0 MB/s (Warning) or < 3.0 MB/s (Critical).
- `backup_duration` > 300s (Warning) or > 600s (Critical).
- `backup_progress` freezing at a specific percentage for extended intervals without advancing.

## 4. Diagnostic Commands
Inspect backup daemon status, disk space, and remote mount points:
```bash
# 1. Check storage volume free disk space and available inodes
df -h /var/backups; df -i /var/backups

# 2. Inspect backup daemon logs for error details
journalctl -u backup-worker -n 50 --no-pager | grep -i -E "error|fail|enospc|stalled|timeout"

# 3. Check NFS/iSCSI mount health and RPC ping latency
rpcinfo -p nfs-storage.internal; nfsstat -m

# 4. Measure disk write speed to backup storage destination
dd if=/dev/zero of=/var/backups/test.img bs=1M count=256 conv=fdatasync; rm -f /var/backups/test.img
```

## 5. Investigation Procedures
1. Run `df -h /var/backups`: if disk utilization is 100%, the backup agent fails immediately with `ENOSPC: No space left on device`.
2. Inspect `dmesg -T | grep -i nfs`: check for `nfs: server not responding, still trying` messages indicating network storage failure.
3. Test target storage write speed with `dd`: if write throughput is below 5 MB/s, investigate physical drive or SAN fabric degradation.
4. Check whether database freeze scripts (e.g. `pg_backup_start()`) held database locks without releasing them.

## 6. Recommended Corrective Actions
- **Immediate Workaround**: Abort stalled, frozen backup processes (`kill -15 <backup_pid>`) and clean up partial temporary snapshots.
- **Purge Obsolete Snapshots**: Apply the backup retention policy to delete expired historical archives and reclaim volume capacity:
  `find /var/backups -name "*.tar.gz" -mtime +30 -delete`
- **Remount Storage Volume**: Force unmount and remount unresponsive NFS destinations:
  `umount -f -l /var/backups && mount /var/backups`
- **Stagger Backup Schedules**: Reschedule resource-intensive archival tasks to run during off-peak traffic hours (e.g., 02:00 AM UTC).
