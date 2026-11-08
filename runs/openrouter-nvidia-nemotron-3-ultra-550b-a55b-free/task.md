# AI Agent Benchmark: Skydiver

**One task, two solution paths:** Solve the following problem **analytically** and **numerically**, and cross-check both solutions against each other. All necessary information is in this document.

---

## 1. Framework

- Python; allowed: `numpy`, `scipy`, `matplotlib`, standard library
- Submission as a folder with exactly these files:

```
solution/
├── solution.md        # analytical derivation (a)–(c)
├── results.json       # metrics (schema see section 4)
└── skydiver.py        # numerical simulation → velocity.jpg (|v(t)| plot), position.jpg (s(t) plot)
```

`skydiver.py` must run standalone and place its outputs in the same folder.

---

## 2. Problem Statement

A skydiver experiences the force in the z-direction (z points up):

$$F_z = -mg + \alpha v^2$$

Here $v$ is their velocity in the z-direction (so $v<0$ while falling).

Assumptions: jump from rest, $g = 9{,}81\,\mathrm{\frac{m}{s^2}}$, $z_0=z(0)=3000\,\mathrm{m}$, constant $m$ and $\alpha$.

**(a)** Determine $v(t)$ analytically. Show that the skydiver reaches a terminal velocity $v_\infty$ and give it as a formula.

**(b)** Assume the terminal velocity is $|v_\infty|=54\,\mathrm{\frac{m}{s}}$. How long does it take to reach $95\,\%$ of this velocity?

**(c)** What distance $s=z_0 - |z|$ does the skydiver cover in this time?

---

## 3. Subtasks for the Solution

1. **Analytical:** Complete derivation of $v(t)$ in `solution.md`, including the stationarity argument, exact values for the time from (b) and the fallen distance from (c). Also give $s(t)$ (distance fallen).
2. **Numerical:** Integrate the equation of motion with a method of your choice until $|v| = 0,95 \cdot |v_\infty|$ is reached. Determine numerically:
   - the time $t_{95}$
   - the distance covered by then $s_{95}$.
3. **Consistency check:** Compute the maximum deviation between the numerical and analytical solution $v(t)$ on $[0, t_{95}]$.
4. **Visualization:** Axes with units, legend, numerical solution and analytical solution, $t\in[0,15]$, marked: level $|v|=0,95\,|v_\infty|$ and $t_{95}$
   - `velocity.jpg`: speed magnitude $|v(t)|$.
   - `position.jpg`: distance fallen $s(t)$.

---

## 4. Submission format: `results.json`

```json
{"agent_name": "<name/version of the agent>",
  results: {
    "v_infty_ms": 54,
    "t95_analytic_s": 0,
    "t95_numeric_s": 0,
    "s95_analytic_m": 0,
    "s95_numeric_m": 0,
    "max_v_deviation_ms": 0
    }
}
```

Missing keys count as not passed (0 points).
