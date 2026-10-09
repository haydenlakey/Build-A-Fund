---
title: Diversification
section: theory
order: 1
summary: Why owning several things that don't move together lowers risk without necessarily lowering return.
related: [efficient-frontier, risk-contribution, estimation-error]
sources:
  - {title: "Markowitz, H. (1952). Portfolio Selection. The Journal of Finance 7(1), 77-91", url: "https://doi.org/10.1111/j.1540-6261.1952.tb01525.x", accessed: 2026-10-09}
---
## The idea in one sentence

If two investments don't rise and fall at exactly the same time, a mix of them swings **less**
than the average of their swings, while its expected return is simply the average of theirs.

## A worked example

Take two shares that each swing about 20% a year (their *volatility*) and each have the same
expected return. Put half your money in each.

- If they move perfectly together (correlation 1), the mix still swings 20%. No benefit.
- If their correlation is 0.3, the mix swings about **16%**.
- If they are unrelated (correlation 0), the mix swings about **14%**.

The expected return is the same in every case. Only the risk changed. Harry Markowitz
formalised this in 1952, and it became the foundation of modern portfolio theory.

## What it can't do

Diversification removes the risk that is **specific** to each holding (one company's bad
news). It can't remove the risk that everything shares, such as a global recession, because
in those moments most shares fall together. Correlations also tend to rise in crises, which
is when diversification is most wanted. See the March 2020 and 2008 case files.

## In this app

*What kind of fund is it?* shows a correlation heatmap of your holdings. Blocks of red are
holdings that move together: owning several of them is closer to one bet than to many.
The Build page's *diversification ratio* is the average volatility of your holdings divided by
the fund's volatility: 1.00 means no benefit at all.

## Show me the maths

For weights $w_1, w_2$, volatilities $\sigma_1, \sigma_2$ and correlation $\rho$:

$$\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2 w_1 w_2 \rho\, \sigma_1 \sigma_2 .$$

With $w_1 = w_2 = 0.5$ and $\sigma_1 = \sigma_2 = 0.2$: $\sigma_p = 0.2\sqrt{(1+\rho)/2}$, which gives
20%, 16.1% and 14.1% for $\rho = 1,\ 0.3,\ 0$.
