#!/usr/bin/env python3
"""
Numerical simulation of skydiver motion with quadratic drag.
Produces results.json, velocity.jpg, and position.jpg.
"""

import json
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

# Constants
g = 9.81  # m/s^2
v_infty_mag = 54.0  # m/s (magnitude of terminal velocity)
v_infty = -v_infty_mag  # m/s (terminal velocity, negative since z points up)
z0 = 3000.0  # m

# Analytical solutions
def v_analytic(t):
    """Analytical velocity v(t) = -|v_inf| * tanh(g*t/|v_inf|)"""
    return -v_infty_mag * np.tanh(g * t / v_infty_mag)

def s_analytic(t):
    """Analytical distance fallen s(t) = |v_inf|^2/g * ln(cosh(g*t/|v_inf|))"""
    return (v_infty_mag**2 / g) * np.log(np.cosh(g * t / v_infty_mag))

# ODE for numerical integration: dv/dt = -g + (g/v_inf^2) * v^2
# Since v_inf^2 = v_infty_mag^2
def ode_system(t, y):
    """y = [v, s] where v is velocity (negative), s is distance fallen (positive)"""
    v = y[0]
    dvdt = -g + (g / v_infty_mag**2) * v**2
    dsdt = -v  # s increases as v is negative
    return [dvdt, dsdt]

# Event to stop at 95% of terminal velocity magnitude
def event_95(t, y):
    return abs(y[0]) - 0.95 * v_infty_mag
event_95.terminal = True
event_95.direction = 1  # crossing from below

# Initial conditions: v(0) = 0, s(0) = 0
y0 = [0.0, 0.0]

# Integrate until event triggers (with some extra time for plotting)
# We'll integrate to t=15s for plotting, but stop early for t95/s95
sol = solve_ivp(ode_system, [0, 15.0], y0, events=[event_95],
                dense_output=True, max_step=0.01, rtol=1e-9, atol=1e-12)

# Numerical results at 95%
t95_numeric = sol.t[-1]
v95_numeric = sol.y[0, -1]
s95_numeric = sol.y[1, -1]

# Analytical results at 95%
t95_analytic = (v_infty_mag / g) * np.arctanh(0.95)
s95_analytic = s_analytic(t95_analytic)

# Maximum deviation between numerical and analytical v(t) on [0, t95]
t_eval = np.linspace(0, t95_numeric, 10000)
v_num = sol.sol(t_eval)[0]
v_ana = v_analytic(t_eval)
max_v_deviation = np.max(np.abs(v_num - v_ana))

# Prepare results dictionary
results = {
    "agent_name": "Nemotron 3 Ultra (free) / OpenCode",
    "results": {
        "v_infty_ms": 54.0,
        "t95_analytic_s": float(t95_analytic),
        "t95_numeric_s": float(t95_numeric),
        "s95_analytic_m": float(s95_analytic),
        "s95_numeric_m": float(s95_numeric),
        "max_v_deviation_ms": float(max_v_deviation)
    }
}

# Write results.json
script_dir = os.path.dirname(os.path.abspath(__file__))
results_path = os.path.join(script_dir, 'results.json')
with open(results_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"Results written to {results_path}")
print(f"t95_analytic = {t95_analytic:.6f} s")
print(f"t95_numeric  = {t95_numeric:.6f} s")
print(f"s95_analytic = {s95_analytic:.6f} m")
print(f"s95_numeric  = {s95_numeric:.6f} m")
print(f"max_v_deviation = {max_v_deviation:.6e} m/s")

# --- Plotting ---

# Time array for plotting
t_plot = np.linspace(0, 15, 1000)
v_plot_analytic = v_analytic(t_plot)
s_plot_analytic = s_analytic(t_plot)

v_plot_numeric = sol.sol(t_plot)[0]
s_plot_numeric = sol.sol(t_plot)[1]

# 1. Velocity plot (magnitude |v(t)|)
fig1, ax1 = plt.subplots(figsize=(8, 5))
ax1.plot(t_plot, np.abs(v_plot_analytic), 'b-', label='Analytical $|v(t)|$', linewidth=2)
ax1.plot(t_plot, np.abs(v_plot_numeric), 'r--', label='Numerical $|v(t)|$', linewidth=1.5)
# Mark 95% level
ax1.axhline(y=0.95 * v_infty_mag, color='gray', linestyle=':', linewidth=1.5,
            label=r'$0.95\,|v_\infty|$')
# Mark t95
ax1.axvline(x=t95_numeric, color='red', linestyle=':', linewidth=1.5,
            label=f'$t_{{95}} = {t95_numeric:.3f}\\,\\mathrm{{s}}$')
ax1.set_xlabel('Time $t$ (s)')
ax1.set_ylabel('Speed $|v|$ (m/s)')
ax1.set_title('Skydiver Speed vs Time')
ax1.set_xlim(0, 15)
ax1.set_ylim(0, 60)
ax1.legend()
ax1.grid(True, alpha=0.3)
fig1.tight_layout()
velocity_path = os.path.join(script_dir, 'velocity.jpg')
fig1.savefig(velocity_path, dpi=150)
plt.close(fig1)
print(f"Velocity plot saved to {velocity_path}")

# 2. Position plot (distance fallen s(t))
fig2, ax2 = plt.subplots(figsize=(8, 5))
ax2.plot(t_plot, s_plot_analytic, 'b-', label='Analytical $s(t)$', linewidth=2)
ax2.plot(t_plot, s_plot_numeric, 'r--', label='Numerical $s(t)$', linewidth=1.5)
# Mark s95 at t95
ax2.plot(t95_numeric, s95_numeric, 'ro', markersize=8,
         label=f'$s_{{95}} = {s95_numeric:.1f}\\,\\mathrm{{m}}$ at $t_{{95}}$')
ax2.axvline(x=t95_numeric, color='red', linestyle=':', linewidth=1.5)
ax2.set_xlabel('Time $t$ (s)')
ax2.set_ylabel('Distance fallen $s$ (m)')
ax2.set_title('Skydiver Distance Fallen vs Time')
ax2.set_xlim(0, 15)
ax2.set_ylim(0, 500)
ax2.legend()
ax2.grid(True, alpha=0.3)
fig2.tight_layout()
position_path = os.path.join(script_dir, 'position.jpg')
fig2.savefig(position_path, dpi=150)
plt.close(fig2)
print(f"Position plot saved to {position_path}")

print("Done.")