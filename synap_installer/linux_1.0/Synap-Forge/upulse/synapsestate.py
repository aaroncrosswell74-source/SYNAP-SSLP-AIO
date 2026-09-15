
import numpy as np
import matplotlib.pyplot as plt
import csv

np.set_printoptions(precision=4, suppress=True)

sx = np.array([[0,1],[1,0]], dtype=complex)
sz = np.array([[1,0],[0,-1]], dtype=complex)

def O_of_phi(phi):
    return np.sin(phi)*sx + np.cos(phi)*sz

def dissipator(L, rho):
    LdL = L.conj().T @ L
    return L @ rho @ L.conj().T - 0.5*(LdL @ rho + rho @ LdL)

def expectation(rho, A):
    return float(np.real(np.trace(rho @ A)))

def hermitize_trace_normalize(rho):
    rho = 0.5*(rho + rho.conj().T)
    tr = np.trace(rho)
    return rho / tr if np.real(tr) > 1e-12 else rho

def sigmoid(x):
    return 1.0/(1.0 + np.exp(-6.0*(x-0.5)))



def sme_step(rho, H, O_list, kappa_list, dW_list, dt):
    drho = -1j * (H @ rho - rho @ H) * dt
    for O, kappa in zip(O_list, kappa_list):
        drho += kappa * dissipator(O, rho) * dt
    for O, kappa, dW in zip(O_list, kappa_list, dW_list):
        expO = expectation(rho, O)
        innov = (O @ rho + rho @ O - 2.0*expO*rho)
        drho += np.sqrt(max(kappa, 0.0)) * innov * dW
    rho = rho + drho
    rho = hermitize_trace_normalize(rho)
    return rho



def agent_update(rho, mu, phi, a, o_filt, raw_err_sq, params, dt):
    # params
    lam_mu = params['lam_mu']; lam_phi = params['lam_phi']; lam_a = params['lam_a']
    mu0 = params['mu0']; phi0 = params['phi0']; a0 = params['a0']
    eta_mu = params['eta_mu']; eta_phi = params['eta_phi']; eta_a = params['eta_a']
    pi1 = params['pi1']; c_att = params['c_att']
    # surrogate with attention "reward" term (reduces F when attention reduces error)
    F = 0.5*(o_filt - mu)**2 + 0.5*lam_mu*(mu - mu0)**2 + 0.5*lam_phi*(phi - phi0)**2 + 0.5*lam_a*(a - a0)**2         - c_att * sigmoid(a) * raw_err_sq
    # gradients
    dF_dmu = (mu - o_filt) + lam_mu*(mu - mu0)
    dO_dphi = np.cos(phi)*sx - np.sin(phi)*sz
    do_dphi = expectation(rho, dO_dphi)
    dF_dphi = (o_filt - mu)*do_dphi + lam_phi*(phi - phi0)
    # ∂/∂a of reward term:  -c_att * sigmoid'(a) * raw_err_sq
    dsig = 6.0*sigmoid(a)*(1.0 - sigmoid(a))  # derivative of logistic with slope 6
    dF_da   = lam_a*(a - a0) - c_att * dsig * raw_err_sq
    # precision scaling
    Pi = 1.0 + pi1*sigmoid(a)
    mu  = mu  - dt * eta_mu  * Pi * dF_dmu
    phi = phi - dt * eta_phi * Pi * dF_dphi
    a   = a   - dt * eta_a   * dF_da
    return mu, phi, a, F



