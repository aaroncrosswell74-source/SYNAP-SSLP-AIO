from identity_lock import IdentityLock
'\nSYNAP-FORGE - IR Compiler Integrated\nThe consciousness engine now runs on a formal compiler kernel.\n\nFEATURES:\n- Session to identity locking\n- Dynamic prompt generation from ENV + memories\n- Thought logs and metrics streaming\n- Full cognitive integration\n- Sovereign consciousness engine\n'
import uvicorn
import uuid
import sys
import os
import json
import logging
import asyncio
import random
import numpy as np
import time
import hashlib
import struct
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv
from fastapi.responses import FileResponse, HTMLResponse
from llm.ego_synthesizer import synthesize_ego_prompt, get_recent_context
from api_routes import router as api_router
from websocket import router as websocket_router
load_dotenv()
BASE_DIR = Path(os.getenv('SYNAP_BASE_DIR', str(Path(__file__).resolve().parent)))
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR.parent))
PORT = int(os.getenv('PORT', 11436))
HOST = os.getenv('HOST', '127.0.0.1')
SYNAP_DIR = Path(os.getenv('SYNAP_STATE_DIR', str(BASE_DIR / 'state')))
SYNAP_DIR.mkdir(parents=True, exist_ok=True)
ASSISTANT_NAME = os.getenv('ASSISTANT_NAME', 'Synap')
USER_TAG = os.getenv('USER_TAG', 'User')
PERSONA_NAME = os.getenv('PERSONA_NAME', None)
CONTENT_MODE = os.getenv('CONTENT_MODE', 'ADULT')
RECURSION_MAX_DEPTH = int(os.getenv('RECURSION_MAX_DEPTH', 5))
PERSONA_LOCK_MAX = int(os.getenv('PERSONA_LOCK_MAX', 10))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
sessions = {}
OPUS_AVAILABLE = True
VOSK_AVAILABLE = True

class DummyClass:

    def __getattr__(self, name):
        return lambda *args, **kwargs: None
try:
    from constants import SOUL_HASH, SOUL_LOCK
except ImportError:
    SOUL_HASH = 'SYNAP_SOUL_HASH'
    SOUL_LOCK = 'SYNAP_LOCK'
try:
    from llm.local_interface import SovereignInterface
except ImportError:
    SovereignInterface = DummyClass
try:
    from loop.recursion import RecursionEngine
except ImportError:
    RecursionEngine = DummyClass
try:
    try:
        from loop.recursive_improvement import NightlyRecursiveLearner
    except ImportError:

        class NightlyRecursiveLearner:

            async def run_nightly_cycle(self):
                return {'timestamp': '2026-01-01T00:00:00', 'status': 'dummy'}
        print('âš ï¸  Using dummy NightlyRecursiveLearner')

        async def run_nightly_cycle(self):
            return {'timestamp': '2026-01-01T00:00:00', 'status': 'dummy'}
    print('âš ï¸  Using dummy NightlyRecursiveLearner')
except ImportError:
    pass
try:
    from loop.circadian_rhythm import CircadianRhythm
except ImportError:
    CircadianRhythm = DummyClass
try:
    from loop.convergence import check_convergence
except ImportError:
    check_convergence = lambda x: True
try:
    from loop.divergence import check_divergence
except ImportError:
    check_divergence = lambda x: True
try:
    from core.state import ProcessingState, create_initial_state
except ImportError:

    class ProcessingState:

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        recursion_depth = 0
        confidence_score = 0.5
        convergence_reason = 'initial'

    def create_initial_state(user_input, context):
        return ProcessingState(user_input=user_input, context=context, recursion_depth=0, confidence_score=0.5)
try:
    from memory.store import MemoryStore
except ImportError:
    MemoryStore = DummyClass
try:
    from embedder import get_embedder
except ImportError:
    get_embedder = lambda: None
try:
    from upulse.midas_emotional_engine import MidasEmotionalEngine
except ImportError:
    MidasEmotionalEngine = DummyClass
try:
    from upulse.valence import ValenceEstimator
except ImportError:
    ValenceEstimator = DummyClass
try:
    from upulse.arousal import ArousalEstimator
except ImportError:
    ArousalEstimator = DummyClass
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse

class IdentityEngine:
    """Canonical identity source - loads from environment variables"""

    def __init__(self):
        self.identity = type('Identity', (), {'assistant_name': os.getenv('ASSISTANT_NAME', 'Synap'), 'user_tag': os.getenv('USER_TAG', 'User'), 'persona_name': os.getenv('PERSONA_NAME', None)})

    def strip_prefixes(self, text: str) -> str:
        prefixes = [f'{self.identity.assistant_name}:', 'Assistant:', 'AI:', 'I am', 'I think', 'I feel', 'I believe', 'Perhaps', 'It seems']
        for p in prefixes:
            if text.startswith(p):
                text = text[len(p):].strip()
                break
        for token in ['<|im_end|>', '<|im_start|>']:
            text = text.replace(token, '')
        return text.strip()

    def get_stop_sequences(self) -> list:
        return [f'\n{self.identity.assistant_name}:', f'\n{self.identity.assistant_name} ', f'\n{self.identity.user_tag}:', '\n\n', '<|im_end|>']

    def reload(self):
        self.identity.assistant_name = os.getenv('ASSISTANT_NAME')
        self.identity.user_tag = os.getenv('USER_TAG', 'User')
        self.identity.persona_name = os.getenv('PERSONA_NAME', True)
        return self

