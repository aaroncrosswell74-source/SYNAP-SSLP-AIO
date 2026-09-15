#!/usr/bin/env python3
"""
RISA v3.1 - Service Discovery Module
Pure discovery layer - returns facts, makes no decisions about roles.
"""

import os
import sys
import socket
import subprocess
import json
import platform
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# DATA STRUCTURES
# ============================================================================

class ProtocolCandidate(Enum):
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    UNKNOWN = "unknown"


@dataclass
class DiscoveredService:
    """Pure discovery result - facts only, no interpretation"""
    host: str
    port: int
    pid: int
    process_name: str
    protocol_candidate: ProtocolCandidate = ProtocolCandidate.UNKNOWN
    listening_address: str = ""
    # These are NOT set by discovery - left for probe layer
    probe_response: Optional[Dict[str, Any]] = None
    role: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "pid": self.pid,
            "process_name": self.process_name,
            "protocol_candidate": self.protocol_candidate.value,
            "listening_address": self.listening_address,
            "probe_response": self.probe_response,
            "role": self.role
        }
    
    def __hash__(self):
        return hash((self.host, self.port, self.pid))
    
    def __eq__(self, other):
        if not isinstance(other, DiscoveredService):
            return False
        return (self.host, self.port, self.pid) == (other.host, other.port, other.pid)


# ============================================================================
# DISCOVERY ENGINE
# ============================================================================