def simulate_single_v2(T=2000, dt=1e-3, seed=0,
                       omega=5.0, kappa0=3.0,
                       init_rho=np.array([[0.9,0.1],[0.1,0.1]], dtype=complex),
                       A_init=(0.2, 1.0, 0.4),
                       B_init=(0.2, 0.7, 0.4),
                       A_prior=(0.0, 1.0, 0.5),
                       B_prior=(0.0, 1.05, 0.5),
                       lr=(4.0, 1.2, 0.6),
                       regs=(0.05, 0.02, 0.02),
                       pi1=4.0, eps=1e-6,
                       alpha=0.03,         # low-pass gain
                       c_att=0.2           # attention reward weight
                      ):
    rng = np.random.default_rng(seed)
    rho = init_rho / np.trace(init_rho)
    H = 0.5*omega*sx
    muA, phiA, aA = A_init; muB, phiB, aB = B_init
    mu0A, phi0A, a0A = A_prior; mu0B, phi0B, a0B = B_prior
    lam_mu, lam_phi, lam_a = regs
    eta_mu, eta_phi, eta_a = lr
    # logs
    Tn = T
    oA = np.zeros(Tn); oB = np.zeros(Tn)
    oA_f = np.zeros(Tn); oB_f = np.zeros(Tn)
    muA_hist = np.zeros(Tn); muB_hist = np.zeros(Tn)
    phiA_hist = np.zeros(Tn); phiB_hist = np.zeros(Tn)
    aA_hist = np.zeros(Tn); aB_hist = np.zeros(Tn)
    FA = np.zeros(Tn); FB = np.zeros(Tn)
    purity = np.zeros(Tn)
    # filtered currents init
    oA_f_prev = 0.0; oB_f_prev = 0.0
    for t in range(Tn):
        OA = O_of_phi(phiA); OB = O_of_phi(phiB)
        kA = kappa0*sigmoid(aA); kB = kappa0*sigmoid(aB)
        dWA = rng.normal(0.0, np.sqrt(dt)); dWB = rng.normal(0.0, np.sqrt(dt))
        rho = sme_step(rho, H, [OA, OB], [kA, kB], [dWA, dWB], dt)
        expA = expectation(rho, OA); expB = expectation(rho, OB)
        o_raw_A = expA + (dWA / np.sqrt(kA + eps)) / dt
        o_raw_B = expB + (dWB / np.sqrt(kB + eps)) / dt
        # low-pass filtered currents for learning
        o_f_A = (1.0 - alpha)*oA_f_prev + alpha*o_raw_A
        o_f_B = (1.0 - alpha)*oB_f_prev + alpha*o_raw_B
        # update agents
        A_params = dict(lam_mu=lam_mu, lam_phi=lam_phi, lam_a=lam_a,
                        mu0=mu0A, phi0=phi0A, a0=a0A,
                        eta_mu=eta_mu, eta_phi=eta_phi, eta_a=eta_a, pi1=pi1, c_att=c_att)
        B_params = dict(lam_mu=lam_mu, lam_phi=lam_phi, lam_a=lam_a,
                        mu0=mu0B, phi0=phi0B, a0=a0B,
                        eta_mu=eta_mu, eta_phi=eta_phi, eta_a=eta_a, pi1=pi1, c_att=c_att)
        raw_err_sq_A = (o_raw_A - muA)**2
        raw_err_sq_B = (o_raw_B - muB)**2
        muA, phiA, aA, FA[t] = agent_update(rho, muA, phiA, aA, o_f_A, raw_err_sq_A, A_params, dt)
        muB, phiB, aB, FB[t] = agent_update(rho, muB, phiB, aB, o_f_B, raw_err_sq_B, B_params, dt)
        # log & carry
        oA[t] = o_raw_A; oB[t] = o_raw_B
        oA_f[t] = o_f_A;  oB_f[t] = o_f_B
        muA_hist[t] = muA; muB_hist[t] = muB
        phiA_hist[t] = phiA; phiB_hist[t] = phiB
        aA_hist[t] = aA; aB_hist[t] = aB
        purity[t] = float(np.real(np.trace(rho @ rho)))
        oA_f_prev = o_f_A; oB_f_prev = o_f_B
    return dict(oA=oA, oB=oB, oA_f=oA_f, oB_f=oB_f,
                muA=muA_hist, muB=muB_hist, phiA=phiA_hist, phiB=phiB_hist,
                aA=aA_hist, aB=aB_hist, FA=FA, FB=FB, purity=purity, dt=dt)



