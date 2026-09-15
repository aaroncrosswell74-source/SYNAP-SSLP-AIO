#!/usr/bin/env python3
"""Test the full agent with gateway tools"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agent.agent import run_agent
import json

payload = {
    "messages": [
        {"role": "user", "content": "List the connected Android devices using adb_devices tool"}
    ]
}

print("🧪 Testing full agent with gateway...")
response, status = run_agent(payload)

print(f"Status: {status}")
print(f"Response: {json.dumps(response, indent=2)[:500]}...")
