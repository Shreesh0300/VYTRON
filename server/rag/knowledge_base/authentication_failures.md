---
title: "Troubleshooting Authentication Failures, SSO Latency, and Identity Provider Degradation"
source: "Microsoft Learn & Red Hat Directory Services Administration Guide"
url: "https://learn.microsoft.com/en-us/entra/identity/monitoring-health/concept-sign-ins"
category: "Security & Identity"
server_relevance: ["AUTH-01"]
---

# Troubleshooting Authentication Failures, Rate Limits, and Token Issuance Delays

## 1. Overview
Authentication server degradation directly disrupts user access and inter-service token validation. Spikes in failed login attempts, authentication latency, and dropped success rates typically stem from credential stuffing attacks, identity directory connection exhaustion (LDAP/Active Directory), Redis token cache cold starts, or token signing key rotation delays.

## 2. Potential Root Causes
- **Credential Stuffing / Brute-Force Attacks**: Automated botnets attempting thousands of stolen username/password combinations against login endpoints.
- **Upstream Identity Provider (IdP) Latency**: Delays in SAML/OIDC round-trips to external identity directories (Entra ID, Okta, Active Directory).
- **Session / Token Cache Eviction**: Redis or Memcached session stores dropping tokens under memory pressure, forcing expensive disk or directory re-authentications.
- **Expired Signing Certificates**: JWT or SAML token signing X.509 certificates expired or failing validation checks.
- **Database Thread Starvation**: Local authentication database connection pool exhausted by concurrent session lookup requests.

## 3. Telemetry Indicators & Metrics
- `failed_login_attempts` > 10 fails/min (Warning) or > 25 fails/min (Critical).
- `auth_latency` > 500ms (Warning) or > 1000ms (Critical).
- `auth_success_rate` < 90% (Warning) or < 75% (Critical).
- HTTP status codes `401 Unauthorized`, `403 Forbidden`, and `429 Too Many Requests` escalating at the API gateway.

## 4. Diagnostic Commands
Inspect authentication service logs, failed attempts, and directory connectivity:
```bash
# 1. Inspect recent authentication failures in Linux PAM / journalctl
journalctl -u auth-service -n 50 --no-pager | grep -i -E "fail|reject|invalid|timeout"

# 2. Count failed login attempts grouped by source IP
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -nr | head -n 15

# 3. Check connectivity and latency to upstream LDAP/Active Directory
nc -zv -w 3 ldap.internal.corp 636

# 4. Inspect Redis session token cache latency and memory
redis-cli --latency-history -h redis-auth.internal -p 6379
```

## 5. Investigation Procedures
1. Group failed login attempts by source IP address and target username to determine if an attack is targeting a single user (brute-force) or thousands of accounts (credential stuffing).
2. Measure round-trip latency to the upstream directory service (`nc -zv` or `ldapsearch`). If latency is >200ms, investigate LDAP domain controller load.
3. Check Redis cache hit ratio: `redis-cli info stats | grep keyspace_hits`. If the hit ratio drops below 95%, investigate token TTL expiry settings.
4. Verify token signing certificate validity: `openssl x509 -in /etc/ssl/auth_cert.pem -noout -dates`.

## 6. Recommended Corrective Actions
- **Immediate Workaround**: Enforce temporary IP-based rate limiting or block attacker IP CIDR subnets at the Cloudflare / WAF edge:
  `iptables -I INPUT -s <malicious_ip> -j DROP`
- **Enable Adaptive Multi-Factor Authentication (MFA)**: Require CAPTCHA or step-up MFA for login attempts originating from untrusted autonomous systems.
- **Scale Redis Cache**: Add replica read nodes to the Redis token validation cluster to offload directory traffic.
- **Certificate Renewal**: Rotate expired JWT signing keys and reload the authentication daemon configuration.
