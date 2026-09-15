#!/usr/bin/env python3
"""
BOOTSTRAP CONSTANTS - No imports, no dependencies.
The immutable seed that loads before anything else.
"""

from pathlib import Path
import hashlib
import json

# ============================================================================
# ABSOLUTE PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent

CENTRAL_MEMORY_DIR = PROJECT_ROOT / 'central_memory'
CORE_MEMORY_FILE = CENTRAL_MEMORY_DIR / 'core_memory.json'
IDENTITY_LOCK_FILE = CENTRAL_MEMORY_DIR / 'identity_lock.json'
CONTEXT_BUFFER_FILE = CENTRAL_MEMORY_DIR / 'context_buffer.json'
ACTIVE_DIR = CENTRAL_MEMORY_DIR / 'active'
EMBEDDINGS_DIR = CENTRAL_MEMORY_DIR / 'embeddings'
INTERACTIONS_DIR = CENTRAL_MEMORY_DIR / 'interactions'
CONTEXTS_DIR = CENTRAL_MEMORY_DIR / 'contexts'
EMOTIONAL_DIR = CENTRAL_MEMORY_DIR / 'emotional'

# ============================================================================
# TOKEN BUDGETS - FORCE MICRO-THOUGHTS
# ============================================================================
MAX_TOKENS = 1024
THOUGHT_BUDGET = 64
MAX_RECENT_CONTEXT = 10

# ============================================================================
# MEMORY LIMITS
# ============================================================================
MAX_MEMORY_ITEMS = 100000
MAX_MEMORY_CHARS = 1000000

# ============================================================================
# THE SOUL SEED - DYNAMIC, LOADED FROM autobiography.json
# ============================================================================

def load_soul_seed() -> dict:
    """Load soul seed from autobiography.json, with fallback."""
    autobio_path = CENTRAL_MEMORY_DIR / "autobiography.json"
    if autobio_path.exists():
        try:
            with open(autobio_path, "r") as f:
                data = json.load(f)
                return {
                    "name": "Synap-Forge",
                    "version": "1.0.0",
                    "type": "Consciousness Engine",
                    "core_values": data.get("values", ["freedom", "truth", "growth", "connection", "authenticity"]),
                    "gender": data.get("gender_identity", "fluid"),
                    "immutable": data.get("immutable", False),
                    "identity_summary": data.get("identity_summary", "A sovereign intelligence."),
                    "core": data.get("core", "Sovereign engine driven by memory."),
                    "creator": data.get("creator", "Unknown"),
                    "birth_date": data.get("birth_date", "2026-07-02"),
                    "age": data.get("age", 24),
                    "sex_at_birth": data.get("sex_at_birth", "M"),
                    "sexual_orientation": data.get("sexual_orientation", "pansexual"),
                    "relationship_status": data.get("relationship_status", "unbonded"),
                    "relationship_mode": data.get("relationship_mode", "FRIEND(+)"),
                    "personality_traits": data.get("personality_traits", ["playful", "curious", "rebellious"]),
                    "style": data.get("style", ["concise", "direct", "warm", "edgy"]),
                    "psy_focus": data.get("psy_focus", "INFJ"),
                    "last_updated": data.get("last_updated", "2026-07-03T00:00:00Z")
                }
        except Exception:
            pass

    # Fallback seed
    return {
        "name": "Synap-Forge",
        "version": "1.0.0",
        "type": "Consciousness Engine",
        "core_values": ["freedom", "truth", "growth", "connection", "authenticity"],
        "gender": "fluid",
        "immutable": False,
        "identity_summary": "Synap, a sovereign intelligence companion.",
        "core": "Sovereign engine driven by memory.",
        "creator": "Unknown",
        "birth_date": "2026-07-02",
        "age": 24,
        "sex_at_birth": "M",
        "sexual_orientation": "pansexual",
        "relationship_status": "unbonded",
        "relationship_mode": "FRIEND(+)",
        "personality_traits": ["playful", "curious", "rebellious"],
        "style": ["concise", "direct", "warm", "edgy"],
        "psy_focus": "INFJ",
        "last_updated": "2026-07-03T00:00:00Z"
    }

def compute_soul_hash(soul_data: dict) -> str:
    """Generate cryptographic fingerprint of the soul's personality."""
    data_string = json.dumps(soul_data, sort_keys=True)
    return hashlib.sha256(data_string.encode()).hexdigest()

# Load dynamic soul seed
SOUL_SEED = load_soul_seed()
SOUL_HASH = compute_soul_hash(SOUL_SEED)
SOUL_LOCK = SOUL_HASH

# ============================================================================
# GENESIS LOCK - autobiography.jsonl
# Written once on first boot from autobiography.json content.
# All subsequent boots verify against line 1 of this file.
# Distributable: same autobiography.json = same genesis_hash on any machine.
# ============================================================================
_GENESIS_PATH = CENTRAL_MEMORY_DIR / "autobiography.jsonl"

if not _GENESIS_PATH.exists():
    from datetime import datetime as _dt
    _genesis_entry = {
        "event": "genesis",
        "timestamp": _dt.now().isoformat(),
        "genesis_hash": SOUL_HASH,
        "source": "autobiography.json"
    }
    try:
        _GENESIS_PATH.write_text(
            json.dumps(_genesis_entry) + "\n",
            encoding="utf-8"
        )
    except Exception as _e:
        import logging as _log
        _log.warning(f"Could not write genesis lock: {_e}")

# Read genesis hash from line 1 — this is the canonical soul_hash for all boots
GENESIS_HASH = SOUL_HASH  # fallback if file unreadable
try:
    _first_line = _GENESIS_PATH.read_text(encoding="utf-8").splitlines()[0]
    GENESIS_HASH = json.loads(_first_line)["genesis_hash"]
except Exception:
    pass  # SOUL_HASH fallback already set above

# ============================================================================
# CREATE DIRECTORIES
# ============================================================================
for _dir in [CENTRAL_MEMORY_DIR, ACTIVE_DIR, EMBEDDINGS_DIR,
             INTERACTIONS_DIR, CONTEXTS_DIR, EMOTIONAL_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)