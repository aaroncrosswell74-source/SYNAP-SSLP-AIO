# mirror_steady_sweep.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from qutip import tensor, qeye, sigmax, sigmay, sigmaz, sigmam, basis, mesolve, entropy_vn, ptrace

# --- Embedding helpers ---
sx = sigmax(); sz = sigmaz(); sm = sigmam(); I2 = qeye(2)
n_qubits = 5  # R,S,A,B,M

def embed(op, pos, n=n_qubits):
    ops = [I2]*n
    ops[pos] = op
    return tensor(ops)

I_full = tensor([I2]*n_qubits)

# --- Base Hamiltonian (same structure as earlier) ---
def build_H(J, gRS, hR=0.5, hS=0.1):
    HR = -hR * embed(sigmax(), 0)
    H_RS = gRS * embed(sigmaz(), 0) * embed(sigmaz(), 1)
    H_SA = J * embed(sigmaz(), 1) * embed(sigmaz(), 2)
    H_AB = J * embed(sigmaz(), 2) * embed(sigmaz(), 3)
    H_BS = J * embed(sigmaz(), 3) * embed(sigmaz(), 1)
    H_local = -hS * embed(sigmax(), 1) - hS * embed(sigmax(), 2) - hS * embed(sigmax(), 3)
    return HR + H_RS + H_SA + H_AB + H_BS + H_local

# --- Refined dissipators (Mirror-Steady) ---
def refined_dissipators(k_self, k_env):
    Ls = []
    Z_RM = embed(sigmaz(), 0) * embed(sigmaz(), 4)
    L_self = np.sqrt(k_self) * (I_full - Z_RM)
    parity_SAB = embed(sigmaz(), 1) * embed(sigmaz(), 2) * embed(sigmaz(), 3)
    L_env = np.sqrt(k_env) * (I_full - parity_SAB)
    Ls.append(L_self)
    Ls.append(L_env)
    return Ls

# --- Collapse operators (baseline noise) ---
def collapse_ops(g_phi=0.01, g1=0.005):
    c_ops = []
    for pos in range(n_qubits):
        c_ops.append(np.sqrt(g_phi) * embed(sigmaz(), pos))
        c_ops.append(np.sqrt(g1) * embed(sigmam(), pos))
    return c_ops

# --- Measurement entangler (CNOT-like R->M) ---
proj0 = basis(2,0) * basis(2,0).dag()
proj1 = basis(2,1) * basis(2,1).dag()
P0 = embed(proj0, 0); P1 = embed(proj1, 0)
X_M = embed(sigmax(), 4)
U_meas = P0 * I_full + P1 * X_M

# --- Pulse operator (Observer Pulse: sigma_z on R) ---
U_pulse = embed(sigmaz(), 0)

# --- Mutual information helpers ---
def entropy(rho):
    return entropy_vn(rho)

def mutual_information(rho_full, subsysA, subsysB):
    rhoA = ptrace(rho_full, subsysA)
    rhoB = ptrace(rho_full, subsysB)
    rhoAB = ptrace(rho_full, subsysA + subsysB if isinstance(subsysA, list) else subsysA + [s for s in subsysB])
    return float((entropy(rhoA) + entropy(rhoB) - entropy(rhoAB)).real)

def I_R_SAB(rho): return mutual_information(rho, [0], [1,2,3])
def I_R_M(rho): return mutual_information(rho, [0], [4])

# --- Single experiment runner ---
def run_experiment(J, gRS, k_self, k_env, gamma_phi=0.01, gamma_1=0.005,
                   t_pre=20.0, t_pulse=1.0, t_post=60.0, dt=0.1, t0=10.0, do_feedback=False):
    H = build_H(J, gRS)
    rho0 = tensor(basis(2,0), basis(2,0), basis(2,0), basis(2,0), basis(2,0)).proj()
    c_ops = collapse_ops(gamma_phi, gamma_1) + refined_dissipators(k_self, k_env)
    # pre-pulse
    times_pre = np.arange(0, t0, dt)
    res_pre = mesolve(H, rho0, times_pre, c_ops, [])
    rho_t0_minus = res_pre.states[-1]
    # pulse
    rho_t0_plus = U_pulse * rho_t0_minus * U_pulse.dag()
    # measurement entangle
    rho_after_meas = U_meas * rho_t0_plus * U_meas.dag()
    # optional feedback (simple parity flip from M to R)
    if do_feedback:
        # controlled X: if M==1 flip R (simple corrective)
        P0_M = embed(proj0, 4); P1_M = embed(proj1, 4)
        X_R = embed(sigmax(), 0)
        U_fb = P0_M * I_full + P1_M * X_R
        rho_after_fb = U_fb * rho_after_meas * U_fb.dag()
    else:
        rho_after_fb = rho_after_meas
    # post evolution
    times_post = np.arange(t0, t0 + t_post + dt, dt)
    res_post = mesolve(H, rho_after_fb, times_post, c_ops, [])
    states_full = res_pre.states[:-1] + res_post.states
    times_full = np.concatenate((times_pre, times_post))
    I_R_SAB_series = np.array([I_R_SAB(s) for s in states_full])
    I_R_M_series = np.array([I_R_M(s) for s in states_full])
    return times_full, I_R_SAB_series, I_R_M_series

