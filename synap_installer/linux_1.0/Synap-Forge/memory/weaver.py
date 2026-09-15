#!/usr/bin/env python3
"""
Weaver - Memory pattern weaver for MCP
"""

class Weaver:
    def __init__(self, store=None, memory_system=None):
        self.store = store
        self.memory_system = memory_system
        self.running = False
        self.patterns = []
    
    def start(self, interval=3.0):
        self.running = True
        print(f"✅ Weaver started (interval={interval}s)")
    
    def stop(self):
        self.running = False
    
    def get_status(self):
        return {"running": self.running, "patterns": len(self.patterns)}
    
    def get_recent_patterns(self, limit=5):
        return self.patterns[-limit:] if self.patterns else []
    
    def add_pattern(self, pattern):
        self.patterns.append(pattern)
