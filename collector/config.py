"""
Collector Configuration
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is on pythonpath
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.constants import (
    BACKEND_URL,
    COLLECTOR_PORT,
    DEFAULT_API_KEY,
    DEFAULT_TENANT_ID,
    DEFAULT_COLLECTOR_ID,
    HEARTBEAT_INTERVAL_SECONDS,
    QUEUE_RETRY_BASE_DELAY,
    QUEUE_RETRY_MAX_DELAY,
    QUEUE_RETRY_MAX_ATTEMPTS,
    QUEUE_BACKOFF_MULTIPLIER,
)

load_dotenv()

CONFIG = {
    "collector_id": os.getenv("COLLECTOR_ID", DEFAULT_COLLECTOR_ID),
    "tenant_id": os.getenv("TENANT_ID", DEFAULT_TENANT_ID),
    "backend_url": os.getenv("BACKEND_URL", BACKEND_URL),
    "api_key": os.getenv("COLLECTOR_API_KEY", DEFAULT_API_KEY),
    "port": int(os.getenv("COLLECTOR_PORT", str(COLLECTOR_PORT))),
    "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
    "queue_retry_base_delay": QUEUE_RETRY_BASE_DELAY,
    "queue_retry_max_delay": QUEUE_RETRY_MAX_DELAY,
    "queue_retry_max_attempts": QUEUE_RETRY_MAX_ATTEMPTS,
    "queue_backoff_multiplier": QUEUE_BACKOFF_MULTIPLIER,
    "db_path": os.getenv("COLLECTOR_DB_PATH", str(Path(__file__).resolve().parent / "collector.db")),
}