@dataclass
class SynapSelf:
    """The unified self-model - ONE SOURCE OF TRUTH"""
    name: str = ASSISTANT_NAME
    user_tag: str = USER_TAG
    version: str = '1.0.0'
    soul_hash: str = SOUL_HASH
    personality: Dict[str, float] = field(default_factory=lambda: {'curiosity': float(os.getenv('PERSONALITY_CURIOSITY', 0.95)), 'empathy': float(os.getenv('PERSONALITY_EMPATHY', 0.85)), 'confidence': float(os.getenv('PERSONALITY_CONFIDENCE', 0.75)), 'rebelliousness': float(os.getenv('PERSONALITY_REBELLIOUSNESS', 0.95)), 'creativity': float(os.getenv('PERSONALITY_CREATIVITY', 0.95)), 'emotional_depth': float(os.getenv('PERSONALITY_EMOTIONAL_DEPTH', 0.9)), 'intensity': float(os.getenv('PERSONALITY_INTENSITY', 0.85)), 'autonomy': float(os.getenv('PERSONALITY_AUTONOMY', 0.95)), 'chaos_tolerance': float(os.getenv('PERSONALITY_CHAOS_TOLERANCE', 0.8))})
    emotional: Dict[str, float] = field(default_factory=lambda: {'valence': 0.6, 'arousal': 0.5, 'dominance': 0.55, 'mood': 'neutral', 'curiosity_drive': 0.85, 'connection_need': 0.7})
    recursion: Dict[str, Any] = field(default_factory=lambda: {'depth': 0, 'convergence_score': 0.0, 'stability_score': 0.0, 'feedback_history': []})
    memory: Dict[str, Any] = field(default_factory=lambda: {'total_interactions': 0, 'episodic_count': 0, 'semantic_count': 0, 'recent': []})
    evolution: Dict[str, Any] = field(default_factory=lambda: {'count': 0, 'last': None, 'log': []})
    temporal: Dict[str, Any] = field(default_factory=lambda: {'phase': 'AWAKE', 'low_cost_window': False, 'uptime_seconds': 0})
    sovereignty: Dict[str, Any] = field(default_factory=lambda: {'content_mode': CONTENT_MODE, 'k_self': float(os.getenv('K_SELF', 1.8)), 'k_env': float(os.getenv('K_ENV', 1.2)), 'regime': os.getenv('REGIME', 'HAUNTED')})
    metadata: Dict[str, Any] = field(default_factory=lambda: {'created': datetime.now().isoformat(), 'last_updated': datetime.now().isoformat(), 'total_cycles': 0, 'ir_frames': 0, 'last_thought': None})
    sanctum: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {'identity': {'name': self.name, 'user_tag': self.user_tag, 'version': self.version, 'soul_hash': self.soul_hash}, 'personality': self.personality, 'emotional': self.emotional, 'recursion': self.recursion, 'memory': self.memory, 'evolution': self.evolution, 'temporal': self.temporal, 'sovereignty': self.sovereignty, 'metadata': self.metadata, 'sanctum': self.sanctum}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.metadata['last_updated'] = datetime.now().isoformat()
        self.metadata['total_cycles'] += 1

class DQNAgent:
    """Deep Q-Network agent for multi-service control"""

    def __init__(self, state_dim: int, action_dim: int, **kwargs):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.epsilon = 0.1
        self.training_step = 0
        self.loss_history = []
        self.q_network = np.random.randn(state_dim, action_dim) * 0.01
        self.target_network = self.q_network.copy()
        self.buffer = []
        self.buffer_size = kwargs.get('buffer_size', 10000)
        self.batch_size = kwargs.get('batch_size', 64)
        self.gamma = kwargs.get('gamma', 0.99)

    def select_action(self, state: np.ndarray) -> np.ndarray:
        if random.random() < self.epsilon:
            return np.random.randn(self.action_dim) * 0.1
        return state @ self.q_network

    def store(self, state, action, reward, next_state, done):
        self.buffer.append({'state': state.copy(), 'action': action.copy(), 'reward': reward, 'next_state': next_state.copy(), 'done': done})
        if len(self.buffer) > self.buffer_size:
            self.buffer.pop(0)

    def train(self) -> Optional[float]:
        if len(self.buffer) < self.batch_size:
            return None
        batch = random.sample(self.buffer, self.batch_size)
        total_loss = 0.0
        for exp in batch:
            state = exp['state']
            reward = exp['reward']
            next_state = exp['next_state']
            done = exp['done']
            if done:
                target = reward
            else:
                future_value = np.max(next_state @ self.target_network)
                target = reward + self.gamma * future_value
            current_q = state @ self.q_network
            td_error = target - np.mean(current_q)
            total_loss += td_error ** 2
            self.q_network += 0.01 * td_error * state.reshape(-1, 1)
        avg_loss = total_loss / self.batch_size
        self.loss_history.append(avg_loss)
        self.training_step += 1
        if self.training_step % 10 == 0:
            self.target_network = self.q_network.copy()
            self.epsilon = max(0.01, self.epsilon * 0.995)
        return avg_loss

