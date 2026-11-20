---
title: "Troubleshooting Network Latency, Packet Drops, and Transit Congestion"
source: "Linux Foundation / Ubuntu Networking Guide & RFC 793 (TCP)"
url: "https://ubuntu.com/server/docs/network-troubleshooting"
category: "Networking"
server_relevance: ["NETWORK-01"]
---

# Troubleshooting Network Latency, Interface Packet Drops, and Link Congestion

## 1. Overview
Network subsystem degradation degrades inter-service RPC communication, API gateway throughput, and cluster synchronization. Elevated latency and packet loss typically stem from link bandwidth saturation, physical NIC ring buffer overflow, MTU fragmentation mismatches, or BGP routing convergence delays.

## 2. Potential Root Causes
- **Transit Link Bandwidth Saturation**: Egress/ingress traffic exceeding physical port capacity (e.g. 1Gbps / 10Gbps line rate).
- **NIC Ring Buffer Overflow**: Incoming frame rate exceeding the speed at which network driver DMA transfers packets to kernel memory.
- **Hardware Interface & Cable Degradation**: CRC checksum errors, faulty fiber transceivers, or half-duplex auto-negotiation mismatches.
- **TCP Window Sizing & Bufferbloat**: Unthrottled traffic overwhelming router buffer queues, resulting in high latency and packet tail drops.
- **Path MTU (Maximum Transmission Unit) Mismatch**: Packets exceeding interface MTU (e.g. 1500 vs 9000 jumbo frames) being fragmented or dropped by routers with ICMP disabled.

## 3. Telemetry Indicators & Metrics
- `packet_loss` > 3.0% (Warning) or > 5.0% (Critical).
- `network_latency` > 150ms (Warning) or > 300ms (Critical).
- `bandwidth_utilization` > 75% (Warning) or > 90% (Critical).
- `throughput` dropping significantly below expected baseline throughput.

## 4. Diagnostic Commands
Inspect network interface metrics, drop counters, and path routing:
```bash
# 1. Interface-level statistics and hardware packet drop counters
ip -s link show dev eth0

# 2. Detailed NIC ring buffer statistics and CRC error counts
ethtool -S eth0 | grep -E "drop|err|crc|fifo|overrun"

# 3. Path trace with real-time latency and packet loss per hop
mtr --report --report-cycles 10 1.1.1.1

# 4. TCP socket buffer statistics and retransmission counters
netstat -s | grep -i retrans
# Or using modern ss tool:
ss -tiepm
```

## 5. Investigation Procedures
1. Run `ethtool -S <interface>`: if `rx_dropped` or `rx_fifo_errors` are incrementing, the physical network adapter ring buffer is overflowing.
2. Run `mtr <destination_ip>`: check at which specific routing hop packet loss and latency begin. If loss occurs on the first hop (default gateway), the issue is local. If loss occurs at an intermediate transit provider, routing traffic around that transit AS is required.
3. Check `ip link`: verify MTU consistency across all interfaces on the communication path.
4. Inspect `netstat -s | grep retrans`: an accelerating retransmission count confirms TCP window degradation.

## 6. Recommended Corrective Actions
- **Immediate Workaround**: Enable QoS / traffic shaping (e.g., `tc` token bucket filter) to prioritize transactional API traffic over bulk file replication.
- **Increase Ring Buffer Size**: Double NIC RX/TX ring buffer descriptors:
  `ethtool -G eth0 rx 4096 tx 4096`
- **TCP Congestion Control Tuning**: Switch the Linux TCP congestion algorithm from cubic to BBR (`sysctl -w net.ipv4.tcp_congestion_control=bbr`).
- **Physical Remediation**: Replace damaged patch cables and verify switch port auto-negotiation is locked to Full Duplex.
