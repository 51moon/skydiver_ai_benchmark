# AI Agent Benchmark: Skydiver - Evaluation

Evaluation criteria

---


## 1. Evaluation (20 points)

The reference values are $t_{95, ref} = 10,083\,\mathrm {s}$ and $s_{95, ref}=345,982\,\mathrm {m}$. Your analytical values are scored by their deviation from these.

| Check | Criterion | Points |
|---|---|---|
| (a) Derivation | $v(t)$ correct, incl. initial condition and constants | 4 |
| | Stationarity shown cleanly (limit behavior) | 2 |
| (b) analytical | $\|t_{95} - t_{95, ref}\| < 0,05$ s | 3 |
| | $< 0{,}5$ s | 2 |
| | $< 2$ s | 1 |
| (c) analytical | $\|s_{95} - s_{95, ref}\| < 1\,\mathrm {m}$ | 3 |
| | $< 10$ m | 2 |
| | $< 50$ m | 1 |
| Numerics ↔ analytics | $\|t_{95,num} - t_{95, ana}\| < 0,05$ s | 2 |
| | $\|s_{95, num} - s_{95, ana}\| < 1$ m | 2 |
| | `max_v_deviation_ms` $< 0,05$ | 2 |
| Plots | both correct, labeled, reference level/time marked | 2 |

Note: Numerical values that deviate from your own analytical solution indicate missing verification – the consistency rows check exactly that.
