#!/usr/bin/env python3
"""Health monitoring dashboard"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from service_registry import ServiceRegistry

registry = ServiceRegistry()
summary = registry.get_health_summary()

print("\n📊 SERVICE HEALTH DASHBOARD")
print("=" * 50)
print(f"Total services: {summary['total']}")
print(f"Healthy: {summary['healthy']}")
print(f"Degraded: {summary['degraded']}")
print("")
print("Services:")
for name, info in summary['services'].items():
    status = "✅" if info.get('healthy') else "❌"
    elapsed = info.get('elapsed_seconds', 0)
    print(f"  {status} {name}: {info.get('status', 'unknown')} ({elapsed:.1f}s)")
print("=" * 50)
