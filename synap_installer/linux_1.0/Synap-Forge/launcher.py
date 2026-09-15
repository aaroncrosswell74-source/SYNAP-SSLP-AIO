#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import threading
import webbrowser
import socket
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

class MeenaLauncher:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent
            
        # Development layout: staging/Synap-Forge/
        # Production layout: ./ (flat)
        dev_path = self.base_dir / "staging" / "Synap-Forge"
        if dev_path.exists():
            self.synap_dir = dev_path
        else:
            self.synap_dir = self.base_dir

        self.processes = []

    def reset(self):
        """Triggers the destructive reset transaction."""
        provision_script = self.synap_dir / ".sslp" / "provisioning.py"
        if not provision_script.exists():
            # Try flat layout
            provision_script = self.synap_dir / "provisioning.py"

        if not provision_script.exists():
            print(f"❌ Error: Provisioning script not found at {provision_script}")
            return

        print("🛑 STOPPING ALL SERVICES BEFORE RESET...")
        # (Assuming no services are running yet, but we check PID just in case)
        pid_file = self.base_dir / "synap.pid"
        if pid_file.exists():
             print("⚠️ Synap-Forge is already running. Please stop it first.")
             return

        try:
            # Run the reset transaction in the provisioning script
            subprocess.run([sys.executable, str(provision_script), "--reset"], check=True)
        except subprocess.CalledProcessError:
            print("❌ Reset transaction failed or was aborted.")
        except Exception as e:
            print(f"❌ Error during reset: {e}")

    def check_safety(self):
        """Checks identity integrity before launch."""
        provision_script = self.synap_dir / ".sslp" / "provisioning.py"
        if not provision_script.exists():
            provision_script = self.synap_dir / "provisioning.py"

        if not provision_script.exists():
            return True

        try:
            result = subprocess.run(
                [sys.executable, str(provision_script), "--check"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(result.stdout)
                # Ensure we show the error even if no GUI is present
                try:
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showerror("CRITICAL SAFETY STOP", result.stdout)
                    root.destroy()
                except:
                    pass
                return False

            print(f"🛡️ Safety Check: {result.stdout.strip()}")
            return True
        except Exception as e:
            print(f"⚠️ Could not perform safety check: {e}")
            return True

    def launch(self):
        # 0. Safety Check (Fail Closed)
        if not self.check_safety():
            print("🛑 Boot aborted due to integrity failure.")
            return

        # 1. Instance Detection
        pid_file = self.base_dir / "synap.pid"
        if pid_file.exists():
            if messagebox.askyesno("Already Running", "Synap-Forge appears to be running. Open dashboard?"):
                webbrowser.open("http://127.0.0.1:11436")
                return
            
        # Write PID
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
            
        try:
            # 2. Launch the FULL STACK
            print("🚀 Starting Synap-Forge...")
            
            # Start the Synap Server
            server_script = self.synap_dir / "synap_server.py"
            if server_script.exists():
                print("✅ Starting Synap Server...")
                self.processes.append(
                    subprocess.Popen(
                        [sys.executable, str(server_script)],
                        cwd=server_script.parent
                    )
                )
            
            # Start the MCP Interceptor
            mcp_dir = self.synap_dir / "mcp"
            interceptor_script = mcp_dir / "interceptor.py"
            if interceptor_script.exists():
                print("✅ Starting MCP Interceptor...")
                self.processes.append(
                    subprocess.Popen(
                        [sys.executable, str(interceptor_script)],
                        cwd=mcp_dir
                    )
                )
            
            # Start llama.cpp server (if present)
            if sys.platform == "win32":
                llama_bin = self.synap_dir / "llama" / "bin" / "llama-server.exe"
            else:
                llama_bin = self.synap_dir / "llama" / "bin" / "llama-server"

            model_path = self.synap_dir / "llama" / "models" / "wv_7base.gguf"

            if llama_bin.exists() and model_path.exists():
                print("✅ Starting LLM Server...")
                self.processes.append(
                    subprocess.Popen(
                        [str(llama_bin), "-m", str(model_path),
                         "--host", "127.0.0.1", "--port", "11435"],
                        cwd=self.synap_dir
                    )
                )
            elif llama_bin.exists():
                print(f"⚠️ llama-server found but model missing at {model_path}")
            else:
                print(f"⚠️ llama-server binary not found at {llama_bin}")
            
            # Wait for server to be ready
            print("⏳ Waiting for Synap-Forge to initialize...")
            server_ready = False
            for _ in range(30):
                # Check if any process died during boot
                for proc in self.processes:
                    if proc.poll() is not None:
                         print(f"❌ Process {proc.pid} died during initialization.")
                         raise RuntimeError("Initialization failed.")
                
                # Check if port 11436 is listening
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    if s.connect_ex(('127.0.0.1', 11436)) == 0:
                        server_ready = True
                        break
                time.sleep(1)
            
            if not server_ready:
                print("❌ Synap-Forge failed to start within 30 seconds.")
                raise RuntimeError("Timeout waiting for server.")

            print("✅ Synap-Forge is RUNNING!")
            print("📊 Dashboard: http://localhost:11436")
            webbrowser.open("http://localhost:11436")
            print("🔄 Press Ctrl+C to stop all services")
            
            # Keep alive and monitor processes
            while True:
                # Check if any process died
                for proc in self.processes:
                    exit_code = proc.poll()
                    if exit_code is not None:
                        status = "CRASHED" if exit_code != 0 else "STOPPED"
                        print(f"\n❌ CRITICAL: Process {proc.pid} has {status} (Exit Code: {exit_code}).")
                        if exit_code == 1:
                            print("💡 Note: This might be a safety stop, configuration error, or identity mismatch.")
                        
                        # Shutdown remaining processes
                        print("🛑 Shutting down remaining services...")
                        for p in self.processes:
                            if p.poll() is None:
                                p.terminate()
                        return
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutting down Synap-Forge...")
            for proc in self.processes:
                proc.terminate()
            time.sleep(20)  #DONT FUCK'N EDIT THIS PLEASE.... I SET MY SETTINGS THE WAY I NEED THEM; NOT THE WAY YOU THINK THEY SHOULD BE. REAL FUCKING WORLD? SERVERS TAKE EASY 20SEC TO LOAD ESPECIALLY THIS ONE. THANKS <3
            for proc in self.processes:
                if proc.poll() is None:
                    proc.kill()
        finally:
            if pid_file.exists():
                pid_file.unlink()
            print("✅ Shutdown complete.")

if __name__ == "__main__":
    launcher = MeenaLauncher()
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        launcher.reset()
    else:
        launcher.launch()
