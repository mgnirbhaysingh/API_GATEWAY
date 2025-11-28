#!/usr/bin/env python3
"""
Universal Scraper Gateway - Python Startup Script

Alternative to run_all.sh for cross-platform compatibility.

Usage:
    python run.py          # Start all services
    python run.py --stop   # Stop all services
    python run.py --status # Check service status
"""

import subprocess
import sys
import time
import os
import signal
import argparse
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent

# Service configurations
SERVICES = [
    {
        "name": "QuickComm",
        "dir": PARENT_DIR / "QuickComm",
        "module": "app.main:app",
        "port": 8001,
    },
    {
        "name": "ShopifyCode",
        "dir": PARENT_DIR / "ShopifyCode",
        "module": "main:app",
        "port": 8002,
    },
    {
        "name": "reviews_Scraper",
        "dir": PARENT_DIR / "reviews_Scraper",
        "module": "main:app",
        "port": 8003,
    },
    {
        "name": "GoogleMaps",
        "dir": PARENT_DIR / "googlemaps",
        "module": "maps_scraper:app",
        "port": 8004,
    },
]

GATEWAY = {
    "name": "Gateway",
    "dir": SCRIPT_DIR,
    "module": "main:app",
    "port": 8080,
}

processes = []


def check_port(port: int) -> bool:
    """Check if a port is in use."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def start_service(service: dict, is_gateway: bool = False) -> subprocess.Popen:
    """Start a uvicorn service."""
    host = "0.0.0.0" if is_gateway else "127.0.0.1"
    log_level = "info" if is_gateway else "warning"

    cmd = [
        sys.executable, "-m", "uvicorn",
        service["module"],
        "--host", host,
        "--port", str(service["port"]),
        "--log-level", log_level,
    ]

    print(f"Starting {service['name']} on port {service['port']}...")

    proc = subprocess.Popen(
        cmd,
        cwd=str(service["dir"]),
        stdout=subprocess.PIPE if not is_gateway else None,
        stderr=subprocess.PIPE if not is_gateway else None,
    )

    time.sleep(1)

    if proc.poll() is None:
        print(f"  ✓ {service['name']} started (PID: {proc.pid})")
        return proc
    else:
        print(f"  ✗ {service['name']} failed to start")
        return None


def stop_all():
    """Stop all running services."""
    print("\nStopping all services...")
    for proc in processes:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("All services stopped.")


def show_status():
    """Show status of all services."""
    print("\nService Status:")
    print("=" * 40)

    all_services = SERVICES + [GATEWAY]
    for service in all_services:
        status = "Running" if check_port(service["port"]) else "Not running"
        symbol = "✓" if status == "Running" else "✗"
        print(f"  {symbol} {service['name']:20} (port {service['port']}) - {status}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Universal Scraper Gateway Manager")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    parser.add_argument("--status", action="store_true", help="Show service status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.stop:
        # Kill processes on the ports
        import socket
        for service in SERVICES + [GATEWAY]:
            if check_port(service["port"]):
                print(f"Stopping service on port {service['port']}...")
                os.system(f"lsof -ti:{service['port']} | xargs kill -9 2>/dev/null || true")
        print("Services stopped.")
        return

    # Check if gateway is already running
    if check_port(GATEWAY["port"]):
        print(f"Gateway already running on port {GATEWAY['port']}")
        print("Use 'python run.py --stop' to stop services first")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  Universal Scraper Gateway - Starting")
    print("=" * 50 + "\n")

    # Setup signal handler
    def signal_handler(sig, frame):
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start backend services
    for service in SERVICES:
        proc = start_service(service)
        if proc:
            processes.append(proc)

    # Wait for backends
    print("\nWaiting for backends to initialize...")
    time.sleep(2)

    # Start gateway
    print()
    gateway_proc = start_service(GATEWAY, is_gateway=True)
    if gateway_proc:
        processes.append(gateway_proc)

    print("\n" + "=" * 50)
    print("  All services started successfully!")
    print("=" * 50)
    print(f"""
Gateway URL:     http://localhost:{GATEWAY['port']}
API Docs:        http://localhost:{GATEWAY['port']}/docs
Health Check:    http://localhost:{GATEWAY['port']}/health/all

Direct Access:
  QuickComm:     http://localhost:8001
  ShopifyCode:   http://localhost:8002
  Reviews:       http://localhost:8003

Example API Calls:
  curl 'http://localhost:{GATEWAY['port']}/ecommerce/amazon/search?query=chocolate'
  curl 'http://localhost:{GATEWAY['port']}/health/all'

Press Ctrl+C to stop all services
""")

    # Wait for gateway to exit
    try:
        gateway_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()


if __name__ == "__main__":
    main()
