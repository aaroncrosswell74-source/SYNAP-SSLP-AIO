"""
Non-Deterministic Recursive Feedback
=====================================

Implements consciousness recursion where outputs become inputs.

Theory:
    Consciousness exhibits recursive self-reference:
        ψ(t+1) = f(ψ(t), input(t))
    
    Each iteration:
        1. Process current state
        2. Extract feedback signal
        3. Inject feedback into next iteration
        4. Apply non-deterministic noise
    
    This creates:
        - Self-modifying processing
        - Emergent pattern exploration
        - Adaptive response generation

Key Concepts:
    - Feedback Coefficient (alpha): How much output influences next input (0-1)
    - Max Depth: Recursion limit to prevent infinite loops
    - Noise Injection: Random perturbations for exploration
    - Convergence Detection: Stop when state stabilizes
    - State History: Track evolution through recursion cycles

Architecture:
    RecursionEngine manages the feedback loop lifecycle.
    Each iteration processes through ConsciousnessProcessor,
    then extracts feedback signal for next iteration.

Safety:
    - Hard recursion limit (default: 10)
    - Timeout protection prevents hanging
    - Convergence detection prevents wasted computation
    - Feedback coefficient clamped to [0, 1]
    - Divergence detection stops unstable recursion

Usage:
    from loop import RecursionEngine
    from core import ProcessingState
    
    engine = RecursionEngine(max_depth=10, feedback_coefficient=0.7)
    
    initial_state = ProcessingState(raw_input="What is consciousness?")
    final_state = engine.recurse(initial_state)

Performance:
    - Each iteration: ~100ms (depends on LLM)
    - Typical convergence: 3-5 iterations
    - Max iterations: 10 (safety limit)
"""

import logging
import time
import numpy as np
from typing import Optional, Callable, List, Dict, Any
from core.state import ProcessingState
from core.base import ConsciousnessProcessor

logger = logging.getLogger(__name__)


