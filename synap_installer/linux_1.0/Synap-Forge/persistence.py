# app/observability/metrics.py
"""Prometheus metrics for production monitoring"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    generate_latest, CONTENT_TYPE_LATEST,
    REGISTRY
)
from fastapi import Response
import time
from functools import wraps

# ── Metrics ──
class SynapMetrics:
    def __init__(self):
        # System metrics
        self.steps_total = Counter(
            'synap_rl_steps_total',
            'Total RL steps taken',
            ['service']
        )
        self.episodes_total = Counter(
            'synap_rl_episodes_total',
            'Total RL episodes completed'
        )
        self.rewards_total = Counter(
            'synap_rl_rewards_total',
            'Total cumulative reward'
        )
        
        # Service metrics
        self.service_risk = Gauge(
            'synap_service_risk',
            'Current risk level per service',
            ['service']
        )
        self.service_canary = Gauge(
            'synap_service_canary',
            'Current canary score per service',
            ['service']
        )
        self.service_throughput = Gauge(
            'synap_service_throughput',
            'Current throughput per service',
            ['service']
        )
        
        # Controller metrics
        self.epsilon = Gauge(
            'synap_rl_epsilon',
            'Current exploration epsilon'
        )
        self.loss = Gauge(
            'synap_rl_loss',
            'Current training loss'
        )
        self.reward = Gauge(
            'synap_rl_current_reward',
            'Current step reward'
        )
        
        # Performance metrics
        self.processing_time = Histogram(
            'synap_processing_seconds',
            'Processing time in seconds',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        self.memory_count = Gauge(
            'synap_memory_count',
            'Number of stored memories'
        )
        
        # Health metrics
        self.uptime_seconds = Gauge(
            'synap_uptime_seconds',
            'System uptime in seconds'
        )
        self.startup_time = time.time()
    
    def update_services(self, health: Dict[str, Dict]):
        """Update service metrics"""
        for name, svc in health.items():
            self.service_risk.labels(service=name).set(svc.get('risk', 0))
            self.service_canary.labels(service=name).set(svc.get('canary', 50))
            self.service_throughput.labels(service=name).set(svc.get('throughput', 0))
    
    def update_rl(self, state: Dict[str, Any]):
        """Update RL metrics"""
        self.epsilon.set(state.get('epsilon', 1.0))
        if 'loss' in state and state['loss'] is not None:
            self.loss.set(state['loss'])
        if 'reward' in state:
            self.reward.set(state['reward'])
            self.rewards_total.inc(state['reward'])

metrics = SynapMetrics()

# ── Metrics endpoint ──
@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(
        generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )

# ── Structured logging ──
class StructuredLogger:
    """JSON structured logging"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: int, msg: str, **kwargs):
        """Log with structured data"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": msg,
            "level": logging.getLevelName(level),
        }
        record.update(kwargs)
        
        if level >= logging.ERROR:
            self.logger.error(json.dumps(record))
        elif level >= logging.WARNING:
            self.logger.warning(json.dumps(record))
        elif level >= logging.INFO:
            self.logger.info(json.dumps(record))
        else:
            self.logger.debug(json.dumps(record))
    
    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)
    
    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

logger = StructuredLogger("synap-forge")