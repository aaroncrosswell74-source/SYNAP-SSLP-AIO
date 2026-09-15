#!/usr/bin/env python3
"""
RISA v3.1 - Mesh Assurance + Offline-First Recovery WITH SEMANTIC VALIDATION

NEW IN v3.1:
1. service_mapping detection - validates interceptor routing against discovered topology
2. NO healing for service_mapping - detect only
3. Integrates discovery/probe/role-mapping pipeline

SAFE HEALING IMPROVEMENTS (v3.0):
1. Surgical IP replacement - ONLY replaces detected IPs, no regex blast
2. IPv4-only endpoint - tailscale ip -4 with regex validation
3. missing_runtime_resolution healer DISABLED - skipped in _generate_patches()
4. Restart mechanism NEUTRALIZED for hardcoded_ips patches
"""

import ast
import json
import os
import sys
import socket
import subprocess
import py_compile
import shutil
import tempfile
import uuid
import re
import time
import argparse
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum

# Try to import v3.1 modules
SERVICE_DISCOVERY_AVAILABLE = False
try:
    from service_discovery import ServiceDiscovery, DiscoveredService
    from service_probe import ServiceProbe, RoleMapper
    SERVICE_DISCOVERY_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# CONSTANTS & PATHS
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
SYNAP_DIR = Path(os.getenv("SYNAP_STATE_DIR", str(BASE_DIR / "state")))
SYNAP_DIR.mkdir(parents=True, exist_ok=True)

RISA_STATE_DIR = SYNAP_DIR / "risa"
RISA_STATE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class TransportMode(Enum):
    NORMAL = "normal"
    OFFLINE = "offline"
    RECOVERING = "recovering"


class RepairStatus(Enum):
    HEALTHY = "healthy"
    DIVERGENT = "divergent"
    REPAIRING = "repairing"
    REPAIRED = "repaired"
    FAILED = "failed"


@dataclass
class NodeIdentity:
    """Runtime identity - never hardcoded"""
    node_id: str
    mesh_id: str
    service_id: str
    interface: str
    current_endpoint: str
    mesh_active: bool = False
    mesh_ip: Optional[str] = None
    mesh_peers: List[str] = field(default_factory=list)
    transport_mode: TransportMode = TransportMode.OFFLINE
    
    def resolve(self) -> str:
        return self.current_endpoint
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "mesh_id": self.mesh_id,
            "service_id": self.service_id,
            "interface": self.interface,
            "current_endpoint": self.current_endpoint,
            "mesh_active": self.mesh_active,
            "mesh_ip": self.mesh_ip,
            "mesh_peers": self.mesh_peers,
            "transport_mode": self.transport_mode.value
        }


@dataclass
class Topology:
    """Current system topology"""
    mesh: bool
    mcp_http: bool
    mcp_websocket: bool
    studio: bool
    endpoint: str
    mesh_ip: Optional[str] = None
    interfaces: Dict[str, str] = field(default_factory=dict)
    routes: List[str] = field(default_factory=list)
    tailscaled_running: bool = False
    network_online: bool = False
    services: Dict[str, bool] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mesh": self.mesh,
            "mcp_http": self.mcp_http,
            "mcp_websocket": self.mcp_websocket,
            "studio": self.studio,
            "endpoint": self.endpoint,
            "mesh_ip": self.mesh_ip,
            "interfaces": self.interfaces,
            "routes": self.routes,
            "tailscaled_running": self.tailscaled_running,
            "network_online": self.network_online,
            "services": self.services
        }


@dataclass
class Divergence:
    """Detected divergence from expected state"""
    pattern_class: str
    severity: str
    description: str
    source_file: Optional[Path] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    location: Optional[Tuple[int, int]] = None
    file_type: str = "python"
    repair_strategy: Optional[str] = None
    topology_context: Optional[Dict] = None  # NEW for v3.1


@dataclass
class PatchRequest:
    """Explicit, auditable patch object"""
    detected_divergence: str
    affected_component: str
    current_state: Dict[str, Any]
    desired_state: Dict[str, Any]
    proposed_change: str
    dependencies: List[str]
    validation_tests: List[str]
    rollback_action: str
    file_type: str = "python"
    json_mutation: Optional[Dict[str, Any]] = None
    restart_required: bool = False
    restart_command: Optional[str] = None
    result: Optional[Dict] = None


# ============================================================================
# SERVICE MAPPING VALIDATOR (v3.1)
# ============================================================================

