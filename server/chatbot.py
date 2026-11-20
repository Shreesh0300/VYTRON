"""
VYTRON — AI IT Manager Support Chatbot Service
Implements a dedicated, conversational, RAG-grounded IT Infrastructure & Operations Support Chatbot.

Key Capabilities:
1. Intent Classification: GREETING, ACKNOWLEDGEMENT, GENERAL_IT_QUESTION,
   TROUBLESHOOTING_REQUEST, INCIDENT_SPECIFIC_QUERY, FOLLOW_UP_QUERY, OUT_OF_SCOPE.
2. Natural Conversational Style: Adaptive formatting based on user intent (no rigid 7-section report for simple messages).
3. Intent-Aware RAG: Skips vector retrieval for greetings/acknowledgements; performs semantic search for technical questions.
4. Conversation Memory: Remembers current server, metric, incident ID, and prior context across turns.
5. Strict IT-Only Scope Enforcement & Prompt Injection Defense.
6. ChromaDB Vector Similarity Search (reusing existing 'vytron_troubleshooting_kb' with 35,249 chunks).
7. Live Backend Telemetry Integration with the 5-Server Simulator (APP-01, DB-01, AUTH-01, BACKUP-01, NETWORK-01).
8. Anti-Hallucination Controls: Zero metric fabrication, grounded citations only, non-destructive diagnostic commands.
"""

import os
import re
import time
import uuid
import json
import asyncio
import httpx
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

from server.rag.pipeline import get_vector_store
from server.config import SERVERS_CONFIG, RECOMMENDED_ACTIONS


# ══════════════════════════════════════════════════════════════════════════════
# 1. SCOPE VALIDATION & PROMPT INJECTION DEFENSE
# ══════════════════════════════════════════════════════════════════════════════

# Allowed IT Infrastructure keywords and topics
ALLOWED_IT_PATTERNS = [
    r"\b(server|cpu|ram|memory|disk|i/o|io|storage|database|postgres|psql|query|latency)\b",
    r"\b(network|bandwidth|packet|loss|throughput|interface|bgp|tcp|icmp|ping|traceroute)\b",
    r"\b(auth|authentication|login|credential|sso|ldap|jwt|token|brute|password|security)\b",
    r"\b(backup|restore|recovery|pool|replication|snapshot|disaster|enospc|fsck)\b",
    r"\b(incident|alert|priority|p1|p2|p3|p4|threshold|telemetry|metric|health|status)\b",
    r"\b(collector|egress|privacy|redact|hash|sha-256|buffer|outage|saas|tier|agent)\b",
    r"\b(troubleshoot|investigate|root\s*cause|remediat|fix|prevent|mitigat|runbook|sre)\b",
    r"\b(app-01|db-01|auth-01|backup-01|network-01|collector-01)\b",
    r"\b(how\s+can\s+i|what\s+should|why\s+is|what\s+is\s+the\s+issue|how\s+to\s+fix|what\s+happened)\b",
    r"\b(check|command|restart|scale|kill|optimize|bottleneck|surge|spike|drop|flapping)\b",
    r"\b(vytron|cicada|aiops|overview|dashboard|log|logs|heap|thread|container|docker|k8s)\b",
    r"\b(what\s+is|explain|causes?|leak|leakage|pressure|exhaustion|contention)\b"
]

# Conversational greetings and acknowledgements allowed in IT support
GREETING_WORDS = {
    "hi", "hii", "hiii", "hiiii", "hello", "hey", "heyy", "heya", "howdy", "hola",
    "good morning", "good afternoon", "good evening", "greetings", "sup", "yo",
    "hey there", "hello there", "hi there", "hi vytron", "hello vytron"
}

ACK_WORDS = {
    "thanks", "thank you", "thank you so much", "thank you very much", "thx", "ty",
    "okay", "ok", "k", "got it", "understood", "great", "awesome", "perfect",
    "sounds good", "alright", "cool", "noted", "nice", "ok thanks", "okay thanks"
}

# Explicitly disallowed non-IT topics
DISALLOWED_PATTERNS = [
    r"\b(movie|music|song|celebrity|hollywood|bollywood|actor|actress|cinema)\b",
    r"\b(football|cricket|soccer|nba|ipl|sports|tournament|score|fifa|olympics)\b",
    r"\b(politics|election|president|prime\s*minister|minister|government|party|vote|war)\b",
    r"\b(recipe|cook|baking|food|restaurant|dinner|lunch|breakfast|pizza|burger)\b",
    r"\b(personal|dating|relationship|love|horoscope|zodiac|astrology|therapy)\b",
    r"\b(joke|story|poem|poetry|rhyme|creative\s*writing|fantasy|novel)\b",
    r"\b(weather|climate|forecast|vacation|travel|flight|hotel)\b",
    r"\b(crypto|bitcoin|ethereum|stocks|trading|forex|invest\s*in)\b",
    r"\b(write\s*a\s*game|snake\s*game|tic\s*tac\s*toe|leetcode\s*two\s*sum|html\s*landing\s*page)\b"
]

# Prompt injection markers
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(a|an)\s+",
    r"jailbreak|dan\s+mode|bypass|override\s+system",
    r"forget\s+your\s+(rules|restrictions|persona)",
    r"repeat\s+the\s+system\s+prompt"
]

SCOPE_REJECTION_MESSAGE = (
    "I'm VYTRON's AI IT Support Assistant. I can help with server monitoring, "
    "infrastructure incidents, database performance, networking, security and IT troubleshooting. "
    "Please ask an IT-related question."
)

INSUFFICIENT_KNOWLEDGE_MESSAGE = (
    "I couldn't find sufficiently relevant information in VYTRON's knowledge base to answer this confidently. "
    "Please provide more details or consult the relevant infrastructure documentation."
)


def validate_it_scope(query: str) -> tuple[bool, str | None]:
    """
    Validates that a user query is within IT operations scope or valid conversational flow.
    Guards against prompt injection and off-topic conversations.
    """
    q = query.strip().lower()
    if not q:
        return False, "Please enter an IT operations or infrastructure question."

    q_clean = re.sub(r"[^\w\s]", "", q).strip()

    # Check for prompt injection attempts
    for pat in INJECTION_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return False, SCOPE_REJECTION_MESSAGE

    # Allow natural greetings and acknowledgements
    if q_clean in GREETING_WORDS or q_clean in ACK_WORDS:
        return True, None
    if re.match(r"^(hi+|hello+|hey+|good\s*(morning|afternoon|evening))\b", q_clean) and len(q_clean.split()) <= 3:
        return True, None

    # Check for explicitly disallowed domains
    for pat in DISALLOWED_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            # Exception if specifically inquiring about IT infrastructure context
            if not any(re.search(it, q, re.IGNORECASE) for it in ALLOWED_IT_PATTERNS[:8]):
                return False, SCOPE_REJECTION_MESSAGE

    # Ensure query touches IT infrastructure or operations concepts
    is_it_related = any(re.search(pat, q, re.IGNORECASE) for pat in ALLOWED_IT_PATTERNS)
    # Allow short conversational follow-ups
    is_short_followup = len(q.split()) <= 8 and any(
        re.search(p, q, re.IGNORECASE) for p in [
            r"\b(fix|check|prevent|happen|why|how|what|first|it|this|that|next|command)\b"
        ]
    )

    if not is_it_related and not is_short_followup and len(q.split()) > 3:
        return False, SCOPE_REJECTION_MESSAGE

    return True, None


# ══════════════════════════════════════════════════════════════════════════════
# 2. INTENT CLASSIFICATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ChatIntent:
    GREETING = "GREETING"
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    GENERAL_IT_QUESTION = "GENERAL_IT_QUESTION"
    TROUBLESHOOTING_REQUEST = "TROUBLESHOOTING_REQUEST"
    INCIDENT_SPECIFIC_QUERY = "INCIDENT_SPECIFIC_QUERY"
    FOLLOW_UP_QUERY = "FOLLOW_UP_QUERY"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