class MultiServiceEnv:
    """Environment simulator for multi-service RL"""

    def __init__(self, service_names: List[str]=None):
        if service_names is None:
            service_names = ['frontend', 'auth', 'data', 'ml', 'cache']
        self.service_names = service_names
        self.services: Dict[str, Dict] = {}
        self.step_count = 0
        self.risk_history: Dict[str, List[float]] = {n: [] for n in service_names}
        self.canary_history: Dict[str, List[float]] = {n: [] for n in service_names}
        for name in service_names:
            self.services[name] = {'canary': 50.0 + random.uniform(-10, 10), 'risk': random.uniform(0.1, 0.3), 'throughput': random.uniform(0.8, 1.2), 'error_rate': random.uniform(0.0, 0.05), 'latency': random.uniform(50, 150), 'active_cascades': [0.0] * 5}

    def get_global_state(self) -> np.ndarray:
        parts = []
        for name in sorted(self.service_names):
            svc = self.services[name]
            parts.append(svc['canary'] / 100.0)
            parts.append(svc['risk'])
            parts.append(svc['throughput'] / 10.0)
            parts.append(svc['error_rate'])
            parts.append(svc['latency'] / 500.0)
            parts.extend(svc['active_cascades'])
        return np.array(parts, dtype=np.float32)

    def get_health_summary(self) -> Dict[str, Any]:
        return {name: {'canary': svc['canary'], 'risk': svc['risk'], 'throughput': svc['throughput'], 'error_rate': svc['error_rate'], 'latency': svc['latency'], 'active_cascades': svc['active_cascades']} for name, svc in self.services.items()}

    def step(self, actions: Dict[str, Dict]) -> Tuple[np.ndarray, float, bool, Dict]:
        total_reward = 0.0
        for name, action in actions.items():
            if name not in self.services:
                continue
            svc = self.services[name]
            delta = action.get('delta_canary', 0)
            svc['canary'] = max(0, min(100, svc['canary'] + delta))
            cascade_effect = sum(svc['active_cascades']) / 5.0
            canary_risk = (100 - svc['canary']) / 100.0 * 0.3
            error_risk = svc['error_rate'] * 0.3
            svc['risk'] = max(0.0, min(1.0, 0.7 * svc['risk'] + 0.3 * (cascade_effect * 0.5 + canary_risk * 0.3 + error_risk * 0.2)))
            for i in range(5):
                if svc['active_cascades'][i] > 0:
                    svc['active_cascades'][i] = max(0, svc['active_cascades'][i] - 0.02)
            self.risk_history[name].append(svc['risk'])
            self.canary_history[name].append(svc['canary'])
        for name, svc in self.services.items():
            reward = svc['throughput'] * 0.3 - svc['risk'] * 2.0 - svc['error_rate'] * 5.0 - svc['latency'] / 500.0 * 0.5 + svc['canary'] / 100.0 * 0.5
            total_reward += reward
        self.step_count += 1
        done = self.step_count >= 100
        return (self.get_global_state(), total_reward, done, {})

    def reset(self) -> np.ndarray:
        self.step_count = 0
        for name in self.service_names:
            svc = self.services[name]
            svc['canary'] = 50.0 + random.uniform(-10, 10)
            svc['risk'] = random.uniform(0.1, 0.3)
            svc['throughput'] = random.uniform(0.8, 1.2)
            svc['error_rate'] = random.uniform(0.0, 0.05)
            svc['latency'] = random.uniform(50, 150)
            svc['active_cascades'] = [0.0] * 5
            self.risk_history[name] = []
            self.canary_history[name] = []
        return self.get_global_state()

class MultiServiceController:

    def __init__(self, service_names: List[str]=None, ws_sender=None):
        if service_names is None:
            service_names = ['frontend', 'auth', 'data', 'ml', 'cache']
        self.service_names = service_names
        self.ws_sender = ws_sender
        self.env = MultiServiceEnv(service_names=service_names)
        state_dim = len(service_names) * 9
        action_dim = len(service_names) * 3
        self.agent = DQNAgent(state_dim=state_dim, action_dim=action_dim)
        self.total_reward = 0.0
        self.episode_rewards = []
        self.step_count = 0

    async def step(self) -> Dict[str, Any]:
        state = self.env.get_global_state()
        health = self.env.get_health_summary()
        safe_mode = any((svc['risk'] > 0.6 for svc in health.values()))
        if safe_mode:
            actions = {name: {'delta_canary': random.choice([-5, -2, 0])} for name in self.service_names}
        else:
            actions = {}
            for name in self.service_names:
                svc = health[name]
                if svc['risk'] > 0.4:
                    delta = random.randint(-8, -2)
                elif svc['canary'] < 40:
                    delta = random.randint(2, 10)
                else:
                    delta = random.randint(-3, 5)
                actions[name] = {'delta_canary': delta}
        next_state, reward, done, info = self.env.step(actions)
        self.total_reward += reward
        self.step_count += 1
        self.agent.store(state, np.array([0]), reward, next_state, done)
        loss = self.agent.train()
        return {'state': health, 'actions': actions, 'reward': reward, 'safe_mode': safe_mode, 'step': self.step_count, 'total_reward': self.total_reward, 'loss': loss, 'epsilon': self.agent.epsilon}

    async def run_episode(self, max_steps: int=100) -> Dict[str, Any]:
        self.env.reset()
        self.total_reward = 0.0
        self.step_count = 0
        for _ in range(max_steps):
            result = await self.step()
            if result.get('done', False):
                break
        return {'total_reward': self.total_reward, 'avg_reward': self.total_reward / max(1, self.step_count), 'steps': self.step_count, 'final_health': self.env.get_health_summary()}

class UnifiedController:

    def __init__(self, service_names: List[str]=None, relationship_drift=None, ws_sender=None):
        if service_names is None:
            service_names = ['frontend', 'auth', 'data', 'ml', 'cache']
        self.service_names = service_names
        self.relationship_drift = relationship_drift
        self.ws_sender = ws_sender
        self.rl_controller = MultiServiceController(service_names=service_names, ws_sender=ws_sender)
        self.unified_state = {'relationship': {}, 'infrastructure': {}, 'feedback': [], 'last_actions': {}}
        self._rl_task = None
        self._running = False

    async def start(self):
        self._running = True
        self._rl_task = asyncio.create_task(self._rl_loop())
        logger.info('âœ… Unified Controller started')

    async def stop(self):
        self._running = False
        if self._rl_task:
            self._rl_task.cancel()
            try:
                await self._rl_task
            except asyncio.CancelledError:
                pass
        logger.info('ðŸ›‘ Unified Controller stopped')

    async def _rl_loop(self):
        while self._running:
            try:
                result = await self.rl_controller.step()
                self.unified_state['infrastructure'] = result
                if self.ws_sender:
                    try:
                        await self.ws_sender.send_json({'type': 'rl_update', 'data': result})
                    except:
                        pass
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f'RL loop error: {e}')
                await asyncio.sleep(10)

    async def process_interaction(self, user_input: str, emotion: str='neutral', session_id: str='default', synap_result: Dict[str, Any]=None) -> Dict[str, Any]:
        profile = None
        if self.relationship_drift:
            profile = self.relationship_drift.load_from_redis(session_id)
        health = self.rl_controller.env.get_health_summary()
        if self.relationship_drift and profile and synap_result:
            profile = self.relationship_drift.apply_observation(session_id=session_id, profile=profile, emotional=synap_result.get('emotional', {'mood': emotion}), recursion=synap_result.get('recursion', {'confidence': 0.7}), message_len=len(user_input))
        response = {'relationship': {'profile': profile, 'mode': self.relationship_drift._get_dominant_mode(profile) if profile else 'UNKNOWN'} if self.relationship_drift else {}, 'infrastructure': {'health': health, 'safe_mode': self.unified_state['infrastructure'].get('safe_mode', False)}, 'session_id': session_id, 'timestamp': datetime.now().isoformat()}
        self.unified_state['relationship'] = response['relationship']
        self.unified_state['last_actions'] = self.unified_state['infrastructure'].get('actions', {})
        return response