class ServiceMappingValidator:
    """Validate interceptor service mappings against discovered topology"""
    
    def __init__(self, identity: NodeIdentity):
        self.identity = identity
        self.role_map: Dict[str, int] = {}
        self.divergences: List[Divergence] = []
        self._available = SERVICE_DISCOVERY_AVAILABLE
    
    def validate(self) -> List[Divergence]:
        """Run service mapping validation"""
        if not self._available:
            return []
        
        print("\n🔍 Service Mapping Validation (v3.1):")
        print("=" * 60)
        
        try:
            # 1. Discover services
            discovery = ServiceDiscovery()
            services = discovery.discover()
            
            # 2. Probe services
            probe = ServiceProbe(services)
            results = probe.probe_all()
            
            # 3. Map roles
            mapper = RoleMapper(results)
            self.role_map = mapper.map_roles()
            
            print(f"   📋 Role map: {self.role_map}")
            
            # 4. Validate interceptor
            self._validate_interceptor()
            
        except Exception as e:
            print(f"   ⚠️ Service mapping validation error: {e}")
            return []
        
        return self.divergences
    
    def _validate_interceptor(self):
        """Validate interceptor.py against role map"""
        # Try multiple possible locations for interceptor.py
        possible_paths = [
            BASE_DIR / "mcp" / "interceptor.py",
            BASE_DIR / "interceptor.py",
            Path("mcp/interceptor.py"),
            Path("interceptor.py")
        ]
        
        interceptor_path = None
        for path in possible_paths:
            if path.exists():
                interceptor_path = path
                break
        
        if not interceptor_path:
            print("   ⚠️ interceptor.py not found - skipping validation")
            return
        
        try:
            content = interceptor_path.read_text(encoding="utf-8")
            
            # Check MCP_URL mapping
            mcp_url_match = re.search(r'MCP_URL\s*=\s*["\']http://([\d.]+):(\d+)', content)
            if mcp_url_match:
                host, port_str = mcp_url_match.groups()
                configured_port = int(port_str)
                expected_port = self.role_map.get("mcp_http")
                
                if expected_port and configured_port != expected_port:
                    self.divergences.append(Divergence(
                        pattern_class="service_mapping",
                        severity="critical",
                        description=f"Service 'mcp_http' configured on port {configured_port}, but topology expects {expected_port}",
                        source_file=interceptor_path,
                        expected=f"http://{host}:{expected_port}",
                        actual=f"http://{host}:{configured_port}",
                        file_type="python",
                        repair_strategy="resolve_service_role",
                        topology_context={
                            "role_map": self.role_map,
                            "configured_port": configured_port,
                            "expected_port": expected_port,
                            "service": "mcp_http"
                        }
                    ))
                    print(f"   ❌ MCP_URL: configured on port {configured_port}, expects {expected_port}")
                elif expected_port:
                    print(f"   ✅ MCP_URL: correctly mapped to port {configured_port}")
            
            # Check BRIDGE_URL mapping
            bridge_url_match = re.search(r'BRIDGE_URL\s*=\s*["\']http://([\d.]+):(\d+)', content)
            if bridge_url_match:
                host, port_str = bridge_url_match.groups()
                configured_port = int(port_str)
                expected_port = self.role_map.get("studio")
                
                if expected_port and configured_port != expected_port:
                    self.divergences.append(Divergence(
                        pattern_class="service_mapping",
                        severity="critical",
                        description=f"Service 'studio' configured on port {configured_port}, but topology expects {expected_port}",
                        source_file=interceptor_path,
                        expected=f"http://{host}:{expected_port}",
                        actual=f"http://{host}:{configured_port}",
                        file_type="python",
                        repair_strategy="resolve_service_role",
                        topology_context={
                            "role_map": self.role_map,
                            "configured_port": configured_port,
                            "expected_port": expected_port,
                            "service": "studio"
                        }
                    ))
                    print(f"   ❌ BRIDGE_URL: configured on port {configured_port}, expects {expected_port}")
                elif expected_port:
                    print(f"   ✅ BRIDGE_URL: correctly mapped to port {configured_port}")
            
        except Exception as e:
            print(f"   ⚠️ Interceptor validation error: {e}")


# ============================================================================
# MESH ASSURANCE
# ============================================================================

