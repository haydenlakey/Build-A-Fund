---
title: Risk contribution
section: theory
order: 3
summary: Why a holding's share of your risk can be very different from its share of your money.
related: [diversification, tracking-error, leverage]
sources:
  - {title: "Markowitz, H. (1952). Portfolio Selection. The Journal of Finance 7(1), 77-91", url: "https://doi.org/10.1111/j.1540-6261.1952.tb01525.x", accessed: 2026-10-09}
---
## The idea

Ten percent of your rands in a steady bond fund and ten percent in a volatile tech share are
the same amount of money but very different amounts of **risk**. A holding's risk contribution
measures how much of the fund's ups and downs it is responsible for. It depends on three things:
how much you hold, how much it swings, and how much it moves with everything else you own.

A holding can even have a **negative** contribution: if it tends to rise when the rest of the
fund falls (gold sometimes does this against shares), adding a little of it lowers total risk.

## Why it matters

Funds that look balanced by money are often dominated by one or two holdings by risk. A
classic example is a "60/40" mix of shares and bonds, where shares usually supply far more
than 60% of the risk because they are so much more volatile than bonds.

## In this app

*What kind of fund is it?* pairs each holding's share of the rands with its share of the risk.
The holdings table on the Build page shows both too.

## Show me the maths

With weights $w$ and covariance matrix $\Sigma$, fund volatility is $\sigma_p = \sqrt{w^\top\Sigma w}$.
Because $\sigma_p$ scales in proportion to the weights, Euler's theorem splits it exactly:

$$\sigma_p = \sum_i RC_i, \qquad RC_i = w_i \frac{\partial \sigma_p}{\partial w_i} = \frac{w_i (\Sigma w)_i}{\sigma_p}.$$

Each holding's share of risk is $RC_i/\sigma_p$, and the shares add to 100%.
