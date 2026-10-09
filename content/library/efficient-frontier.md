---
title: The efficient frontier
section: theory
order: 2
summary: The best trade-off between risk and expected return you could get from a given set of holdings, and why it is less useful in practice than it looks.
related: [diversification, estimation-error, risk-contribution]
sources:
  - {title: "Markowitz, H. (1952). Portfolio Selection. The Journal of Finance 7(1), 77-91", url: "https://doi.org/10.1111/j.1540-6261.1952.tb01525.x", accessed: 2026-10-09}
---
## What it is

Take a set of holdings. Every way of splitting your money between them gives a fund with some
expected return and some risk. Plot them all and the upper-left edge of the cloud is the
**efficient frontier**: for each level of risk, the highest expected return those holdings can
offer (and for each return, the lowest risk). Markowitz's 1952 paper introduced the idea.

A fund *on* the frontier can't get more expected return without taking more risk. A fund
*below* it could, in principle, have had the same return with less risk, just by changing
the weights.

## Why it is less useful than it looks

The frontier needs every holding's expected return, and expected returns are very hard to
estimate (see *Estimation error*). Small changes in those estimates swing the "optimal" weights
wildly, often into a handful of holdings that happened to do well recently. That is why this
app shows the frontier as a guide to direction (did a change move you toward it or away?)
rather than as a target.

## In this app

The Build page draws the frontier for your holdings (no borrowing, no short selling) and
shows your fund before and after a change. Moving up and to the left is better.

## Show me the maths

For expected returns $\mu$ and covariance matrix $\Sigma$, each point on the frontier solves

$$\min_w \; w^\top \Sigma w \quad\text{subject to}\quad w^\top\mu = m,\;\; \mathbf 1^\top w = 1,\;\; w \ge 0$$

for a target return $m$. The app solves it for a grid of targets.
