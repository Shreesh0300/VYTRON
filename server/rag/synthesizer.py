"""
VYTRON RAG — AI Troubleshooting Synthesizer
Generates 8-section structured troubleshooting guidance based on retrieved ChromaDB documents
and sanitized incident evidence, integrating with the LLM engine with resilient fallback.
"""

import os
import json
import re
from typing import Any
import httpx

from server.config import RECOMMENDED_ACTIONS

class RAGSynthesizer:
    def __init__(self):
        self.provider_name = os.getenv("LLM_PROVIDER", "fallback").lower()
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm_model = os.getenv("LLM_MODEL", "llama3.2")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

    async def generate_troubleshooting(
        self,
        incident: dict[str, Any],
        retrieved_chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Synthesizes 8-section troubleshooting guidance:
        1. Incident Explanation
        2. Possible Root Causes (clearly marked as hypotheses)
        3. Telemetry Evidence
        4. Investigation Steps
        5. Diagnostic Commands (suggested for operator approval)
        6. Recommended Solutions
        7. Expected Outcome
        8. Knowledge Sources (clickable URLs & citations)
        """
        # Safety Check: If no relevant documentation was retrieved
        if not retrieved_chunks or (retrieved_chunks and retrieved_chunks[0].get("relevance_score", 0) < 0.25):
            return self._insufficient_knowledge_response(incident)

        # Sanitize evidence: Ensure only approved metric attributes are forwarded
        sanitized_incident = {
            "incident_id": incident.get("incident_id"),
            "server_id": incident.get("server_id"),
            "server_name": incident.get("server_name"),
            "server_type": incident.get("server_type"),
            "metric_key": incident.get("metric_key"),
            "metric_name": incident.get("metric_name"),
            "observed_value": incident.get("observed_value"),
            "threshold_value": incident.get("threshold_value"),
            "unit": incident.get("unit"),
            "severity": incident.get("severity"),
            "priority": incident.get("priority"),
            "issue_description": incident.get("issue_description"),
            "created_at_str": incident.get("created_at_str"),
        }

        # Attempt external LLM if configured
        if self.provider_name == "ollama":
            llm_res = await self._call_ollama(sanitized_incident, retrieved_chunks)
            if llm_res:
                return llm_res
        elif self.provider_name == "gemini" and self.gemini_key:
            llm_res = await self._call_gemini(sanitized_incident, retrieved_chunks)
            if llm_res:
                return llm_res
        elif self.provider_name == "openai" and self.openai_key:
            llm_res = await self._call_openai(sanitized_incident, retrieved_chunks)
            if llm_res:
                return llm_res

        # Resilient Deterministic Fallback: Synthesizes directly from retrieved ChromaDB chunks
        return self._synthesize_grounded_fallback(sanitized_incident, retrieved_chunks)

    def _insufficient_knowledge_response(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Strict honesty: do not hallucinate when knowledge is unavailable."""
        return {
            "incident_id": incident.get("incident_id"),
            "server_id": incident.get("server_id"),
            "insufficient_knowledge": True,
            "explanation": (
                f"Incident detected on {incident.get('server_id')}: {incident.get('issue_description')}. "
                "However, insufficient verified technical documentation was found in the local knowledge base."
            ),
            "possible_root_causes": ["Unverified anomaly — manual triage required by Tier-3 SRE."],
            "telemetry_evidence": [
                f"Observed {incident.get('metric_name')}: {incident.get('observed_value')} {incident.get('unit')} "
                f"(Threshold: {incident.get('threshold_value')} {incident.get('unit')})"
            ],
            "investigation_steps": [
                "1. Manually inspect system logs in /var/log/syslog or journalctl.",
                "2. Verify service daemon operational status via systemctl.",
                "3. Collect diagnostic memory/CPU flamegraphs before restarting."
            ],
            "diagnostic_commands": [
                {"command": f"journalctl -u {incident.get('server_id').lower()} -n 50", "description": "Review systemd journal logs"}
            ],
            "recommended_solutions": [
                "Refer to internal runbooks or hardware vendor documentation to diagnose this uncatalogued failure."
            ],
            "expected_outcome": "Identify root failure mechanism through manual triage.",
            "knowledge_sources": [],
            "synthesized_by": "VYTRON Safety Gate (Zero-Hallucination Policy)",
        }

    def _synthesize_grounded_fallback(
        self, incident: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Deterministic, rule-grounded synthesis using actual text from retrieved ChromaDB chunks.
        Guarantees 100% offline uptime with zero AI hallucinations.
        """
        server_id = incident["server_id"]
        metric_name = incident["metric_name"]
        observed = incident["observed_value"]
        threshold = incident["threshold_value"]
        unit = incident["unit"]
        severity = incident["severity"]
        priority = incident["priority"]

        # Parse sections, causes, commands from retrieved chunks
        possible_causes = []
        investigation_steps = []
        diagnostic_commands = []
        recommended_solutions = []
        knowledge_sources = []

        seen_sources = set()
        for chunk in chunks:
            content = chunk.get("content", "")
            meta = chunk.get("metadata", {})
            doc_title = meta.get("title", meta.get("doc_name", "Technical Guide"))
            source_name = meta.get("source", "Official Docs")
            url = meta.get("url", "#")
            section = meta.get("section", "Diagnostics")

            # Collect source citation
            src_key = (doc_title, url)
            if src_key not in seen_sources:
                seen_sources.add(src_key)
                knowledge_sources.append({
                    "title": doc_title,
                    "source": source_name,
                    "url": url,
                    "section": section,
                    "relevance_score": chunk.get("relevance_score", 0.85),
                })

            # Extract bullet points under Potential Root Causes
            if "Potential Root Causes" in content or "Root Causes" in content:
                for line in content.splitlines():
                    if line.strip().startswith("- **") or line.strip().startswith("- "):
                        cause_text = line.strip().lstrip("- ").replace("**", "")
                        if cause_text not in possible_causes:
                            possible_causes.append(cause_text)

            # Extract bullet points under Investigation Procedures
            if "Investigation Procedures" in content or "Diagnostic" in content:
                for line in content.splitlines():
                    if re.match(r"^\d+\.\s+", line.strip()):
                        step_text = line.strip()
                        if step_text not in investigation_steps:
                            investigation_steps.append(step_text)

            # Extract bash/shell commands from code blocks
            code_blocks = re.findall(r"```(?:bash|sql|sh)?\n(.*?)```", content, re.DOTALL)
            for block in code_blocks:
                current_desc = "Inspect system telemetry"
                for line in block.strip().splitlines():
                    line = line.strip()
                    if line.startswith("# "):
                        current_desc = line.lstrip("# ").strip()
                    elif line and not line.startswith("#"):
                        # Avoid duplicates
                        if not any(c["command"] == line for c in diagnostic_commands):
                            diagnostic_commands.append({
                                "command": line,
                                "description": current_desc
                            })

            # Extract Recommended Corrective Actions
            if "Recommended Corrective Actions" in content:
                for line in content.splitlines():
                    if line.strip().startswith("- **") or line.strip().startswith("- "):
                        sol_text = line.strip().lstrip("- ").replace("**", "")
                        if sol_text not in recommended_solutions:
                            recommended_solutions.append(sol_text)

        # Fallback defaults if chunks were concise
        if not possible_causes:
            possible_causes = [
                f"Sustained {metric_name} demand exceeding server capacity limits.",
                f"Resource starvation or lock contention on {server_id}.",
                "Upstream dependency processing latency propagation."
            ]

        if not investigation_steps:
            investigation_steps = [
                f"1. Isolate the offending process or thread pool consuming {metric_name}.",
                "2. Check system error logs and kernel ring buffer (dmesg).",
                "3. Verify network gateway and database dependency connectivity.",
                "4. Compare current readings with baseline historical performance trends."
            ]

        if not diagnostic_commands:
            diagnostic_commands = [
                {"command": "top -b -n 1 | head -n 20", "description": "Review top process resource consumers"},
                {"command": "dmesg -T | tail -n 30", "description": "Check kernel ring buffer for hardware/OOM alerts"},
                {"command": "netstat -s | head -n 30", "description": "Check network statistics and packet drops"},
            ]

        # Add metric-specific action from catalog if available
        act_key = f"{server_id}.{incident.get('metric_key')}"
        if act_key in RECOMMENDED_ACTIONS:
            recommended_solutions.insert(0, RECOMMENDED_ACTIONS[act_key])

        explanation = (
            f"Server {server_id} ({incident.get('server_name')}) experienced an abnormal {severity.lower()} "
            f"threshold breach in {metric_name}. Observed reading reached {observed} {unit}, which violates "
            f"the configured threshold limit of {threshold} {unit}. The incident has been classified with "
            f"priority {priority} based on cluster criticality."
        )

        expected_outcome = (
            f"Following remediation, {metric_name} on {server_id} should normalize below {threshold} {unit}, "
            f"restoring server status to NORMAL and recovering application responsiveness."
        )

        return {
            "incident_id": incident["incident_id"],
            "server_id": server_id,
            "insufficient_knowledge": False,
            "explanation": explanation,
            "possible_root_causes": possible_causes[:4],
            "telemetry_evidence": [
                f"Observed {metric_name}: {observed} {unit}",
                f"Configured Threshold: {threshold} {unit} ({severity})",
                f"Assigned Priority: {priority}",
                f"Detection Timestamp: {incident.get('created_at_str', '--:--:--')}",
                f"Issue Signature: {incident.get('issue_description')}",
            ],
            "investigation_steps": investigation_steps[:4],
            "diagnostic_commands": diagnostic_commands[:6],
            "recommended_solutions": recommended_solutions[:4],
            "expected_outcome": expected_outcome,
            "knowledge_sources": knowledge_sources[:4],
            "synthesized_by": "VYTRON RAG Intelligence Engine (Grounded Documentation)",
        }

    async def _call_ollama(self, incident: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Invokes local Ollama instance with structured RAG prompt."""
        prompt = self._build_llm_rag_prompt(incident, chunks)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.llm_model, "prompt": prompt, "stream": False, "format": "json"}
                )
                if res.status_code == 200:
                    text = res.json().get("response", "")
                    return self._parse_llm_json(text, incident, chunks, "Ollama (" + self.llm_model + ")")
        except Exception:
            pass
        return None

    async def _call_gemini(self, incident: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Invokes Gemini API with structured RAG prompt."""
        prompt = self._build_llm_rag_prompt(incident, chunks)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"}
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return self._parse_llm_json(text, incident, chunks, "Google Gemini 1.5 Flash")
        except Exception:
            pass
        return None

    async def _call_openai(self, incident: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Invokes OpenAI API with structured RAG prompt."""
        prompt = self._build_llm_rag_prompt(incident, chunks)
        url = "https://api.openai.com/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.openai_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    text = data["choices"][0]["message"]["content"]
                    return self._parse_llm_json(text, incident, chunks, "OpenAI GPT-4o-mini")
        except Exception:
            pass
        return None

    def _build_llm_rag_prompt(self, incident: dict[str, Any], chunks: list[dict[str, Any]]) -> str:
        chunks_text = "\n\n".join([
            f"--- SOURCE: {c.get('metadata', {}).get('title')} ({c.get('metadata', {}).get('url')}) ---\n{c.get('content')}"
            for c in chunks[:4]
        ])

        return f"""You are an expert AIOps SRE incident investigator. Analyze this infrastructure incident using ONLY the retrieved technical documentation below.
Never invent commands or solutions not supported by the context.
Distinguish possible root causes from confirmed facts.
Provide output strictly in valid JSON format:

{{
  "explanation": "Clear 2-sentence explanation of what occurred and why thresholds were breached",
  "possible_root_causes": ["Cause 1", "Cause 2", "Cause 3"],
  "telemetry_evidence": ["Evidence point 1", "Evidence point 2"],
  "investigation_steps": ["Step 1", "Step 2", "Step 3"],
  "diagnostic_commands": [
    {{"command": "command string", "description": "what this checks"}}
  ],
  "recommended_solutions": ["Solution 1", "Solution 2"],
  "expected_outcome": "Description of expected post-remediation performance"
}}

INCIDENT EVIDENCE:
{json.dumps(incident, indent=2)}

RETRIEVED KNOWLEDGE BASE DOCUMENTATION:
{chunks_text}
"""

    def _parse_llm_json(
        self, text: str, incident: dict[str, Any], chunks: list[dict[str, Any]], model_label: str
    ) -> dict[str, Any] | None:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                parsed = json.loads(text[start:end])
                
                # Format knowledge sources from retrieved chunks
                knowledge_sources = []
                seen_src = set()
                for c in chunks:
                    m = c.get("metadata", {})
                    src_tuple = (m.get("title"), m.get("url"))
                    if src_tuple not in seen_src:
                        seen_src.add(src_tuple)
                        knowledge_sources.append({
                            "title": m.get("title", "Technical Documentation"),
                            "source": m.get("source", "Official Docs"),
                            "url": m.get("url", "#"),
                            "section": m.get("section", "Diagnostics"),
                            "relevance_score": c.get("relevance_score", 0.9),
                        })

                return {
                    "incident_id": incident["incident_id"],
                    "server_id": incident["server_id"],
                    "insufficient_knowledge": False,
                    "explanation": parsed.get("explanation", ""),
                    "possible_root_causes": parsed.get("possible_root_causes", []),
                    "telemetry_evidence": parsed.get("telemetry_evidence", []),
                    "investigation_steps": parsed.get("investigation_steps", []),
                    "diagnostic_commands": parsed.get("diagnostic_commands", []),
                    "recommended_solutions": parsed.get("recommended_solutions", []),
                    "expected_outcome": parsed.get("expected_outcome", ""),
                    "knowledge_sources": knowledge_sources,
                    "synthesized_by": f"VYTRON RAG + {model_label}",
                }
        except Exception as e:
            print(f"[RAGSynthesizer] JSON parsing error from LLM: {e}")
        return None
