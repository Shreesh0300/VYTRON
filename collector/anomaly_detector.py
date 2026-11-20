"""
Collector Local Anomaly Detector
Performs immediate edge-level rule verification.
"""
from shared.constants import RULE_THRESHOLDS
from shared.schemas import Severity


def detect_local_anomalies(source_id: str, metric: str, value: float, category: str) -> tuple[bool, Severity, str | None, str | None]:
    """
    Evaluates telemetry against local static thresholds.
    Returns: (anomaly_detected, severity, detection_method, description)
    """
    thresholds = RULE_THRESHOLDS.get(metric)
    if not thresholds:
        return False, Severity.INFO, None, None

    # Handle service availability specifically
    if metric == "service_availability":
        if value <= 0:
            return True, Severity.CRITICAL, "rule", f"Service on {source_id} is unavailable (value: {value})"
        return False, Severity.INFO, None, None

    crit_thresh = thresholds.get("critical")
    warn_thresh = thresholds.get("warning")

    if crit_thresh is not None and value >= crit_thresh:
        return True, Severity.CRITICAL, "rule", f"{metric} breached critical threshold: {value} >= {crit_thresh}"

    if warn_thresh is not None and value >= warn_thresh:
        return True, Severity.WARNING, "rule", f"{metric} breached warning threshold: {value} >= {warn_thresh}"

    return False, Severity.INFO, None, None
