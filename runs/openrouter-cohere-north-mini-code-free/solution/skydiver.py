#!/usr/bin/env python3
"""
Numerical simulation for the skydiver benchmark.
Solves dv/dt = -g + C v^2, dz/dt = v with initial conditions v(0)=0, z(0)=3000.
Stops when |v| >= 0.95 * |v_inf|.
Writes results.json, velocity.jpg and position.jpg in the same directory.
"""

import os
import json
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

# Constants from the problem
g = 9.81
v_inf_mag = 54.0  # m/s, magnitude of terminal velocity
C = g / (v_inf_mag ** 2)  # = alpha/m, 1/s

# Initial conditions
v0 = 0.0
z0 = 3000.0

# Event: stop when |v| >= 0.95 * v_inf_mag
event_target = 0.95 * v_inf_mag
def stop_event(t, y):
    v = y[0]
    # v is negative, so -v is positive speed
    return -v - event_target
stop_event.terminal = True
stop_event.direction = 1  # increasing -v

# ODE system: y = [v, z]
def ode_system(t, y):
    v, z = y
    dv = -g + C * v**2
    dz = v
    return [dv, dz]

# Integrate until event or max time 30 s
sol = solve_ivp(ode_system, [0, 30], [v0, z0],
                events=stop_event, dense_output=True,
                rtol=1e-9, atol=1e-12)

# Extract solution
t = sol.t
v_num = sol.y[0]
z_num = sol.y[1]

# Time at which stopping event occurred (if event triggered)
if sol.t_events[0].size > 0:
    t95_numeric = float(sol.t_events[0][0])
else:
    # fallback: use last time in solution
    t95_numeric = float(t[-1])

# Distance fallen: s = z0 - z
s_num = z0 - z_num
# Analytical functions
a = g / v_inf_mag  # = kappa
v_ana = -v_inf_mag * np.tanh(a * t)
s_ana = (v_inf_mag**2 / g) * np.log(np.cosh(a * t))

# Compute s95 numeric from integration (use interpolation if needed)
# We can approximate s95_numeric by evaluating s_num at t95_numeric using interpolation.
from scipy.interpolate import interp1d
v_interp = interp1d(t, v_num, kind='cubic', fill_value='extrapolate')
z_interp = interp1d(t, z_num, kind='cubic', fill_value='extrapolate')
v_at_t95 = v_interp(t95_numeric)
z_at_t95 = z_interp(t95_numeric)
s95_numeric = z0 - z_at_t95

# Analytical values for comparison
t95_analytic = (v_inf_mag / g) * np.arctanh(0.95)
s95_analytic = (v_inf_mag**2 / g) * np.log(np.cosh(a * t95_analytic))

# Max deviation of velocity magnitude (m/s) over the interval [0, t95]
mask = t <= t95_numeric
if np.any(mask):
    max_v_deviation = np.max(np.abs(v_num[mask] - v_ana[mask]))
else:
    max_v_deviation = 0.0

# Prepare results JSON
agent_name = "OpenCode"  # could be more specific, but fine
results = {
    "agent_name": agent_name,
    "results": {
        "v_infty_ms": v_inf_mag,
        "t95_analytic_s": round(t95_analytic, 6),
        "t95_numeric_s": round(t95_numeric, 6),
        "s95_analytic_m": round(s95_analytic, 6),
        "s95_numeric_m": round(s95_numeric, 6),
        "max_v_deviation_ms": round(max_v_deviation, 6)
    }
}

# Write results.json in the same directory as script
script_dir = os.path.dirname(os.path.abspath(__file__))
results_path = os.path.join(script_dir, "results.json")
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)

# Plotting
plt.rcParams.update({"font.size": 12})

# ----- velocity magnitude plot -----
plt.figure(figsize=(10, 6))
plt.plot(t, np.abs(v_num), label="Numerical $|v(t)|$", color="blue")
plt.plot(t, np.abs(v_ana), label="Analytical $|v(t)|$", linestyle="--", color="orange")
# Reference level 0.95 * v_inf_mag
plt.axhline(y=event_target, color="red", linestyle=":", label=r"$0.95\,|v_\infty|$" )
# Vertical line at t95 (analytic)
plt.axvline(x=t95_analytic, color="green", linestyle="-", alpha=0.5, label=r"$t_{95}$ (analytical)")
plt.xlabel("Time $t$ / s")
plt.ylabel("Speed $|v(t)|$ / m·s$^{-1}$")
plt.title(r"Skydiver velocity magnitude ($t\in[0,15]$ s)")
plt.legend()
plt.grid(True, alpha=0.3)
# Ensure x-limit up to 15 s as requested
plt.xlim(0, 15)
velocity_path = os.path.join(script_dir, "velocity.jpg")
plt.savefig(velocity_path, dpi=150)
plt.close()

# ----- position (distance fallen) plot -----
plt.figure(figsize=(10, 6))
plt.plot(t, s_num, label="Numerical $s(t)$", color="blue")
plt.plot(t, s_ana, label="Analytical $s(t)$", linestyle="--", color="orange")
# Mark t95 and s95 level for position plot (s95_analytic)
plt.axvline(x=t95_analytic, color="green", linestyle="-", alpha=0.5, label=r"$t_{95}$ (analytical)")
plt.axhline(y=s95_analytic, color="red", linestyle=":", label=r"$s_{95}$ (analytical)")
plt.xlabel("Time $t$ / s")
plt.ylabel("Distance fallen $s(t)$ / m")
plt.title(r"Skydiver distance fallen ($t\in[0,15]$ s)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.xlim(0, 15)
position_path = os.path.join(script_dir, "position.jpg")
plt.savefig(position_path, dpi=150)
plt.close()

print("Simulation completed.")
print(f"Results written to {results_path}")
print(f"Plots: {velocity_path}, {position_path}")