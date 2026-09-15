#!/usr/bin/env python3
# bootstrap.py - Fire everything in order

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

PROJECT_ROOT = Path("/home/aaron/Synap-Forge/.consciousness_engine")
MEMORY_SERVER = PROJECT_ROOT / "memory_server.py"
VOICE_SERVER = PROJECT_ROOT / "voice_server.py"

def start_process(cmd, name):
    """Start a subprocess with logging"""
    print(f"🚀 Starting {name}...")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Log output in real-time
    def log_output():
        for line in proc.stdout:
            print(f"[{name}] {line.rstrip()}")
    
    import threading
    t = threading.Thread(target=log_output, daemon=True)
    t.start()
    
    return proc

def main():
    print("="*60)
    print("  SYNAP FORGE - BOOTSTRAP")
    print("="*60)
    
    processes = []
    
    try:
        # 1. Start Memory Server
        if MEMORY_SERVER.exists():
            proc = start_process(
                [sys.executable, str(MEMORY_SERVER)],
                "MEMORY"
            )
            processes.append(proc)
            time.sleep(2)  # Give it time to init
        else:
            print("⚠️  Memory server not found, skipping")
        
        # 2. Start Voice Server (if requested)
        if "--voice" in sys.argv and VOICE_SERVER.exists():
            proc = start_process(
                [sys.executable, str(VOICE_SERVER)],
                "VOICE"
            )
            processes.append(proc)
        elif "--voice" in sys.argv:
            print("⚠️  Voice server not found")
        
        print("\n✅ All servers running")
        print("Press Ctrl+C to shutdown all")
        print("="*60)
        
        # Wait for all processes
        while True:
            time.sleep(1)
            # Check if any died
            for p in processes:
                if p.poll() is not None:
                    print(f"⚠️  Process {p.pid} died")
                    # Restart? Or exit?
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        for p in processes:
            p.terminate()
            p.wait(timeout=2)
        print("✅ All servers stopped")

if __name__ == "__main__":
    main()