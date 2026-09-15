# app/rl/safety.py
"""Production safety guardrails for RL controller"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class SafetyConfig:
    max_action_frequency: float = 0.2  # Hz
    max_single_action_delta: float = 15.0  # points
    max_risk_tolerance: float = 0.7
    min_safety_margin: float = 0.2
    reward_anomaly_std: float = 3.0
    action_history_size: int = 100
    enabled: bool = True

class SafetyLayer:
    """Production safety guardrails for RL"""
    
    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()
        self.action_history = deque(maxlen=self.config.action_history_size)
        self.reward_history = deque(maxlen=self.config.action_history_size)
        self.last_action_time = 0.0
        self.anomaly_count = 0
        self.circuit_breaker = False
    
    def check_action(self, actions: Dict[str, Dict]) -> tuple[bool, str]:
        """Validate action before execution"""
        
        # 1. Circuit breaker
        if self.circuit_breaker:
            return False, "Circuit breaker open - manual reset required"
        
        # 2. Rate limiting
        if self.config.max_action_frequency > 0:
            now = time.time()
            min_interval = 1.0 / self.config.max_action_frequency
            if now - self.last_action_time < min_interval:
                return False, f"Rate limit: {1/min_interval:.1f} Hz max"
            self.last_action_time = now
        
        # 3. Check each action
        for service, action in actions.items():
            delta = action.get("delta_canary", 0)
            
            # Max delta check
            if abs(delta) > self.config.max_single_action_delta:
                return False, f"Delta {delta:.1f} exceeds max {self.config.max_single_action_delta}"
            
            # Risk check (if service has current risk)
            if hasattr(self, 'service_risks'):
                risk = self.service_risks.get(service, 0)
                if risk > self.config.max_risk_tolerance:
                    return False, f"Service {service} risk {risk:.2f} exceeds tolerance"
        
        # 4. All checks passed
        self.action_history.append(actions)
        return True, "OK"
    
    def check_reward(self, reward: float) -> tuple[bool, str]:
        """Check for reward anomalies"""
        self.reward_history.append(reward)
        
        if len(self.reward_history) < 10:
            return True, "Learning phase"
        
        # Detect anomalies
        mean = np.mean(self.reward_history)
        std = np.std(self.reward_history)
        
        if std > 0:
            z_score = abs(reward - mean) / std
            if z_score > self.config.reward_anomaly_std:
                self.anomaly_count += 1
                if self.anomaly_count > 3:
                    self.circuit_breaker = True
                    return False, f"Anomaly detected: z={z_score:.2f}, circuit broken"
                return False, f"Anomaly detected: z={z_score:.2f}"
            else:
                self.anomaly_count = max(0, self.anomaly_count - 1)
        
        return True, "OK"
    
    def update_risks(self, service_risks: Dict[str, float]):
        """Update service risk levels for checks"""
        self.service_risks = service_risks
    
    def get_safe_action(self, actions: Dict[str, Dict]) -> Dict[str, Dict]:
        """Generate safe fallback action"""
        safe = {}
        for service, action in actions.items():
            delta = action.get("delta_canary", 0)
            # Clamp to safety limits
            safe[service] = {
                "delta_canary": np.clip(delta, -5.0, 5.0)
            }
        return safe
    
    def reset(self):
        """Reset safety state"""
        self.circuit_breaker = False
        self.anomaly_count = 0
        self.action_history.clear()
        self.reward_history.clear()
    
    def get_status(self) -> dict:
        """Get safety status"""
        return {
            "circuit_breaker": self.circuit_breaker,
            "anomaly_count": self.anomaly_count,
            "action_count": len(self.action_history),
            "reward_count": len(self.reward_history),
            "enabled": self.config.enabled
        }