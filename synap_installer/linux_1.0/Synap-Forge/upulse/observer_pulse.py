
"""
Observer Pulse Parameter Sweep: Elastic Phase Diagram
=====================================================

Sweeps (J, g_RS, κ, γ_φ) to map:
- Integration zones (fast recovery, high fidelity)
- Fracture zones (slow/no recovery, low fidelity)
- Haunted zones (oscillatory, intermediate recovery)

Metrics tracked:
- Steady-state I(R:SAB) and I(R:M)
- Recovery time to 90% plateau
- Post-pulse fidelity to pre-pulse state
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Import from your observer_pulse.py
from observer_pulse import (
    SynapseState, ObserverPulseExperiment,
    engineered_dissipator, feedback_modulation
)


@dataclass
class SweepPoint:
    """Single point in parameter space"""
    J: float
    g_RS: float
    kappa: float
    gamma_phi: float
    
    # Metrics
    I_R_SAB_steady: float = np.nan
    I_R_M_steady: float = np.nan
    recovery_time: float = np.nan
    post_pulse_fidelity: float = np.nan
    
    # Classification
    regime: str = "unknown"  # integration, fracture, haunted, unstable
    
    def to_dict(self) -> Dict:
            return asdict(self)


class ParameterSweep:
    """
    Orchestrates parameter sweep for Observer Pulse experiments
    """
    
def run_single_point(self, point: SweepPoint) -> SweepPoint:
        """
        Run Observer Pulse experiment for a single parameter point
        """
        try:
            # Create experiment
            exp = ObserverPulseExperiment
                J=point.J,
    """
    Parameters:
    -----------
    *_range : (min, max, n_points) for each parameter
    output_dir : Directory for results
    n_workers : Parallel workers (None = sequential, -1 = all cores)
    """
    self.J_vals = np.linspace(*J_range)
    self.g_RS_vals = np.linspace(*g_RS_range)
    self.kappa_vals = np.linspace(*kappa_range)
    self.gamma_phi_vals = np.linspace(*gamma_phi_range)
    
    self.output_dir = Path(output_dir)
    self.output_dir.mkdir(exist_ok=True)
    
    self.n_workers = n_workers
    self.results: List[SweepPoint] = []
    
    # Experiment parameters (fixed across sweep)
    self.exp_params = {
        'dt': 0.01,
        'T_pre': 50.0,
        'T_pulse': 10.0,
        'T_post': 100.0,
        'pulse_strength': 0.5,
        'fidelity_threshold': 0.90
    }
    
def generate_grid(self) -> List[SweepPoint]:
    """Generate all parameter combinations"""
    points = []
for J in self.J_vals:
    for g_RS in self.g_RS_vals:
        for kappa in self.kappa_vals:
            for gamma_phi in self.gamma_phi_vals:
                points.append(SweepPoint(J, g_RS, kappa, gamma_phi))
    return points
    
    def run_single_point(self, point: SweepPoint) -> SweepPoint:
    """
    Run Observer Pulse experiment for a single parameter point
    """
    try:
        # Create experiment
        exp = ObserverPulseExperiment(
        J=point.J,
        g_RS=point.g_RS,
        kappa=point.kappa,
        gamma_phi=point.gamma_phi,
        dt=self.exp_params['dt']
        )
        
        # Run experiment
        exp.run_experiment(
        T_pre=self.exp_params['T_pre'],
        T_pulse=self.exp_params['T_pulse'],
        T_post=self.exp_params['T_post'],
        pulse_strength=self.exp_params['pulse_strength'],
        dissipator_fn=engineered_dissipator,
        feedback_fn=feedback_modulation
        )
        
        # Extract metrics
        metrics = self._extract_metrics(exp)
        
        # Update point
        point.I_R_SAB_steady = metrics['I_R_SAB_steady']
        point.I_R_M_steady = metrics['I_R_M_steady']
        point.recovery_time = metrics['recovery_time']
        point.post_pulse_fidelity = metrics['post_pulse_fidelity']
        point.regime = metrics['regime']
        
    except Exception as e:
        print(f"Error at J={point.J:.3f}, g_RS={point.g_RS:.3f}, "
          f"κ={point.kappa:.3f}, γ_φ={point.gamma_phi:.3f}: {e}")
        point.regime = "error"
    
    return point
    
    def _extract_metrics(self, exp: ObserverPulseExperiment) -> Dict:
    """Extract all metrics from completed experiment"""
    
    # Time indices
    t = exp.times
    pulse_start_idx = np.argmin(np.abs(t - self.exp_params['T_pre']))
    pulse_end_idx = np.argmin(np.abs(t - (self.exp_params['T_pre'] + 
                        self.exp_params['T_pulse'])))
    
    # Pre-pulse steady state (average last 20% of pre-pulse)
    pre_window = slice(int(0.8 * pulse_start_idx), pulse_start_idx)
    I_R_SAB_steady = np.mean(exp.I_R_SAB[pre_window])
    I_R_M_steady = np.mean(exp.I_R_M[pre_window])
    
    # Post-pulse behavior
    post_slice = slice(pulse_end_idx, None)
    t_post = t[post_slice] - t[pulse_end_idx]
    I_R_SAB_post = exp.I_R_SAB[post_slice]
    I_R_M_post = exp.I_R_M[post_slice]
    
    # Recovery time (to 90% of pre-pulse value)
    target = self.exp_params['fidelity_threshold'] * I_R_SAB_steady
    recovery_idx = np.where(I_R_SAB_post >= target)
    
    if len(recovery_idx) > 0:
        recovery_time = t_post[recovery_idx]
    else:
        recovery_time = np.inf  # Never recovered
    
    # Post-pulse fidelity (final 20% average vs pre-pulse)
    final_window = slice(int(0.8 * len(I_R_SAB_post)), None)
    final_I_R_SAB = np.mean(I_R_SAB_post[final_window])
    post_pulse_fidelity = final_I_R_SAB / I_R_SAB_steady if I_R_SAB_steady > 0 else 0
    
    # Classify regime
    regime = self._classify_regime(
        recovery_time, post_pulse_fidelity, I_R_SAB_post, I_R_M_post
    )
    
    return {
        'I_R_SAB_steady': I_R_SAB_steady,
        'I_R_M_steady': I_R_M_steady,
        'recovery_time': recovery_time,
        'post_pulse_fidelity': post_pulse_fidelity,
        'regime': regime
    }
    
    def _classify_regime(
    self, 
    recovery_time: float, 
    fidelity: float,
    I_R_SAB_post: np.ndarray,
    I_R_M_post: np.ndarray
    ) -> str:
    """
    Classify parameter point into regime:
    - integration: Fast recovery (< 20), high fidelity (> 0.95)
    - fracture: Slow/no recovery (> 50 or inf), low fidelity (< 0.80)
    - haunted: Oscillatory behavior, intermediate recovery
    - unstable: Divergent or invalid behavior
    """
    
    # Check for instability
    if np.any(np.isnan(I_R_SAB_post)) or np.any(np.isinf(I_R_SAB_post)):
        return "unstable"
    
    # Check for oscillations (haunted regime)
    # Look for multiple zero crossings in derivative
    if len(I_R_SAB_post) > 10:
        deriv = np.diff(I_R_SAB_post)
        zero_crossings = np.sum(np.diff(np.sign(deriv)) != 0)
        if zero_crossings > 5:  # Significant oscillation
        return "haunted"
    
    # Integration: fast recovery, high fidelity
    if recovery_time < 20 and fidelity > 0.95:
        return "integration"
    
    # Fracture: slow/no recovery, low fidelity
    if recovery_time > 50 or fidelity < 0.80:
        return "fracture"
    
    # Intermediate cases -> haunted
    return "haunted"
    
    def run_sweep(self, save_interval: int = 50):
    """
    Execute full parameter sweep
    
    Parameters:
    -----------
    save_interval : Save intermediate results every N points
    """
    points = self.generate_grid()
    total = len(points)
    
    print(f"\n{'='*60}")
    print(f"Observer Pulse Parameter Sweep")
    print(f"{'='*60}")
    print(f"Total points: {total}")
    print(f"J: {len(self.J_vals)} values")
    print(f"g_RS: {len(self.g_RS_vals)} values")
    print(f"κ: {len(self.kappa_vals)} values")
    print(f"γ_φ: {len(self.gamma_phi_vals)} values")
    print(f"Workers: {self.n_workers if self.n_workers else 'Sequential'}")
    print(f"{'='*60}\n")
    
    if self.n_workers is None or self.n_workers == 1:
        # Sequential execution
        for i, point in enumerate(tqdm(points, desc="Sweep progress")):
        self.results.append(self.run_single_point(point))
        
        if (i + 1) % save_interval == 0:
            self._save_intermediate()
    else:
        # Parallel execution
        n_workers = self.n_workers if self.n_workers > 0 else None
        
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(self.run_single_point, p): p 
              for p in points}
        
        for i, future in enumerate(tqdm(
            as_completed(futures), 
            total=total, 
            desc="Sweep progress"
        )):
            self.results.append(future.result())
            
            if (i + 1) % save_interval == 0:
            self._save_intermediate()
    
    # Final save
    self.save_results()
    print(f"\n✓ Sweep complete! Results saved to {self.output_dir}")
    
    def _save_intermediate(self):
    """Save intermediate results"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = self.output_dir / f"intermediate_{timestamp}.csv"
    self._save_to_csv(filename)
    
    def save_results(self, filename: Optional[str] = None):
    """Save results to CSV"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"sweep_results_{timestamp}.csv"
    else:
        filename = Path(filename)
    
    self._save_to_csv(filename)
    
    # Also save metadata
    meta_file = filename.with_suffix('.json')
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'total_points': len(self.results),
        'exp_params': self.exp_params,
        'parameter_ranges': {
        'J': [float(self.J_vals.min()), float(self.J_vals.max()), len(self.J_vals)],
        'g_RS': [float(self.g_RS_vals.min()), float(self.g_RS_vals.max()), len(self.g_RS_vals)],
        'kappa': [float(self.kappa_vals.min()), float(self.kappa_vals.max()), len(self.kappa_vals)],
        'gamma_phi': [float(self.gamma_phi_vals.min()), float(self.gamma_phi_vals.max()), len(self.gamma_phi_vals)]
        }
    }
    
    with open(meta_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    def _save_to_csv(self, filename: Path):
    """Internal CSV save"""
    df = pd.DataFrame([p.to_dict() for p in self.results])
    df.to_csv(filename, index=False)
    
    def load_results(self, filename: str):
    """Load results from CSV"""
    df = pd.read_csv(filename)
    self.results = [SweepPoint(**row) for _, row in df.iterrows()]
    
    def plot_phase_diagram(
    self, 
    x_param: str = 'J', 
    y_param: str = 'g_RS',
    fixed_params: Optional[Dict[str, float]] = None,
    save: bool = True
    ):
        
             """
    Plot 2D phase diagram for specified parameters
    
    Parameters:
    -----------
    x_param, y_param : Parameters for x and y axes
    fixed_params : Dict of fixed parameter values for slicing
    save : Whether to save figure
    """
    if not self.results:
        raise ValueError("No results to plot. Run sweep first.")
    
    # Convert to DataFrame
    df = pd.DataFrame([p.to_dict() for p in self.results])
    
    # Apply fixed parameter filter
    if fixed_params:
        for param, value in fixed_params.items():
        df = df[np.isclose(df[param], value, atol=1e-6)]
    
    if len(df) == 0:
        raise ValueError("No data points match the fixed parameters")
    
    # Create figure with multiple subplots
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle(f'Observer Pulse Phase Diagram: {x_param} vs {y_param}', 
             fontsize=16, y=0.995)
    
    # Get unique values for grid
    x_vals = sorted(df[x_param].unique())
    y_vals = sorted(df[y


...vals].unique())

```
# Create meshgrid for plotting
X, Y = np.meshgrid(x_vals, y_vals)

# Helper to map regime strings to numbers/colors
regime_map = {"integration": 0, "haunted": 1, "fracture": 2, "unstable": 3, "error": 4}
cmap = plt.get_cmap("tab10", len(regime_map))

# Prepare Z grid
Z_regime = np.full_like(X, fill_value=-1, dtype=int)
for i, xv in enumerate(x_vals):
    for j, yv in enumerate(y_vals):
    mask = np.isclose(df[x_param], xv) & np.isclose(df[y_param], yv)
    if fixed_params:
        for param, value in fixed_params.items():
        mask &= np.isclose(df[param], value)
    if np.any(mask):
        reg_str = df.loc[mask, "regime"].values[0]
        Z_regime[j, i] = regime_map.get(reg_str, -1)

# Plot regime map
ax0 = axes[0,0]
im0 = ax0.imshow(Z_regime, origin='lower', aspect='auto', 
         extent=[min(x_vals), max(x_vals), min(y_vals), max(y_vals)],
         cmap=cmap)
ax0.set_xlabel(x_param); ax0.set_ylabel(y_param)
ax0.set_title("Regime Classification")
cbar0 = fig.colorbar(im0, ax=ax0, ticks=list(regime_map.values()))
cbar0.ax.set_yticklabels(list(regime_map.keys()))

# Plot I(R:SAB) steady
Z_I_R_SAB = np.full_like(X, fill_value=np.nan, dtype=float)
for i, xv in enumerate(x_vals):
    for j, yv in enumerate(y_vals):
    mask = np.isclose(df[x_param], xv) & np.isclose(df[y_param], yv)
    if fixed_params:
        for param, value in fixed_params.items():
        mask &= np.isclose(df[param], value)
    if np.any(mask):
        Z_I_R_SAB[j, i] = df.loc[mask, "I_R_SAB_steady"].values[0]
ax1 = axes[0,1]
im1 = ax1.imshow(Z_I_R_SAB, origin='lower', aspect='auto',
         extent=[min(x_vals), max(x_vals), min(y_vals), max(y_vals)],
         cmap="viridis")
ax1.set_xlabel(x_param); ax1.set_ylabel(y_param)
ax1.set_title("I(R:SAB) Steady-State")
fig.colorbar(im1, ax=ax1)

# Plot I(R:M) steady
Z_I_R_M = np.full_like(X, fill_value=np.nan, dtype=float)
for i, xv in enumerate(x_vals):
    for j, yv in enumerate(y_vals):
    mask = np.isclose(df[x_param], xv) & np.isclose(df[y_param], yv)
    if fixed_params:
        for param, value in fixed_params.items():
        mask &= np.isclose(df[param], value)
    if np.any(mask):
        Z_I_R_M[j, i] = df.loc[mask, "I_R_M_steady"].values[0]
ax2 = axes[0,2]
im2 = ax2.imshow(Z_I_R_M, origin='lower', aspect='auto',
         extent=[min(x_vals), max(x_vals), min(y_vals), max(y_vals)],
         cmap="viridis")
ax2.set_xlabel(x_param); ax2.set_ylabel(y_param)
ax2.set_title("I(R:M) Steady-State")
fig.colorbar(im2, ax=ax2)

# Plot recovery time
Z_recovery = np.full_like(X, fill_value=np.nan, dtype=float)
for i, xv in enumerate(x_vals):
    for j, yv in enumerate(y_vals):
    mask = np.isclose(df[x_param], xv) & np.isclose(df[y_param], yv)
    if fixed_params:
        for param, value in fixed_params.items():
        mask &= np.isclose(df[param], value)
    if np.any(mask):
        Z_recovery[j, i] = df.loc[mask, "recovery_time"].values[0]
ax3 = axes[1,0]
im3 = ax3.imshow(Z_recovery, origin='lower', aspect='auto',
         extent=[min(x_vals), max(x_vals), min(y_vals), max(y_vals)],
         cmap="plasma", norm=LogNorm(vmin=0.1, vmax=np.nanmax(Z_recovery)))
ax3.set_xlabel(x_param); ax3.set_ylabel(y_param)
ax3.set_title("Recovery Time")
fig.colorbar(im3, ax=ax3)

# Plot post-pulse fidelity
Z_fidelity = np.full_like(X, fill_value=np.nan, dtype=float)
for i, xv in enumerate(x_vals):
    for j, yv in enumerate(y_vals):
    mask = np.isclose(df[x_param], xv) & np.isclose(df[y_param], yv)
    if fixed_params:
        for param, value in fixed_params.items():
        mask &= np.isclose(df[param], value)
    if np.any(mask):
        Z_fidelity[j, i] = df.loc[mask, "post_pulse_fidelity"].values[0]
ax4 = axes[1,1]
im4 = ax4.imshow(Z_fidelity, origin='lower', aspect='auto',
         extent=[min(x_vals), max(x_vals), min(y_vals), max(y_vals)],
         cmap="coolwarm", vmin=0, vmax=1)
ax4.set_xlabel(x_param); ax4.set_ylabel(y_param)
ax4.set_title("Post-Pulse Fidelity")
fig.colorbar(im4, ax=ax4)

# Hide the last subplot (axes[1,2]) if unused
axes[1,2].axis('off')

plt.tight_layout()
if save:
    filename = self.output_dir / f"phase_diagram_{x_param}_vs_{y_param}.png"
    plt.savefig(filename, dpi=200)
    print(f"Phase diagram saved to {filename}")
plt.show()
```

