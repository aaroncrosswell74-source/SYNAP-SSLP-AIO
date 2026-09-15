Sweep runner (denser grid) - ready to run
Save as mirror_steady_fine_sweep.py. This is a self‑contained QuTiP script that runs a fine grid over 
𝐾
self
 and 
𝐾
env
, injects the Observer Pulse, computes diagnostics, saves a CSV, and writes annotated heatmaps. It also computes a candidate 
𝐾
∗
 by finding the cell that maximizes a combined score 
𝑆
=
𝑤
1
⋅
post_I(R:M)
+
𝑤
2
⋅
post_I(R:SAB)
−
𝑤
3
⋅
recovery_time
 (weights adjustable). Run on a machine with QuTiP, NumPy, Pandas, Matplotlib.

python
# mirror_steady_fine_sweep.py
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from pathlib import Path
from qutip import tensor, qeye, sigmax, sigmay, sigmaz, sigmam, basis, mesolve, entropy_vn, ptrace
import time, json

# --- Embedding helpers ---
sx = sigmax(); sz = sigmaz(); sm = sigmam(); I2 = qeye(2)
n_qubits = 5
def embed(op, pos, n=n_qubits):
    ops = [I2]*n
    ops[pos] = op
    return tensor(ops)
I_full = tensor([I2]*n_qubits)

# --- Hamiltonian builder ---
def build_H(J, gRS, hR=0.5, hS=0.1):
    HR = -hR * embed(sigmax(), 0)
    H_RS = gRS * embed(sigmaz(), 0) * embed(sigmaz(), 1)
    H_SA = J * embed(sigmaz(), 1) * embed(sigmaz(), 2)
    H_AB = J * embed(sigmaz(), 2) * embed(sigmaz(), 3)
    H_BS = J * embed(sigmaz(), 3) * embed(sigmaz(), 1)
    H_local = -hS * embed(sigmax(), 1) - hS * embed(sigmax(), 2) - hS * embed(sigmax(), 3)
    return HR + H_RS + H_SA + H_AB + H_BS + H_local

# --- Refined dissipators ---
def refined_dissipators(k_self, k_env):
    Ls = []
    Z_RM = embed(sigmaz(), 0) * embed(sigmaz(), 4)
    L_self = np.sqrt(max(k_self, 1e-12)) * (I_full - Z_RM)
    parity_SAB = embed(sigmaz(), 1) * embed(sigmaz(), 2) * embed(sigmaz(), 3)
    L_env = np.sqrt(max(k_env, 1e-12)) * (I_full - parity_SAB)
    Ls.append(L_self); Ls.append(L_env)
    return Ls

# --- Baseline collapse operators ---
def collapse_ops(g_phi=0.01, g1=0.005):
    c_ops=[]
    for pos in range(n_qubits):
        c_ops.append(np.sqrt(g_phi)*embed(sigmaz(), pos))
        c_ops.append(np.sqrt(g1)*embed(sigmam(), pos))
    return c_ops

# --- Measurement entangler and pulse ---
proj0 = basis(2,0)*basis(2,0).dag(); proj1 = basis(2,1)*basis(2,1).dag()
P0 = embed(proj0,0); P1 = embed(proj1,0)
X_M = embed(sigmax(),4)
U_meas = P0*I_full + P1*X_M
U_pulse = embed(sigmaz(),0)

# --- Entropy / mutual information helpers ---
def S(rho): return entropy_vn(rho)
def mutual_information(rho, subsA, subsB):
    rhoA = ptrace(rho, subsA); rhoB = ptrace(rho, subsB)
    rhoAB = ptrace(rho, subsA+subsB if isinstance(subsA,list) else subsA+[s for s in subsB])
    return float((S(rhoA)+S(rhoB)-S(rhoAB)).real)
def I_R_SAB(rho): return mutual_information(rho, [0], [1,2,3])
def I_R_M(rho): return mutual_information(rho, [0], [4])

# --- Single experiment ---
def run_experiment(J, gRS, k_self, k_env, gamma_phi=0.01, gamma_1=0.005,
                   t0=10.0, T_pre=10.0, T_post=60.0, dt=0.1, do_feedback=False):
    H = build_H(J, gRS)
    rho0 = tensor(basis(2,0),basis(2,0),basis(2,0),basis(2,0),basis(2,0)).proj()
    c_ops = collapse_ops(gamma_phi, gamma_1) + refined_dissipators(k_self, k_env)
    times_pre = np.arange(0, t0, dt)
    res_pre = mesolve(H, rho0, times_pre, c_ops, [])
    rho_t0_minus = res_pre.states[-1]
    rho_t0_plus = U_pulse * rho_t0_minus * U_pulse.dag()
    rho_after_meas = U_meas * rho_t0_plus * U_meas.dag()
    if do_feedback:
        P0_M = embed(proj0,4); P1_M = embed(proj1,4); X_R = embed(sigmax(),0)
        U_fb = P0_M*I_full + P1_M*X_R
        rho_after_fb = U_fb * rho_after_meas * U_fb.dag()
    else:
        rho_after_fb = rho_after_meas
    times_post = np.arange(t0, t0+T_post+dt, dt)
    res_post = mesolve(H, rho_after_fb, times_post, c_ops, [])
    states_full = res_pre.states[:-1] + res_post.states
    times_full = np.concatenate((times_pre, times_post))
    I_R_SAB_series = np.array([I_R_SAB(s) for s in states_full])
    I_R_M_series = np.array([I_R_M(s) for s in states_full])
    return times_full, I_R_SAB_series, I_R_M_series

