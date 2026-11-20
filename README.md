# CICADA AIOps — Secure AI-Powered Observability Platform

> **CICADA 2026 Hackathon** | 24-Hour Prototype
> Privacy-first, two-tier AIOps with hybrid anomaly detection

---

## 🏗️ Architecture

```
┌─────────────────────────── TIER 1: Customer Environment ───────────────────────────┐
│                                                                                     │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────────────┐  │
│  │  Simulator    │────▶│  Local Collector (:8002)                                │  │
│  │  (:8001)      │     │  Ingest → Normalize → Privacy Filter → Anomaly Detect  │  │
│  │  10 servers   │     │  → Egress Proof → Queue → Transmit                     │  │
│  └──────────────┘     └──────────────────────┬───────────────────────────────────┘  │
│                                               │ collector.db                        │
└───────────────────────────────────────────────┼─────────────────────────────────────┘
                            Only approved       │
                            metadata crosses    │  API-key auth
                            the trust boundary  ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│  TIER 2: Central Platform (:8000)                                                     │
│  Ingest → Rules Engine → Statistical Engine → Correlation → LLM Analysis             │
│  → Recommendations → Dashboard APIs                                platform.db       │
└──────────────────────────────────────────────────┬────────────────────────────────────┘
                                                   │
                                                   ▼
                                     ┌──────────────────────┐
                                     │  Dashboard (:5500)    │
                                     │  HTML/CSS/Vanilla JS  │
                                     └──────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- pip

### Setup

```bash
# 1. Clone and enter project
cd cicada-aiops

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (optional — defaults work)
copy .env.example .env

# 4. Start all services
python start.py
```

### Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Dashboard | http://localhost:5500 | Web UI |
| Backend API | http://localhost:8000/docs | API docs (Swagger) |
| Simulator | http://localhost:8001/docs | Simulator controls |
| Collector | http://localhost:8002/docs | Collector status |

### Stop All Services

```bash
python start.py --stop
# or Ctrl+C in the terminal running start.py
```

## 📁 Project Structure

```
cicada-aiops/
├── simulator/          # Infrastructure Simulator (10 logical servers)
├── collector/          # Local Collector (Tier 1 — privacy boundary)
├── backend/            # Central Platform (Tier 2 — AIOps engine)
├── frontend/           # Dashboard (HTML/CSS/JS)
├── shared/             # Shared Pydantic schemas and constants
├── start.py            # Multi-process launcher
├── requirements.txt    # Python dependencies
└── .env.example        # Environment variable template
```

## 🔒 Privacy & Security

- **Allow-list enforcement**: Only explicitly approved fields leave Tier 1
- **Secret detection**: Regex patterns catch passwords, API keys, tokens
- **Egress Proof**: Exact serialized JSON of every outgoing payload is recorded
- **API-key auth**: Collector-to-backend communication is authenticated
- **Tenant isolation**: All queries scoped by tenant_id

## 🤖 Hybrid AIOps Engine

1. **Rule-Based Detection**: Configurable thresholds (CPU > 80% → warning, > 90% → critical)
2. **Statistical Detection**: NumPy rolling mean/std, z-score deviation (> 2.0 → warning, > 3.0 → critical)
3. **Event Correlation**: Groups related alerts by source, time proximity, service dependencies
4. **LLM Analysis**: Ollama/hosted API generates evidence-grounded explanations (graceful fallback)
5. **Recommendations**: Actionable steps with approval workflow and simulated remediation

## 🧪 Demo Scenarios

Inject scenarios manually via the Simulator API:

```bash
# CPU spike on APP-01
curl -X POST http://localhost:8001/scenarios/inject -H "Content-Type: application/json" -d '{"scenario":"cpu_spike","server_id":"APP-01"}'

# Database failure
curl -X POST http://localhost:8001/scenarios/inject -H "Content-Type: application/json" -d '{"scenario":"database_failure","server_id":"DB-01"}'

# Sensitive data injection (test privacy filter)
curl -X POST http://localhost:8001/scenarios/inject -H "Content-Type: application/json" -d '{"scenario":"sensitive_data","server_id":"APP-01"}'

# Recovery
curl -X POST http://localhost:8001/scenarios/inject -H "Content-Type: application/json" -d '{"scenario":"recovery","server_id":"APP-01"}'
```

## 📊 Performance Targets

| Metric | Target |
|--------|--------|
| Collection-to-dashboard latency | ≤ 10 seconds (p95) |
| Threshold breach-to-alert | ≤ 15 seconds |
| Collector offline detection | Within 60 seconds |
| Buffered data recovery | No loss, no duplicates |

## 👥 Team

Built for CICADA 2026 | TechForcz × Atria Institute of Technology

## 📄 License

Hackathon prototype — not for production use.
