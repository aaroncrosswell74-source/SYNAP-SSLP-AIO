# /home/aaron/Synap-Forge/.consciousness_engine/core/__init__.py
"""
Core module - cognition orchestration layer.
All imports are lazy or re-exported from their true locations.
"""

# ============================================================================
# Direct exports (no circular deps)
# ============================================================================
from .pipeline import CognitivePipeline, PipelineStage, StageResult
from .budget import CognitiveBudget
from .prompt_manager import ConversationTurn, SovereignPromptManager
from .serialization import sanitize, SerializedState
from .scheduler import ParallelScheduler, CognitiveChannel
from .base import ConsciousnessProcessor
from .orchestrator import EngineOrchestrator, Orchestrator
from .state import ProcessingState
from loop.state import StateSnapshot, create_initial_state
from .stages import ProcessingStage
from .contract import ContractViolationError
from .event_log import CognitiveEvent, GlobalEventLedger
from .arbitration import ArbitrationResult, ArbitrationEngine

# ============================================================================
# Lazy imports to break circular dependency with loop
# ============================================================================
def _lazy_import(name):
    """Lazy import to avoid circular dependencies"""
    import importlib
    module, attr = name.rsplit('.', 1) if '.' in name else (name, None)
    mod = importlib.import_module(module)
    return getattr(mod, attr) if attr else mod

# These are accessed via properties to avoid circular import at module load time

__all__ = [
    # Core exports
    "ProcessingState",
    "StateSnapshot", 
    "create_initial_state",
    "CognitivePipeline",
    "PipelineStage",
    "StageResult",
    "CognitiveBudget",
    "PromptFrame",
    "PromptSegment",
    "ConversationTurn",
    "SovereignPromptManager",
    "sanitize",
    "SerializedState",
    "ParallelScheduler",
    "CognitiveChannel",
    "ConsciousnessProcessor",
    "EngineOrchestrator",
    "Orchestrator",
    "ProcessingStage",
    "ContractViolationError",
    "CognitiveEvent",
    "GlobalEventLedger",
    "ArbitrationResult",
    "ArbitrationEngine",
]