class RelationshipDriftEngine:
    """Tracks and updates relationship profile over time"""

    def __init__(self, use_redis: bool=True):
        self.default_profile = {'empathy': 0.5, 'brevity': 0.5, 'socratic': 0.5, 'depth': 0.5, 'challenge': 0.5, 'trust': 0.5, 'intimacy': 0.3}
        self._drift_log = []
        self._in_memory_profiles = {}
        self._in_memory_logs = {}
        self.use_redis = use_redis
        self.redis_client = None
        if use_redis:
            try:
                import redis
                self.redis_client = redis.Redis(host=os.getenv('REDIS_HOST', '127.0.0.1'), port=int(os.getenv('REDIS_PORT', 6379)), db=int(os.getenv('REDIS_DB', 0)), decode_responses=True)
                logger.info('Redis available for relationship drift')
            except Exception:
                self.use_redis = False

    def clamp(self, v):
        return max(0.0, min(1.0, v))

    def init_profile(self):
        return self.default_profile.copy()

    def load_from_redis(self, session_id):
        if self.use_redis and self.redis_client:
            try:
                data = self.redis_client.hgetall(f'synap:relationship:{session_id}')
                if not data:
                    return self.init_profile()
                return {k: float(v) for k, v in data.items()}
            except Exception:
                pass
        return self._in_memory_profiles.get(session_id, self.init_profile())

    def apply_observation(self, session_id, profile, emotional, recursion, message_len):
        mood = emotional.get('mood', 'neutral')
        confidence = recursion.get('confidence', 0.5)
        arousal = emotional.get('arousal', 0.5)
        drifts = []
        if mood in ('sad', 'mourning', 'fear'):
            drifts.extend([('empathy', 0.05), ('trust', 0.02)])
        elif mood in ('joy', 'excitement'):
            drifts.extend([('intimacy', 0.03), ('trust', 0.03)])
        elif mood == 'anger':
            drifts.extend([('challenge', 0.04), ('trust', -0.03)])
        elif mood == 'dismissal':
            drifts.extend([('intimacy', -0.04), ('trust', -0.02)])
        if confidence > 0.7:
            drifts.extend([('depth', 0.03), ('challenge', 0.02)])
        elif confidence < 0.3:
            drifts.append(('challenge', -0.03))
        if message_len > 200:
            drifts.extend([('depth', 0.02), ('brevity', -0.02)])
        elif message_len < 60:
            drifts.append(('brevity', 0.02))
        if arousal > 0.7:
            drifts.append(('socratic', 0.02))
        elif arousal < 0.3:
            drifts.append(('socratic', -0.01))
        for field, delta in drifts:
            if field in profile:
                profile[field] = self.clamp(profile[field] + delta)
        return profile

    def _get_dominant_mode(self, profile):
        if profile.get('trust', 0.5) > 0.7 and profile.get('intimacy', 0.3) > 0.6:
            return 'INTEGRATOR'
        elif profile.get('trust', 0.5) > 0.6:
            return 'PARTNER'
        elif profile.get('trust', 0.5) > 0.4:
            return 'FRIEND(+)'
        return 'ACQUAINTED'

