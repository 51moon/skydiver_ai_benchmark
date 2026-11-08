# Analytical solution for the skydiver problem

## (a) Determination of $v(t)$ and terminal velocity

The motion in the $z$-direction (upward positive) is governed by the force balance:

$$F_z = m\,a_z = m\frac{dv}{dt} = -mg + \alpha v^2.$$

Dividing by $m$ and introducing the constant $C\equiv \alpha/m$ we have the ordinary differential equation

$$\frac{dv}{dt} = -g + C v^2 \qquad (v<0 \text{ while falling}).$$

A terminal velocity $v_\infty$ is reached when the acceleration vanishes, i.e. $dv/dt\to0$. Setting the right‑hand side to zero gives

$$-g + C v_\infty^2 = 0 \;\Longrightarrow\; v_\infty = -\sqrt{\frac{g}{C}} = -\sqrt{\frac{gm}{\alpha}}.$$

(The negative sign follows from the definition that the skydiver falls, $v<0$.)

Thus the magnitude of the terminal speed is $|v_\infty|=\sqrt{gm/\alpha}$.

### Solving the ODE

The equation can be separated:

$$\frac{dv}{v^2 - v_\infty^2}= C\,dt.$$

Integrating from $v(0)=0$ to an arbitrary $v(t)$ gives

$$\frac{1}{2v_\infty}\ln\!\Bigl|\frac{v-v_\infty}{v+v_\infty}\Bigr| = C t.$$

Solving for $v$ yields

$$\frac{v-v_\infty}{v+v_\infty}=e^{2C v_\infty t}.$$

With $v_\infty<0$ and $C>0$ the right‑hand side decays from $1$ to $0$ as $t$ grows. Solving for $v$ gives the closed‑form solution

$$\boxed{v(t)=v_\infty\frac{1-e^{2C v_\infty t}}{1+e^{2C v_\infty t}} = -|v_\infty|\tanh\!\Bigl(\frac{g}{|v_\infty|}t\Bigr)}.$$

Here we used the identities $C v_\infty = -g/|v_\infty|$ and $\tanh x = (1-e^{-2x})/(1+e^{-2x})$.

The expression shows that as $t\to\infty$, $\tanh(\cdot)\to1$ and $v(t)\to -|v_\infty| = v_\infty$. Hence the skydiver approaches a constant speed $v_\infty$ – the terminal velocity.

## (b) Time to reach $95\%$ of the terminal speed

We are told $|v_\infty|=54\,\mathrm{m/s}$. The $95\%$ level is $|v|=0.95\,|v_\infty|=51.3\,\mathrm{m/s}$.

From the analytical solution,

$$\tanh\!\Bigl(\frac{g}{|v_\infty|}t_{95}\Bigr)=0.95.$$

Thus

$$\frac{g}{|v_\infty|}t_{95}=\operatorname{arctanh}(0.95)=\frac12\ln\!\frac{1+0.95}{1-0.95}\approx1.831781.$$

Hence

$$\boxed{t_{95}= \frac{|v_\infty|}{g}\,\operatorname{arctanh}(0.95)\approx\frac{54}{9.81}\times1.831781\approx10.08\ \mathrm{s}}.$$

## (c) Distance fallen $s_{95}$ in that time

The distance fallen is $s(t)=z_0-z(t)=\displaystyle\int_0^{t}|v(t')|\,dt'$.

Using $v(t)=-|v_\infty|\tanh(\kappa t)$ with $\kappa=g/|v_\infty|$, we obtain

$$s(t)=|v_\infty|\int_0^{t}\tanh(\kappa t')dt'
      =\frac{|v_\infty|}{\kappa}\ln\!\bigl(\cosh(\kappa t)\bigr)
      =\frac{|v_\infty|^2}{g}\,\ln\!\bigl(\cosh(\kappa t)\bigr).$$

Therefore

$$\boxed{s(t)=\frac{54^2}{9.81}\,\ln\!\bigl(\cosh(0.18166667\,t)\bigr)\approx 297.247\ln\!\bigl(\cosh(0.18166667\,t)\bigr)\ \text{m}}.$$

Evaluating at $t_{95}$:

$$\kappa t_{95}=\operatorname{arctanh}(0.95)\approx1.831781,$$

so $\cosh(\kappa t_{95})=1/\sqrt{1-0.95^2}=1/\sqrt{0.0975}\approx3.2026$ and $\ln\cosh(\kappa t_{95})\approx1.166$. Hence

$$\boxed{s_{95}=s(t_{95})\approx\frac{2916}{9.81}\times1.166\approx346.6\ \mathrm{m}}.$$

## Summary of analytical results

| Quantity | Symbol | Value |
|----------|--------|-------|
| Terminal speed magnitude | $|v_\infty|$ | $54\,\mathrm{m/s}$ |
| Time to $95\%$ of terminal speed | $t_{95}$ | $10.08\,\mathrm{s}$ |
| Distance fallen up to $t_{95}$ | $s_{95}$ | $346.6\,\mathrm{m}$ |

The analytical solution also provides the general expressions for $v(t)$ and $s(t)$ given above.

---

*Note: All derivations respect the initial condition $v(0)=0$ and the sign conventions described in the problem.*