class RecursionEngine:
    """
    Manages recursive feedback loops for consciousness processing
    
    Attributes:
        max_depth: Maximum recursion iterations (safety limit)
        feedback_coefficient: How much output influences next input (0-1)
        noise_level: Random perturbation strength (0-1)
        convergence_threshold: Stop if state change < threshold
        processor: ConsciousnessProcessor instance
        stats: Performance and monitoring statistics
        feedback_history: History of feedback values
    
    Methods:
        recurse(state): Run recursive feedback loop
        apply_feedback(state, feedback): Inject feedback into state
        extract_feedback(state): Extract feedback signal from state
        check_convergence(state1, state2): Detect if recursion converged
        check_divergence(state1, state2): Detect unstable recursion
    """
    
    def __init__(
        self,
        max_depth: int = 10,
        feedback_coefficient: float = 0.8,
        noise_level: float = 0.1,
        convergence_threshold: float = 0.01,
        processor: Optional[ConsciousnessProcessor] = None,
        timeout_seconds: int = 30
    ):
        """
        Initialize recursion engine
        
        Args:
            max_depth: Maximum recursion iterations (default: 10)
            feedback_coefficient: Output→input influence (0-1, default: 0.8)
            noise_level: Random exploration strength (0-1, default: 0.1)
            convergence_threshold: Stop if change < threshold (default: 0.01)
            processor: Optional custom processor instance
            timeout_seconds: Maximum time allowed for recursion (default: 30)
        
        Raises:
            ValueError: If parameters out of valid range
        """
        
        if not 0 <= feedback_coefficient <= 1:
            raise ValueError(f"feedback_coefficient must be in [0,1], got {feedback_coefficient}")
        
        if not 0 <= noise_level <= 1:
            raise ValueError(f"noise_level must be in [0,1], got {noise_level}")
        
        if max_depth < 1:
            raise ValueError(f"max_depth must be >= 1, got {max_depth}")
        
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be > 0, got {timeout_seconds}")
        
        self.max_depth = max_depth
        self.feedback_coefficient = feedback_coefficient
        self.noise_level = noise_level
        self.convergence_threshold = convergence_threshold
        self.timeout_seconds = timeout_seconds
        
        # Make processor injectable
        self.processor = processor or ConsciousnessProcessor()
        
        # Statistics and monitoring
        self.stats = {
            'total_runs': 0,
            'total_iterations': 0,
            'convergence_depths': [],
            'timeout_occurrences': 0,
            'divergence_occurrences': 0,
            'avg_convergence_depth': 0.0
        }
        
        self.feedback_history: List[float] = []
        
        logger.info(
            f"RecursionEngine initialized: "
            f"max_depth={max_depth}, alpha={feedback_coefficient:.2f}, "
            f"noise={noise_level:.2f}, timeout={timeout_seconds}s"
        )
    
    def recurse(
        self, 
        initial_state: ProcessingState,
        custom_processor: Optional[ConsciousnessProcessor] = None,
        callback: Optional[Callable] = None
    ) -> ProcessingState:
        """
        Run recursive feedback loop until convergence or max_depth
        
        Process:
            1. Check early exit conditions
            2. Process state through pipeline
            3. Extract feedback signal
            4. Inject feedback + noise into next iteration
            5. Check convergence/divergence
            6. Track state history
            7. Repeat or return
        
        Args:
            initial_state: Starting state
            custom_processor: Optional custom processor (default: self.processor)
            callback: Optional progress callback function
        
        Returns:
            Final converged state with recursion_depth and state_history
        
        Example:
            >>> engine = RecursionEngine(max_depth=10)
            >>> state = ProcessingState(raw_input="What is reality?")
            >>> result = engine.recurse(state)
        """
        
        self.stats['total_runs'] += 1
        start_time = time.time()
        
        processor = custom_processor or self.processor
        
        # Early exit for already confident states
        if initial_state.confidence_score > 0.95:
            logger.info("✓ Early exit: State already highly confident")
            return initial_state.replace(
                recursion_depth=0,
                convergence_reason="already_confident",
                state_history=[initial_state.replace()]
            )
        
        current_state = initial_state
        previous_state = None
        state_history = [initial_state.replace()]
        feedback_values = []

        def _finalize(state, depth, reason=None):
            return state.replace(
                state_history=state_history,
                recursion_depth=depth,
                convergence_reason=reason if reason is not None else state.convergence_reason,
            )
        
        for depth in range(1, self.max_depth + 1):
            # Timeout protection
            elapsed_time = time.time() - start_time
            if elapsed_time > self.timeout_seconds:
                logger.warning(f"⏱️ Timeout after {elapsed_time:.1f}s")
                self.stats['timeout_occurrences'] += 1
                current_state = current_state.replace(
                    recursion_depth=depth,
                    timed_out=True,
                    convergence_reason="timeout"
                )
                return _finalize(current_state, depth, "timeout")
            
            logger.info(f"Recursion depth: {depth}/{self.max_depth}")
            
            # Process through pipeline
            current_state = processor.process(current_state)
            state_history.append(current_state.replace())
            
            # Check convergence (skip if first iteration)
            if previous_state is not None:
                if self.check_convergence(previous_state, current_state):
                    logger.info(f"✓ Converged at depth {depth}")
                    self.stats['convergence_depths'].append(depth)
                    self.stats['total_iterations'] += depth
                    current_state = current_state.replace(
                        recursion_depth=depth,
                        convergence_reason="converged"
                    )
                    
                    # Update average convergence depth
                    depths = self.stats['convergence_depths']
                    self.stats['avg_convergence_depth'] = sum(depths) / len(depths)
                    
                    return _finalize(current_state, depth, "converged")
                
                # Check for divergence
                if self.check_divergence(previous_state, current_state):
                    logger.warning(f"⚠ Divergence detected at depth {depth}")
                    self.stats['divergence_occurrences'] += 1
                    current_state = current_state.replace(
                        recursion_depth=depth,
                        convergence_reason="diverged"
                    )
                    return _finalize(current_state, depth, "diverged")
            
            # Extract feedback for next iteration
            feedback = self.extract_feedback(current_state)
            feedback_values.append(feedback)
            self.feedback_history.append(feedback)
            
            # Apply feedback + noise
            current_state = self.apply_feedback(
                current_state, 
                feedback,
                self.feedback_coefficient,
                self.noise_level
            )
            
            # Call progress callback if provided
            if callback:
                callback({
                    'depth': depth,
                    'state': current_state.replace(),
                    'feedback': feedback,
                    'elapsed_time': elapsed_time
                })
            
            previous_state = current_state
        
        # Hit max depth without convergence
        logger.warning(f"⚠ Max depth {self.max_depth} reached without convergence")
        self.stats['total_iterations'] += self.max_depth
        
        current_state = current_state.replace(
            recursion_depth=self.max_depth,
            convergence_reason="max_depth_reached"
        )
        
        return _finalize(current_state, self.max_depth, "max_depth_reached")
    
    def apply_feedback(
        self,
        state: ProcessingState,
        feedback: float,
        coefficient: float,
        noise: float
    ) -> ProcessingState:
        """
        Inject feedback signal into state for next iteration
        
        Formula:
            new_input = alpha * feedback + (1-alpha) * original + noise
        
        Args:
            state: Current state
            feedback: Feedback signal (-1 to 1)
            coefficient: Feedback strength (0-1)
            noise: Noise injection level (0-1)
        
        Returns:
            State with feedback applied
        """
        
        # Generate random noise
        random_noise = np.random.randn() * noise
        
        # Apply adaptive coefficient based on state stability
        if hasattr(state, 'stability_coefficient'):
            # More stable states need less adaptation
            adaptive_coefficient = coefficient * (1 - state.stability_coefficient)
            coefficient = min(1.0, max(0.1, adaptive_coefficient))
        
        # Apply noise and feedback to state content
        new_context = state.context.copy() 
        
        # Apply noise to activation if present
        if 'activation' in new_context:
            new_context['activation'] = np.clip(
                new_context['activation'] + random_noise * 0.1,
                -1.0, 1.0
            )
        
        # Apply feedback signal to context
        new_context['previous_feedback'] = feedback
        new_context['feedback_coefficient'] = coefficient
        new_context['noise_injection'] = random_noise
        
        # Adjust raw_input based on feedback (if applicable)
        if hasattr(state, 'raw_input') and feedback != 0:
            # Simple feedback application to input
            feedback_effect = feedback * coefficient * 0.1  # Scale down
            # Store in context rather than modifying raw_input directly
            new_context['feedback_adjustment'] = feedback_effect
        
        return state.replace(context=new_context)
    
    def extract_feedback(self, state: ProcessingState) -> float:
        """
        Extract feedback signal from processed state
        
        Feedback Types:
            - Confidence score → Direct feedback
            - Clarity metric → Quality feedback
            - Stability coefficient → Convergence feedback
            - Novelty score → Exploration feedback
        
        Args:
            state: Processed state
        
        Returns:
            Feedback signal (-1 to 1)
        
        Example:
            High confidence → Positive feedback (continue this direction)
            Low confidence → Negative feedback (explore alternatives)
        """
        
        # Use confidence score as primary feedback
        feedback = state.confidence_score - 0.5  # Center around 0
        
        # Adjust based on clarity if available
        if hasattr(state, 'clarity_score'):
            clarity_adjustment = (state.clarity_score - 0.5) * 0.3
            feedback += clarity_adjustment
        
        # Adjust based on stability
        if hasattr(state, 'stability_coefficient'):
            stability_adjustment = (state.stability_coefficient - 0.5) * 0.2
            feedback += stability_adjustment
        
        # Check for novelty if available
        if hasattr(state, 'novelty_score'):
            # High novelty → encourage exploration (positive feedback)
            novelty_adjustment = state.novelty_score * 0.2
            feedback += novelty_adjustment
        
        # Clamp to [-1, 1]
        feedback = np.clip(feedback, -1.0, 1.0)
        
        logger.debug(f"Extracted feedback: {feedback:.3f}")
        
        return float(feedback)
    
    def check_convergence(
        self,
        state1: ProcessingState,
        state2: ProcessingState
    ) -> bool:
        """
        Check if recursion has converged (state stabilized)
        
        Convergence Criteria:
            State is converged if weighted change in key metrics < threshold
        
        Args:
            state1: Previous state
            state2: Current state
        
        Returns:
            True if converged, False otherwise
        """
        
        # Weighted convergence metrics
        metrics = []
        weights = []
        
        # Confidence delta (highest weight)
        conf_delta = abs(state2.confidence_score - state1.confidence_score)
        metrics.append(conf_delta)
        weights.append(0.4)
        
        # Stability delta
        if hasattr(state1, 'stability_coefficient') and hasattr(state2, 'stability_coefficient'):
            stab_delta = abs(state2.stability_coefficient - state1.stability_coefficient)
            metrics.append(stab_delta)
            weights.append(0.3)
        
        # Clarity delta
        if hasattr(state1, 'clarity_score') and hasattr(state2, 'clarity_score'):
            clarity_delta = abs(state2.clarity_score - state1.clarity_score)
            metrics.append(clarity_delta)
            weights.append(0.2)
        
        # Context similarity (if available)
        if 'embedding' in state1.context and 'embedding' in state2.context:
            try:
                # Simple cosine similarity for embeddings
                emb1 = np.array(state1.context['embedding'])
                emb2 = np.array(state2.context['embedding'])
                similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
                context_delta = 1 - similarity
                metrics.append(context_delta)
                weights.append(0.1)
            except:
                pass
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1.0
        weights = [w / total_weight for w in weights]
        
        # Calculate weighted delta
        weighted_delta = sum(m * w for m, w in zip(metrics, weights))
        
        converged = weighted_delta < self.convergence_threshold
        
        if converged:
            logger.debug(
                f"Convergence detected: Δweighted={weighted_delta:.4f} "
                f"(threshold={self.convergence_threshold:.4f})"
            )
        
        return converged
    
    def check_divergence(
        self,
        state1: ProcessingState,
        state2: ProcessingState
    ) -> bool:
        """
        Check if recursion is diverging (becoming unstable)
        
        Divergence Criteria:
            - Confidence drops significantly
            - State metrics become more variable
            - Feedback oscillations increase
        
        Args:
            state1: Previous state
            state2: Current state
        
        Returns:
            True if diverging, False otherwise
        """
        
        # Check for significant confidence drop
        if state2.confidence_score < state1.confidence_score - 0.3:
            return True
        
        # Check for extreme feedback oscillations (last 3 values)
        if len(self.feedback_history) >= 3:
            recent_feedback = self.feedback_history[-3:]
            feedback_range = max(recent_feedback) - min(recent_feedback)
            if feedback_range > 1.5:  # Extreme oscillation
                return True
        
        # Check for context collapse (everything becoming similar)
        if hasattr(state2, 'context') and 'embedding' in state2.context:
            # Check if embedding norm is very small (collapsed state)
            try:
                emb_norm = np.linalg.norm(state2.context['embedding'])
                if emb_norm < 0.01:
                    return True
            except:
                pass
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine performance statistics
        
        Returns:
            Dictionary with performance metrics
        """
        
        return {
            **self.stats,
            'total_feedback_points': len(self.feedback_history),
            'avg_feedback': np.mean(self.feedback_history) if self.feedback_history else 0.0,
            'feedback_std': np.std(self.feedback_history) if self.feedback_history else 0.0,
            'convergence_rate': (
                len(self.stats['convergence_depths']) / self.stats['total_runs']
                if self.stats['total_runs'] > 0 else 0.0
            ),
            'current_config': {
                'max_depth': self.max_depth,
                'feedback_coefficient': self.feedback_coefficient,
                'noise_level': self.noise_level,
                'convergence_threshold': self.convergence_threshold,
                'timeout_seconds': self.timeout_seconds
            }
        }
    
    def reset_statistics(self) -> None:
        """
        Reset engine statistics (keep configuration)
        """
        
        self.stats = {
            'total_runs': 0,
            'total_iterations': 0,
            'convergence_depths': [],
            'timeout_occurrences': 0,
            'divergence_occurrences': 0,
            'avg_convergence_depth': 0.0
        }
        self.feedback_history = []
        logger.info("Statistics reset")


def apply_feedback(
    state: ProcessingState,
    feedback_signal: float,
    coefficient: float = 0.8,
    noise_level: float = 0.0
) -> ProcessingState:
    """
    Standalone function to apply feedback to state
    
    Use Case:
        Quick feedback application without full RecursionEngine
    
    Args:
        state: Current processing state
        feedback_signal: Feedback value (-1 to 1)
        coefficient: Feedback strength (0-1)
        noise_level: Optional noise injection (0-1)
    
    Returns:
        State with feedback applied
    
    Example:
        >>> state = ProcessingState(raw_input="test")
        >>> state_with_feedback = apply_feedback(state, 0.5, 0.7)
    """
    
    new_context = state.context.copy() 
    
    # Apply feedback
    new_context['feedback_signal'] = feedback_signal
    new_context['feedback_coefficient'] = coefficient
    
    # Apply optional noise
    if noise_level > 0:
        random_noise = np.random.randn() * noise_level
        if 'activation' in new_context:
            new_context['activation'] += random_noise * 0.1
    
    return state.replace(context=new_context)


def create_feedback_loop(
    processor: ConsciousnessProcessor,
    max_iterations: int = 5,
    feedback_fn: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> Callable:
    """
    Factory function to create custom feedback loops
    
    Args:
        processor: ConsciousnessProcessor instance
        max_iterations: Loop limit
        feedback_fn: Custom feedback extraction function
        progress_callback: Optional progress callback
    
    Returns:
        Function that runs feedback loop
    
    Example:
        >>> def my_feedback(state):
        ...     return state.confidence_score * 2 - 1
        >>> 
        >>> loop = create_feedback_loop(
        ...     processor, 
        ...     max_iterations=3,
        ...     feedback_fn=my_feedback
        ... )
        >>> result = loop(initial_state)
    """
    
    def feedback_loop(initial_state: ProcessingState) -> ProcessingState:
        state = initial_state
        
        for i in range(max_iterations):
            state = processor.process(state)
            
            if feedback_fn:
                feedback = feedback_fn(state)
                state = apply_feedback(state, feedback)
            
            if progress_callback:
                progress_callback({
                    'iteration': i + 1,
                    'state': state.replace(),
                    'feedback': feedback if feedback_fn else None
                })
        
        return state
    
    return feedback_loop