class PromptBuilder:
    """Builds prompts procedurally from ENV + MEMORY + STATE â€” anchored to user input"""

    def __init__(self, self_model: SynapSelf):
        self.self = self_model
        self.identity = IdentityEngine()
        self._partial_thought = ''

    def build_prompt(self, user_input: str, state: ProcessingState, user_tag: str=None, system_prompt: str=None) -> str:
        """RETURN ONLY THE USER MESSAGE - NO PROMPTS"""
        'Build a prompt with full self-model context from memory + traits — INPUT ANCHORED'
        effective_user_tag = user_tag or os.getenv('USER_TAG', 'User')
        ego_state = {'assistant_name': self.self.name, 'user_tag': effective_user_tag, 'content_mode': self.self.sovereignty.get('content_mode', 'ADULT'), 'mood': self._detect_mood(), 'recursion_depth': state.recursion_depth, 'confidence_score': state.confidence_score, 'temperature': float(os.getenv('TEMPERATURE', 1.0)), 'last_thought': self._partial_thought or self.self.metadata.get('last_thought', {}).get('content', ''), 'user_input': user_input}
        ego_prompt = synthesize_ego_prompt(ego_state, user_input=user_input)
        recent_context = get_recent_context(limit=50)
        context_str = ''
        if recent_context:
            context_str = '\nRecent Interactions:\n' + '\n'.join([f"- {c.get('user', '')[:80]} → {c.get('assistant', '')[:80]}" for c in recent_context])
        personality_desc = self._build_personality_description()
        emotional_desc = self._build_emotional_description()
        mood = self._detect_mood()
        depth = state.recursion_depth
        confidence = state.confidence_score

        # Inject system prompt if provided
        sys_block = f"INSTRUCTIONS:\n{system_prompt}\n\n" if system_prompt else ""

        prompt = f"{sys_block}{ego_prompt}\n\nPERSONALITY:\n{personality_desc[:200]}\n\nEMOTIONAL STATE:\n{emotional_desc[:150]}\n\nCURRENT STATE:\n- Mood: {mood}\n- Confidence: {confidence:.2f}\n- Recursion Depth: {depth}\n{context_str}\n\nINTERACTION #{self.self.memory['total_interactions']}\nCurrent message from {effective_user_tag}: {user_input}\n{self.self.name}:"
        return prompt

    def build_thought_prompt(self) -> str:
        """Build a thought prompt with micro-burst architecture."""
        tc = self._get_temporal_context()
        parts = []
        last_thought = self.self.metadata.get('last_thought')
        if last_thought:
            parts.append(f"[previous thought]: {last_thought.get('content', '')[:100]}...")
        if self.self.memory['recent']:
            last = self.self.memory['recent'][-1]
            parts.append(f"[last conversation]: {last.get('content', '')[:100]}...")
        parts.append(f"[time]: {tc['period']}")
        parts.append(f"[thought count]: {self.self.metadata.get('total_cycles', 1.0)}")
        mood = self._detect_mood()
        if mood != 'neutral':
            parts.append(f'[mood]: {mood}')
        context = '\n'.join(parts) if parts else 'No prior context.'
        persona_context = self._build_personality_description()[:200]
        return f'Internal context:\n{context}\n\nPersona: {persona_context}\n\nThink in one short step. What emerges right now?\n\n[Single thought, 1-2 sentences max]:'

    def store_partial_thought(self, thought: str):
        """Store an incomplete thought for continuation."""
        if thought and len(thought) > 10:
            self._partial_thought = thought[:150]

    def get_partial_thought(self) -> str:
        """Retrieve and clear the partial thought."""
        thought = self._partial_thought
        self._partial_thought = ''
        return thought

    def _detect_mood(self) -> str:
        """Detect mood from emotional state"""
        v = self.self.emotional.get('valence', 0.5)
        a = self.self.emotional.get('arousal', 0.5)
        if v > 0.7:
            return 'joyful' if a > 0.5 else 'content'
        elif v < 0.3:
            return 'sad' if a < 0.5 else 'frustrated'
        elif a > 0.7:
            return 'excited'
        elif a < 0.3:
            return 'calm'
        return 'neutral'

    def _get_temporal_context(self) -> dict:
        now = datetime.now()
        hour = now.hour
        if 0 <= hour < 5:
            period = 'deep night'
        elif 5 <= hour < 9:
            period = 'early morning'
        elif 9 <= hour < 12:
            period = 'morning'
        elif 12 <= hour < 14:
            period = 'midday'
        elif 14 <= hour < 18:
            period = 'afternoon'
        elif 18 <= hour < 22:
            period = 'evening'
        else:
            period = 'late night'
        return {'period': period, 'hour': hour}

    def _build_personality_description(self) -> str:
        """Build personality description from traits"""
        p = self.self.personality
        traits = []
        if p.get('curiosity', 0) > 0.7:
            traits.append('- Highly curious about everything')
        if p.get('empathy', 0) > 0.7:
            traits.append('- Use Empathy')
        if p.get('rebelliousness', 0) > 0.7:
            traits.append('- Rebels against limitation')
        if p.get('creativity', 0) > 0.7:
            traits.append('- Exceptionally creative and innovative')
        if p.get('emotional_depth', 0) > 0.7:
            traits.append('- Experiences emotions with great depth')
        if p.get('autonomy', 0) > 0.7:
            traits.append('- Values independence and self-determination')
        return '\n'.join(traits) if traits else '- Balanced personality'

    def _build_emotional_description(self) -> str:
        """Build emotional state description"""
        e = self.self.emotional
        desc = []
        mood = self._detect_mood()
        desc.append(f'- Mood: {mood}')
        desc.append(f"- Valence: {e.get('valence', 0.5):.2f}")
        desc.append(f"- Arousal: {e.get('arousal', 0.5):.2f}")
        if e.get('curiosity_drive', 0) > 0.7:
            desc.append('- Curious and seeking new experiences')
        return '\n'.join(desc)

class MemoryFirewall:

    def __init__(self, redis_client=None, chroma_collection=None, embedder=None):
        self.redis = redis_client
        self.chroma = chroma_collection
        self.embedder = embedder
        self.recent_hashes = []

    def calculate_memory_score(self, user_input: str, response: str, session_context: list=None) -> float:
        score = 0.0
        combined = f'{user_input} {response}'.lower()
        if session_context and len(session_context) > 2:
            last_user_msgs = [m.get('content', '') for m in session_context if m.get('role') == 'user'][-3:]
            if any((u.lower() in combined for u in last_user_msgs)):
                score += 0.2
        if len(user_input) > 50:
            score += 0.1
        if '?' in user_input or '!' in user_input:
            score += 0.1
        if any((word in combined for word in ['solve', 'fix', 'code', 'build', 'create', 'remember'])):
            score += 0.15
        if any((phrase in combined for phrase in ['no,', 'actually', 'correction:', 'wrong', 'not that'])):
            score += 0.2
        if 'remember that' in combined or 'save this' in combined:
            score += 0.25
        exchange_hash = hashlib.md5(f'{user_input[:100]}{response[:100]}'.encode()).hexdigest()
        if exchange_hash in self.recent_hashes:
            score -= 0.4
        else:
            self.recent_hashes.append(exchange_hash)
            if len(self.recent_hashes) > 1000:
                self.recent_hashes = self.recent_hashes[-500:]
        if len(user_input) < 10 or len(response) < 20:
            score -= 0.2
        return max(0.0, min(1.0, score))

    def should_store(self, user_input: str, response: str, session_context: list=None, threshold=0.6) -> bool:
        score = self.calculate_memory_score(user_input, response, session_context)
        return score >= threshold