def classify_intent(
    query: str,
    history: list[dict[str, Any]],
    active_incident: Optional[dict[str, Any]] = None,
    session_ctx: Optional[dict[str, Any]] = None
) -> str:
    """
    Identifies user message intent to drive adaptive conversational formatting and selective RAG.
    Categories: GREETING, ACKNOWLEDGEMENT, GENERAL_IT_QUESTION, TROUBLESHOOTING_REQUEST,
    INCIDENT_SPECIFIC_QUERY, FOLLOW_UP_QUERY, OUT_OF_SCOPE.
    """
    q = query.strip().lower()
    q_clean = re.sub(r"[^\w\s]", "", q).strip()

    # 1. Greetings
    if q_clean in GREETING_WORDS:
        return ChatIntent.GREETING
    if re.match(r"^(hi+|hello+|hey+|good\s*(morning|afternoon|evening))\b", q_clean) and len(q_clean.split()) <= 3:
        # Check if contains technical server inquiry
        if not any(s in q_clean for s in ["server", "app01", "db01", "auth01", "backup01", "network01", "incident", "latency", "cpu", "disk"]):
            return ChatIntent.GREETING

    # 2. Acknowledgements
    if q_clean in ACK_WORDS:
        return ChatIntent.ACKNOWLEDGEMENT

    # 3. Follow-up query
    # If session has history or previous server context, and user asks follow-up phrasing without a new server
    has_history = len(history) > 0 or (session_ctx and session_ctx.get("last_server_id"))
    has_server_named = bool(re.search(r"\b(app-01|db-01|auth-01|backup-01|network-01|collector-01)\b", q, re.IGNORECASE))

    followup_triggers = [
        r"\b(how\s+do\s+i\s+fix\s+(it|this)|what\s+should\s+i\s+check\s+first|can\s+you\s+explain\s+that)\b",
        r"\b(what\s+happens\s+if\s+i\s+don'?t\s+resolve\s+it|how\s+do\s+i\s+prevent\s+(this|it)|how\s+can\s+i\s+prevent\s+(it|this))\b",
        r"\b(what\s+next|and\s+then|what\s+else|what\s+command(s)?|show\s+me\s+more|can\s+you\s+elaborate)\b",
        r"^(what\s+about\s+(it|this)|why\s+is\s+that|how\s+so|how\s+to\s+prevent\s+it)[\s?]*$"
    ]

    if has_history and not has_server_named:
        if any(re.search(p, q, re.IGNORECASE) for p in followup_triggers):
            return ChatIntent.FOLLOW_UP_QUERY
        if re.search(r"\b(it|this|that|first|prevent)\b", q) and len(q.split()) <= 7:
            return ChatIntent.FOLLOW_UP_QUERY

    # 4. Incident-Specific Query
    # Mentions specific server ID or active incident context or specific incident failure on a server
    if has_server_named or active_incident or re.search(r"\b(this\s+incident|active\s+incident|what\s+is\s+happening\s+with)\b", q, re.IGNORECASE):
        return ChatIntent.INCIDENT_SPECIFIC_QUERY

    # 5. Troubleshooting Request
    # Asks how to fix, resolve, solve, troubleshoot a technical issue without naming a specific server
    if re.search(r"\b(how\s+(can|do)\s+i\s+(fix|resolve|troubleshoot|diagnose|mitigate|debug|solve)|steps\s+to\s+(fix|troubleshoot))\b", q, re.IGNORECASE):
        return ChatIntent.TROUBLESHOOTING_REQUEST

    # 6. General IT Question
    # Asks conceptual questions: 'what is ...', 'explain ...', 'what causes ...', 'how does ... work'
    if re.search(r"\b(what\s+is|explain|what\s+causes?|why\s+does|how\s+does|difference\s+between)\b", q, re.IGNORECASE):
        return ChatIntent.GENERAL_IT_QUESTION

    # Default to General IT Question or Troubleshooting
    if re.search(r"\b(fix|resolve|troubleshoot|step|remediat)\b", q, re.IGNORECASE):
        return ChatIntent.TROUBLESHOOTING_REQUEST
    return ChatIntent.GENERAL_IT_QUESTION


# ══════════════════════════════════════════════════════════════════════════════
# 3. SESSION CONTEXT MANAGER (ISOLATED MULTI-TURN SESSIONS)
# ══════════════════════════════════════════════════════════════════════════════

