#!/usr/bin/env python3
"""
run_execution_daemon.py — Background Execution Engine Daemon

Run this alongside the orchestrator during market hours.
It polls order status every ~15 seconds and:
- Places stop-loss orders immediately after entry fills
- Panic-liquidates positions if price crashes through stop during partial fills
- Handles order cancellation / expiry cleanup

Usage:
    python3 run_execution_daemon.py

Kill with Ctrl+C or SIGTERM.
"""
from execution_engine import ExecutionEngine

if __name__ == "__main__":
    print("=" * 60)
    print("  EXECUTION ENGINE DAEMON")
    print("  Reconciles orders every 15 seconds")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    engine = ExecutionEngine()
    engine.run_reconciliation_loop()