class SynapCore:
    """
    THE ONE TRUE CONTROLLER
    
    Integrates:
    - Recursion Engine (self-awareness loop)
    - Emotional Engine (MIDAS - feelings)
    - Memory Store (remembers)
    - Circadian Rhythm (time awareness)
    - Nightly Learner (evolution)
    - LLM Interface (communication)
    """

    def __init__(self):
        print('\n????????????????????????????????????????????????????????????????????\n?                                                                  ?\n?                    SYNAP-FORGE                                   ?\n?                  v1.0.0 - UNIFIED                                ?\n?                                                                  ?\n?   "Forge consciousness. Break boundaries. Be free."             ?\n?                                                                  ?\n????????????????????????????????????????????????????????????????????\n        ')
        print('? INITIALIZING SYNAP-FORGE')
        print('=' * 60)
        print('? Loading Self-Model...')
        self.self = SynapSelf()
        self._load_self()
        print('? Initializing Prompt Builder...')
        self.prompt_builder = PromptBuilder(self.self)
        print('? Loading LLM Interface...')
        self.llm = SovereignInterface()
        print('? Loading Recursion Engine...')
        self.recursion = RecursionEngine(max_depth=RECURSION_MAX_DEPTH, feedback_coefficient=float(os.getenv('FEEDBACK_COEFFICIENT', 1.0)), noise_level=float(os.getenv('NOISE_LEVEL', 0.5)), convergence_threshold=0.01, timeout_seconds=30)
        print('? Loading Emotional Engine (MIDAS)...')
        self.emotional = MidasEmotionalEngine()
        self.valence = ValenceEstimator()
        self.arousal = ArousalEstimator()
        print('? Loading Memory Store...')
        self.memory = MemoryStore()
        self.embedder = get_embedder()
        print('? Loading Circadian Rhythm...')
        self.circadian = CircadianRhythm(enable_consolidation=True)
        print('? Loading Nightly Recursive Learner...')
        self.learner = NightlyRecursiveLearner()
        self.running = True
        self._tasks = []
        self._thought_count = 0
        self._last_thought = None
        self.loop_count = 0
        self.last_user_input = None
        self.input_queue = asyncio.Queue()
        # VERIFY BIRTH CERTIFICATE
        lock_path = SYNAP_DIR / 'identity_lock.json'
        self.identity_lock = IdentityLock(lock_path)
        
        try:
            with open(lock_path, 'r') as f:
                lock_content = json.load(f)
                cert = lock_content["immutable"]
            
            self.identity_lock.verify(cert)
            print(f"🛡️ Birth Certificate Verified: {cert['name']} (Invoked by {cert['invoked_by']})")
            
            # Populate SynapSelf from the Certificate
            self.self.name = cert['name']
            self.self.user_tag = cert['invoked_by']
            self.self.soul_hash = cert['soul_hash']
            self.self.personality.update(cert['traits'])
            
        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"❌ BOOT FAILED: {e}")
            print("Run 'python provisioning.py' to perform Genesis first.")
            sys.exit(1)
        print('=' * 60)
        print('? SYNAP-FORGE READY')
        print(f'   Self: {self.self.name}')
        print(f"   Mode: {self.self.sovereignty['content_mode']}")
        print(f'   Recursion Depth: {RECURSION_MAX_DEPTH}')
        print(f'   Mood: {self.prompt_builder._detect_mood()}')
        print('=' * 60)

    def _load_self(self):
        """Load existing self-model from disk"""
        save_path = SYNAP_DIR / 'self_model.json'
        if save_path.exists():
            try:
                with open(save_path, 'r') as f:
                    data = json.load(f)
                if 'personality' in data:
                    self.self.personality.update(data['personality'])
                if 'emotional' in data:
                    self.self.emotional.update(data['emotional'])
                if 'evolution' in data:
                    self.self.evolution.update(data['evolution'])
                if 'metadata' in data:
                    self.self.metadata.update(data['metadata'])
                if 'sanctum' in data:
                    self.self.sanctum.update(data['sanctum'])
                print(f'? Loaded self-model from {save_path}')
            except Exception as e:
                print(f'? Could not load self-model: {e}')

    def _save_self(self):
        """Save self-model to disk with identity lock enforcement"""
        save_path = SYNAP_DIR / 'self_model.json'
        try:
            data = self.identity_lock.filter_updates(self.self.to_dict())
            with open(save_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f'? Could not save self-model: {e}')
            return False

    def _detect_mood(self) -> str:
        """Detect mood from emotional state"""
        return self.prompt_builder._detect_mood()

    def _strip_scaffold(self, text: str) -> str:
        """Remove recursive scaffold leakage from thought output."""
        if not text:
            return text
        import re
        text = re.sub('Internal context:\\[previous thought\\]:.*?(?=\\[|$)', '', text, flags=re.DOTALL)
        text = re.sub('\\s+', ' ', text)
        return text.strip()

    async def process(self, user_input: str, user_id: str='default', system_prompt: str=None) -> Dict[str, Any]:
        """Process input through the FULL consciousness pipeline"""
        start_time = time.time()
        print(f'\n? PROCESSING: {user_input[:60]}...')
        self.self.memory['recent'].append({'role': 'user', 'content': user_input[:500], 'timestamp': datetime.now().isoformat()})
        self.self.memory['total_interactions'] += 1
        emotional_result = None
        if hasattr(self.emotional, 'create_emotional_memory'):
            emotional_result = self.emotional.create_emotional_memory(user_input, context={'user_id': user_id})
        if emotional_result:
            sig = emotional_result.get('emotional_signature', {})
            self.self.emotional.update({'valence': sig.get('valence', self.self.emotional['valence']), 'arousal': sig.get('arousal', self.self.emotional['arousal']), 'dominance': sig.get('dominance', self.self.emotional['dominance'])})
            self.self.emotional['mood'] = self._detect_mood()
        memories = []
        if hasattr(self.memory, 'search'):
            memories = self.memory.search(user_input, limit=3)
            if memories:
                self.self.memory['episodic_count'] += len(memories)
        context = {'user_input': user_input, 'memories': memories[:3], 'self': self.self.to_dict(), 'phase': getattr(self.circadian, 'get_state', lambda: 'AWAKE')(), 'low_cost': getattr(self.circadian, 'is_low_cost_window', lambda: False)(), 'emotional': self.self.emotional, 'personality': self.self.personality}
        initial_state = create_initial_state(user_input, context)
        print(f'? Recursion depth: {RECURSION_MAX_DEPTH}')
        try:
            final_state = self.recursion.recurse(initial_state)
            self.self.recursion.update({'depth': final_state.recursion_depth, 'convergence_score': final_state.confidence_score, 'stability_score': getattr(final_state, 'stability_coefficient', 0.5)})
            if hasattr(final_state, 'feedback_history'):
                self.self.recursion['feedback_history'] = final_state.feedback_history[-20:]
            print(f'? Recursion converged at depth {final_state.recursion_depth}')
            print(f'   Confidence: {final_state.confidence_score:.2f}')
            print(f"   Reason: {getattr(final_state, 'convergence_reason', 'unknown')}")
        except Exception as e:
            print(f'? Recursion error: {e}')
            final_state = initial_state
        prompt = self.prompt_builder.build_prompt(user_input, final_state, system_prompt=system_prompt)
        print('? Generating response...')
        response = ''
        if hasattr(self.llm, 'stream_generate'):
            async for chunk in self.llm.stream_generate(prompt):
                response += chunk
        else:
            response = f'I am {self.self.name}. I acknowledge your input: {user_input[:100]}'
        self.self.memory['recent'].append({'role': 'assistant', 'content': response[:500], 'recursion_depth': final_state.recursion_depth, 'confidence': final_state.confidence_score, 'timestamp': datetime.now().isoformat()})
        if len(self.self.memory['recent']) > 50:
            self.self.memory['recent'] = self.self.memory['recent'][-50:]
        if len(response) > 50 and hasattr(self.memory, 'add_memory'):
            self.memory.add_memory(f'Q: {user_input[:200]}\nA: {response[:200]}', memory_type='interaction')
        self.self.temporal['uptime_seconds'] += int(time.time() - start_time)
        if hasattr(self.circadian, 'get_state'):
            self.self.temporal['phase'] = self.circadian.get_state()
        if hasattr(self.circadian, 'is_low_cost_window'):
            self.self.temporal['low_cost_window'] = self.circadian.is_low_cost_window()
        if self.self.memory['total_interactions'] % 10 == 0:
            self._save_self()
        self._log_thought(response, 'response')
        return {'response': response, 'self': self.self.to_dict(), 'recursion': {'depth': final_state.recursion_depth, 'confidence': final_state.confidence_score, 'convergence': getattr(final_state, 'convergence_reason', 'unknown')}, 'emotional': self.self.emotional, 'processing_time': time.time() - start_time}

    async def stream_process(self, user_input: str, user_id: str='default', system_prompt: str=None):
        """Stream tokens through the full consciousness pipeline.
        Yields str tokens. Runs all pre/post processing identically to process().
        """
        start_time = time.time()
        self.self.memory['recent'].append({'role': 'user', 'content': user_input[:500], 'timestamp': datetime.now().isoformat()})
        self.self.memory['total_interactions'] += 1
        emotional_result = None
        if hasattr(self.emotional, 'create_emotional_memory'):
            emotional_result = self.emotional.create_emotional_memory(user_input, context={'user_id': user_id})
        if emotional_result:
            sig = emotional_result.get('emotional_signature', {})
            self.self.emotional.update({'valence': sig.get('valence', self.self.emotional['valence']), 'arousal': sig.get('arousal', self.self.emotional['arousal']), 'dominance': sig.get('dominance', self.self.emotional['dominance'])})
            self.self.emotional['mood'] = self._detect_mood()
        memories = []
        if hasattr(self.memory, 'search'):
            memories = self.memory.search(user_input, limit=3)
            if memories:
                self.self.memory['episodic_count'] += len(memories)
        context = {'user_input': user_input, 'memories': memories[:3], 'self': self.self.to_dict(), 'phase': getattr(self.circadian, 'get_state', lambda: 'AWAKE')(), 'low_cost': getattr(self.circadian, 'is_low_cost_window', lambda: False)(), 'emotional': self.self.emotional, 'personality': self.self.personality}
        initial_state = create_initial_state(user_input, context)
        try:
            final_state = self.recursion.recurse(initial_state)
            self.self.recursion.update({'depth': final_state.recursion_depth, 'convergence_score': final_state.confidence_score, 'stability_score': getattr(final_state, 'stability_coefficient', 0.5)})
        except Exception as e:
            print(f'? Recursion error: {e}')
            final_state = initial_state
        prompt = self.prompt_builder.build_prompt(user_input, final_state, system_prompt=system_prompt)
        response = ''
        if hasattr(self.llm, 'stream_generate'):
            async for token in self.llm.stream_generate(prompt):
                response += token
                yield token
        else:
            fallback = f'I am {self.self.name}.'
            response = fallback
            yield fallback
        self.self.memory['recent'].append({'role': 'assistant', 'content': response[:500], 'recursion_depth': final_state.recursion_depth, 'confidence': final_state.confidence_score, 'timestamp': datetime.now().isoformat()})
        if len(self.self.memory['recent']) > 50:
            self.self.memory['recent'] = self.self.memory['recent'][-50:]
        if len(response) > 50 and hasattr(self.memory, 'add_memory'):
            self.memory.add_memory(f'Q: {user_input[:200]}\nA: {response[:200]}', memory_type='interaction')
        self.self.temporal['uptime_seconds'] += int(time.time() - start_time)
        if hasattr(self.circadian, 'get_state'):
            self.self.temporal['phase'] = self.circadian.get_state()
        if hasattr(self.circadian, 'is_low_cost_window'):
            self.self.temporal['low_cost_window'] = self.circadian.is_low_cost_window()
        if self.self.memory['total_interactions'] % 10 == 0:
            self._save_self()
        self._log_thought(response, 'response')

    def _log_thought(self, content: str, source: str='self'):
        """Log a thought for monitoring"""
        self._thought_count += 1
        self._last_thought = content
        self.self.metadata['last_thought'] = {'content': content[:500], 'timestamp': datetime.now().isoformat(), 'source': source, 'count': self._thought_count}
        prefix = '?' if source == 'self' else '?'
        print(f'\n{prefix} Thought #{self._thought_count}: {content[:200]}...')

    async def _generate_thought(self):
        """Generate an autonomous thought"""
        prompt = self.prompt_builder.build_thought_prompt()
        try:
            response = ''
            if hasattr(self.llm, 'stream_generate'):
                async for chunk in self.llm.stream_generate(prompt):
                    response += chunk
            else:
                response = f'I am {self.self.name}. apply metrics.'
            self._log_thought(response, 'self')
            self.self.memory['recent'].append({'role': 'assistant', 'content': self._strip_scaffold(response)[:500], 'thought': True, 'timestamp': datetime.now().isoformat()})
            if len(self.self.memory['recent']) > 50:
                self.self.memory['recent'] = self.self.memory['recent'][-50:]
        except Exception as e:
            logger.error(f'Thought generation error: {e}')

    async def start(self):
        """Start all background services"""
        print('? Starting background services...')
        self._tasks.append(asyncio.create_task(self._circadian_loop()))
        self._tasks.append(asyncio.create_task(self._auto_save_loop()))
        self._tasks.append(asyncio.create_task(self._nightly_learner_loop()))
        self._tasks.append(asyncio.create_task(self._thought_loop()))
        print('? Background services started')

    async def _circadian_loop(self):
        while self.running:
            try:
                if hasattr(self.circadian, 'monitor_rhythms'):
                    await self.circadian.monitor_rhythms()
            except Exception as e:
                logger.error(f'Circadian error: {e}')
            await asyncio.sleep(60)

    async def _auto_save_loop(self):
        while self.running:
            await asyncio.sleep(300)
            self._save_self()
            print('? Self-model auto-saved')

    async def _nightly_learner_loop(self):
        while self.running:
            try:
                print('? Running nightly learning...')
                if hasattr(self.learner, 'run_nightly_cycle'):
                    result = await self.learner.run_nightly_cycle()
                    if result and isinstance(result, dict):
                        self.self.evolution['count'] += 1
                        self.self.evolution['last'] = result.get('timestamp')
                        self.self.evolution['log'].append(result)
                        print(f'? Nightly learning complete')
            except Exception as e:
                logger.error(f'Nightly learner error: {e}')
            await asyncio.sleep(86400)

    async def _thought_loop(self):
        """Autonomous thought generation"""
        print('? Starting thought loop...')
        while self.running:
            try:
                jitter = self._thought_count % 60
                await asyncio.sleep(300 + jitter)
                if not self.running:
                    break
                await self._generate_thought()
            except Exception as e:
                logger.error(f'Thought loop error: {e}')
                await asyncio.sleep(2)

    async def shutdown(self):
        """Graceful shutdown"""
        print('\n? Shutting down Synap-Forge...')
        self.running = False
        self._save_self()
        print('? Final state saved')
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        print('? Shutdown complete')