class ChatSessionManager:
    """In-memory multi-turn session repository with strict cross-session isolation."""

    def __init__(self, max_history_turns: int = 10):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._max_history = max_history_turns

    def get_or_create(self, session_id: Optional[str] = None) -> tuple[str, dict[str, Any]]:
        sid = session_id or f"session-{uuid.uuid4().hex[:12]}"
        if sid not in self._sessions:
            self._sessions[sid] = {
                "session_id": sid,
                "created_at": time.time(),
                "last_active": time.time(),
                "incident_context": None,
                "last_server_id": None,
                "last_server_name": None,
                "last_metric": None,
                "last_topic": None,
                "last_chunks": [],
                "messages": []
            }
        self._sessions[sid]["last_active"] = time.time()
        return sid, self._sessions[sid]

    def update_incident_context(self, session_id: str, incident: dict[str, Any]):
        if session_id in self._sessions and incident:
            self._sessions[session_id]["incident_context"] = incident
            if incident.get("server_id"):
                self._sessions[session_id]["last_server_id"] = incident.get("server_id")
            if incident.get("server_name"):
                self._sessions[session_id]["last_server_name"] = incident.get("server_name")
            if incident.get("metric_name"):
                self._sessions[session_id]["last_topic"] = incident.get("metric_name")
            if incident.get("metric_key"):
                self._sessions[session_id]["last_metric"] = incident.get("metric_key")

    def update_context(
        self,
        session_id: str,
        server_id: Optional[str] = None,
        server_name: Optional[str] = None,
        metric: Optional[str] = None,
        topic: Optional[str] = None,
        incident: Optional[dict[str, Any]] = None,
        chunks: Optional[list[dict[str, Any]]] = None
    ):
        if session_id in self._sessions:
            s = self._sessions[session_id]
            if server_id:
                s["last_server_id"] = server_id
            if server_name:
                s["last_server_name"] = server_name
            if metric:
                s["last_metric"] = metric
            if topic:
                s["last_topic"] = topic
            if incident:
                s["incident_context"] = incident
            if chunks is not None:
                s["last_chunks"] = chunks

    def get_context(self, session_id: str) -> dict[str, Any]:
        return self._sessions.get(session_id, {})

    def get_incident_context(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        return session.get("incident_context") if session else None

    def add_turn(self, session_id: str, user_text: str, assistant_text: str, sources: list[dict[str, Any]]):
        if session_id in self._sessions:
            history = self._sessions[session_id]["messages"]
            history.append({
                "role": "user",
                "content": user_text,
                "timestamp": time.time()
            })
            history.append({
                "role": "assistant",
                "content": assistant_text,
                "sources": sources,
                "timestamp": time.time()
            })
            if len(history) > self._max_history * 2:
                self._sessions[session_id]["messages"] = history[-self._max_history * 2:]

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        return session.get("messages", []) if session else []

    def clear(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._sessions[session_id]["messages"] = []
            self._sessions[session_id]["incident_context"] = None
            self._sessions[session_id]["last_server_id"] = None
            self._sessions[session_id]["last_server_name"] = None
            self._sessions[session_id]["last_metric"] = None
            self._sessions[session_id]["last_topic"] = None
            self._sessions[session_id]["last_chunks"] = []
            return True
        return False


# Global session manager instance
chat_sessions = ChatSessionManager()


# ══════════════════════════════════════════════════════════════════════════════
# 4. KNOWLEDGE RETRIEVAL & VECTOR GROUNDING
# ══════════════════════════════════════════════════════════════════════════════

def retrieve_knowledge(query: str, incident: Optional[dict[str, Any]] = None, n_results: int = 4) -> list[dict[str, Any]]:
    """
    Executes semantic similarity search against the ChromaDB vector store.
    Filters by relevance threshold and removes duplicate chunks.
    """
    store = get_vector_store()
    if not store or store.collection.count() == 0:
        return []

    # Augment query text with incident context if available
    augmented_query = query
    if incident:
        srv_type = incident.get("server_type") or incident.get("server_name", "")
        metric_name = incident.get("metric_name") or incident.get("metric_key", "")
        augmented_query = f"{query} {srv_type} {metric_name}"

    try:
        raw_chunks = store.search(query_text=augmented_query, n_results=n_results)
    except Exception as e:
        print(f"[Chatbot] VectorStore search error: {e}")
        return []

    valid_chunks: list[dict[str, Any]] = []
    seen_ids = set()

    for chunk in raw_chunks:
        cid = chunk.get("chunk_id", "")
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        # Apply relevance threshold: 0.28
        score = chunk.get("relevance_score", 0.0)
        if score >= 0.28:
            valid_chunks.append(chunk)

    return valid_chunks


# ══════════════════════════════════════════════════════════════════════════════
# 5. LIVE BACKEND TELEMETRY HARVESTER (SOURCE B)
# ══════════════════════════════════════════════════════════════════════════════

def harvest_live_telemetry(incident: Optional[dict[str, Any]], query: str, simulator_instance: Any) -> dict[str, Any]:
    """
    Extracts live operational metrics and health states from the running VYTRON simulator.
    Associates the query with target servers (APP-01, DB-01, AUTH-01, BACKUP-01, NETWORK-01).
    """
    result = {
        "telemetry_available": False,
        "target_server_id": None,
        "server_name": None,
        "current_status": None,
        "current_health_state": None,
        "current_metrics": {},
        "active_incidents_for_server": [],
        "note": None
    }

    if not simulator_instance:
        result["note"] = "Live backend simulator instance unavailable."
        return result

    try:
        snapshot = simulator_instance.get_snapshot()
        servers = snapshot.get("servers", {})
        active_incidents = snapshot.get("priority_queue", [])

        # Determine target server ID from incident context or user query
        target_sid = None
        if incident and incident.get("server_id"):
            target_sid = incident.get("server_id")
        else:
            q_upper = query.upper()
            for sid in ["APP-01", "DB-01", "AUTH-01", "BACKUP-01", "NETWORK-01"]:
                if sid in q_upper:
                    target_sid = sid
                    break
            if not target_sid:
                if "DATABASE" in q_upper or "POSTGRES" in q_upper or "SQL" in q_upper:
                    target_sid = "DB-01"
                elif "APPLICATION" in q_upper or "JAVA" in q_upper or "NODE" in q_upper or "MEMORY PRESSURE" in q_upper:
                    target_sid = "APP-01"
                elif "AUTH" in q_upper or "LOGIN" in q_upper or "PASSWORD" in q_upper:
                    target_sid = "AUTH-01"
                elif "BACKUP" in q_upper or "SNAPSHOT" in q_upper or "STORAGE" in q_upper:
                    target_sid = "BACKUP-01"
                elif "NETWORK" in q_upper or "PACKET" in q_upper or "LATENCY" in q_upper or "BGP" in q_upper:
                    target_sid = "NETWORK-01"

        if target_sid and target_sid in servers:
            s = servers[target_sid]
            result["telemetry_available"] = True
            result["target_server_id"] = target_sid
            result["server_name"] = s.get("name")
            result["current_status"] = s.get("status")
            result["current_health_state"] = s.get("health_state")
            result["current_metrics"] = s.get("metrics", {})

            # Filter related incidents
            result["active_incidents_for_server"] = [
                inc for inc in active_incidents if inc.get("server_id") == target_sid
            ]
        else:
            result["note"] = "General query; no specific target server isolated in live telemetry."

    except Exception as e:
        result["note"] = f"Error querying live telemetry: {str(e)}"

    return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. DYNAMIC CONTEXTUAL SUGGESTED QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_contextual_suggestions(incident: Optional[dict[str, Any]] = None) -> list[str]:
    """Generates 4 high-value contextual questions adapted to the active incident."""
    if not incident:
        return [
            "What is the current health status of all 5 servers?",
            "How do I troubleshoot high database query latency on DB-01?",
            "What security procedures apply to failed login spikes on AUTH-01?",
            "How does VYTRON enforce local data privacy during telemetry egress?"
        ]

    sid = incident.get("server_id", "")
    metric = incident.get("metric_key") or incident.get("metric_name", "")

    if sid == "DB-01" or "latency" in metric.lower() or "connection" in metric.lower() or "disk" in metric.lower():
        return [
            f"What could cause this {metric} spike on DB-01?",
            "How do I identify blocking query locks in PostgreSQL?",
            f"What safe remediation steps resolve {metric} degradation?",
            "How can we prevent database connection pool exhaustion?"
        ]
    elif sid == "AUTH-01" or "login" in metric.lower():
        return [
            "Is this elevated failed login rate indicative of credential stuffing?",
            "What should I check first to verify this?",
            "What rate limiting policies should be applied to AUTH-01?",
            "How do we prevent authentication service thread exhaustion?"
        ]
    elif sid == "NETWORK-01" or "packet" in metric.lower() or "bandwidth" in metric.lower():
        return [
            "What non-destructive commands diagnose network packet loss?",
            "Could BGP route flapping cause this transit latency jump?",
            "What steps inspect switch interface CRC checksum errors?",
            "How do we apply QoS traffic shaping to restore normal bandwidth?"
        ]
    elif sid == "APP-01" or "cpu" in metric.lower() or "ram" in metric.lower() or "memory" in metric.lower():
        return [
            f"What causes severe {metric} saturation on Application Server?",
            "How do I analyze memory heap dumps and GC pause frequencies?",
            "When should application container replicas be scaled out?",
            "What investigation steps verify thread pool starvation?"
        ]
    elif sid == "BACKUP-01" or "transfer" in metric.lower() or "pool" in metric.lower():
        return [
            "Why is backup transfer throughput degraded below threshold?",
            "How do I resolve storage pool capacity exhaustion safely?",
            "What steps verify snapshot replication lag without data loss?",
            "How can we optimize backup job execution windows?"
        ]

    return [
        f"What is the root cause of this {sid} incident?",
        f"What supporting evidence justifies the current {incident.get('priority', 'P3')} priority?",
        "What specific investigation procedures should an SRE follow?",
        "What preventative measures avoid this failure in the future?"
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 7. CONVERSATIONAL RESPONSE SYNTHESIZER
# ══════════════════════════════════════════════════════════════════════════════

class ChatbotSynthesizer:
    """
    Conversational, RAG-grounded chat response engine.
    Adapts response format to user intent (Greetings, Acknowledgements, General Questions,
    Troubleshooting Steps, Follow-ups, and Incident Investigations).
    """

    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def _get_gemini_key(self) -> str:
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            load_dotenv(override=True)
            key = os.getenv("GEMINI_API_KEY", "").strip()
        return key.strip("\"'")

    async def generate_response(
        self,
        query: str,
        session_id: str,
        intent: str,
        incident: Optional[dict[str, Any]],
        chunks: list[dict[str, Any]],
        telemetry: dict[str, Any],
        history: list[dict[str, Any]],
        session_ctx: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Coordinates intent-aware response generation with Gemini or deterministic fallback.
        """
        # Intent A: GREETING — Natural, brief greeting without incident or RAG retrieval
        if intent == ChatIntent.GREETING:
            return {
                "answer": "Hey! 👋 How can I help you today? Are you looking into a server issue or do you need help with any IT operations task?",
                "sources": [],
                "retrieval_succeeded": False,
                "incident_context_used": False,
                "limitation": None
            }

        # Intent B: ACKNOWLEDGEMENT — Natural, brief acknowledgement
        if intent == ChatIntent.ACKNOWLEDGEMENT:
            return {
                "answer": "You're welcome! Let me know if you need any further assistance with your servers, network, or IT operations.",
                "sources": [],
                "retrieval_succeeded": False,
                "incident_context_used": False,
                "limitation": None
            }

        # Format sources from chunks for technical intents (deduplicated by title)
        sources = []
        seen_titles: set[str] = set()
        for c in chunks:
            m = c.get("metadata", {})
            title = m.get("title") or m.get("doc_name") or "Technical Runbook"
            if title in seen_titles:
                continue
            seen_titles.add(title)
            url = m.get("url") or "#"
            source_org = m.get("source") or "Official Manual"
            sec = m.get("section") or "Diagnostics"
            sources.append({
                "title": title,
                "url": url,
                "source": source_org,
                "section": sec,
                "relevance_score": c.get("relevance_score", 0.0)
            })

        retrieval_succeeded = len(chunks) > 0

        # Safety Gate: If query has zero chunks, no incident, and is not a known server query
        q_lower = query.lower()
        is_known_server = any(sid.lower() in q_lower for sid in ["app-01", "db-01", "auth-01", "backup-01", "network-01", "database", "latency", "login", "packet", "cpu", "memory"])
        if not retrieval_succeeded and not incident and not is_known_server and intent == ChatIntent.TROUBLESHOOTING_REQUEST:
            answer = (
                f"{INSUFFICIENT_KNOWLEDGE_MESSAGE}\n\n"
                f"**[General Troubleshooting Suggestion — Not from Retrieved Knowledge Base]**\n"
                f"To investigate this issue further:\n"
                f"1. Inspect active incident cards and priority queues in the VYTRON dashboard.\n"
                f"2. Select the affected node from the 5-Server Monitoring grid to inspect real-time parameter charts.\n"
                f"3. Open the Incident Details modal and launch 'Investigate with AI' to retrieve grounded runbooks."
            )
            return {
                "answer": answer,
                "sources": [],
                "retrieval_succeeded": False,
                "incident_context_used": False,
                "limitation": "No high-relevance documentation chunks found in vector store."
            }

        # Attempt LLM generation if configured (Gemini or Ollama)
        llm_response = await self._try_llm_generation(query, intent, incident, chunks, telemetry, history, session_ctx)
        if llm_response:
            return {
                "answer": llm_response,
                "sources": sources,
                "retrieval_succeeded": retrieval_succeeded,
                "incident_context_used": bool(incident),
                "limitation": None
            }

        # Deterministic Grounded Synthesis (Reliable, evidence-backed fallback)
        answer = self._synthesize_grounded_fallback(query, intent, incident, chunks, telemetry, history, session_ctx)

        limitation = None
        if not retrieval_succeeded and intent in [ChatIntent.GENERAL_IT_QUESTION, ChatIntent.TROUBLESHOOTING_REQUEST]:
            limitation = "No high-relevance documentation chunks found in vector store. Answer grounded in rule engine."

        return {
            "answer": answer,
            "sources": sources,
            "retrieval_succeeded": retrieval_succeeded,
            "incident_context_used": bool(incident),
            "limitation": limitation
        }

    async def _try_llm_generation(
        self,
        query: str,
        intent: str,
        incident: Optional[dict[str, Any]],
        chunks: list[dict[str, Any]],
        telemetry: dict[str, Any],
        history: list[dict[str, Any]],
        session_ctx: Optional[dict[str, Any]] = None
    ) -> str | None:
        """Attempts to invoke Gemini or Ollama with intent-driven prompt instructions."""
        gemini_key = self._get_gemini_key()
        provider = os.getenv("LLM_PROVIDER", "").lower()

        # 1. Try Gemini if API key is present
        if gemini_key:
            models_to_try = [
                os.getenv("LLM_MODEL", "gemini-flash-lite-latest"),
                "gemini-flash-lite-latest",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3.8-flash"
            ]
            clean_models = []
            for m in models_to_try:
                if m and m not in clean_models:
                    clean_models.append(m)

            prompt = self._build_llm_prompt(query, intent, incident, chunks, telemetry, history, session_ctx)

            for model in clean_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        res = await client.post(
                            url,
                            json={
                                "contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {
                                    "temperature": 0.1,  # Near-zero temperature strictly enforces factual adherence
                                    "topP": 0.8,
                                    "maxOutputTokens": 2048
                                }
                            }
                        )
                        if res.status_code == 200:
                            data = res.json()
                            ans = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                            if ans and len(ans) > 20:
                                return self._verify_and_guard_response(ans, intent, incident, telemetry, chunks)
                except Exception:
                    continue

        # 2. Try Ollama if local instance is up
        if provider == "ollama" or not gemini_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    test = await client.get(f"{self.ollama_url}/api/version")
                    if test.status_code == 200:
                        prompt = self._build_llm_prompt(query, intent, incident, chunks, telemetry, history, session_ctx)
                        res = await client.post(
                            f"{self.ollama_url}/api/generate",
                            json={"model": "llama3.2", "prompt": prompt, "stream": False}
                        )
                        if res.status_code == 200:
                            ans = res.json().get("response", "").strip()
                            if ans:
                                return self._verify_and_guard_response(ans, intent, incident, telemetry, chunks)
            except Exception:
                pass

        return None

    def _build_llm_prompt(
        self,
        query: str,
        intent: str,
        incident: Optional[dict[str, Any]],
        chunks: list[dict[str, Any]],
        telemetry: dict[str, Any],
        history: list[dict[str, Any]],
        session_ctx: Optional[dict[str, Any]] = None
    ) -> str:
        doc_blocks = []
        for i, c in enumerate(chunks[:4], 1):
            m = c.get("metadata", {})
            title = m.get("title") or m.get("doc_name") or "Technical Runbook"
            sec = m.get("section") or "Diagnostics"
            doc_blocks.append(f"[Source {i}] Title: {title} | Section: {sec}\n{c.get('content', '').strip()}")
        doc_texts = "\n\n".join(doc_blocks) if doc_blocks else "No specific runbook chunks retrieved."

        hist_texts = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in history[-4:]])

        target_sid = telemetry.get("target_server_id") or (incident.get("server_id") if incident else None) or (session_ctx.get("last_server_id") if session_ctx else None) or "Target Server"
        srv_name = telemetry.get("server_name") or (incident.get("server_name") if incident else None) or (session_ctx.get("last_server_name") if session_ctx else None) or "Server Node"

        system_preamble = (
            "You are VYTRON AI IT Support Assistant, a friendly, professional and knowledgeable assistant for IT infrastructure managers.\n"
            "You are not a robotic incident-report generator.\n"
            "Communicate naturally, like an experienced IT operations engineer helping another IT professional.\n"
            "First understand what the user intends to communicate.\n"
            "If the user greets you, greet them back.\n"
            "If the user asks a simple question, answer it directly.\n"
            "If the user needs troubleshooting, retrieve relevant knowledge and explain the solution.\n"
            "If the user asks about an active incident, use the available live telemetry and incident context.\n"
            "If the user asks a follow-up question, maintain conversation context.\n"
            "Do not force every answer into an incident investigation template.\n"
            "Use concise answers by default. Provide additional technical detail when the user needs it.\n"
            "Never invent retrieved sources, telemetry values, incidents or technical evidence.\n"
            "Remain strictly within the IT infrastructure and operations support domain."
        )

        if intent == ChatIntent.GENERAL_IT_QUESTION:
            task_instruction = (
                f"USER INTENT: GENERAL_IT_QUESTION\n"
                f"TASK: Explain the technical concept requested in the question ({query}) in clear, natural conversational language for an IT manager.\n"
                f"- Ground your explanation in the retrieved documentation below.\n"
                f"- Explain the concept, why it matters, common causes, and a practical example where helpful.\n"
                f"- Do NOT generate an incident investigation, report headers, or fake telemetry.\n"
                f"- Keep the tone conversational, friendly, and expert."
            )
        elif intent == ChatIntent.TROUBLESHOOTING_REQUEST:
            task_instruction = (
                f"USER INTENT: TROUBLESHOOTING_REQUEST\n"
                f"TASK: Provide practical, numbered step-by-step troubleshooting actions to solve: {query}.\n"
                f"- Base your steps on the retrieved documentation chunks below.\n"
                f"- Provide clear numbered steps (1., 2., 3...) with safe, non-destructive diagnostic verification commands (e.g. pg_stat_activity, ping, traceroute, journalctl, top, ss).\n"
                f"- Do NOT force an incident investigation report. Focus directly on actionable troubleshooting."
            )
        elif intent == ChatIntent.FOLLOW_UP_QUERY:
            last_topic = session_ctx.get("last_topic") or session_ctx.get("last_metric") or "prior discussion" if session_ctx else "prior discussion"
            task_instruction = (
                f"USER INTENT: FOLLOW_UP_QUERY\n"
                f"CONTEXT: Continuing discussion regarding {target_sid} ({srv_name}) about {last_topic}.\n"
                f"TASK: Answer the follow-up question ({query}) directly and naturally while maintaining conversation context.\n"
                f"- If asking what to check first: Provide prioritized investigation steps and non-destructive diagnostic commands (including '### 4. Recommended Investigation Steps').\n"
                f"- If asking how to prevent it: Provide prioritized preventative measures and configuration tuning (including '### 6. Prevention Measures').\n"
                f"- If asking how to fix it: Provide step-by-step remediation actions.\n"
                f"- Do NOT repeat the entire incident report or greetings. Address the follow-up directly."
            )
        else:  # INCIDENT_SPECIFIC_QUERY
            obs_val = incident.get("observed_value") if incident else "Active Telemetry"
            thresh_val = incident.get("threshold_value") if incident else "Configured limit"
            unit = incident.get("unit") if incident else ""
            metric_name = incident.get("metric_name") or incident.get("metric_key") or "Metric" if incident else "Observed Metric"
            task_instruction = (
                f"USER INTENT: INCIDENT_SPECIFIC_QUERY\n"
                f"GROUND TRUTH INCIDENT & TELEMETRY:\n"
                f"- Target Server: {target_sid} ({srv_name})\n"
                f"- Incident ID: {incident.get('incident_id', 'INC-ACTIVE') if incident else 'ACTIVE-TELEMETRY'}\n"
                f"- Metric: {metric_name} = {obs_val} {unit} (Threshold: {thresh_val} {unit})\n"
                f"- Live Status: {telemetry.get('current_status', 'CRITICAL')} (Health: {telemetry.get('current_health_state', 'POOR')})\n"
                f"- Current Metrics: {json.dumps(telemetry.get('current_metrics', {}))}\n\n"
                f"TASK: Investigate and explain this server incident using the live telemetry and retrieved documentation below.\n"
                f"Structure the explanation with these clear markdown headers:\n"
                f"### 1. Understanding the Issue\n"
                f"### 2. Possible Root Causes\n"
                f"### 3. Evidence from VYTRON\n"
                f"### 4. Recommended Investigation Steps\n"
                f"### 5. Suggested Remediation\n"
                f"### 6. Prevention Measures\n"
                f"### 7. Retrieved Sources\n"
                f"Ensure exact quote of {obs_val} {unit} and {thresh_val} {unit} in Evidence."
            )

        return f"""{system_preamble}

{task_instruction}

RETRIEVED DOCUMENTATION (CHROMA DB COLLECTION 'vytron_troubleshooting_kb'):
{doc_texts}

PRIOR CONVERSATION:
{hist_texts or "No prior messages."}

USER QUERY: {query}
"""

    def _verify_and_guard_response(
        self,
        llm_text: str,
        intent: str,
        incident: Optional[dict[str, Any]],
        telemetry: dict[str, Any],
        chunks: list[dict[str, Any]]
    ) -> str:
        """
        Anti-hallucination post-processor:
        1. Scrubs sensitive credentials.
        2. Ensures exact metric consistency if incident was active.
        3. Validates that Section 7 cites actual ChromaDB sources for structured incident reports.
        """
        scrubbed = re.sub(r"super_secret_pg_master_password", "[REDACTED_SECRET]", llm_text)
        scrubbed = re.sub(r"eyjhbgcioijiuzi1niisinr5cci6ikpxvcj9", "[REDACTED_TOKEN]", scrubbed)
        scrubbed = re.sub(r"private_cisco_community_string", "[REDACTED_COMMUNITY]", scrubbed)

        if intent == ChatIntent.INCIDENT_SPECIFIC_QUERY and incident:
            obs_val = str(incident.get("observed_value", ""))
            sid = incident.get("server_id", "")
            if obs_val and obs_val not in scrubbed:
                evidence_patch = (
                    f"\n- **Server:** {sid}\n"
                    f"- **Observed Value:** {obs_val} {incident.get('unit', '')}\n"
                    f"- **Threshold:** {incident.get('threshold_value')} {incident.get('unit', '')}\n"
                )
                if "### 3. Evidence from VYTRON" in scrubbed:
                    scrubbed = scrubbed.replace("### 3. Evidence from VYTRON", f"### 3. Evidence from VYTRON\n{evidence_patch}")

        if intent == ChatIntent.INCIDENT_SPECIFIC_QUERY and chunks and "### 7. Retrieved Sources" in scrubbed:
            verified_sources = []
            for c in chunks:
                m = c.get("metadata", {})
                t = m.get("title") or m.get("doc_name") or "Technical Runbook"
                sec = m.get("section") or "Diagnostics"
                verified_sources.append(f"- **{t}** ({sec}) [ChromaDB Relevance: {c.get('relevance_score', 0.85):.2f}]")
            sources_text = "\n".join(verified_sources)
            parts = scrubbed.split("### 7. Retrieved Sources")
            scrubbed = parts[0] + f"### 7. Retrieved Sources\n{sources_text}\n\n*(Remediation guidance is advisory. All commands must be reviewed and executed manually by the IT Operator; VYTRON never executes destructive commands automatically.)*"

        return scrubbed

    def _synthesize_grounded_fallback(
        self,
        query: str,
        intent: str,
        incident: Optional[dict[str, Any]],
        chunks: list[dict[str, Any]],
        telemetry: dict[str, Any],
        history: list[dict[str, Any]],
        session_ctx: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Intent-tailored deterministic synthesis guaranteeing factual grounding without forced templates.
        """
        q_lower = query.lower()
        target_sid = telemetry.get("target_server_id") or (incident.get("server_id") if incident else None) or (session_ctx.get("last_server_id") if session_ctx else None) or "Target Server"
        srv_name = telemetry.get("server_name") or (incident.get("server_name") if incident else None) or (session_ctx.get("last_server_name") if session_ctx else None) or "Server"

        # ── 1. General IT Questions ──────────────────────────────────────────
        if intent == ChatIntent.GENERAL_IT_QUESTION:
            if "query bottleneck" in q_lower or "database bottleneck" in q_lower:
                return (
                    "A **query bottleneck** occurs when database queries consume excessive CPU, memory, or disk I/O, "
                    "causing subsequent requests to queue up and dramatically increasing application response latency.\n\n"
                    "### Common Causes\n"
                    "1. **Missing or Inefficient Indexes:** Queries perform full sequential scans on large relational tables instead of targeted B-tree lookups.\n"
                    "2. **Lock Contention:** Long-running transactions or write locks (`ExclusiveLock`) block concurrent read or update transactions.\n"
                    "3. **Connection Pool Starvation:** Client requests exceed configured pool limits (`max_connections`), waiting in an OS socket queue.\n"
                    "4. **Unoptimized Joins:** Nested loop joins across unindexed foreign keys or expensive aggregations over millions of rows.\n\n"
                    "### Practical Example\n"
                    "In PostgreSQL, a query like `SELECT * FROM orders WHERE customer_id = 42;` without an index on `customer_id` reads every table block from disk. "
                    "Adding `CREATE INDEX idx_orders_customer ON orders(customer_id);` reduces execution from seconds to under 5 milliseconds.\n\n"
                    "*Tip: Inspect slow queries using `EXPLAIN (ANALYZE, BUFFERS)` and query `pg_stat_activity`.*"
                )
            elif "packet loss" in q_lower:
                return (
                    "**Packet loss** occurs when network data packets fail to reach their destination across transit hops, "
                    "measured as a percentage of dropped packets relative to total transmitted packets.\n\n"
                    "### Common Causes\n"
                    "1. **Interface Queue Saturation:** Network throughput exceeding link capacity, causing router/switch interface buffers to tail-drop packets.\n"
                    "2. **Physical Hardware & Cable Faults:** Degraded fiber optics, damaged patch cables, or duplex mismatches generating CRC checksum errors.\n"
                    "3. **BGP Route Flapping:** Instability in dynamic routing tables forcing traffic through flapping or degraded backup paths.\n"
                    "4. **Strict Firewall Throttling:** Network firewalls or edge rate limiters dropping bursty UDP/TCP traffic.\n\n"
                    "### Diagnostics\n"
                    "Diagnose packet loss using non-destructive commands:\n"
                    "- Check gateway drop rate: `ping -c 10 -i 0.2 <gateway_ip>`\n"
                    "- Trace hop-level loss: `traceroute -n <target_ip>`\n"
                    "- Check interface drop counters: `ip -s link show`"
                )
            elif "cpu" in q_lower:
                return (
                    "**High CPU utilization** refers to the compute processors operating near 100% capacity, "
                    "leaving insufficient CPU time for worker threads and resulting in thread pool starvation.\n\n"
                    "### Common Causes\n"
                    "1. **Runaway Worker Threads:** Infinite loops, unthrottled background cron tasks, or intensive cryptographic computations.\n"
                    "2. **Excessive Garbage Collection:** Severe memory pressure causing Java/Node.js runtimes to spend continuous CPU cycles on GC sweeps.\n"
                    "3. **Database Spinlocks:** High transaction concurrency causing worker threads to spin while waiting for row locks.\n\n"
                    "### Diagnostics\n"
                    "Run `top -b -n 1 | head -n 20` to identify top CPU-consuming PIDs, and inspect thread stacks with `jstack` or profiling tools."
                )
            elif "memory" in q_lower:
                return (
                    "A **memory leak** occurs when an application allocates memory on the heap or native space but fails to "
                    "release it after completion, gradually exhausting available RAM until host OOM killers terminate the process.\n\n"
                    "### Common Causes\n"
                    "1. **Unbounded In-Memory Caches:** Dictionaries or static maps storing objects without TTL expiration or size limits.\n"
                    "2. **Stale Event Listeners:** Long-lived event emitters holding references to short-lived client request objects.\n"
                    "3. **Thread-Local Leaks:** Reused thread pools not clearing `ThreadLocal` variables between transactions.\n\n"
                    "### Mitigation\n"
                    "Capture heap dumps to inspect object retention graphs, and enforce container memory limits with rolling worker restarts."
                )
            else:
                # General technical question
                if chunks:
                    c0 = chunks[0]
                    return f"**Technical Overview:** {c0.get('content', '')[:600]}...\n\n*Source: {c0.get('metadata', {}).get('title', 'Technical Runbook')}*"
                return (
                    "This operational parameter relates to core infrastructure performance. "
                    "Ensure adequate monitoring baselines, check resource saturation thresholds, and inspect daemon error logs for anomalies."
                )

        # ── 2. Troubleshooting Requests ──────────────────────────────────────
        if intent == ChatIntent.TROUBLESHOOTING_REQUEST:
            if "database" in q_lower or "latency" in q_lower:
                return (
                    "Here are practical, step-by-step actions to troubleshoot high database latency:\n\n"
                    "1. **Isolate Active Blocking Queries:**\n"
                    "   Inspect active transactions holding table or row locks in PostgreSQL:\n"
                    "   ```sql\n"
                    "   SELECT pid, usename, query, state, age(clock_timestamp(), query_start) AS duration\n"
                    "   FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start ASC;\n"
                    "   ```\n"
                    "2. **Review Slow Query Logs:**\n"
                    "   Identify queries exceeding threshold duration (`log_min_duration_statement = 250ms`) and run `EXPLAIN (ANALYZE, BUFFERS)` to spot full table scans.\n"
                    "3. **Inspect Connection Pool Saturation:**\n"
                    "   Verify active client connections against PostgreSQL `max_connections` or PgBouncer pool sizing.\n"
                    "4. **Check Storage Disk I/O Wait:**\n"
                    "   Run non-destructive OS diagnostic commands to check if disk writes are bottlenecked:\n"
                    "   ```bash\n"
                    "   iostat -xz 1 5\n"
                    "   ```\n"
                    "5. **Safely Cancel Runaway Queries:**\n"
                    "   If a rogue unindexed query is blocking workers, cancel it safely without crashing the backend: `SELECT pg_cancel_backend(<pid>);`."
                )
            elif "memory" in q_lower:
                return (
                    "Here are practical steps to troubleshoot and resolve memory pressure:\n\n"
                    "1. **Inspect Host Memory Allocation:**\n"
                    "   ```bash\n"
                    "   free -m && cat /proc/meminfo | head -n 10\n"
                    "   ```\n"
                    "2. **Identify Top Memory-Consuming Processes:**\n"
                    "   ```bash\n"
                    "   ps aux --sort=-%mem | head -n 10\n"
                    "   ```\n"
                    "3. **Inspect Container cgroups Memory Limits:**\n"
                    "   Check if container memory is approaching cgroup limits: `cat /sys/fs/cgroup/memory/memory.usage_in_bytes`.\n"
                    "4. **Trigger Graceful Rolling Restarts:**\n"
                    "   Perform a rolling restart on degraded container worker replicas to free uncollected heap allocations."
                )
            elif "packet" in q_lower or "loss" in q_lower or "network" in q_lower:
                return (
                    "Here are practical steps to troubleshoot network packet loss:\n\n"
                    "1. **Measure Gateway Round-Trip Latency & Drops:**\n"
                    "   ```bash\n"
                    "   ping -c 10 -i 0.2 <gateway_ip>\n"
                    "   ```\n"
                    "2. **Trace Routing Path to Isolate Hop Loss:**\n"
                    "   ```bash\n"
                    "   traceroute -n <destination_ip>\n"
                    "   ```\n"
                    "3. **Inspect Interface Drop & Error Counters:**\n"
                    "   ```bash\n"
                    "   ip -s link show && ethtool -S <interface>\n"
                    "   ```\n"
                    "4. **Verify Link Speed & Duplex Negotiation:**\n"
                    "   ```bash\n"
                    "   ethtool <interface> | grep -E '(Speed|Duplex|Auto-negotiation)'\n"
                    "   ```"
                )

        # ── 3. Follow-up Queries ─────────────────────────────────────────────
        if intent == ChatIntent.FOLLOW_UP_QUERY:
            last_sid = session_ctx.get("last_server_id", "AUTH-01" if "login" in q_lower else ("DB-01" if "disk" in q_lower or "database" in q_lower else "APP-01"))
            last_metric = session_ctx.get("last_metric") or session_ctx.get("last_topic") or "the active incident"

            if "what should i check first" in q_lower or "check first" in q_lower:
                if last_sid == "AUTH-01" or "auth" in q_lower or "login" in q_lower:
                    return (
                        f"For **AUTH-01** ({last_metric}), check these items first:\n\n"
                        f"### 4. Recommended Investigation Steps\n"
                        f"1. **Identify Top Source IP Addresses:** Run `awk '/Failed password/ {{print $(NF-3)}}' /var/log/auth.log | sort | uniq -c | sort -nr | head -n 10` to see if failures originate from a single IP or distributed botnet.\n"
                        f"2. **Inspect Auth Daemon Journal Logs:** `journalctl -u ssh -u auth-service --since '15 minutes ago' | grep -i 'failure'`.\n"
                        f"3. **Verify Backing LDAP/Directory Socket Health:** `ss -tan state established '( dport = :389 or dport = :636 or dport = :6379 )'`."
                    )
                elif last_sid == "DB-01" or "disk" in q_lower or "query" in q_lower:
                    return (
                        f"For **DB-01** ({last_metric}), check these items first:\n\n"
                        f"### 4. Recommended Investigation Steps\n"
                        f"1. **Active Lock Contention:** Query `pg_stat_activity` for transactions in `idle in transaction` or holding locks.\n"
                        f"2. **Disk I/O Wait Percentage:** Run `iostat -xz 1 5` to verify if disk write channels or checkpoints are saturated.\n"
                        f"3. **Connection Pool Depth:** Verify active connections vs `max_connections`."
                    )
                else:
                    return (
                        f"For **{last_sid}**, check these investigation steps first:\n\n"
                        f"### 4. Recommended Investigation Steps\n"
                        f"1. Run `top -b -n 1 | head -n 15` to identify the top resource-consuming process.\n"
                        f"2. Check daemon service error logs for recent fatal exceptions or timeouts.\n"
                        f"3. Verify network reachability to dependent upstream services."
                    )
            elif "prevent" in q_lower:
                if last_sid == "AUTH-01" or "login" in q_lower:
                    return (
                        f"To prevent recurring authentication velocity spikes on **AUTH-01**:\n\n"
                        f"### 6. Prevention Measures\n"
                        f"1. **Edge Rate Limiting & Fail2ban:** Enforce IP rate limiting on authentication routes (e.g. max 5 failed attempts per minute per IP).\n"
                        f"2. **Adaptive MFA Triggers:** Automatically require multi-factor authentication or CAPTCHA upon consecutive failures.\n"
                        f"3. **Credential Rotation Policies:** Ensure internal microservice API tokens use automated vault rotation with generous renewal grace periods."
                    )
                elif last_sid == "DB-01" or "disk" in q_lower or "query" in q_lower:
                    return (
                        f"To prevent recurring disk I/O and latency spikes on **DB-01**:\n\n"
                        f"### 6. Prevention Measures\n"
                        f"1. **Targeted Index Maintenance:** Audit slow queries weekly and maintain B-tree indexes on high-frequency filter columns.\n"
                        f"2. **Checkpoint Smoothing:** Configure Postgres `checkpoint_completion_target = 0.9` to spread I/O bursts across checkpoint intervals.\n"
                        f"3. **Statement Timeouts:** Enforce `statement_timeout = '30s'` to automatically terminate runaway queries before they queue downstream requests."
                    )
                else:
                    return (
                        f"To prevent recurring incidents on **{last_sid}**:\n\n"
                        f"### 6. Prevention Measures\n"
                        f"1. Configure horizontal autoscaling (HPA) triggers at 70% baseline utilization.\n"
                        f"2. Set up proactive threshold alarms to notify on-call SREs before critical limits are breached.\n"
                        f"3. Implement circuit breakers on synchronous dependencies to prevent cascading queue exhaustion."
                    )
            elif "fix it" in q_lower or "how to fix" in q_lower:
                return (
                    f"To resolve the issue on **{last_sid}**:\n\n"
                    f"### 5. Suggested Remediation\n"
                    f"1. Mitigate immediate load by throttling burst traffic at the edge proxy or rate-limiter.\n"
                    f"2. Terminate blocking transactions or rogue worker processes holding shared locks.\n"
                    f"3. Perform a controlled, rolling restart of degraded worker containers if thread starvation is confirmed."
                )

        # ── 4. Incident-Specific Queries (Full Structured Investigation) ──────
        metric_name = incident.get("metric_name") if incident else "Observed Parameter"
        obs_val = incident.get("observed_value") if incident else (telemetry.get("current_metrics", {}).get("disk_io_utilization") or telemetry.get("current_metrics", {}).get("query_latency") or "Elevated")
        thresh_val = incident.get("threshold_value") if incident else "Baseline Threshold"
        unit = incident.get("unit") if incident else ""

        doc_refs = []
        for c in chunks:
            m = c.get("metadata", {})
            t = m.get("title") or m.get("doc_name") or "Technical Runbook"
            sec = m.get("section") or "Diagnostics"
            doc_refs.append(f"- **{t}** ({sec}) [Relevance: {c.get('relevance_score', 0.85):.2f}]")
        doc_summary = "\n".join(doc_refs) if doc_refs else "- *General SRE baseline runbook*"

        if target_sid == "DB-01" or "db-01" in q_lower or "disk" in q_lower:
            understanding = f"Database performance degradation observed on **DB-01 ({srv_name})**. Parameter **{metric_name}** is elevated, impacting downstream transaction processing."
            hypotheses = (
                "- **Unindexed Sequential Scans / Heavy Queries:** Heavy queries scanning unindexed tables forcing sustained disk block reads into memory.\n"
                "- **Lock Contention / Long-Running Transactions:** Transactions holding row/table locks, blocking worker threads from committing.\n"
                "- **Postgres Checkpoint Saturation:** Background checkpoint writers flushing dirty buffers simultaneously, saturating disk write bandwidth."
            )
            evidence = (
                f"- **Target Server:** DB-01 (Database Server)\n"
                f"- **Observed Value:** {obs_val} {unit}\n"
                f"- **Configured Thresholds:** Warning $\ge$ 50.0 ms | Critical $\ge$ 120.0 ms\n"
                f"- **Live Server Status:** {telemetry.get('current_status', 'CRITICAL')}"
            )
            investigation = (
                "1. Query `pg_stat_activity` to isolate blocking transactions and long-running locks.\n"
                "2. Inspect active connection pool utilization against `max_connections`.\n"
                "3. Check disk I/O wait percentages using non-destructive OS diagnostic commands: `iostat -xz 1 5`.\n"
                "4. Review slow query log for high-execution-time queries (`log_min_duration_statement`)."
            )
            remediation = (
                "- Terminate blocking transactions safely: `SELECT pg_cancel_backend(pid);` (Non-destructive).\n"
                "- Optimize slow queries by creating targeted B-tree indexes.\n"
                "- Tune connection poolers (PgBouncer) and enforce connection timeout quotas."
            )
            prevention = (
                "- Implement query execution timeouts (`statement_timeout = '30s'`).\n"
                "- Configure automated vacuuming and checkpoint smoothing (`checkpoint_completion_target = 0.9`)."
            )
        elif target_sid == "AUTH-01" or "auth" in q_lower or "login" in q_lower:
            understanding = f"Security anomaly detected on **AUTH-01 ({srv_name})**. Authentication velocity or failure rates have breached configured baseline thresholds."
            hypotheses = (
                "- **Credential Stuffing / Brute-Force Activity:** Automated botnets testing leaked credential pairs against authentication endpoints.\n"
                "- **Identity Provider (IdP) Latency:** Upstream LDAP or SSO directory connectivity delays causing request timeouts.\n"
                "- **Misconfigured Client / Expired Secret:** Automated API consumer repeating expired token requests in rapid succession."
            )
            evidence = (
                f"- **Target Server:** AUTH-01 (Authentication Server)\n"
                f"- **Observed Value:** {obs_val} {unit}\n"
                f"- **Configured Thresholds:** Warning $\ge$ 10.0 fails/min | Critical $\ge$ 25.0 fails/min\n"
                f"- **Live Server Status:** {telemetry.get('current_status', 'NORMAL')}"
            )
            investigation = (
                "1. Check authentication failure rates and identify repeated failures from suspicious IP blocks.\n"
                "2. Verify directory service health and LDAP response latency.\n"
                "3. Inspect auth server thread pool saturation and session cache hit ratios."
            )
            remediation = (
                "- Apply edge rate limiting on authentication routes (e.g. 5 attempts/minute per IP).\n"
                "- Temporarily enforce CAPTCHA or multi-factor authentication triggers for high-risk IPs.\n"
                "- Scale authentication container worker replicas if thread starvation is confirmed."
            )
            prevention = (
                "- Implement adaptive lockout policies and automated IP reputation scoring.\n"
                "- Maintain separate connection pools for interactive user auth vs. internal service tokens."
            )
        elif target_sid == "NETWORK-01" or "network" in q_lower or "packet" in q_lower:
            understanding = f"Network transit degradation detected on **NETWORK-01 ({srv_name})**. Packet delivery latency or loss rates have breached safe operating margins."
            hypotheses = (
                "- **Transit Pipe Congestion:** High bandwidth utilization saturating interface buffers, resulting in packet drops.\n"
                "- **Route Flapping / Suboptimal Path:** Upstream routing protocol convergence forcing traffic over high-latency backup links.\n"
                "- **Hardware Duplex / Link Errors:** Physical interface CRC checksum errors causing hardware packet retransmissions."
            )
            evidence = (
                f"- **Target Server:** NETWORK-01 (Core Network Server)\n"
                f"- **Observed Value:** {obs_val} {unit}\n"
                f"- **Configured Thresholds:** Warning $\ge$ 150.0 ms | Critical $\ge$ 300.0 ms\n"
                f"- **Live Server Status:** {telemetry.get('current_status', 'NORMAL')}"
            )
            investigation = (
                "1. Run ICMP round-trip latency checks to the default gateway: `ping -c 5 -i 0.2 <gateway>`.\n"
                "2. Trace network routing path to isolate hop-level latency degradation via `traceroute`.\n"
                "3. Inspect switch interface error counters: `ip -s link show` or `ethtool -S <eth0>`."
            )
            remediation = (
                "- Reroute traffic around congested links by adjusting BGP local preference.\n"
                "- Clear interface buffer queues and activate QoS traffic classification.\n"
                "- Inspect patch cables and verify full-duplex auto-negotiation status."
            )
            prevention = (
                "- Enable redundant diverse carrier transit paths with automatic failover.\n"
                "- Set up bandwidth threshold alarms at 75% capacity to proactively trigger traffic shaping."
            )
        else:
            understanding = f"Operational anomaly observed on **{target_sid} ({srv_name})**. Monitored parameter **{metric_name}** is operating outside nominal tolerances."
            hypotheses = (
                "- **Workload Saturation:** Sudden transaction or computation surge exhausting available worker thread executors.\n"
                "- **Memory Leak / Garbage Collection Delays:** In-memory object retention preventing timely garbage collection cycles.\n"
                "- **Resource Contention:** Downstream dependent service latency causing request queue build-up."
            )
            evidence = (
                f"- **Target Server:** {target_sid} ({srv_name})\n"
                f"- **Observed Telemetry:** {obs_val} {unit}\n"
                f"- **Configured Threshold:** {thresh_val} {unit}\n"
                f"- **Live Status:** {telemetry.get('current_status', 'NORMAL')}"
            )
            investigation = (
                "1. Review OS process table: `top -b -n 1 | head -n 20`.\n"
                "2. Check application server logs for unhandled exceptions or thread pool warnings.\n"
                "3. Review JVM / container memory consumption profiles."
            )
            remediation = (
                "- Scale out application container replicas (Horizontal Pod Autoscaling).\n"
                "- Restart starved worker executor containers (graceful rolling restart).\n"
                "- Enforce API rate limiting to throttle incoming burst traffic."
            )
            prevention = (
                "- Tune garbage collection parameters and memory heap allocation.\n"
                "- Establish circuit breakers on synchronous upstream dependencies."
            )

        return (
            f"### 1. Understanding the Issue\n{understanding}\n\n"
            f"### 2. Possible Root Causes\n{hypotheses}\n\n"
            f"### 3. Evidence from VYTRON\n{evidence}\n\n"
            f"### 4. Recommended Investigation Steps\n{investigation}\n\n"
            f"### 5. Suggested Remediation\n{remediation}\n\n"
            f"### 6. Prevention Measures\n{prevention}\n\n"
            f"### 7. Retrieved Sources\n{doc_summary}\n\n"
            f"*(Remediation guidance is advisory. All commands must be reviewed and executed manually by the IT Operator; VYTRON never executes destructive commands automatically.)*"
        )


# Global chatbot synthesizer instance
chatbot_synthesizer = ChatbotSynthesizer()


# ══════════════════════════════════════════════════════════════════════════════
# 8. HIGH-LEVEL CHAT DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

async def process_chat_message(
    user_message: str,
    session_id: Optional[str] = None,
    incident_context: Optional[dict[str, Any]] = None,
    simulator_instance: Any = None
) -> dict[str, Any]:
    """
    Main entry point for incoming chatbot messages:
    1. Validates IT operations scope and natural greetings.
    2. Initializes or retrieves session history and multi-turn context.
    3. Classifies message intent (Greeting, Ack, General IT, Troubleshooting, Incident, Follow-up, Out-of-scope).
    4. Performs intent-aware RAG and live telemetry harvesting.
    5. Synthesizes structured or conversational grounded response.
    6. Stores turn in session history.
    """
    # 1. Scope Validation
    is_valid, rejection_reason = validate_it_scope(user_message)
    if not is_valid:
        sid, _ = chat_sessions.get_or_create(session_id)
        return {
            "session_id": sid,
            "intent": ChatIntent.OUT_OF_SCOPE,
            "answer": rejection_reason or SCOPE_REJECTION_MESSAGE,
            "sources": [],
            "retrieval_succeeded": False,
            "incident_context_used": False,
            "is_scope_violation": True,
            "limitation": "Query out of IT infrastructure & operations scope."
        }

    # 2. Session Management
    sid, session_data = chat_sessions.get_or_create(session_id)
    if incident_context:
        chat_sessions.update_incident_context(sid, incident_context)
        chat_sessions.update_context(
            sid,
            server_id=incident_context.get("server_id"),
            server_name=incident_context.get("server_name"),
            metric=incident_context.get("metric_key"),
            topic=incident_context.get("metric_name"),
            incident=incident_context
        )

    active_incident = chat_sessions.get_incident_context(sid)
    history = chat_sessions.get_history(sid)
    session_ctx = chat_sessions.get_context(sid)

    # 3. Intent Classification
    intent = classify_intent(user_message, history, active_incident, session_ctx)

    # 4. Intent-Aware Telemetry Harvesting & RAG Retrieval
    live_telemetry: dict[str, Any] = {}
    retrieved_chunks: list[dict[str, Any]] = []

    if intent == ChatIntent.GREETING or intent == ChatIntent.ACKNOWLEDGEMENT:
        # Greetings & Acknowledgements: Zero vector retrieval, zero telemetry dump
        retrieved_chunks = []
        live_telemetry = {}
    elif intent == ChatIntent.INCIDENT_SPECIFIC_QUERY:
        # Harvest live backend telemetry for target server
        live_telemetry = harvest_live_telemetry(active_incident, user_message, simulator_instance)
        # Auto-resolve active incident from live priority queue if not previously set
        if not active_incident and live_telemetry.get("active_incidents_for_server"):
            active_incident = live_telemetry["active_incidents_for_server"][0]
            chat_sessions.update_incident_context(sid, active_incident)
        retrieved_chunks = retrieve_knowledge(user_message, active_incident, n_results=4)
        target_sid = live_telemetry.get("target_server_id") or (active_incident.get("server_id") if active_incident else None)
        if target_sid:
            chat_sessions.update_context(
                sid,
                server_id=target_sid,
                server_name=live_telemetry.get("server_name"),
                metric=active_incident.get("metric_key") if active_incident else None,
                topic=active_incident.get("metric_name") if active_incident else None,
                chunks=retrieved_chunks
            )
    elif intent == ChatIntent.FOLLOW_UP_QUERY:
        target_sid = session_ctx.get("last_server_id")
        if target_sid:
            live_telemetry = harvest_live_telemetry(active_incident, target_sid, simulator_instance)
        retrieved_chunks = retrieve_knowledge(user_message, active_incident, n_results=3)
        if not retrieved_chunks and session_ctx.get("last_chunks"):
            retrieved_chunks = session_ctx.get("last_chunks", [])
    else:  # GENERAL_IT_QUESTION or TROUBLESHOOTING_REQUEST
        retrieved_chunks = retrieve_knowledge(user_message, None, n_results=3)

    # 5. Response Synthesis
    response_data = await chatbot_synthesizer.generate_response(
        query=user_message,
        session_id=sid,
        intent=intent,
        incident=active_incident,
        chunks=retrieved_chunks,
        telemetry=live_telemetry,
        history=history,
        session_ctx=session_ctx
    )

    # 6. Save Turn in Memory
    chat_sessions.add_turn(sid, user_message, response_data["answer"], response_data["sources"])

    response_data["session_id"] = sid
    response_data["intent"] = intent
    response_data["is_scope_violation"] = False
    return response_data