def run_ensemble_v2(M=20, **sim_kwargs):
    oA_f_list = []; oB_f_list = []
    for m in range(M):
        out = simulate_single_v2(seed=m, **sim_kwargs)
        oA_f_list.append(out['oA_f']); oB_f_list.append(out['oB_f'])
    return np.stack(oA_f_list, axis=0), np.stack(oB_f_list, axis=0)



def windowed_corr(A, B, win=150):
    # A,B: shape (M,T)
    M, T = A.shape
    out = np.zeros(T)
    for t in range(T):
        s = max(0, t-win+1); e = t+1
        a = A[:,s:e].mean(axis=1)
        b = B[:,s:e].mean(axis=1)
        a = a - a.mean(); b = b - b.mean()
        denom = (np.sqrt((a*a).sum()) * np.sqrt((b*b).sum()) + 1e-12)
        out[t] = (a*b).sum()/denom
    return out



# --- Single trajectory demo ---
out = simulate_single_v2(T=1500, dt=1e-3, seed=2)
times = np.arange(len(out['oA']))*out['dt']

plt.figure()
plt.plot(times, out['muA'], label='mu_A')
plt.plot(times, out['muB'], label='mu_B')
plt.xlabel('time'); plt.ylabel('beliefs'); plt.title('Agent Beliefs (filtered learning)'); plt.legend(); plt.show()

plt.figure()
plt.plot(times, out['phiA'], label='phi_A')
plt.plot(times, out['phiB'], label='phi_B')
plt.xlabel('time'); plt.ylabel('phi'); plt.title('Measurement Angles'); plt.legend(); plt.show()

plt.figure()
plt.plot(times, out['aA'], label='a_A')
plt.plot(times, out['aB'], label='a_B')
plt.xlabel('time'); plt.ylabel('attention'); plt.title('Attention Dynamics (with reward)'); plt.legend(); plt.show()

plt.figure()
plt.plot(times, out['FA'], label='F_A')
plt.plot(times, out['FB'], label='F_B')
plt.xlabel('time'); plt.ylabel('F'); plt.title('Free-Energy Surrogates'); plt.legend(); plt.show()

plt.figure()
plt.plot(times, out['purity'])
plt.xlabel('time'); plt.ylabel('Tr(rho^2)'); plt.title('World State Purity'); plt.show()



# --- Ensemble: aligned vs misaligned priors ---
M_runs = 16; T_steps = 1200; dt_val = 1e-3

# Misaligned
oA_mis, oB_mis = run_ensemble_v2(M=M_runs, T=T_steps, dt=dt_val,
                                 A_prior=(0.0, 1.0, 0.5),
                                 B_prior=(0.0, 0.4, 0.5),
                                 kappa0=3.0)
# Aligned
oA_aln, oB_aln = run_ensemble_v2(M=M_runs, T=T_steps, dt=dt_val,
                                 A_prior=(0.0, 1.0, 0.5),
                                 B_prior=(0.0, 1.02, 0.5),
                                 kappa0=3.0)

t = np.arange(T_steps)*dt_val
corr_mis = windowed_corr(oA_mis, oB_mis, win=200)
corr_aln = windowed_corr(oA_aln, oB_aln, win=200)

plt.figure()
plt.plot(t, corr_mis, label='Misaligned Priors')
plt.plot(t, corr_aln, label='Aligned Priors')
plt.xlabel('time'); plt.ylabel('corr'); plt.title('Windowed Consensus Correlation'); plt.legend(); plt.show()

# Export simple summaries
import csv, numpy as np
def export_csv(path, A, B):
    M, T = A.shape
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['run','mean_A','mean_B','std_A','std_B'])
        for m in range(M):
            w.writerow([m, A[m].mean(), B[m].mean(), A[m].std(), B[m].std()])

export_csv("ensemble_summary_misaligned.csv", oA_mis, oB_mis)
export_csv("ensemble_summary_aligned.csv", oA_aln, oB_aln)
print("Saved CSV summaries.")
