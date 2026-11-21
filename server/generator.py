"""
VYTRON — Dynamic Randomized Incident Generation Engine
Responsible for selecting affected servers, metrics, issue types, durations,
and calculating correlated target values without directly emitting incidents.
"""

import time
import random
from typing import Any
from server.config import SERVERS_CONFIG, ISSUE_CATALOGUE, METRIC_RELATIONSHIPS

class RandomIncidentEngine:
    def __init__(self):
        self.last_selected_servers: set[str] = set()

    def reset(self):
        """Resets incident generator history and state."""
        self.last_selected_servers.clear()

    def generate_plan(self, server_count: int | None = None) -> dict[str, Any]:
        """
        Generates a new randomized simulation plan:
        1. Selects between 1 and 5 unique servers (avoiding exact repeat of previous combo).
        2. Selects 1 or 2 valid metrics per server.
        3. Selects valid issue types from ISSUE_CATALOGUE.
        4. Calculates target values for gradual degradation (targeting WARNING or CRITICAL).
        5. Computes rule-based secondary metric relationships.
        6. Configures realistic durations and auto-recovery behavior.
        """
        all_servers = list(SERVERS_CONFIG.keys())
        
        # 1. Determine number of affected servers (1 to 5)
        if server_count is not None and 1 <= server_count <= len(all_servers):
            count = server_count
        else:
            # Weighted distribution: 1 server (20%), 2 servers (35%), 3 servers (25%), 4 servers (10%), 5 servers (10%)
            count = random.choices([1, 2, 3, 4, 5], weights=[20, 35, 25, 10, 10])[0]

        # 2. Select unique servers using random.sample, avoiding immediate repeat of exact combination
        selected_servers = random.sample(all_servers, count)
        if set(selected_servers) == self.last_selected_servers and len(all_servers) > count:
            # Try once more to get a different set
            for _ in range(5):
                candidate = random.sample(all_servers, count)
                if set(candidate) != self.last_selected_servers:
                    selected_servers = candidate
                    break

        self.last_selected_servers = set(selected_servers)

        issues: list[dict[str, Any]] = []
        targets: dict[str, float] = {}
        target_severities: dict[str, str] = {}
        durations: dict[str, dict[str, Any]] = {}

        now = time.time()
        plan_id = f"SIM-{int(now) % 100000:05d}"

        # 3. For each selected server, choose 1 or 2 unique metrics
        for server_id in selected_servers:
            server_conf = SERVERS_CONFIG[server_id]
            valid_metrics = list(server_conf["parameters"].keys())
            
            # Select 1 to 2 metrics per server (never more than total available metrics)
            max_metrics = min(2, len(valid_metrics))
            if count == 1:
                # If only 1 server affected, allow up to 2-3 metrics
                k_metrics = random.choice([1, 2, 3])
            else:
                k_metrics = 1 if random.random() < 0.60 else 2
            k_metrics = min(k_metrics, len(valid_metrics))

            selected_metrics = random.sample(valid_metrics, k_metrics)

            for metric_key in selected_metrics:
                # 4. Lookup valid issue types in ISSUE_CATALOGUE
                catalogue_entries = ISSUE_CATALOGUE.get(server_id, {}).get(metric_key, [])
                if not catalogue_entries:
                    continue

                profile = random.choice(catalogue_entries)
                issue_type = profile["issue_type"]

                # 5. Determine severity target: 65% CRITICAL, 35% WARNING
                target_sev = "CRITICAL" if random.random() < 0.65 else "WARNING"
                if target_sev == "CRITICAL":
                    rng = profile["crit_range"]
                else:
                    rng = profile["warn_range"]

                target_val = round(random.uniform(rng[0], rng[1]), 2)
                
                # Duration configuration: short (20-30s), medium (40-60s), long (60-120s), or persistent
                duration_choice = random.choices(
                    ["short", "medium", "long", "persistent"],
                    weights=[25, 35, 20, 20]
                )[0]

                if duration_choice == "short":
                    dur_sec = random.uniform(20.0, 30.0)
                    auto_rec = True
                elif duration_choice == "medium":
                    dur_sec = random.uniform(40.0, 60.0)
                    auto_rec = random.random() < 0.60
                elif duration_choice == "long":
                    dur_sec = random.uniform(60.0, 120.0)
                    auto_rec = random.random() < 0.40
                else:
                    dur_sec = 9999.0
                    auto_rec = False

                t_key = f"{server_id}.{metric_key}"
                targets[t_key] = target_val
                target_severities[t_key] = target_sev
                durations[t_key] = {
                    "start_time": now,
                    "duration_seconds": dur_sec,
                    "auto_recover": auto_rec,
                    "is_recovering": False,
                }

                issues.append({
                    "server_id": server_id,
                    "server_name": server_conf["name"],
                    "metric_key": metric_key,
                    "metric_name": server_conf["parameters"][metric_key]["name"],
                    "unit": server_conf["parameters"][metric_key]["unit"],
                    "issue_type": issue_type,
                    "description": profile["description"],
                    "target_severity": target_sev,
                    "target_value": target_val,
                    "duration_seconds": round(dur_sec, 1),
                    "auto_recover": auto_rec,
                    "recommended_action": profile["recommended_action"],
                })

            # 6. Apply Rule-Based Metric Relationships (Secondary Correlations)
            server_relations = METRIC_RELATIONSHIPS.get(server_id, {})
            for primary_metric in selected_metrics:
                if primary_metric in server_relations:
                    rules = server_relations[primary_metric]
                    for rule in rules:
                        sec_metric = rule["target_metric"]
                        sec_key = f"{server_id}.{sec_metric}"
                        # Only apply correlation if secondary metric wasn't independently selected as a primary issue
                        if sec_key not in targets and sec_metric in server_conf["parameters"]:
                            sec_conf = server_conf["parameters"][sec_metric]
                            base = sec_conf["baseline"]
                            factor = rule["factor"]
                            prim_val = targets[f"{server_id}.{primary_metric}"]
                            prim_base = server_conf["parameters"][primary_metric]["baseline"]
                            delta = prim_val - prim_base

                            # Compute correlated secondary value
                            sec_target = base + (delta * factor) + random.gauss(0, rule.get("noise_scale", 1.0))
                            sec_target = max(sec_conf["min"], min(sec_conf["max"], sec_target))
                            sec_target = round(sec_target, 2)

                            targets[sec_key] = sec_target
                            target_severities[sec_key] = "CORRELATED"
                            durations[sec_key] = {
                                "start_time": now,
                                "duration_seconds": 9999.0,
                                "auto_recover": False,
                                "is_recovering": False,
                            }

        # Build human-readable summary
        summary_parts = []
        for iss in issues:
            summary_parts.append(f"{iss['server_id']} ({iss['issue_type']})")
        readable_summary = ", ".join(summary_parts) if summary_parts else "No active incidents"

        return {
            "plan_id": plan_id,
            "created_at": now,
            "affected_servers": selected_servers,
            "issues": issues,
            "summary": readable_summary,
            "targets": targets,
            "target_severities": target_severities,
            "durations": durations,
        }