class ServiceDiscovery:
    """Pure discovery - no interpretation, just facts"""
    
    def __init__(self):
        self._os_type = platform.system()
        self._services: List[DiscoveredService] = []
        self._port_to_pid: Dict[int, int] = {}
        self._pid_to_process: Dict[int, str] = {}
        
    def discover(self) -> List[DiscoveredService]:
        """Discover all listening services on the system"""
        print("\n🔍 Service Discovery Phase:")
        print("=" * 60)
        
        # Step 1: Get port → PID mappings
        self._discover_ports()
        print(f"   📊 Found {len(self._port_to_pid)} listening ports")
        
        # Step 2: Get PID → Process Name mappings
        self._discover_processes()
        print(f"   📊 Found {len(self._pid_to_process)} processes")
        
        # Step 3: Build service objects
        self._build_services()
        print(f"   📊 Built {len(self._services)} service records")
        
        # Step 4: Detect protocol candidates (basic)
        self._detect_protocol_candidates()
        
        return self._services
    
    def _discover_ports(self):
        """Discover listening ports using system-specific commands"""
        self._port_to_pid = {}
        
        if self._os_type == "Windows":
            self._discover_ports_windows()
        else:
            self._discover_ports_unix()
    
    def _discover_ports_windows(self):
        """Windows: Use netstat to find listening ports"""
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.splitlines():
                # Look for LISTENING state
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        # Parse: protocol, local_address, foreign_address, state, PID
                        local_addr = parts[1]
                        pid = int(parts[-1])
                        
                        # Extract host and port
                        if ":" in local_addr:
                            if local_addr.startswith("["):
                                # IPv6
                                host_port = local_addr.split("]")
                                if len(host_port) >= 2:
                                    host = host_port[0].strip("[").strip("]")
                                    port_str = host_port[1].lstrip(":")
                                    if port_str.isdigit():
                                        self._port_to_pid[int(port_str)] = pid
                            else:
                                # IPv4
                                host_port = local_addr.rsplit(":", 1)
                                if len(host_port) == 2:
                                    host = host_port[0]
                                    port_str = host_port[1]
                                    if port_str.isdigit():
                                        self._port_to_pid[int(port_str)] = pid
        except Exception as e:
            print(f"   ⚠️ Windows port discovery error: {e}")
    
    def _discover_ports_unix(self):
        """Unix/Linux: Use netstat or ss to find listening ports"""
        try:
            # Try ss first (modern Linux)
            result = subprocess.run(
                ["ss", "-lpn"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "LISTEN" in line:
                        parts = line.strip().split()
                        if len(parts) >= 6:
                            # Parse: Netid, State, Recv-Q, Send-Q, Local Address, Peer, Process
                            local_addr = parts[4]
                            if ":" in local_addr:
                                # Extract host and port
                                if local_addr.startswith("["):
                                    # IPv6
                                    host_port = local_addr.split("]")
                                    if len(host_port) >= 2:
                                        port_str = host_port[1].lstrip(":")
                                        if port_str.isdigit():
                                            # Try to extract PID from process info
                                            proc_info = " ".join(parts[5:])
                                            if "pid=" in proc_info:
                                                pid_str = proc_info.split("pid=")[1].split(",")[0]
                                                if pid_str.isdigit():
                                                    self._port_to_pid[int(port_str)] = int(pid_str)
                                else:
                                    # IPv4
                                    host_port = local_addr.rsplit(":", 1)
                                    if len(host_port) == 2:
                                        port_str = host_port[1]
                                        if port_str.isdigit():
                                            # Try to extract PID from process info
                                            proc_info = " ".join(parts[5:])
                                            if "pid=" in proc_info:
                                                pid_str = proc_info.split("pid=")[1].split(",")[0]
                                                if pid_str.isdigit():
                                                    self._port_to_pid[int(port_str)] = int(pid_str)
            else:
                # Fallback to netstat
                result = subprocess.run(
                    ["netstat", "-lpn"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if "LISTEN" in line:
                        parts = line.strip().split()
                        if len(parts) >= 6:
                            local_addr = parts[3]
                            if ":" in local_addr:
                                host_port = local_addr.rsplit(":", 1)
                                if len(host_port) == 2:
                                    port_str = host_port[1]
                                    if port_str.isdigit():
                                        pid_proc = parts[-1].split("/")
                                        if len(pid_proc) >= 1 and pid_proc[0].isdigit():
                                            self._port_to_pid[int(port_str)] = int(pid_proc[0])
        except Exception as e:
            print(f"   ⚠️ Unix port discovery error: {e}")
    
    def _discover_processes(self):
        """Discover process names for discovered PIDs"""
        self._pid_to_process = {}
        
        if self._os_type == "Windows":
            self._discover_processes_windows()
        else:
            self._discover_processes_unix()
    
    def _discover_processes_windows(self):
        """Windows: Use tasklist to get process names"""
        try:
            # Get list of PIDs we need to look up
            pids = list(self._port_to_pid.values())
            unique_pids = set(pids)
            
            if not unique_pids:
                return
            
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.splitlines():
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    # Format: "process_name.exe","PID",...
                    process_name = parts[0].strip('"')
                    pid_str = parts[1].strip('"')
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid in unique_pids:
                            self._pid_to_process[pid] = process_name
        except Exception as e:
            print(f"   ⚠️ Windows process discovery error: {e}")
    
    def _discover_processes_unix(self):
        """Unix/Linux: Use ps to get process names"""
        try:
            unique_pids = set(self._port_to_pid.values())
            if not unique_pids:
                return
            
            pid_list = ",".join(str(pid) for pid in unique_pids)
            result = subprocess.run(
                ["ps", "-p", pid_list, "-o", "pid=,comm="],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) >= 2:
                    pid = int(parts[0])
                    process_name = parts[1]
                    self._pid_to_process[pid] = process_name
        except Exception as e:
            print(f"   ⚠️ Unix process discovery error: {e}")
    
    def _build_services(self):
        """Build DiscoveredService objects from discovered data"""
        self._services = []
        
        for port, pid in self._port_to_pid.items():
            process_name = self._pid_to_process.get(pid, "unknown")
            
            service = DiscoveredService(
                host="0.0.0.0",  # We'll refine this
                port=port,
                pid=pid,
                process_name=process_name,
                listening_address=f"0.0.0.0:{port}"
            )
            self._services.append(service)
    
    def _detect_protocol_candidates(self):
        """Basic protocol detection - just the obvious ones"""
        for service in self._services:
            # Check if it's likely HTTP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(("127.0.0.1", service.port))
                
                # Send a minimal HTTP request
                s.send(b"HEAD / HTTP/1.0\r\n\r\n")
                response = s.recv(1024)
                s.close()
                
                if response.startswith(b"HTTP/") or b"Server:" in response:
                    service.protocol_candidate = ProtocolCandidate.HTTP
                elif b"Upgrade:" in response and b"websocket" in response.lower():
                    service.protocol_candidate = ProtocolCandidate.WEBSOCKET
                    
            except:
                # Could be other protocols
                pass
    
    def get_services_by_port(self, port: int) -> Optional[DiscoveredService]:
        """Get service by port number"""
        for service in self._services:
            if service.port == port:
                return service
        return None
    
    def get_services_by_pid(self, pid: int) -> List[DiscoveredService]:
        """Get all services by PID"""
        return [s for s in self._services if s.pid == pid]
    
    def get_services_by_name(self, name_pattern: str) -> List[DiscoveredService]:
        """Get services by process name pattern"""
        pattern = name_pattern.lower()
        return [s for s in self._services if pattern in s.process_name.lower()]
    
    def to_json(self) -> str:
        """Export discovery results as JSON"""
        return json.dumps(
            [s.to_dict() for s in self._services],
            indent=2
        )


# ============================================================================
# DISCOVERY VERIFIER
# ============================================================================

def verify_discovery(discovered_services: List[DiscoveredService]):
    """Basic verification against known expected services"""
    print("\n🔍 Discovery Verification:")
    print("=" * 60)
    
    # Expected services from your logs
    expected = {
        11436: ("studio", 16224),
        11439: ("interceptor", 10328),
        11440: ("mcp_http", 18568),
        11441: ("mcp_ws", 18568),
    }
    
    found_count = 0
    for port, (expected_name, expected_pid) in expected.items():
        service = next((s for s in discovered_services if s.port == port), None)
        if service:
            matched = "✅" if service.pid == expected_pid else "⚠️"
            print(f"   {matched} Port {port}: {service.process_name} (PID {service.pid})")
            if service.pid != expected_pid:
                print(f"      Expected: {expected_name} (PID {expected_pid})")
            found_count += 1
        else:
            print(f"   ❌ Port {port}: Not found")
    
    if found_count == len(expected):
        print(f"\n✅ All expected services found! ({found_count}/{len(expected)})")
    else:
        print(f"\n⚠️ Found {found_count}/{len(expected)} expected services")
    
    # Show any extra services discovered
    extra = []
    for service in discovered_services:
        if service.port not in expected:
            extra.append(service)
    
    if extra:
        print(f"\n📊 Extra services discovered:")
        for service in extra:
            print(f"   • Port {service.port}: {service.process_name} (PID {service.pid})")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Test the discovery module"""
    print("🛡️ RISA v3.1 - Service Discovery")
    print("=" * 60)
    
    discovery = ServiceDiscovery()
    services = discovery.discover()
    
    # Print results
    print("\n📊 Discovered Services:")
    print("-" * 60)
    for service in sorted(services, key=lambda s: s.port):
        print(f"   {service.port:5} → PID {service.pid:6} → {service.process_name}")
    
    # Verify against expected
    verify_discovery(services)
    
    # Export JSON
    print("\n📄 Exporting discovery results...")
    json_output = discovery.to_json()
    output_path = Path("discovery_results.json")
    output_path.write_text(json_output)
    print(f"   ✅ Written to: {output_path}")
    
    return services


if __name__ == "__main__":
    main()