# --- Sweep grid and metrics collection ---
def sweep_and_save(J_vals, gRS_vals, Kself_vals, Kenv_vals, outdir="mirror_sweep"):
    outdir = Path(outdir); outdir.mkdir(exist_ok=True)
    records = []
    for J in J_vals:
        for gRS in gRS_vals:
            for k_self in Kself_vals:
                for k_env in Kenv_vals:
                    times, I_R_SAB, I_R_M = run_experiment(J, gRS, k_self, k_env)
                    # pre-pulse steady: average of first 20% of pre-pulse window
                    pre_mask = times < 9.0
                    pre_I_R_SAB = np.mean(I_R_SAB[pre_mask]) if np.any(pre_mask) else 0.0
                    pre_I_R_M = np.mean(I_R_M[pre_mask]) if np.any(pre_mask) else 0.0
                    # post-pulse steady: average last 20% of series
                    final_window = slice(int(0.8 * len(I_R_SAB)), None)
                    post_I_R_SAB = np.mean(I_R_SAB[final_window])
                    post_I_R_M = np.mean(I_R_M[final_window])
                    # recovery time to 90% of pre_I_R_SAB
                    target = 0.9 * pre_I_R_SAB
                    post_series = I_R_SAB[int(len(times)*0.2):]
                    t_post = times[int(len(times)*0.2):] - times[int(len(times)*0.2)]
                    idx = np.where(post_series >= target)[0]
                    recovery_time = float(t_post[idx[0]]) if idx.size>0 else np.inf
                    fidelity = post_I_R_SAB / pre_I_R_SAB if pre_I_R_SAB>0 else 0.0
                    # classification (simple)
                    if recovery_time < 20 and fidelity > 0.95:
                        regime = "integration"
                    elif recovery_time > 50 or fidelity < 0.8:
                        regime = "fracture"
                    else:
                        regime = "haunted"
                    records.append({
                        "J": J, "g_RS": gRS, "k_self": k_self, "k_env": k_env,
                        "pre_I_R_SAB": pre_I_R_SAB, "pre_I_R_M": pre_I_R_M,
                        "post_I_R_SAB": post_I_R_SAB, "post_I_R_M": post_I_R_M,
                        "recovery_time": recovery_time, "fidelity": fidelity, "regime": regime
                    })
                    # lightweight progress print
                    print(f"J={J:.2f} gRS={gRS:.2f} k_self={k_self:.2f} k_env={k_env:.2f} -> {regime}")
    df = pd.DataFrame(records)
    csv_path = outdir / "mirror_sweep_results.csv"
    df.to_csv(csv_path, index=False)
    print("Saved:", csv_path)
    return df

# --- Example grid (coarse to start) ---
if __name__ == "__main__":
    J_vals = [0.2, 0.8, 1.2]
    gRS_vals = [0.3, 0.6, 0.9]
    Kself_vals = [0.1, 0.5, 1.2, 2.0]
    Kenv_vals = [0.1, 0.5, 1.0]
    df = sweep_and_save(J_vals, gRS_vals, Kself_vals, Kenv_vals)
    # Quick heatmap example for k_env fixed at 0.5
    slice_df = df[df["k_env"]==0.5]
    pivot = slice_df.pivot_table(index="g_RS", columns="J", values="post_I_R_M")
    plt.imshow(pivot.values, origin='lower', aspect='auto', cmap='viridis',
               extent=[min(pivot.columns), max(pivot.columns), min(pivot.index), max(pivot.index)])
    plt.colorbar(label="post I(R:M)")
    plt.xlabel("J"); plt.ylabel("g_RS"); plt.title("post I(R:M) (k_env=0.5)")
    plt.show()