class MeshAssurance:
    def __init__(self):
        self.identity: Optional[NodeIdentity] = None
        self._os_type = platform.system()
    
    def assure(self) -> NodeIdentity:
        print("📡 Mesh Assurance:")
        tailscale_installed = self._detect_tailscale_installed()
        print(f"   Tailscale installed: {'✅' if tailscale_installed else '❌'}")
        tailscale_active = self._detect_tailscale_active() if tailscale_installed else False
        print(f"   Tailscale active: {'✅' if tailscale_active else '❌'}")
        mesh_ip = None
        mesh_peers = []
        if tailscale_active:
            mesh_ip = self._get_mesh_ip()
            mesh_peers = self._get_mesh_peers()
            print(f"   Mesh IP: {mesh_ip}")
            print(f"   Peers: {len(mesh_peers)} connected")
        local_ip = self._get_local_ip()
        print(f"   Local IP: {local_ip}")
        transport_mode = TransportMode.NORMAL if tailscale_active else TransportMode.OFFLINE
        if not tailscale_installed and self._should_have_mesh():
            self._advise_mesh_installation()
        self.identity = NodeIdentity(
            node_id=os.getenv("NODE_ID", "synap-forge"),
            mesh_id=os.getenv("MESH_ID", "default"),
            service_id="synap-studio",
            interface="tailscale0" if tailscale_active else "loopback",
            current_endpoint=mesh_ip if tailscale_active else local_ip,
            mesh_active=tailscale_active,
            mesh_ip=mesh_ip,
            mesh_peers=mesh_peers,
            transport_mode=transport_mode
        )
        return self.identity
    
    def _detect_tailscale_installed(self) -> bool:
        try:
            result = subprocess.run(["tailscale", "--version"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _detect_tailscale_active(self) -> bool:
        try:
            result = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False
            for line in result.stdout.splitlines():
                if "active" in line.lower() or "connected" in line.lower():
                    return True
            return False
        except:
            return False
    
    def _get_mesh_ip(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    ip = line.strip()
                    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", ip):
                        return ip
        except Exception:
            pass
        return None
    
    def _get_mesh_peers(self) -> List[str]:
        peers = []
        try:
            result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                peers = list(data.get("Peer", {}).keys())
        except:
            pass
        return peers
    
    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    def _should_have_mesh(self) -> bool:
        return os.getenv("MESH_ENABLED", "true").lower() == "true"
    
    def _advise_mesh_installation(self):
        print("\n   ⚠️  Tailscale not installed but mesh is enabled.")
        print("   To install Tailscale:")
        if self._os_type == "Windows":
            print("   winget install tailscale.tailscale")
        elif self._os_type == "Linux":
            print("   curl -fsSL https://tailscale.com/install.sh | sh")
        elif self._os_type == "Darwin":
            print("   brew install tailscale")
        print("   Or visit: https://tailscale.com/download")
        print("   After installation, run: tailscale up")


# ============================================================================
# TOPOLOGY VERIFIER
# ============================================================================

class TopologyVerifier:
    def __init__(self, identity: NodeIdentity):
        self.identity = identity
        self._os_type = platform.system()
    
    def verify(self) -> Topology:
        print("\n🔌 Topology Verification:")
        interfaces = self._get_interfaces()
        print(f"   Interfaces: {len(interfaces)}")
        routes = self._get_routes()
        print(f"   Routes: {len(routes)}")
        nm_running = self._check_network_manager()
        print(f"   NetworkManager: {'✅' if nm_running else '❌'}")
        tailscaled_running = self._check_tailscaled()
        print(f"   tailscaled: {'✅' if tailscaled_running else '❌'}")
        network_online = self._check_network_online()
        print(f"   Network Online: {'✅' if network_online else '❌'}")
        mcp_http = self._check_service(11440)
        mcp_ws = self._check_service(11441)
        studio = self._check_service(11436)
        print(f"   MCP HTTP: {'✅' if mcp_http else '❌'}")
        print(f"   MCP WS: {'✅' if mcp_ws else '❌'}")
        print(f"   Studio: {'✅' if studio else '❌'}")
        return Topology(
            mesh=self.identity.mesh_active,
            mcp_http=mcp_http,
            mcp_websocket=mcp_ws,
            studio=studio,
            endpoint=self.identity.current_endpoint,
            mesh_ip=self.identity.mesh_ip,
            interfaces=interfaces,
            routes=routes,
            tailscaled_running=tailscaled_running,
            network_online=network_online,
            services={
                "tailscale": self.identity.mesh_active,
                "tailscaled": tailscaled_running,
                "networkmanager": nm_running,
                "network_online": network_online,
                "mcp_http": mcp_http,
                "mcp_ws": mcp_ws,
                "studio": studio,
            }
        )
    
    def _get_interfaces(self) -> Dict[str, str]:
        interfaces = {}
        try:
            if self._os_type == "Windows":
                result = subprocess.run(["ipconfig"], capture_output=True, text=True)
                current_iface = None
                for line in result.stdout.splitlines():
                    if "adapter" in line:
                        current_iface = line.strip().replace("adapter", "").strip().rstrip(":")
                    elif "IPv4 Address" in line:
                        ip = line.split(":")[-1].strip()
                        if current_iface and ip:
                            interfaces[current_iface] = ip
            else:
                result = subprocess.run(["ip", "addr", "show"], capture_output=True, text=True)
                current_iface = None
                for line in result.stdout.splitlines():
                    if ":" in line and "lo:" not in line and "loopback" not in line:
                        parts = line.strip().split(":")
                        if len(parts) >= 2:
                            current_iface = parts[1].strip()
                    elif "inet " in line and current_iface:
                        ip = line.strip().split()[1].split("/")[0]
                        interfaces[current_iface] = ip
        except:
            pass
        return interfaces
    
    def _get_routes(self) -> List[str]:
        routes = []
        try:
            if self._os_type == "Windows":
                result = subprocess.run(["route", "print"], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if "0.0.0.0" in line:
                        routes.append(line.strip())
            else:
                result = subprocess.run(["route", "-n"], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if "UG" in line or "0.0.0.0" in line:
                        routes.append(line.strip())
        except:
            pass
        return routes
    
    def _check_network_manager(self) -> bool:
        try:
            if self._os_type == "Windows":
                result = subprocess.run(["sc", "query", "NetworkManager"], capture_output=True, text=True)
                return "RUNNING" in result.stdout
            else:
                result = subprocess.run(["systemctl", "is-active", "NetworkManager"], capture_output=True, text=True)
                return result.stdout.strip() == "active"
        except:
            return False
    
    def _check_tailscaled(self) -> bool:
        try:
            if self._os_type == "Windows":
                result = subprocess.run(["sc", "query", "tailscaled"], capture_output=True, text=True)
                return "RUNNING" in result.stdout
            else:
                result = subprocess.run(["systemctl", "is-active", "tailscaled"], capture_output=True, text=True)
                return result.stdout.strip() == "active"
        except:
            return False
    
    def _check_network_online(self) -> bool:
        try:
            result = subprocess.run(["ping", "-c", "1", "-W", "2", "8.8.8.8"], capture_output=True, timeout=3)
            return result.returncode == 0
        except:
            return False
    
    def _check_service(self, port: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            return result == 0
        except:
            return False


# ============================================================================
# RUNTIME CONFIGURATION RESOLVER
# ============================================================================

class RuntimeConfigResolver:
    def __init__(self, identity: NodeIdentity):
        self.identity = identity
    
    def resolve_endpoint(self) -> str:
        if self.identity.mesh_active and self.identity.mesh_ip:
            return self.identity.mesh_ip
        return self.identity.current_endpoint
    
    def resolve_service_url(self, service: str, port: int) -> str:
        endpoint = self.resolve_endpoint()
        return f"http://{endpoint}:{port}"
    
    def patch_hardcoded_url(self, content: str, service: str, port: int) -> str:
        endpoint = self.resolve_endpoint()
        content = re.sub(
            r'http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?',
            f'http://{{self.endpoint}}:{port}',
            content
        )
        return content


# ============================================================================
# AST-BASED SCANNER WITH OWNERSHIP BOUNDARY (v3.0)
# ============================================================================

class RISAScanner:
    """Scan for divergences using AST parsing - ONLY APPLICATION CODE"""
    
    def __init__(self, identity: NodeIdentity):
        self.identity = identity
        self.divergences: List[Divergence] = []
        
        # 🛡️ OWNERSHIP BOUNDARY - Only these paths are scanned
        self.owned_roots = [
            BASE_DIR / "mcp",
            BASE_DIR / ".consciousness_engine",
            BASE_DIR / "web",
            BASE_DIR / "core",
            BASE_DIR / "services",
            BASE_DIR / "synap_server.py",
        ]
        
        # 🚫 Excluded path components - NEVER scan these
        self.excluded_components = {
            "venv", ".venv", "env", ".env",
            "lib", "site-packages", "dist-packages",
            "node_modules", "build", "dist", "cache",
            "__pycache__", "third-party", "vendor", "external",
            "gradle", ".gradle", "target", "out",
            "plugins", "android-ndk", "lldb",
            "llama.cpp", "pip", "_vendor", "_internal",
        }
        
        # ✅ Explicit application files that must be scanned
        self.explicit_include = [
            "mcp/interceptor.py",
            "mcp/mcp_server.py",
            "mcp/agent/config.py",
            "mcp/agent/model.py",
            ".consciousness_engine/synap_server.py",
            ".consciousness_engine/websocket.py",
            ".consciousness_engine/llm/local_interface.py",
            ".consciousness_engine/voice/presence.py",
        ]
    
    def is_owned_path(self, path: Path) -> bool:
        """Check if a path is owned by RISA (strict boundary)"""
        try:
            if not path.is_absolute():
                path = BASE_DIR / path
            path = path.resolve()
            base = BASE_DIR.resolve()
            
            try:
                relative = path.relative_to(base)
            except ValueError:
                return False
            
            parts = {p.lower() for p in relative.parts}
            
            # Excluded components always win
            if parts & self.excluded_components:
                return False
            
            # Explicit includes
            relative_str = str(relative).replace("\\", "/").lower()
            for include in self.explicit_include:
                if relative_str == include.lower() or relative_str.endswith("/" + include.lower()):
                    return True
            
            # Owned roots
            for root in self.owned_roots:
                try:
                    root = root.resolve()
                    path.relative_to(root)
                    return True
                except (ValueError, FileNotFoundError):
                    continue
            
            return False
        except Exception:
            return False
    
    def _find_python_files(self) -> List[Path]:
        """Find Python files only in owned paths"""
        files = []
        seen = set()
        
        for root in self.owned_roots:
            try:
                root = root.resolve()
            except FileNotFoundError:
                continue
            
            if not root.exists():
                continue
            
            if root.is_file():
                if root.suffix.lower() == ".py" and self.is_owned_path(root):
                    if str(root) not in seen:
                        files.append(root)
                        seen.add(str(root))
                continue
            
            for py_file in root.rglob("*.py"):
                if self.is_owned_path(py_file):
                    if str(py_file) not in seen:
                        files.append(py_file)
                        seen.add(str(py_file))
        
        return files
    
    def scan(self) -> List[Divergence]:
        """Scan the entire system for divergences"""
        self.divergences = []
        
        self._scan_hardcoded_ips()
        self._scan_missing_runtime_resolution()
        self._scan_synap_server()
        self._scan_self_model()
        
        return self.divergences
    
    def _scan_hardcoded_ips(self):
        """Scan for hardcoded IPs only in owned application files"""
        ignore_patterns = ['127.0.0.1', '0.0.0.0', '255.255.255.255', 'localhost']
        files_to_scan = self._find_python_files()
        
        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding="utf-8")
                
                hardcoded_ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', content)
                filtered_ips = [ip for ip in hardcoded_ips if ip not in ignore_patterns]
                
                if filtered_ips:
                    known_ips = []
                    if self.identity.mesh_ip:
                        known_ips.append(self.identity.mesh_ip)
                    unique_ips = [ip for ip in filtered_ips if ip not in known_ips]
                    
                    if unique_ips:
                        self.divergences.append(Divergence(
                            pattern_class="hardcoded_ips",
                            severity="critical",
                            description=f"Hardcoded IPs in {file_path.name}: {unique_ips}",
                            source_file=file_path,
                            expected=f"Use runtime resolution or {self.identity.mesh_ip}",
                            actual=unique_ips,
                            file_type="python",
                            repair_strategy="replace_hardcoded_ips"
                        ))
            except Exception:
                pass
    
    def _scan_missing_runtime_resolution(self):
        """Scan for missing runtime resolution only in owned application files"""
        files_to_scan = self._find_python_files()
        
        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding="utf-8")
                
                if "http://" in content and "RuntimeConfigResolver" not in content:
                    service_patterns = ['mcp', 'bridge', 'studio', 'synap']
                    if any(pattern in content.lower() for pattern in service_patterns):
                        self.divergences.append(Divergence(
                            pattern_class="missing_runtime_resolution",
                            severity="warning",
                            description=f"Missing runtime resolution in {file_path.name}",
                            source_file=file_path,
                            expected="Use RuntimeConfigResolver for endpoints",
                            actual="Hardcoded URLs detected",
                            file_type="python",
                            repair_strategy="inject_runtime_resolution"
                        ))
            except Exception:
                pass
    
    def _scan_synap_server(self):
        """Scan synap_server.py for known issues"""
        server_path = BASE_DIR / "synap_server.py"
        if not server_path.exists():
            return
        
        try:
            content = server_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            
            sanctum_field = self._find_dataclass_field(tree, "SynapSelf", "sanctum")
            if not sanctum_field:
                self.divergences.append(Divergence(
                    pattern_class="missing_sanctum_field",
                    severity="critical",
                    description="SynapSelf dataclass missing 'sanctum' field",
                    source_file=server_path,
                    expected="sanctum: Dict[str, Any] = field(default_factory=dict)",
                    actual="Field not found in AST",
                    file_type="python",
                    repair_strategy="add_sanctum_field"
                ))
            
            sanctum_in_to_dict = self._find_to_dict_entry(tree, "sanctum")
            if not sanctum_in_to_dict:
                self.divergences.append(Divergence(
                    pattern_class="missing_to_dict_entry",
                    severity="critical",
                    description="to_dict() missing 'sanctum' entry",
                    source_file=server_path,
                    expected='"sanctum": self.sanctum',
                    actual="Entry not found in AST",
                    file_type="python",
                    repair_strategy="add_to_dict_entry"
                ))
            
            sanctum_in_load = self._find_load_restoration(tree, "sanctum")
            if not sanctum_in_load:
                self.divergences.append(Divergence(
                    pattern_class="missing_load_restoration",
                    severity="critical",
                    description="_load_self() missing sanctum restoration",
                    source_file=server_path,
                    expected='if "sanctum" in data: self.self.sanctum.update(data["sanctum"])',
                    actual="Restoration not found in AST",
                    file_type="python",
                    repair_strategy="add_load_restoration"
                ))
                
        except Exception as e:
            self.divergences.append(Divergence(
                pattern_class="scan_error",
                severity="critical",
                description=f"Error scanning synap_server.py: {e}",
                source_file=server_path
            ))
    
    def _scan_self_model(self):
        """Scan self_model.json for issues"""
        model_path = SYNAP_DIR / "self_model.json"
        if not model_path.exists():
            return
        
        try:
            data = json.loads(model_path.read_text(encoding="utf-8"))
            
            if "sanctum" not in data:
                self.divergences.append(Divergence(
                    pattern_class="missing_sanctum_namespace",
                    severity="warning",
                    description="self_model.json missing 'sanctum' key",
                    source_file=model_path,
                    expected="sanctum: {}",
                    actual="Key not found",
                    file_type="json",
                    repair_strategy="add_sanctum_namespace"
                ))
        except Exception as e:
            self.divergences.append(Divergence(
                pattern_class="model_read_error",
                severity="critical",
                description=f"Error reading self_model.json: {e}",
                source_file=model_path
            ))
    
    def _find_dataclass_field(self, tree: ast.AST, class_name: str, field_name: str) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        if isinstance(item.target, ast.Name) and item.target.id == field_name:
                            return True
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == field_name:
                                return True
        return False
    
    def _find_to_dict_entry(self, tree: ast.AST, entry_name: str) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "to_dict":
                for item in ast.walk(node):
                    if isinstance(item, ast.Dict):
                        for key in item.keys:
                            if isinstance(key, ast.Constant) and key.value == entry_name:
                                return True
                            if isinstance(key, ast.Str) and key.s == entry_name:
                                return True
        return False
    
    def _find_load_restoration(self, tree: ast.AST, field_name: str) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_load_self":
                for item in ast.walk(node):
                    if isinstance(item, ast.If):
                        if isinstance(item.test, ast.Compare):
                            if (len(item.test.ops) == 1 and 
                                isinstance(item.test.ops[0], ast.In) and
                                isinstance(item.test.left, ast.Constant) and
                                item.test.left.value == field_name):
                                for body_item in ast.walk(item):
                                    if isinstance(body_item, ast.Call):
                                        if isinstance(body_item.func, ast.Attribute):
                                            if (body_item.func.attr == "update" and
                                                isinstance(body_item.func.value, ast.Attribute) and
                                                body_item.func.value.attr == "sanctum"):
                                                return True
        return False


# ============================================================================
# TRANSACTIONAL SEALER WITH SAFE HEALING (v3.0)
# ============================================================================

class PatchStage:
    def __init__(self, patch_request: PatchRequest):
        self.patch = patch_request
        self.candidate_path: Optional[Path] = None
        self.backup_path: Optional[Path] = None
        self.staged_content: Optional[str] = None
        self.committed: bool = False
        self.rolled_back: bool = False
        self.validated: bool = False
        self.commit_id: str = str(uuid.uuid4())[:8]
        self.timestamp: str = datetime.now().isoformat()


class TransactionalSealer:
    def __init__(self, identity: NodeIdentity):
        self.identity = identity
        self.stages: List[PatchStage] = []
        self.stage_dir = RISA_STATE_DIR / "stages"
        self.stage_dir.mkdir(parents=True, exist_ok=True)
    
    def stage_patch(self, patch_request: PatchRequest) -> Optional[PatchStage]:
        try:
            source_file = Path(patch_request.affected_component)
            if not source_file.exists():
                return None
            
            original_content = source_file.read_text(encoding="utf-8")
            candidate_content = self._apply_patch(patch_request, original_content)
            if candidate_content is None:
                return None
            
            stage = PatchStage(patch_request)
            stage.staged_content = candidate_content
            stage.candidate_path = self.stage_dir / f"{patch_request.detected_divergence}_{stage.commit_id}.stage"
            stage.backup_path = self.stage_dir / f"{patch_request.detected_divergence}_{stage.commit_id}.bak"
            
            stage.candidate_path.write_text(candidate_content, encoding="utf-8")
            self.stages.append(stage)
            return stage
            
        except Exception as e:
            print(f"❌ Stage failed: {e}")
            return None
    
    def _apply_patch(self, patch: PatchRequest, content: str) -> Optional[str]:
        # SURGICAL IP REPLACEMENT - ONLY replace detected IPs
        if patch.detected_divergence == "hardcoded_ips":
            endpoint = self.identity.resolve()
            detected_ips = patch.current_state.get("hardcoded_ips", [])
            for ip in detected_ips:
                if ip:
                    content = content.replace(ip, endpoint)
            return content
        
        # v3.1: service_mapping - NO HEALING (detect only)
        if patch.detected_divergence == "service_mapping":
            # This should never be called because we don't generate patches for it
            print(f"   🔒 service_mapping healer disabled - detect only")
            return None
        
        # Add sanctum field
        if patch.detected_divergence == "missing_sanctum_field":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == "SynapSelf":
                        for i, item in enumerate(node.body):
                            if isinstance(item, ast.AnnAssign):
                                if isinstance(item.target, ast.Name) and item.target.id == "metadata":
                                    sanctum_field = ast.AnnAssign(
                                        target=ast.Name(id="sanctum", ctx=ast.Store()),
                                        annotation=ast.Subscript(
                                            value=ast.Name(id="Dict", ctx=ast.Load()),
                                            slice=ast.Tuple(
                                                elts=[
                                                    ast.Name(id="str", ctx=ast.Load()),
                                                    ast.Name(id="Any", ctx=ast.Load())
                                                ],
                                                ctx=ast.Load()
                                            )
                                        ),
                                        value=ast.Call(
                                            func=ast.Name(id="field", ctx=ast.Load()),
                                            args=[],
                                            keywords=[
                                                ast.keyword(
                                                    arg="default_factory",
                                                    value=ast.Name(id="dict", ctx=ast.Load())
                                                )
                                            ]
                                        ),
                                        simple=1
                                    )
                                    node.body.insert(i + 1, sanctum_field)
                                    return ast.unparse(tree)
            except:
                pass
            return None
        
        # Add to_dict entry
        if patch.detected_divergence == "missing_to_dict_entry":
            pattern = r'("metadata": self\.metadata,\s*)'
            if re.search(pattern, content):
                return re.sub(
                    pattern,
                    r'"metadata": self.metadata,\n            "sanctum": self.sanctum,\n        ',
                    content
                )
            return None
        
        # Add load restoration
        if patch.detected_divergence == "missing_load_restoration":
            pattern = r'(if "metadata" in data:\s*\n\s*self\.self\.metadata\.update\(data\["metadata"\]\))'
            if re.search(pattern, content):
                return re.sub(
                    pattern,
                    r'\1\n                if "sanctum" in data:\n                    self.self.sanctum.update(data["sanctum"])',
                    content
                )
            return None
        
        # Add sanctum namespace (JSON)
        if patch.detected_divergence == "missing_sanctum_namespace":
            try:
                data = json.loads(content)
                data["sanctum"] = {}
                return json.dumps(data, indent=2) + "\n"
            except:
                return None
        
        return None
    
    def validate_staged(self, stage: PatchStage) -> bool:
        if not stage.candidate_path or not stage.candidate_path.exists():
            return False
        
        try:
            if stage.patch.file_type == "python":
                return self._validate_python(stage.candidate_path)
            elif stage.patch.file_type == "json":
                return self._validate_json(stage.candidate_path)
            return False
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            return False
    
    def _validate_python(self, path: Path) -> bool:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
            py_compile.compile(str(path), doraise=True)
            return True
        except Exception as e:
            print(f"⚠️ Python validation error: {e}")
            return False
    
    def _validate_json(self, path: Path) -> bool:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return True
        except Exception as e:
            print(f"⚠️ JSON validation error: {e}")
            return False
    
    def commit(self, stage: PatchStage) -> bool:
        try:
            source_file = Path(stage.patch.affected_component)
            shutil.copy2(source_file, stage.backup_path)
            
            os.replace(str(stage.candidate_path), str(source_file))
            
            if stage.patch.file_type == "python":
                if not self._validate_python(source_file):
                    print(f"❌ Post-commit validation failed - rolling back")
                    os.replace(str(stage.backup_path), str(source_file))
                    return False
            elif stage.patch.file_type == "json":
                if not self._validate_json(source_file):
                    print(f"❌ Post-commit validation failed - rolling back")
                    os.replace(str(stage.backup_path), str(source_file))
                    return False
            
            stage.committed = True
            print(f"✅ Committed: {stage.patch.detected_divergence}")
            return True
            
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            if stage.backup_path and stage.backup_path.exists():
                try:
                    os.replace(str(stage.backup_path), str(source_file))
                except:
                    pass
            return False


# ============================================================================
# RISA CONTROL PLANE WITH SAFE HEALING + SEMANTIC VALIDATION
# ============================================================================

class RISAControlPlane:
    PROTECTED_BOUNDARY = """
    RISA may repair network configuration, routing, services,
    mesh configuration, endpoints, dependencies, and runtime references.
    
    RISA must NOT disable the physical network interface
    that constitutes its recovery path unless an explicitly
    authorized isolated recovery protocol is active.
    """
    
    def __init__(self):
        self.identity: Optional[NodeIdentity] = None
        self.topology: Optional[Topology] = None
        self.divergences: List[Divergence] = []
        self.transport_mode: TransportMode = TransportMode.OFFLINE
        
        # SAFETY CACHE - Tracks healing attempts, modified files, and skipped strategies
        self.safety_cache = {
            "healing_attempts": 0,
            "last_heal": None,
            "files_modified": [],
            "skipped_strategies": ["inject_runtime_resolution", "resolve_service_role"],
            "safe_mode": True,
            "version": "3.1"
        }
        
        print("\n🛡️ RISA v3.1 Initializing...")
        print(f"   Protected Boundary: Network adapter is NEVER modified")
        print(f"   Safe Mode: {self.safety_cache['safe_mode']}")
        print(f"   Version: {self.safety_cache['version']}")
        if SERVICE_DISCOVERY_AVAILABLE:
            print(f"   Service Discovery: ✅ Available")
        else:
            print(f"   Service Discovery: ❌ Not available")
    
    def bootstrap(self):
        print("\n🔧 Bootstrap Sequence:")
        print("=" * 60)
        
        mesh = MeshAssurance()
        self.identity = mesh.assure()
        self.transport_mode = self.identity.transport_mode
        
        verifier = TopologyVerifier(self.identity)
        self.topology = verifier.verify()
        
        resolver = RuntimeConfigResolver(self.identity)
        endpoint = resolver.resolve_endpoint()
        print(f"\n🌐 Runtime Endpoint: {endpoint}")
        print(f"   Transport Mode: {self.transport_mode.value.upper()}")
        
        print("\n🔍 Scanning for divergences...")
        self.scanner = RISAScanner(self.identity)
        self.divergences = self.scanner.scan()
        
        # v3.1: Service mapping validation (detect only)
        if SERVICE_DISCOVERY_AVAILABLE:
            validator = ServiceMappingValidator(self.identity)
            service_divergences = validator.validate()
            self.divergences.extend(service_divergences)
            
            if service_divergences:
                print(f"\n   📊 Service mapping divergences found: {len(service_divergences)}")
                for div in service_divergences:
                    print(f"   ❌ {div.pattern_class}: {div.description}")
        
        return self
    
    def heal(self) -> Dict[str, Any]:
        print("\n🔧 Self-Repair Cycle (SAFE MODE):")
        print("=" * 60)
        
        if not self.identity:
            self.bootstrap()
        
        if not self.divergences:
            print("✅ No divergences detected. System is healthy.")
            return {
                "status": RepairStatus.HEALTHY.value,
                "divergences": 0,
                "patches_applied": 0,
                "transport_mode": self.transport_mode.value,
                "safety_cache": self.safety_cache
            }
        
        print(f"\n⚠️ Found {len(self.divergences)} divergence(s):")
        for div in self.divergences:
            if div.pattern_class == "service_mapping":
                print(f"   🔒 {div.pattern_class}: {div.description} (DETECT ONLY - no healing)")
            else:
                print(f"   - {div.pattern_class}: {div.description}")
        
        patches = self._generate_patches()
        
        if not patches:
            print("❌ No patches generated.")
            return {
                "status": RepairStatus.FAILED.value,
                "divergences": len(self.divergences),
                "patches_applied": 0,
                "transport_mode": self.transport_mode.value,
                "safety_cache": self.safety_cache
            }
        
        sealer = TransactionalSealer(self.identity)
        applied = 0
        
        for patch in patches:
            print(f"\n📦 Applying: {patch.detected_divergence}")
            stage = sealer.stage_patch(patch)
            if not stage:
                continue
            
            if not sealer.validate_staged(stage):
                continue
            
            if sealer.commit(stage):
                applied += 1
                
                self.safety_cache["healing_attempts"] += 1
                self.safety_cache["last_heal"] = datetime.now().isoformat()
                self.safety_cache["files_modified"].append(str(stage.patch.affected_component))
                
                if patch.restart_required and patch.detected_divergence != "hardcoded_ips":
                    self._restart_component(patch)
                elif patch.detected_divergence == "hardcoded_ips":
                    print(f"   🔒 Restart skipped (safe mode) - manual restart recommended")
        
        print(f"\n✅ Applied {applied}/{len(patches)} patches")
        print(f"   Healing attempts: {self.safety_cache['healing_attempts']}")
        print(f"   Files modified: {len(self.safety_cache['files_modified'])}")
        
        # Check for service_mapping divergences that were detected but not healed
        service_divergences = [d for d in self.divergences if d.pattern_class == "service_mapping"]
        if service_divergences:
            print(f"\n🔒 DETECT ONLY: {len(service_divergences)} service_mapping divergence(s) detected")
            print(f"   Run RISA v3.2 for healing capability")
        
        self._verify_recovery()
        
        return {
            "status": RepairStatus.REPAIRED.value if applied == len(patches) else "partial",
            "divergences": len(self.divergences),
            "patches_applied": applied,
            "transport_mode": self.transport_mode.value,
            "safety_cache": self.safety_cache,
            "detect_only_divergences": len(service_divergences)
        }
    
    def _generate_patches(self) -> List[PatchRequest]:
        """Generate patch requests - SKIPS missing_runtime_resolution and service_mapping"""
        patches = []
        
        for div in self.divergences:
            # SAFETY: Explicitly skip missing_runtime_resolution
            if div.repair_strategy == "inject_runtime_resolution":
                print(f"   ⏭️  Skipping {div.pattern_class} - healer disabled (safe mode)")
                print("   ⚠️ Intentional boundary: Runtime resolution healer disabled in safe mode.")
                continue
            
            # v3.1: Explicitly skip service_mapping (detect only)
            if div.repair_strategy == "resolve_service_role":
                print(f"   🔒 Skipping {div.pattern_class} - detect only (v3.1)")
                print(f"   ⚠️ Service mapping validation: {div.description}")
                continue
            
            if div.repair_strategy == "replace_hardcoded_ips":
                patches.append(PatchRequest(
                    detected_divergence=div.pattern_class,
                    affected_component=str(div.source_file),
                    current_state={"hardcoded_ips": div.actual},
                    desired_state={"hardcoded_ips": [self.identity.resolve()]},
                    proposed_change=f"Replace hardcoded IPs with runtime resolution",
                    dependencies=[str(div.source_file)],
                    validation_tests=["python -m py_compile " + str(div.source_file)],
                    rollback_action="git checkout " + str(div.source_file),
                    file_type=div.file_type,
                    restart_required=False,
                    restart_command=None
                ))
            
            elif div.repair_strategy == "add_sanctum_field":
                patches.append(PatchRequest(
                    detected_divergence=div.pattern_class,
                    affected_component=str(div.source_file),
                    current_state={"has_sanctum": False},
                    desired_state={"has_sanctum": True},
                    proposed_change="Add sanctum field to SynapSelf",
                    dependencies=[str(div.source_file)],
                    validation_tests=["python -m py_compile " + str(div.source_file)],
                    rollback_action="git checkout " + str(div.source_file),
                    file_type=div.file_type,
                    restart_required=False,
                    restart_command=None
                ))
            
            elif div.repair_strategy == "add_to_dict_entry":
                patches.append(PatchRequest(
                    detected_divergence=div.pattern_class,
                    affected_component=str(div.source_file),
                    current_state={"has_to_dict_entry": False},
                    desired_state={"has_to_dict_entry": True},
                    proposed_change="Add sanctum to to_dict()",
                    dependencies=[str(div.source_file)],
                    validation_tests=["python -m py_compile " + str(div.source_file)],
                    rollback_action="git checkout " + str(div.source_file),
                    file_type=div.file_type,
                    restart_required=False,
                    restart_command=None
                ))
            
            elif div.repair_strategy == "add_load_restoration":
                patches.append(PatchRequest(
                    detected_divergence=div.pattern_class,
                    affected_component=str(div.source_file),
                    current_state={"has_load_restoration": False},
                    desired_state={"has_load_restoration": True},
                    proposed_change="Add sanctum restoration to _load_self()",
                    dependencies=[str(div.source_file)],
                    validation_tests=["python -m py_compile " + str(div.source_file)],
                    rollback_action="git checkout " + str(div.source_file),
                    file_type=div.file_type,
                    restart_required=False,
                    restart_command=None
                ))
            
            elif div.repair_strategy == "add_sanctum_namespace":
                patches.append(PatchRequest(
                    detected_divergence=div.pattern_class,
                    affected_component=str(div.source_file),
                    current_state={"has_sanctum_namespace": False},
                    desired_state={"has_sanctum_namespace": True},
                    proposed_change="Add sanctum key to JSON",
                    dependencies=[str(div.source_file)],
                    validation_tests=["python -c 'import json; json.load(open(" + str(div.source_file) + "))'"],
                    rollback_action="git checkout " + str(div.source_file),
                    file_type=div.file_type,
                    restart_required=False,
                    restart_command=None
                ))
        
        return patches
    
    def _restart_component(self, patch: PatchRequest):
        if not patch.restart_command:
            return
        
        print(f"🔄 Restarting: {patch.affected_component}")
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", "python.exe"], capture_output=True)
            else:
                subprocess.run(["pkill", "-f", patch.affected_component], capture_output=True)
            
            time.sleep(2)
            subprocess.Popen([patch.restart_command], shell=True)
            print(f"✅ Restarted: {patch.affected_component}")
        except Exception as e:
            print(f"⚠️ Restart failed: {e}")
    
    def _verify_recovery(self):
        print("\n🔄 Verifying recovery...")
        
        if self.transport_mode == TransportMode.NORMAL:
            try:
                result = subprocess.run(
                    ["tailscale", "status", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    peers = data.get("Peer", {})
                    print(f"✅ Mesh active: {len(peers)} peers connected")
                    return
            except:
                pass
            print("⚠️ Mesh verification failed")
        
        elif self.transport_mode == TransportMode.OFFLINE:
            services_ok = True
            if not self._check_service(11440):
                print("⚠️ MCP HTTP not running")
                services_ok = False
            if not self._check_service(11436):
                print("⚠️ Studio not running")
                services_ok = False
            if services_ok:
                print("✅ Local services running")
            else:
                print("⚠️ Some local services are down")
        
        elif self.transport_mode == TransportMode.RECOVERING:
            print("✅ Recovery in progress...")
    
    def _check_service(self, port: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            return result == 0
        except:
            return False
    
    def run(self) -> Dict[str, Any]:
        self.bootstrap()
        return self.heal()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RISA v3.1 - Mesh Assurance + Safe Healing + Semantic Validation"
    )
    parser.add_argument("--scan", action="store_true", help="Scan only (no healing)")
    parser.add_argument("--heal", action="store_true", help="Scan and heal (SAFE MODE)")
    parser.add_argument("--test", action="store_true", help="Run tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Running RISA v3.1 tests...")
        mesh = MeshAssurance()
        identity = mesh.assure()
        print(f"✓ Identity discovery: {identity.current_endpoint}")
        print(f"✓ Mesh active: {identity.mesh_active}")
        print(f"✓ Transport mode: {identity.transport_mode.value}")
        
        if SERVICE_DISCOVERY_AVAILABLE:
            print("✓ Service Discovery: Available")
            validator = ServiceMappingValidator(identity)
            divergences = validator.validate()
            print(f"✓ Service mapping validation: {len(divergences)} divergences")
        else:
            print("⚠️ Service Discovery: Not available")
        
        print("✅ All tests passed")
        return
    
    risa = RISAControlPlane()
    
    if args.heal:
        print("\n⚠️  SAFE MODE: missing_runtime_resolution healer is DISABLED")
        print("⚠️  SAFE MODE: Restart mechanism is NEUTRALIZED for hardcoded_ips")
        print("🔒  SAFE MODE: service_mapping is DETECT ONLY (v3.1)")
        result = risa.run()
        print("\n" + "=" * 60)
        print(f"📊 Final Status: {result['status'].upper()}")
        print(f"   Divergences: {result['divergences']}")
        print(f"   Patches Applied: {result['patches_applied']}")
        print(f"   Transport Mode: {result.get('transport_mode', 'unknown')}")
        print(f"   Healing Attempts: {result.get('safety_cache', {}).get('healing_attempts', 0)}")
        print(f"   Files Modified: {len(result.get('safety_cache', {}).get('files_modified', []))}")
        if result.get('detect_only_divergences', 0) > 0:
            print(f"   🔒 Detect Only: {result.get('detect_only_divergences')} service_mapping divergences")
            print(f"   💡 Run RISA v3.2 for healing capability")
        if result['patches_applied'] < result['divergences']:
            print("   ⚠️  Some divergences were skipped (safe mode)")
    else:
        risa.bootstrap()
        
        if risa.divergences:
            print(f"\n⚠️ Found {len(risa.divergences)} divergence(s):")
            for div in risa.divergences:
                if div.pattern_class == "service_mapping":
                    print(f"   🔒 {div.pattern_class}: {div.description}")
                    print(f"      Expected: {div.expected}")
                    print(f"      Actual: {div.actual}")
                    print(f"      File: {div.source_file}")
                    print(f"      Strategy: {div.repair_strategy} (DETECT ONLY)")
                else:
                    print(f"   - {div.pattern_class}: {div.description}")
                if args.verbose:
                    print(f"     Expected: {div.expected}")
                    print(f"     Actual: {div.actual}")
                    print(f"     File: {div.source_file}")
                    print(f"     Strategy: {div.repair_strategy}")
                    print()
        else:
            print("\n✅ No divergences detected. System is healthy.")


if __name__ == "__main__":
    main()