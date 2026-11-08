# Analytical Solution: Skydiver Problem

## Given
- Equation of motion: $m \frac{dv}{dt} = -mg + \alpha v^2$
- $z$-axis points upward, so $v < 0$ during fall
- Jump from rest: $v(0) = 0$
- $g = 9.81\,\mathrm{m/s^2}$, $z_0 = 3000\,\mathrm{m}$
- Terminal velocity magnitude: $|v_\infty| = 54\,\mathrm{m/s}$

---

## (a) Analytical derivation of $v(t)$ and terminal velocity

### Terminal velocity (stationarity argument)
At terminal velocity, acceleration vanishes: $\frac{dv}{dt} = 0$.
$$
-mg + \alpha v_\infty^2 = 0 \quad \Rightarrow \quad v_\infty^2 = \frac{mg}{\alpha}
$$
Since the skydiver falls downward ($v < 0$), the terminal velocity is
$$
v_\infty = -\sqrt{\frac{mg}{\alpha}} = -|v_\infty|
$$
Given $|v_\infty| = 54\,\mathrm{m/s}$, we have $v_\infty = -54\,\mathrm{m/s}$.

### Solving the ODE for $v(t)$
The equation of motion is
$$
\frac{dv}{dt} = -g + \frac{\alpha}{m}v^2 = -g\left(1 - \frac{v^2}{v_\infty^2}\right)
$$
where we used $\frac{\alpha}{m} = \frac{g}{v_\infty^2}$. This is a separable ODE:
$$
\frac{dv}{1 - v^2/v_\infty^2} = -g\,dt
$$
Integrate from $0$ to $t$ with $v(0)=0$:
$$
\int_0^v \frac{dv'}{1 - v'^2/v_\infty^2} = -gt
$$
The integral evaluates to $v_\infty \operatorname{artanh}(v/v_\infty)$ (for $|v| < |v_\infty|$):
$$
v_\infty \operatorname{artanh}\left(\frac{v}{v_\infty}\right) = -gt
$$
Solve for $v$:
$$
\frac{v}{v_\infty} = \tanh\left(-\frac{gt}{v_\infty}\right) = -\tanh\left(\frac{gt}{|v_\infty|}\right)
$$
Since $v_\infty = -|v_\infty|$,
$$
\boxed{v(t) = -|v_\infty| \tanh\left(\frac{gt}{|v_\infty|}\right)}
$$
This satisfies $v(0)=0$ and $\lim_{t\to\infty} v(t) = -|v_\infty| = v_\infty$, confirming the stationarity argument.

---

## (b) Time to reach 95% of terminal velocity

We want $|v(t_{95})| = 0.95\,|v_\infty|$. Since $v(t) < 0$,
$$
|v_\infty| \tanh\left(\frac{gt_{95}}{|v_\infty|}\right) = 0.95\,|v_\infty|
\quad\Rightarrow\quad
\tanh\left(\frac{gt_{95}}{|v_\infty|}\right) = 0.95
$$
$$
\frac{gt_{95}}{|v_\infty|} = \operatorname{artanh}(0.95)
= \frac{1}{2}\ln\left(\frac{1+0.95}{1-0.95}\right)
= \frac{1}{2}\ln(39)
$$
Thus the exact analytical expression is
$$
\boxed{t_{95} = \frac{|v_\infty|}{g}\,\operatorname{artanh}(0.95)
= \frac{|v_\infty|}{2g}\ln(39)}
$$
Numerically:
$$
\operatorname{artanh}(0.95) \approx 1.8317817357867764
$$
$$
t_{95} = \frac{54}{9.81} \times 1.8317817357867764
\approx \boxed{10.0833\,\mathrm{s}}
$$

---

## (c) Distance fallen in time $t_{95}$

The distance fallen is $s(t) = z_0 - z(t) = \int_0^t |v(\tau)|\,d\tau$.
Since $|v(\tau)| = |v_\infty| \tanh(g\tau/|v_\infty|)$,
$$
s(t) = |v_\infty| \int_0^t \tanh\left(\frac{g\tau}{|v_\infty|}\right) d\tau
$$
Substitute $u = g\tau/|v_\infty|$, $d\tau = (|v_\infty|/g)\,du$:
$$
s(t) = \frac{|v_\infty|^2}{g} \int_0^{gt/|v_\infty|} \tanh u\,du
= \frac{|v_\infty|^2}{g} \Bigl[\ln\cosh u\Bigr]_0^{gt/|v_\infty|}
$$
$$
\boxed{s(t) = \frac{|v_\infty|^2}{g} \ln\cosh\left(\frac{gt}{|v_\infty|}\right)}
$$
At $t = t_{95}$, we have $gt_{95}/|v_\infty| = \operatorname{artanh}(0.95)$. Using $\cosh(\operatorname{artanh} x) = 1/\sqrt{1-x^2}$:
$$
\cosh(\operatorname{artanh}(0.95)) = \frac{1}{\sqrt{1-0.95^2}} = \frac{1}{\sqrt{0.0975}}
$$
$$
s_{95} = \frac{|v_\infty|^2}{g} \ln\left(\frac{1}{\sqrt{0.0975}}\right)
= -\frac{|v_\infty|^2}{2g} \ln(0.0975)
$$
Numerically:
$$
s_{95} = \frac{54^2}{9.81} \times \ln\left(\frac{1}{\sqrt{0.0975}}\right)
\approx 297.2477 \times 1.163951
\approx \boxed{345.96\,\mathrm{m}}
$$

---

## Summary of analytical results

| Quantity | Symbol | Exact expression | Numerical value |
|----------|--------|------------------|-----------------|
| Terminal velocity | $v_\infty$ | $-\sqrt{mg/\alpha}$ | $-54\,\mathrm{m/s}$ |
| Velocity | $v(t)$ | $-|v_\infty|\tanh(gt/|v_\infty|)$ | — |
| 95% time | $t_{95}$ | $\frac{|v_\infty|}{g}\operatorname{artanh}(0.95)$ | $10.0833\,\mathrm{s}$ |
| Distance fallen | $s(t)$ | $\frac{|v_\infty|^2}{g}\ln\cosh(gt/|v_\infty|)$ | — |
| 95% distance | $s_{95}$ | $\frac{|v_\infty|^2}{g}\ln\cosh(\operatorname{artanh}(0.95))$ | $345.96\,\mathrm{m}$ |