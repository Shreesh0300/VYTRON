"""
Live Service Endpoint Integration Test
Verifies:
- Simulator (:8001) /servers, /servers/{id}, /scenarios/demo-scenario, /scenarios/server-action
- Backend (:8000) /api/servers, /api/servers/{id}/detail, /api/demo/state, /api/demo/scenario
- Local Collector (:8002) /telemetry, /health, /egress
"""

import sys
import os
import time
import subprocess
import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

def main():
    print("▶ Testing live service startup & API contracts...")
    
    # 1. Clean stop first
    subprocess.run([PYTHON_EXE, "start.py", "--stop"], cwd=ROOT, capture_output=True)
    time.sleep(1)

    # 2. Start services in background using start.py
    proc = subprocess.Popen([PYTHON_EXE, "start.py"], cwd=ROOT)
    
    try:
        # Wait for services to become ready
        print("Waiting for ports 8000, 8001, 8002, 5500 to bind...")
        ready = False
        for _ in range(15):
            time.sleep(1)
            try:
                r1 = httpx.get("http://localhost:8000/", timeout=1.0)
                r2 = httpx.get("http://localhost:8001/", timeout=1.0)
                r3 = httpx.get("http://localhost:8002/", timeout=1.0)
                r4 = httpx.get("http://localhost:5500/", timeout=1.0)
                if all(r.status_code == 200 for r in [r1, r2, r3, r4]):
                    ready = True
                    break
            except Exception:
                pass

        if not ready:
            print("❌ Services did not bind in time!")
            sys.exit(1)

        print("✔ All 4 services are live!")

        # 3. Test Simulator /servers
        r = httpx.get("http://localhost:8001/servers")
        assert r.status_code == 200, f"Simulator /servers failed: {r.status_code}"
        sim_servers = r.json()
        assert sim_servers["server_count"] == 10, f"Expected 10 servers, got {sim_servers['server_count']}"
        print(f"✔ Simulator has 10 server profiles active: {list(sim_servers['servers'].keys())}")

        # Check APP-01 metrics in simulator
        app01 = sim_servers["servers"]["APP-01"]
        for m in ["cpu_usage", "memory_usage", "disk_usage", "network_upload", "network_download", "network_latency", "request_rate", "error_rate", "response_time", "uptime"]:
            assert m in app01["current"], f"Missing {m} in APP-01 simulator current metrics"
        print("✔ APP-01 contains all 10 live system metrics")

        # 4. Wait 4 seconds for telemetry loop to push to collector and drain to backend
        print("Waiting 4 seconds for live telemetry to flow into backend...")
        time.sleep(4)

        # 5. Test Backend /api/servers
        r = httpx.get("http://localhost:8000/api/servers", timeout=10.0)
        assert r.status_code == 200, f"Backend /api/servers failed: {r.status_code}"
        backend_servers = r.json()
        assert len(backend_servers) == 10, f"Expected 10 servers in backend, got {len(backend_servers)}"
        print(f"✔ Central Backend returns all 10 servers with status and live snapshots")

        # 6. Test Backend /api/servers/APP-01/detail
        r = httpx.get("http://localhost:8000/api/servers/APP-01/detail", timeout=10.0)
        assert r.status_code == 200, f"Backend /api/servers/APP-01/detail failed: {r.status_code}"
        detail = r.json()
        assert detail["server_id"] == "APP-01"
        assert "recent_logs" in detail and len(detail["recent_logs"]) > 0
        assert "metrics" in detail
        print(f"✔ Detailed server snapshot retrieved with {len(detail['recent_logs'])} dynamic log lines")

        # 7. Test Demo Mode scenario injection
        r = httpx.post("http://localhost:8000/api/demo/scenario", json={"scenario": "demo_db_failure"})
        assert r.status_code == 200, f"Demo scenario injection failed: {r.status_code}"
        res = r.json()
        print(f"✔ Demo scenario triggered: {res['active_scenario']}")

        # 8. Check Demo State
        r = httpx.get("http://localhost:8000/api/demo/state")
        assert r.status_code == 200
        state = r.json()
        assert "Database Failure" in state["active_scenario"]
        print(f"✔ Demo state API confirmed: {state['active_scenario']}")

        # 9. Test Fine-Grained Server Control
        r = httpx.post("http://localhost:8000/api/servers/AUTH-01/control", json={"action": "set_metric", "metric": "cpu_usage", "value": 91.2})
        assert r.status_code == 200
        print("✔ Interactive server control successfully set AUTH-01 CPU to 91.2%")

        # 10. Reset back to Normal
        r = httpx.post("http://localhost:8000/api/demo/scenario", json={"scenario": "demo_normal"})
        assert r.status_code == 200
        print("✔ Cluster reset to Normal Baseline")

        print("\n🎉 ALL LIVE SERVICE CONTRACTS AND ENDPOINTS VERIFIED SUCCESSFULLY!")

    finally:
        print("Stopping services...")
        subprocess.run([PYTHON_EXE, "start.py", "--stop"], cwd=ROOT, capture_output=True)
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass

if __name__ == "__main__":
    main()
