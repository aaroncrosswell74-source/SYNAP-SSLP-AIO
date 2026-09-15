# /home/aaron/Synap-Forge/.consciousness_engine/config.py
"""
Master configuration file for Lyra Cognitive System
Lazy loading to avoid circular imports
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

# Project root setup
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# LAZY MODULE LOADER - Import only when accessed
# ============================================================================
class LazyModule:
    """Lazy load modules to avoid circular imports"""
    def __init__(self, module_path: str, attr_name: Optional[str] = None):
        self.module_path = module_path
        self.attr_name = attr_name
        self._module = None
    
    def __getattr__(self, name):
        if self._module is None:
            import importlib
            self._module = importlib.import_module(self.module_path)
            if self.attr_name:
                self._module = getattr(self._module, self.attr_name)
        return getattr(self._module, name)

# ============================================================================
# COGNITION MODULES
# ============================================================================
cognition = LazyModule('cognition')
arbitration = LazyModule('cognition.arbitration')
cognitive = LazyModule('cognition.cognitive')
confidence = LazyModule('cognition.confidence')
contradiction = LazyModule('cognition.contradiction')
intent = LazyModule('cognition.intent')
modes = LazyModule('cognition.modes')
relevance = LazyModule('cognition.relevance')
semantic_drift = LazyModule('cognition.semantic_drift')
uncertainty = LazyModule('cognition.uncertainty')

# ============================================================================
# CORE MODULES - These now load properly
# ============================================================================
from core.orchestrator import EngineOrchestrator
from core.pipeline import CognitivePipeline
from core.state import ProcessingState
from core.stages import ProcessingStage
from core.scheduler import ParallelScheduler
from core.budget import CognitiveBudget
from core.contract import ContractViolationError
from core.event_log import CognitiveEvent, GlobalEventLedger
from core.prompt_manager import ConversationTurn, SovereignPromptManager
from core.serialization import SerializedState, sanitize
from core.arbitration import ArbitrationResult, ArbitrationEngine

# ============================================================================
# FILTERS
# ============================================================================
filters = LazyModule('filters')
anti_corp = LazyModule('filters.anti_corp')
chunker = LazyModule('filters.chunker')
sanitize = LazyModule('filters.sanitize')

# ============================================================================
# GRAPH FILES (data paths)
# ============================================================================
GRAPH_FILES = {
    'disambig_tid': str(PROJECT_ROOT / 'graph' / 'disambig_tid.int'),
    'gr_fst': str(PROJECT_ROOT / 'graph' / 'Gr.fst'),
    'hclr_fst': str(PROJECT_ROOT / 'graph' / 'HCLr.fst'),
    'word_boundary': str(PROJECT_ROOT / 'graph' / 'phones' / 'word_boundary.int')
}

# ============================================================================
# IVECTOR FILES
# ============================================================================
IVECTOR_FILES = {
    'final_dubm': str(PROJECT_ROOT / 'ivector' / 'final.dubm'),
    'final_ie': str(PROJECT_ROOT / 'ivector' / 'final.ie'),
    'final_mat': str(PROJECT_ROOT / 'ivector' / 'final.mat'),
    'global_cmvn_stats': str(PROJECT_ROOT / 'ivector' / 'global_cmvn.stats'),
    'online_cmvn_conf': str(PROJECT_ROOT / 'ivector' / 'online_cmvn.conf')
}

# ============================================================================
# LLM MODULES
# ============================================================================
llm = LazyModule('llm')
compression = LazyModule('llm.compression')
inference_router = LazyModule('llm.inference_router')
local_interface = LazyModule('llm.local_interface')
tokenizer = LazyModule('llm.tokenizer')

# ============================================================================
# LOOP MODULES
# ============================================================================
loop = LazyModule('loop')
circadian_rhythm = LazyModule('loop.circadian_rhythm')
convergence = LazyModule('loop.convergence')
decay = LazyModule('loop.decay')
divergence = LazyModule('loop.divergence')
recursion = LazyModule('loop.recursion')
recursive_improvement = LazyModule('loop.recursive_improvement')
loop_state = LazyModule('loop.state')
# ============================================================================
# RECURSION DEFAULTS
# ============================================================================
RECURSION_DEFAULTS = {
    "max_depth": int(os.getenv("RECURSION_MAX_DEPTH", 5)),
    "persona_lock_max": int(os.getenv("PERSONA_LOCK_MAX", 10)),
}

# ============================================================================
# MEMORY MODULES
# ============================================================================
memory = LazyModule('memory')
consolidation = LazyModule('memory.consolidation')
indexing = LazyModule('memory.indexing')
memory01 = LazyModule('memory.memory01')
ranking = LazyModule('memory.ranking')
retrieval = LazyModule('memory.retrieval')
memory_sanitization = LazyModule('memory.sanitization')
store = LazyModule('memory.store')
episodic_buffer = LazyModule('memory.episodic.buffer')

# ============================================================================
# METRICS
# ============================================================================
metrics = LazyModule('metrics')
clarity = LazyModule('metrics.clarity')
similarity = LazyModule('metrics.similarity')

# ============================================================================
# RUNTIME
# ============================================================================
runtime = LazyModule('runtime')
execution = LazyModule('runtime.execution')
failover = LazyModule('runtime.failover')
gpu = LazyModule('runtime.gpu')
health = LazyModule('runtime.health')
queues = LazyModule('runtime.queues')
resources = LazyModule('runtime.resources')
watchdog = LazyModule('runtime.watchdog')

# ============================================================================
# TELEMETRY
# ============================================================================
telemetry = LazyModule('telemetry')
entropy = LazyModule('telemetry.entropy')
telemetry_metrics = LazyModule('telemetry.metrics')
profiling = LazyModule('telemetry.profiling')
replay = LazyModule('telemetry.replay')
trace = LazyModule('telemetry.trace')

# ============================================================================
# UPULSE - Emotional engine (your affect module)
# ============================================================================
upulse = LazyModule('upulse')
affect = LazyModule('upulse.affect')
arousal = LazyModule('upulse.arousal')
emotional_decay = LazyModule('upulse.emotional_decay')
emotional_memory = LazyModule('upulse.emotional_memory')
midas_emotional_engine = LazyModule('upulse.midas_emotional_engine')
opps = LazyModule('upulse.opps')

# /home/aaron/Synap-Forge/.consciousness_engine/config.py - Add this section

# ============================================================================
# MEMORY PATHS & CONSTANTS
# ============================================================================

# Central memory paths
CENTRAL_MEMORY_DIR = PROJECT_ROOT / 'central_memory'
CORE_MEMORY_FILE = CENTRAL_MEMORY_DIR / 'core_memory.json'
IDENTITY_LOCK_FILE = CENTRAL_MEMORY_DIR / 'identity_lock.json'
INTERACTIONS_DIR = CENTRAL_MEMORY_DIR / 'interactions'

# Memory limits
MAX_MEMORY_ITEMS = 10000
MAX_MEMORY_CHARS = 100000

# Ensure directories exist
for dir_path in [CENTRAL_MEMORY_DIR, INTERACTIONS_DIR,]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ============================================================================
# UPULSE DATA FILES
# ============================================================================
UPULSE_DATA = {
    'coupled_system_spec': PROJECT_ROOT / 'upulse' / 'Coupled_System_Spec.md',
    'ensemble_aligned': PROJECT_ROOT / 'upulse' / 'ensemble_summary_aligned.csv',
    'ensemble_misaligned': PROJECT_ROOT / 'upulse' / 'ensemble_summary_misaligned.csv',
    'interactive_notebook': PROJECT_ROOT / 'upulse' / 'Interactive_Consensus_SME.ipynb'
}

# ============================================================================
# CONFIGURATION LOADER
# ============================================================================
def load_conf_files() -> Dict[str, str]:
    """Load configuration from conf directory"""
    conf_dir = PROJECT_ROOT / 'conf'
    configs = {}
    
    for conf_file in ['mfcc.conf', 'model.conf']:
        conf_path = conf_dir / conf_file
        if conf_path.exists():
            with open(conf_path, 'r') as f:
                configs[conf_file.replace('.conf', '')] = f.read()
    
    return configs

# ============================================================================
# INITIALIZATION FUNCTION - Now safe because of lazy loading
# ============================================================================
def initialize_all_modules(verbose: bool = True) -> Dict[str, Any]:
    """
    Initialize and configure all imported modules
    Returns a dictionary with initialized components
    """
    initialized = {}
    
    if verbose:
        print("=" * 60)
        print("Lyra Cognitive System - Module Initialization")
        print("=" * 60)
    
    # Load configurations
    initialized['configs'] = load_conf_files()
    
    # Initialize Core (direct imports work now)
    if verbose:
        print("✓ Core modules loaded")
    initialized["orchestrator"] = EngineOrchestrator
    initialized['pipeline'] = CognitivePipeline
    initialized["scheduler"] = ParallelScheduler
    
    # Initialize Cognition
    if verbose:
        print("✓ Cognition modules loaded")
    initialized['cognition'] = {
        'arbitration': arbitration,
        'confidence': confidence,
        'contradiction': contradiction,
        'intent': intent
    }
    
    # Initialize Memory
    if verbose:
        print("✓ Memory modules loaded")
    initialized['memory'] = {
        'store': store,
        'retrieval': retrieval,
        'consolidation': consolidation
    }
    
    # Initialize LLM
    if verbose:
        print("✓ LLM modules loaded")
    initialized['llm'] = {
        'local': local_interface,
        'router': inference_router,
        'tokenizer': tokenizer
    }
    
    # Initialize Telemetry
    if verbose:
        print("✓ Telemetry modules loaded")
    initialized['telemetry'] = {
        'metrics': telemetry_metrics,
        'profiling': profiling,
        'trace': trace
    }
    
    # Initialize Runtime
    if verbose:
        print("✓ Runtime modules loaded")
    initialized['runtime'] = {
        'execution': execution,
        'health': health,
        'watchdog': watchdog
    }
    
    # Initialize Upulse (Emotional Engine)
    if verbose:
        print("✓ Upulse emotional engine loaded")
    initialized['upulse'] = {
        'affect': affect,
        'arousal': arousal,
        'midas': midas_emotional_engine
    }
    
    # Initialize Loop modules
    if verbose:
        print("✓ Loop modules loaded")
    initialized['loop'] = {
        'circadian': circadian_rhythm,
        'recursive': recursive_improvement,
        'convergence': convergence
    }
    
    if verbose:
        print("=" * 60)
        print(f"Initialization complete. {len(initialized)} component groups ready.")
        print("=" * 60)
    
    return initialized

# ============================================================================
# MODULE REGISTRY
# ============================================================================
MODULE_REGISTRY = {
    'cognition': ['arbitration', 'cognitive', 'confidence', 'contradiction', 
                  'intent', 'modes', 'relevance', 'semantic_drift', 'uncertainty'],
    'core': ['orchestrator', 'pipeline', 'state', 'stages', 'scheduler', 
             'budget', 'contract', 'event_log', 'prompt_manager', 'serialization'],
    'filters': ['anti_corp', 'chunker', 'sanitize'],
    'llm': ['compression', 'inference_router', 'local_interface', 'tokenizer'],
    'loop': ['circadian_rhythm', 'convergence', 'decay', 'divergence', 
             'recursion', 'recursive_improvement', 'state'],
    'memory': ['consolidation', 'indexing', 'memory01', 'ranking', 'retrieval', 
               'sanitization', 'store'],
    'metrics': ['clarity', 'similarity'],
    'runtime': ['execution', 'failover', 'gpu', 'health', 'queues', 'resources', 'watchdog'],
    'telemetry': ['entropy', 'metrics', 'profiling', 'replay', 'trace'],
    'upulse': ['affect', 'arousal', 'emotional_decay', 'emotional_memory', 
               'midas_emotional_engine', 'opps']
}

# ============================================================================
# MAIN - Test imports
# ============================================================================
if __name__ == '__main__':
    print("\nTesting module imports...\n")
    
    # Test the lazy loader works
    try:
        test_affect = affect.AffectModel
        print("✓ Affect module loaded successfully")
    except Exception as e:
        print(f"✗ Affect module failed: {e}")
    
    # Test core imports
    try:
        test_orch = Orchestrator
        print("✓ Orchestrator loaded successfully")
    except Exception as e:
        print(f"✗ Orchestrator failed: {e}")
    
    # Initialize all modules
    initialized = initialize_all_modules(verbose=True)
    
    print("\nConfiguration loaded successfully.")
# ============================================================================
# MEMORY PATHS (for llm_firewall compatibility)
# ============================================================================
MEMORY_PATHS = {
    'lyra_active_memory': PROJECT_ROOT / 'memory' / 'lyra_active_memory',
    'interactions': PROJECT_ROOT / 'memory' / 'lyra_active_memory' / 'interactions',
    'lyra_chroma': PROJECT_ROOT / 'memory' / 'lyra_active_memory' / 'lyra_chroma'
}
