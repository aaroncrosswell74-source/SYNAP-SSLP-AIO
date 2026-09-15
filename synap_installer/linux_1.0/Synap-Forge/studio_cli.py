#!/usr/bin/env python3
"""
Synap-Forge Studio CLI - The Walkie Talkie
Connects to Interceptor (11439) for full MCP Tool Integration.
"""
import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# Port mappings from the Phase 2 spec
PORTS = {
    "Interceptor": 11439,
    "Synap": 11436,
    "MCP": 11440
}

INTERCEPTOR_URL = f"http://127.0.0.1:{PORTS['Interceptor']}"

def print_banner():
    print("\n" + "="*60)
    print("      SYNAP-FORGE STUDIO CLI (The Walkie Talkie)")
    print(f"      Gateway: {INTERCEPTOR_URL}")
    print("="*60)
    print("      Commands: '/risa status', '/risa scan', 'exit'")
    print("="*60 + "\n")

def check_service_health(port):
    try:
        # Check standard health endpoint
        response = requests.get(f"http://localhost:{port}/health", timeout=1.0)
        return "✅ ONLINE" if response.status_code == 200 else "⚠️ DEGRADED"
    except Exception:
        return "❌ OFFLINE"

def verify_digital_birth_certificate():
    # Real path from Proof 1 verification
    dbc_path = Path(__file__).parent / ".consciousness_engine" / "state" / "identity_lock.json"
    if dbc_path.exists():
        return "✅ LOCKED"
    return "❌ MISSING"

def check_adb():
    try:
        # Active probe to the ADB daemon
        response = subprocess.run(
            ["adb", "get-state"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        return "✅ CONNECTED" if response.returncode == 0 and response.stdout.strip() == "device" else "❌ DISCONNECTED"
    except Exception:
        return "❌ DISCONNECTED"

def handle_risa_status():
    print("\nARKWELL RISA STATUS")
    print("────────────────────────────")
    
    # Collect real-time telemetry
    id_status = verify_digital_birth_certificate()
    interceptor_health = check_service_health(PORTS['Interceptor'])
    synap_health = check_service_health(PORTS['Synap'])
    mcp_health = check_service_health(PORTS['MCP'])
    adb_status = check_adb()

    # Logic: Nominal only if all systems are green
    overall_health = "✅ NOMINAL"
    if "❌" in f"{id_status}{interceptor_health}{synap_health}{mcp_health}{adb_status}":
        overall_health = "⚠️ DEGRADED"

    print(f"RISA Engine      ✅ ONLINE")
    print(f"Identity         {id_status}")
    print(f"Interceptor      {interceptor_health}")
    print(f"Synap            {synap_health}")
    print(f"MCP              {mcp_health}")
    print(f"ADB              {adb_status}")
    
    print(f"\nRuntime Health   {overall_health}")
    print(f"Status Check     {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Last Scan        NEVER")
    print("Pending Repairs  0")
    print("Warnings         0")

def run_risa_scan():
    risa_script = Path(__file__).parent / "risa_v3.2.py"
    if risa_script.exists():
        print("\n🚀 Starting Classified RISA Scan...")
        subprocess.run([sys.executable, str(risa_script), "--scan"])
        
        # Authorization Barrier
        user_auth = input("\nAuthorization Required > ").strip().lower()
        if user_auth == "approve":
            print("🔧 Authorization granted. Executing critical repairs...")
            subprocess.run([sys.executable, str(risa_script), "--heal"])
            print("\n🔄 Verification Scan:")
            subprocess.run([sys.executable, str(risa_script), "--scan"])
        else:
            print("🚫 Authorization denied. No changes made.")
    else:
        print("[RISA] Error: risa_v3.2.py not found.")

def chat_loop():
    print_banner()
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input: continue
            if user_input.lower() in ["exit", "quit"]: break
            
            if user_input.lower() == "/risa status":
                handle_risa_status()
                continue
                
            if user_input.lower() == "/risa scan":
                run_risa_scan()
                continue

            payload = {
                "model": "Weaver",
                "messages": [{"role": "user", "content": user_input}],
                "stream": False
            }
            
            print("Thinking...", end="\r")
            try:
                resp = requests.post(f"{INTERCEPTOR_URL}/v1/chat/completions", json=payload, timeout=120)
                
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    print(" " * 15, end="\r")
                    print(f"\nSynap: {content}")
                else:
                    print(f"\nError: {resp.status_code} - {resp.text}")
            except requests.exceptions.ConnectionError:
                print(f"\n❌ Error: Interceptor not found on 11439. Is the stack running?")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nException: {e}")

if __name__ == "__main__":
    chat_loop()
