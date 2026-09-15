#!/usr/bin/env python3
"""
RISA v3.2 - Runtime Topology Module
Consumes role_map.json and provides role-based endpoint resolution.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class ServiceEndpoint:
    """A resolved service endpoint with protocol and address"""
    role: str
    host: str
    port: int
    protocol: str = "http"
    
    @property
    def http_url(self) -> str:
        """HTTP URL for this endpoint"""
        if self.protocol == "http" or self.protocol == "https":
            return f"{self.protocol}://{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"
    
    @property
    def ws_url(self) -> str:
        """WebSocket URL for this endpoint"""
        if self.protocol == "ws" or self.protocol == "wss":
            return f"{self.protocol}://{self.host}:{self.port}"
        return f"ws://{self.host}:{self.port}"
    
    @property
    def address(self) -> str:
        """Raw host:port address"""
        return f"{self.host}:{self.port}"


class RuntimeTopology:
    """
    Runtime topology from discovered services.
    Consumes role_map.json and provides role-based resolution.
    """
    
    def __init__(self, role_map: Dict[str, int], host: str):
        self.role_map = role_map
        self.host = host
        self._endpoints: Dict[str, ServiceEndpoint] = {}
        self._build_endpoints()
    
    @classmethod
    def from_discovery(cls, role_map_path: Path, host: str) -> "RuntimeTopology":
        """Load topology from role_map.json"""
        if not role_map_path.exists():
            raise FileNotFoundError(f"role_map.json not found at {role_map_path}")
        
        with open(role_map_path, 'r') as f:
            role_map = json.load(f)
        
        return cls(role_map, host)
    
    def _build_endpoints(self):
        """Build endpoint objects from role map"""
        # Role to protocol mapping
        role_protocols = {
            "studio": "http",
            "mcp_http": "http",
            "mcp_ws": "ws",
            "ollama": "http",
        }
        
        for role, port in self.role_map.items():
            protocol = role_protocols.get(role, "http")
            self._endpoints[role] = ServiceEndpoint(
                role=role,
                host=self.host,
                port=port,
                protocol=protocol
            )
    
    def resolve(self, role: str) -> Optional[ServiceEndpoint]:
        """Resolve a role to its endpoint, returns None if not found"""
        return self._endpoints.get(role)
    
    def require(self, role: str) -> ServiceEndpoint:
        """Resolve a role to its endpoint, raises KeyError if not found"""
        if role not in self._endpoints:
            raise KeyError(f"Role '{role}' not found in topology. Available: {list(self._endpoints.keys())}")
        return self._endpoints[role]
    
    def validate_mapping(self, role: str, url: str) -> tuple[bool, str]:
        """
        Validate that a URL matches the expected endpoint for a role.
        Returns (is_valid, message)
        """
        try:
            endpoint = self.require(role)
            expected_url = endpoint.http_url
            
            if url == expected_url:
                return True, f"Correct: {url} → {role}"
            else:
                # Check if it's pointing to the wrong role
                for other_role, other_endpoint in self._endpoints.items():
                    if url == other_endpoint.http_url:
                        return False, f"Wrong role: {url} → {other_role}, expected {role}"
                
                return False, f"Unknown endpoint: {url}, expected {expected_url}"
                
        except KeyError as e:
            return False, str(e)
    
    def get_http_ports(self) -> Dict[str, int]:
        """Get all HTTP service ports"""
        return {role: endpoint.port for role, endpoint in self._endpoints.items() 
                if endpoint.protocol in ["http", "https"]}
    
    def get_ws_ports(self) -> Dict[str, int]:
        """Get all WebSocket service ports"""
        return {role: endpoint.port for role, endpoint in self._endpoints.items()
                if endpoint.protocol in ["ws", "wss"]}
    
    def to_dict(self) -> Dict[str, Any]:
        """Export topology as dictionary"""
        return {
            "host": self.host,
            "services": {
                role: {
                    "port": endpoint.port,
                    "protocol": endpoint.protocol,
                    "http_url": endpoint.http_url,
                    "ws_url": endpoint.ws_url if endpoint.protocol in ["ws", "wss"] else None
                }
                for role, endpoint in self._endpoints.items()
            }
        }


# ============================================================================
# TEST
# ============================================================================

def test_runtime_topology():
    """Test RuntimeTopology with the known role_map.json"""
    print("🧪 Testing RuntimeTopology...")
    print("=" * 60)
    
    # Load topology
    topology = RuntimeTopology.from_discovery(
        Path("role_map.json"),
        "127.0.0.1"
    )
    
    print("📋 Loaded topology:")
    for role, endpoint in topology._endpoints.items():
        print(f"   {role} → {endpoint.address} ({endpoint.protocol})")
    
    print("\n🔍 Validating mappings:")
    
    # Test 1: Wrong mapping - MCP_URL pointing to studio
    wrong_url = "http://127.0.0.1:11436"
    is_valid, message = topology.validate_mapping("mcp_http", wrong_url)
    print(f"   Test 1: {wrong_url} → mcp_http: {message}")
    assert is_valid == False, "Test 1 should fail"
    
    # Test 2: Correct mapping
    correct_url = "http://127.0.0.1:11440"
    is_valid, message = topology.validate_mapping("mcp_http", correct_url)
    print(f"   Test 2: {correct_url} → mcp_http: {message}")
    assert is_valid == True, "Test 2 should pass"
    
    # Test 3: BRIDGE_URL mapping
    bridge_url = "http://127.0.0.1:11436"
    is_valid, message = topology.validate_mapping("studio", bridge_url)
    print(f"   Test 3: {bridge_url} → studio: {message}")
    assert is_valid == True, "Test 3 should pass"
    
    print("\n✅ All tests passed!")
    
    # Print resolved endpoints
    print("\n📊 Resolved endpoints:")
    print(f"   BRIDGE_URL  → {topology.require('studio').http_url}")
    print(f"   MCP_URL     → {topology.require('mcp_http').http_url}")
    print(f"   MCP_WS_URL  → {topology.require('mcp_ws').ws_url}")
    
    return topology


if __name__ == "__main__":
    test_runtime_topology()