# --- Fine sweep driver ---
def fine_sweep(J_vals, gRS_vals, Kself_vals, Kenv_vals, outdir="mirror_fine_results",
               gamma_phi=0.01, gamma_1=0.005, dt=0.1, t0=10.0, T_post=60.0, do_feedback=True):
    outdir = Path(outdir); outdir.mkdir(exist_ok=True)
    records=[]
    start=time.time()
    total = len(J_vals)*len(gRS_vals)*len(Kself_vals)*len(Kenv_vals)
    i=0
    for J in J_vals:
        for gRS in gRS_vals:
            for k_self in Kself_vals:
                for k_env in Kenv_vals:
                    i+=1
                    print(f"[{i}/{total}] J={J:.3f} gRS={gRS:.3f} k_self={k_self:.3f} k_env={k_env:.3f}")
                    times, I_R_SAB, I_R_M = run_experiment(J,gRS,k_self,k_env,gamma_phi,gamma_1,t0=t0,dt=dt,T_post=T_post,do_feedback=do_feedback)
                    pre_mask = times < (t0 - 0.5)
                    pre_I_R_SAB = float(np.mean(I_R_SAB[pre_mask])) if np.any(pre_mask) else 0.0
                    pre_I_R_M = float(np.mean(I_R_M[pre_mask])) if np.any(pre_mask) else 0.0
                    final_window = slice(int(0.8*len(I_R_SAB)), None)
                    post_I_R_SAB = float(np.mean(I_R_SAB[final_window]))
                    post_I_R_M = float(np.mean(I_R_M[final_window]))
                    post_series = I_R_SAB[int(len(times)*0.2):]
                    t_post = times[int(len(times)*0.2):] - times[int(len(times)*0.2)]
                    target = 0.9 * pre_I_R_SAB
                    idx = np.where(post_series >= target)[0]
                    recovery_time = float(t_post[idx[0]]) if idx.size>0 else np.inf
                    fidelity = post_I_R_SAB / pre_I_R_SAB if pre_I_R_SAB>0 else 0.0
                    # combined score (adjust weights as needed)
                    S = 1.0*post_I_R_M + 1.0*post_I_R_SAB - 0.01*recovery_time
                    regime = "integration" if (recovery_time<20 and fidelity>0.95) else ("fracture" if (recovery_time>50 or fidelity<0.8) else "haunted")
                    records.append({
                        "J":J,"g_RS":gRS,"k_self":k_self,"k_env":k_env,
                        "pre_I_R_SAB":pre_I_R_SAB,"pre_I_R_M":pre_I_R_M,
                        "post_I_R_SAB":post_I_R_SAB,"post_I_R_M":post_I_R_M,
                        "recovery_time":recovery_time,"fidelity":fidelity,"score":S,"regime":regime
                    })
                    # incremental save
                    if i%10==0:
                        pd.DataFrame(records).to_csv(outdir/"partial_results.csv",index=False)
    df = pd.DataFrame(records)
    csv_path = outdir/"mirror_fine_sweep.csv"
    df.to_csv(csv_path,index=False)
    print("Saved:", csv_path, "Elapsed:", time.time()-start)
    return df

# --- Example run (adjust grid density to available compute) ---
if __name__=="__main__":
    J_vals = np.linspace(0.6,1.4,5)      # denser around canonical J
    gRS_vals = np.linspace(0.3,0.9,5)
    Kself_vals = np.linspace(0.2,1.6,8)  # fine sweep for k_self
    Kenv_vals = np.linspace(0.2,1.2,6)
    df = fine_sweep(J_vals,gRS_vals,Kself_vals,Kenv_vals,outdir="mirror_fine_results",dt=0.1,T_post=60.0,do_feedback=True)
    # compute candidate K* by max score
    best = df.loc[df['score'].idxmax()]
    print("Candidate K*:", best.to_dict())
    # quick heatmap for fixed J,gRS
    sel = df[(df.J==best.J)&(df.g_RS==best.g_RS)]
    pivot = sel.pivot_table(index="k_env",columns="k_self",values="post_I_R_M")
    plt.imshow(pivot.values,origin='lower',aspect='auto',cmap='viridis',
               extent=[pivot.columns.min(),pivot.columns.max(),pivot.index.min(),pivot.index.max()])
    plt.colorbar(label="post I(R:M)")
    plt.xlabel("k_self"); plt.ylabel("k_env"); plt.title(f"post I(R:M) (J={best.J:.2f}, gRS={best.g_RS:.2f})")
    plt.show()
