"""
CICADA AIOps — Shared Constants
Central reference for all configurable values, thresholds, and field lists.
"""

# ── Service Ports ────────────────────────────────────────────────────────

BACKEND_PORT = 8000
SIMULATOR_PORT = 8001
COLLECTOR_PORT = 8002
FRONTEND_PORT = 5500

BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
SIMULATOR_URL = f"http://localhost:{SIMULATOR_PORT}"
COLLECTOR_URL = f"http://localhost:{COLLECTOR_PORT}"

# ── Authentication ───────────────────────────────────────────────────────

DEFAULT_API_KEY = "cicada-collector-key-2026"
DEFAULT_TENANT_ID = "TENANT-01"
DEFAULT_COLLECTOR_ID = "COLLECTOR-01"

# ── Privacy: Allowed Fields (Allow-List) ─────────────────────────────────
# Only these fields may leave Tier 1.  Everything else is blocked/redacted.

ALLOWED_EGRESS_FIELDS = [
    "payload_id",
    "tenant_id",
    "collector_id",
    "source_id",
    "timestamp",
    "metric",
    "value",
    "severity",
    "category",
    "anomaly_detected",
    "detection_method",
    "metadata",
]

# ── Privacy: Sensitive Patterns (Regex) ──────────────────────────────────

SENSITIVE_PATTERNS = [
    r"(?i)password\s*[:=]\s*\S+",
    r"(?i)passwd\s*[:=]\s*\S+",
    r"(?i)secret\s*[:=]\s*\S+",
    r"(?i)api[_-]?key\s*[:=]\s*\S+",
    r"(?i)token\s*[:=]\s*\S+",
    r"(?i)authorization\s*[:=]\s*\S+",
    r"(?i)bearer\s+\S+",
    r"(?i)aws[_-]?access[_-]?key\s*[:=]\s*\S+",
    r"(?i)private[_-]?key\s*[:=]\s*\S+",
    r"(?i)ssh-rsa\s+\S+",
    r"(?i)-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
]

# Fields in raw metadata that must never be transmitted
BLOCKED_METADATA_KEYS = [
    "password", "passwd", "secret", "api_key", "apikey",
    "token", "access_token", "refresh_token", "private_key",
    "authorization", "credential", "credentials", "ssh_key",
    "raw_log", "raw_payload", "raw_body",
]

# ── Rule-Based Detection Thresholds ──────────────────────────────────────

RULE_THRESHOLDS = {
    "cpu_usage": {"warning": 80.0, "critical": 90.0},
    "memory_usage": {"warning": 85.0, "critical": 95.0},
    "disk_usage": {"warning": 80.0, "critical": 90.0},
    "network_latency": {"warning": 150.0, "critical": 300.0},  # ms
    "packet_loss": {"warning": 3.0, "critical": 5.0},          # %
    "failed_logins": {"warning": 5, "critical": 10},            # per minute
    "service_availability": {"warning": 0, "critical": 0},      # 0 = unavailable
}

# ── Statistical Detection Config ─────────────────────────────────────────

STAT_MIN_SAMPLES = 30          # minimum observations before alerting
STAT_Z_SCORE_WARNING = 2.0     # z-score threshold for warning
STAT_Z_SCORE_CRITICAL = 3.0    # z-score threshold for critical
STAT_ROLLING_WINDOW = 60       # number of recent data points for baseline

# ── Correlation Config ───────────────────────────────────────────────────

CORRELATION_TIME_WINDOW_SECONDS = 120   # group alerts within this window
CORRELATION_MIN_ALERTS = 2              # minimum alerts to form an incident

# Service dependency map for correlation
SERVICE_DEPENDENCIES = {
    "APP-01": ["DB-01", "AUTH-01", "STORAGE-01"],
    "APP-02": ["DB-02", "AUTH-01", "STORAGE-01"],
    "WEB-01": ["APP-01", "APP-02"],
    "DB-01": ["STORAGE-01"],
    "DB-02": ["STORAGE-01"],
    "AUTH-01": ["DB-01"],
    "BACKUP-01": ["STORAGE-01", "DB-01", "DB-02"],
    "NETWORK-01": [],
    "STORAGE-01": [],
    "INTERNAL-01": ["APP-01", "DB-01"],
}

# ── Queue / Reliability Config ───────────────────────────────────────────

QUEUE_RETRY_BASE_DELAY = 2.0        # seconds
QUEUE_RETRY_MAX_DELAY = 60.0        # seconds
QUEUE_RETRY_MAX_ATTEMPTS = 10
QUEUE_BACKOFF_MULTIPLIER = 2.0

# ── Heartbeat Config ─────────────────────────────────────────────────────

HEARTBEAT_INTERVAL_SECONDS = 15
COLLECTOR_OFFLINE_TIMEOUT_SECONDS = 60

# ── Simulator Config ─────────────────────────────────────────────────────

TELEMETRY_INTERVAL_SECONDS = 3     # how often the simulator pushes data
SCENARIO_INJECTION_INTERVAL = 30   # seconds between scenario injections

# ── Server Profiles ──────────────────────────────────────────────────────

SERVER_PROFILES = {
    "APP-01":      {"name": "Application Server",           "type": "application"},
    "DB-01":       {"name": "Database Server",              "type": "database"},
    "AUTH-01":     {"name": "Authentication Server",        "type": "authentication"},
    "WEB-01":      {"name": "Web Server",                   "type": "web"},
    "STORAGE-01":  {"name": "Storage Server",               "type": "storage"},
    "APP-02":      {"name": "Secondary Application Server", "type": "application"},
    "DB-02":       {"name": "Secondary Database Server",    "type": "database"},
    "NETWORK-01":  {"name": "Network Service",              "type": "network"},
    "BACKUP-01":   {"name": "Backup Server",                "type": "backup"},
    "INTERNAL-01": {"name": "Internal Service Server",      "type": "internal"},
}

# ── Health State Thresholds ──────────────────────────────────────────────

HEALTH_STATE_THRESHOLDS = {
    "excellent": {"max_active_critical": 0, "max_active_warning": 1},
    "good":      {"max_active_critical": 0, "max_active_warning": 5},
    "fair":      {"max_active_critical": 2, "max_active_warning": 10},
    # anything beyond "fair" thresholds → "poor"
}

# ── LLM Config ───────────────────────────────────────────────────────────

LLM_PROVIDER_DEFAULT = "ollama"     # "ollama" | "gemini" | "openai"
LLM_MODEL_DEFAULT = "llama3.2"
LLM_TIMEOUT_SECONDS = 30
LLM_MAX_EVIDENCE_ITEMS = 20        # limit evidence sent to LLM