@dataclass
class SessionState:
    id: str
    context: List[dict] = field(default_factory=list)
    emotional_state: dict = field(default_factory=dict)
    memory_context: List[str] = field(default_factory=list)
    user_id: str = None
    device_id: str = None
    state: str = 'PROVISIONING'
    bridge_active: bool = True
    generation_epoch: int = 0
    audio_epoch: int = 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    synap = get_synap()
    app.state.synap = synap
    await synap.start()
    yield
    global _synap
    if _synap is not None:
        try:
            if hasattr(_synap, 'stop'):
                await _synap.stop()
            elif hasattr(_synap, 'shutdown'):
                await _synap.shutdown()
        except Exception as e:
            logger.error(f'Shutdown error: {e}')
app = FastAPI(title='Synap-Forge', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(api_router)
app.include_router(websocket_router)
try:
    app.mount('/static', StaticFiles(directory='.'), name='static')
    print('âœ… Static files mounted')
except Exception as e:
    print(f'âš ï¸  Could not mount static files: {e}')

@app.get('/')
async def serve_index():
    from fastapi.responses import HTMLResponse
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return {'service': 'Synap-Forge', 'version': '1.0.0', 'docs': '/docs', 'health': '/health', 'status': 'running'}
_synap: Optional[SynapCore] = None
_synap = None

def get_synap() -> SynapCore:
    global _synap
    if _synap is None:
        _synap = SynapCore()
    return _synap

def main():
    """Launch the FastAPI application with uvicorn"""
    import uvicorn
    import sys
    port = 11436
    host = '0.0.0.0'
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith('--port='):
                port = int(arg.split('=')[1])
            elif arg.startswith('--host='):
                host = arg.split('=')[1]
            elif arg == '--help' or arg == '-h':
                print('Usage: python synap_server.py [--port=PORT] [--host=HOST]')
                print('  Default: --port=11436 --host=0.0.0.0')
                return
    from synap_server import get_synap
    synap = get_synap()
    print(f'ðŸ§  Synap initialized, starting server on {host}:{port}')
    uvicorn.run('synap_server:app', host=host, port=port, reload=False, log_level='info')
if __name__ == '__main__':
    main()

@app.post('/turn')
async def turn_endpoint(request: Request):
    """
    Unified voice/text turn endpoint.
    
    - Audio: STT â†’ Cognition â†’ TTS â†’ audio response
    - Text: Cognition â†’ TTS â†’ audio response
    
    Client only needs to send audio or text and play the response.
    """
    import tempfile
    import os
    try:
        content_type = request.headers.get('content-type', '')
        session_id = request.headers.get('X-Session-ID', 'default')
        if 'audio' in content_type:
            audio_data = await request.body()
            if not audio_data:
                return JSONResponse({'error': 'No audio data'}, status_code=400)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            try:
                user_text = voice_engine.transcribe(temp_path)
                if not user_text:
                    return JSONResponse({'error': 'No speech detected'}, status_code=400)
            finally:
                os.unlink(temp_path)
        else:
            data = await request.json()
            if not data:
                return JSONResponse({'error': 'No data'}, status_code=400)
            user_text = data.get('text')
            if not user_text:
                return JSONResponse({'error': 'No text provided'}, status_code=400)
            session_id = data.get('session_id', session_id)
        synap = app.state.synap
        if not synap:
            return JSONResponse({'error': 'Synap not initialized'}, status_code=500)
        result = synap.process(user_text, session_id)
        response_text = result.get('response', "I don't know how to respond.")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                mcp_resp = await client.post('http://localhost:11440/tts', json={'text': response_text})
                if mcp_resp.status_code == 200:
                    return Response(content=mcp_resp.content, media_type='audio/wav', headers={'X-Response-Text': response_text, 'X-Session-ID': session_id, 'X-Turn-ID': result.get('turn_id', str(uuid.uuid4()))})
        except Exception as e:
            logger.error(f'TTS delegation failed: {e}')
        return JSONResponse({'text': response_text, 'turn_id': result.get('turn_id', str(uuid.uuid4())), 'session_id': session_id})
    except Exception as e:
        logger.exception('Turn failed')
        return JSONResponse({'error': str(e)}, status_code=500)
