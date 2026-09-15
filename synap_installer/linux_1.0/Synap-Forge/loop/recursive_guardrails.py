# recursive_guardrails.py

from dataclasses import dataclass
import time
import asyncio

@dataclass
class RecursionLimits:
    max_depth: int = 5          # Maximum recursion depth
    max_cost: float = 100.0     # Maximum token cost in USD (or units)
    max_time: float = 30.0      # Maximum seconds per recursive cycle
    max_iterations: int = 10    # Maximum iterations before forced convergence

class RecursionGuard:
    def __init__(self):
        self.limits = RecursionLimits()
        self.metrics = {
            "depth": 0,
            "cost": 0.0,
            "time": 0.0,
            "iterations": 0
        }
        self.start_time = None
        
    def enter_recursion(self, module_name: str):
        """Called when entering a recursive module"""
        self.start_time = time.time()
        self.metrics["depth"] += 1
        self.metrics["iterations"] += 1
        
        # Check limits BEFORE entering
        self._check_limits(module_name)
        
    def _check_limits(self, module_name: str):
        if self.metrics["depth"] > self.limits.max_depth:
            raise RecursionError(
                f"Max recursion depth exceeded in {module_name}. "
                f"Depth: {self.metrics['depth']} > {self.limits.max_depth}"
            )
            
        if self.metrics["cost"] > self.limits.max_cost:
            raise CostError(
                f"Max token cost exceeded in {module_name}. "
                f"Cost: ${self.metrics['cost']:.2f} > ${self.limits.max_cost:.2f}"
            )
            
        if time.time() - self.start_time > self.limits.max_time:
            raise TimeoutError(
                f"Max time exceeded in {module_name}. "
                f"Time: {time.time() - self.start_time:.2f}s > {self.limits.max_time:.2f}s"
            )
            
    def exit_recursion(self, cost_incurred: float = 0.0):
        """Called when exiting a recursive module"""
        self.metrics["depth"] -= 1
        self.metrics["cost"] += cost_incurred
        
    def reset(self):
        """Reset between top-level operations"""
        self.metrics = {
            "depth": 0,
            "cost": 0.0,
            "time": 0.0,
            "iterations": 0
        }
        self.start_time = None

# Usage example:
guard = RecursionGuard()

async def recursive_improvement(data):
    guard.enter_recursion("recursive_improvement")
    try:
        # Your recursive logic here
        result = await process_data(data)
        
        # Track token cost
        cost = estimate_tokens(result) * 0.0001  # Example cost calculation
        guard.exit_recursion(cost)
        return result
    except (RecursionError, CostError, TimeoutError) as e:
        # Graceful fallback
        logger.error(f"Recursion terminated: {e}")
        return data  # Return original data as fallback