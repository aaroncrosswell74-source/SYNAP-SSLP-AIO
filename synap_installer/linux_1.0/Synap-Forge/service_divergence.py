#!/usr/bin/env python3
"""
RISA v3.1 - Service Mapping Divergence Detector
Compares interceptor configuration against semantic topology.
"""

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ServiceMappingDivergence:
    """Divergence between interceptor config and semantic topology"""
    service_name: str
    configured_url: str
    expected_port: int
    configured_port: int
    description: str
    severity: str  # "critical", "warning", "info"
    file_path: str
    line_number: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "service_name": self.service_name,
            "configured_url": self.configured_url,
            "expected_port": self.expected_port,
            "configured_port": self.configured_port,
            "description": self.description,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_number": self.line_number
        }


# ============================================================================
# DIVERGENCE DETECTOR
# ============================================================================

class ServiceMappingDetector:
    """Detect service mapping divergences"""
    
    def __init__(self, role_map: Dict[str, int]):
        self.role_map = role_map
        self.divergences: List[ServiceMappingDivergence] = []
        
        # Known interceptor config patterns
        self.config_patterns = {
            "BRIDGE_URL": {"service": "studio", "role": "studio"},
            "MCP_URL": {"service": "mcp_http", "role": "mcp_http"},
            "MCP_WS_URL": {"service": "mcp_ws", "role": "mcp_ws"},
        }
    
    def scan_interceptor(self) -> List[ServiceMappingDivergence]:
        """Scan interceptor.py for service mapping divergences"""
        interceptor_path = Path("mcp/interceptor.py")
        if not interceptor_path.exists():
            interceptor_path = Path("interceptor.py")
            if not interceptor_path.exists():
                print("❌ interceptor.py not found")
                return []
        
        print("\n🔍 Scanning interceptor.py for service mapping divergences...")
        print("=" * 60)
        
        content = interceptor_path.read_text(encoding="utf-8")
        
        for pattern, config in self.config_patterns.items():
            divergence = self._check_pattern(content, pattern, config, interceptor_path)
            if divergence:
                self.divergences.append(divergence)
                self._print_divergence(divergence)
        
        return self.divergences
    
    def _check_pattern(self, content: str, pattern: str, config: Dict, file_path: Path) -> Optional[ServiceMappingDivergence]:
        """Check a specific config pattern"""
        # Find the line
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if pattern in line and "http://" in line:
                # Extract URL
                url_match = re.search(r'http://([\d.]+):(\d+)', line)
                if url_match:
                    host, port_str = url_match.groups()
                    configured_port = int(port_str)
                    expected_port = self.role_map.get(config["role"])
                    
                    if expected_port is None:
                        return ServiceMappingDivergence(
                            service_name=config["service"],
                            configured_url=f"http://{host}:{configured_port}",
                            expected_port=0,
                            configured_port=configured_port,
                            description=f"Unknown service role '{config['role']}'",
                            severity="warning",
                            file_path=str(file_path),
                            line_number=i + 1
                        )
                    
                    if configured_port != expected_port:
                        return ServiceMappingDivergence(
                            service_name=config["service"],
                            configured_url=f"http://{host}:{configured_port}",
                            expected_port=expected_port,
                            configured_port=configured_port,
                            description=f"Service '{config['service']}' configured on port {configured_port}, but topology expects {expected_port}",
                            severity="critical",
                            file_path=str(file_path),
                            line_number=i + 1
                        )
                    else:
                        print(f"   ✅ {pattern}: correctly mapped to port {configured_port}")
                        return None
        
        # Pattern not found in file
        return None
    
    def _print_divergence(self, div: ServiceMappingDivergence):
        """Print a divergence"""
        emoji = "❌" if div.severity == "critical" else "⚠️"
        print(f"   {emoji} {div.service_name}: {div.description}")
        print(f"      Line {div.line_number}: {div.configured_url}")


# ============================================================================
# MAIN - Full Validation Pipeline
# ============================================================================

def main():
    """Run the full semantic topology validation"""
    print("🛡️ RISA v3.1 - Semantic Topology Validation")
    print("=" * 60)
    
    # 1. Load role map
    role_map_path = Path("role_map.json")
    if not role_map_path.exists():
        print("❌ role_map.json not found. Run service_probe.py first.")
        return
    
    role_map = json.loads(role_map_path.read_text())
    print(f"📋 Loaded role map: {role_map}")
    
    # 2. Scan interceptor
    detector = ServiceMappingDetector(role_map)
    divergences = detector.scan_interceptor()
    
    # 3. Summary
    print("\n" + "=" * 60)
    if divergences:
        print(f"❌ Found {len(divergences)} service mapping divergence(s):")
        for div in divergences:
            print(f"   • {div.service_name}: {div.description}")
        print(f"\n💡 Expected topology:")
        for role, port in role_map.items():
            print(f"   • {role} → port {port}")
    else:
        print("✅ No service mapping divergences found.")
    
    # 4. Save divergence report
    report_path = Path("divergence_report.json")
    report_path.write_text(json.dumps(
        [d.to_dict() for d in divergences],
        indent=2
    ))
    print(f"\n📄 Divergence report written to: {report_path}")
    
    return divergences


if __name__ == "__main__":
    main()