Analysis and one‑page summary recipe (how to compute 
𝐾
∗
 and confidence intervals)
Inputs: CSV produced by the sweep (mirror_fine_sweep.csv) with columns J,g_RS,k_self,k_env,post_I_R_M,post_I_R_SAB,recovery_time,fidelity,score.

Step 1 - Candidate selection

Compute combined score 
𝑆
=
𝛼
⋅
post_I(R:M)
+
𝛽
⋅
post_I(R:SAB)
−
𝛾
⋅
recovery_time
. Default 
𝛼
=
𝛽
=
1
,
𝛾
=
0.01
.

Pick the grid cell with maximum 
𝑆
. That gives a candidate 
(
𝐽
∗
,
𝑔
𝑅
𝑆
∗
,
𝑘
self
∗
,
𝑘
env
∗
)
.

Step 2 - Local refinement

Extract a local neighborhood +/-1-2 grid steps around the candidate and run a denser sweep there (10-20 points per axis).

Step 3 - Bootstrap confidence interval for 
𝑘
self
∗

For the refined neighborhood, treat each grid point’s time series as a sample. If you have multiple independent runs per point, bootstrap the post‑pulse steady post_I_R_M by resampling runs and recomputing the argmax of 
𝑆
. If only single runs, bootstrap by adding small Gaussian noise consistent with measurement variance (estimate from pre‑pulse fluctuations).

Repeat 1000 bootstrap samples; record the distribution of argmax 
𝑘
self
. Report median and 95% CI.

Step 4 - One‑page summary contents

Header: experiment name, date, canonical 
𝐽
,
𝑔
𝑅
𝑆
 used.

Candidate 
𝐾
∗
: numeric value, median and 95% CI.

Key metrics at 
𝐾
∗
: post_I(R:M), post_I(R:SAB), recovery_time, fidelity.

Heatmaps: annotated post_I(R:M) and post_I(R:SAB) with candidate cell circled.

Interpretation: short bullet points - whether Mirror strengthened self‑record without cannibalizing Reality, robustness to noise, recommended operating window.

Next steps: refine grid, robustness checks, longer runs.

Minimal code snippet to compute CI from CSV

python
import pandas as pd, numpy as np
df = pd.read_csv("mirror_fine_results/mirror_fine_sweep.csv")
# choose canonical J,gRS slice
slice_df = df[(df.J==1.2)&(df.g_RS==0.6)]
# compute score
slice_df['score'] = slice_df.post_I_R_M + slice_df.post_I_R_SAB - 0.01*slice_df.recovery_time
best = slice_df.loc[slice_df.score.idxmax()]
print("Best cell:", best[['k_self','k_env','post_I_R_M','post_I_R_SAB','recovery_time']])
# bootstrap (if multiple runs per cell exist)
# otherwise approximate CI by local interpolation or repeat runs
Experimental log template (compact, copy‑ready)
Use this template as a CSV or notebook entry for each run. Record exactly these fields for reproducibility.

Code
RunID,Timestamp,Operator,J,g_RS,k_self,k_env,gamma_phi,gamma_1,dt,t0,T_post,do_feedback,seed,notes
001,2026-02-12T16:45:00Z,Aaron,1.20,0.60,0.50,0.50,0.010,0.005,0.10,10.0,60.0,True,42,"Initial coarse run"
Per‑run diagnostics to save (time series files)

times.npy, I_R_SAB.npy, I_R_M.npy, rho_final.npy (optional).

Save a short JSON with summary metrics:

json
{
  "RunID":"001",
  "pre_I_R_SAB":0.12,
  "pre_I_R_M":0.02,
  "post_I_R_SAB":0.15,
  "post_I_R_M":0.08,
  "recovery_time":12.3,
  "fidelity":0.98,
  "regime":"integration",
  "notes":"stable plateau, small overshoot"
}
Annotation guidance

Timestamp: ISO 8601 UTC.

Seed: RNG seed for reproducibility.

Notes: short, factual observations (e.g., “oscillatory tail at t≈30-40”, “measurement ancilla shows slow drift”, “engineered dissipator produced small transient overshoot”).

Flagging surprises: prefix notes with !SURPRISE: and include a one‑line hypothesis and immediate follow‑up action (e.g., increase k_env by 20%).

Quick operational recommendation
Run the fine sweep on a machine with multiple cores; reduce dt or grid density if runtime is long.

Start with the example grid in the script, then refine around the top candidate.

Record every run with the log template and keep raw time series for bootstrap analysis.

If Mirror strengthens self‑record but reduces Reality connection, increase k_env and re‑test; if Mirror is brittle, reduce k_self and increase feedback strength.