"""
VYTRON AIOps — Multi-Process Launcher
Starts all four services as separate processes on one machine.

Usage:
    python start.py          # Start all services
    python start.py --stop   # Stop all services
"""

import subprocess
import sys
import os
import signal
import time
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {
        "name": "Central Backend",
        "module": "backend.main:app",
        "port": 8000,
        "color": "\033[94m",  # Blue
    },
    {
        "name": "Simulator",
        "module": "simulator.main:app",
        "port": 8001,
        "color": "\033[92m",  # Green
    },
    {
        "name": "Local Collector",
        "module": "collector.main:app",
        "port": 8002,
        "color": "\033[93m",  # Yellow
    },
]

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"


def start_services():
    """Launch all services as subprocesses."""
    # Ensure any lingering processes on ports 8000, 8001, 8002, 5500 are stopped first
    stop_services()

    processes = []
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT

    print(f"\n{BOLD}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║    VYTRON — Autonomous Observability Platform    ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════╝{RESET}\n")

    logs_dir = os.path.join(ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Start backend, then simulator, then collector
    for svc in SERVICES:
        cmd = [
            sys.executable, "-m", "uvicorn",
            svc["module"],
            "--host", "0.0.0.0",
            "--port", str(svc["port"]),
            "--log-level", "info",
        ]
        log_file_path = os.path.join(logs_dir, f"{svc['name'].lower().replace(' ', '_')}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")
        print(f"{svc['color']}▶ Starting {svc['name']} on port {svc['port']} (logs: logs/{os.path.basename(log_file_path)})...{RESET}")
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        processes.append((svc, proc))
        time.sleep(1)  # Stagger starts

    # Start frontend static server
    frontend_dir = os.path.join(ROOT, "frontend")
    frontend_cmd = [
        sys.executable, "-m", "http.server", "5500",
        "--directory", frontend_dir,
        "--bind", "0.0.0.0",
    ]
    fe_log_path = os.path.join(logs_dir, "frontend.log")
    fe_log = open(fe_log_path, "a", encoding="utf-8")
    print(f"\033[95m▶ Starting Frontend on port 5500 (logs: logs/frontend.log)...{RESET}")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        env=env,
        stdout=fe_log,
        stderr=subprocess.STDOUT,
    )
    processes.append(({"name": "Frontend", "port": 5500, "color": "\033[95m"}, frontend_proc))

    print(f"\n{BOLD}All services started!{RESET}\n")
    print(f"  🌐 Dashboard:    http://localhost:5500")
    print(f"  🖥️  Backend API:  http://localhost:8000/docs")
    print(f"  📡 Simulator:    http://localhost:8001/docs")
    print(f"  🔒 Collector:    http://localhost:8002/docs")
    print(f"\n  Press Ctrl+C to stop all services.\n")

    # Wait and handle Ctrl+C
    try:
        while True:
            # Check if any process died
            for svc, proc in processes:
                if proc.poll() is not None:
                    print(f"{RED}✖ {svc['name']} exited with code {proc.returncode}{RESET}")
            time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n{BOLD}Stopping all services...{RESET}")
        for svc, proc in processes:
            print(f"  ■ Stopping {svc['name']}...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print(f"{BOLD}All services stopped.{RESET}\n")


def stop_services():
    """Kill any running processes on our ports."""
    ports = [8000, 8001, 8002, 5500]
    pids_killed = set()
    for port in ports:
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True
                )
                for line in result.stdout.splitlines():
                    if f":{port}" in line:
                        parts = line.strip().split()
                        if parts:
                            pid = parts[-1]
                            if pid.isdigit() and pid != "0" and pid not in pids_killed:
                                pids_killed.add(pid)
                                subprocess.run(["taskkill", "/F", "/PID", pid],
                                               capture_output=True)
                                print(f"  Killed previous process on port {port} (PID {pid})")
        except Exception as e:
            print(f"  Could not stop port {port}: {e}")
    if pids_killed:
        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VYTRON AIOps Launcher")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    args = parser.parse_args()

    if args.stop:
        stop_services()
    else:
        start_services()
