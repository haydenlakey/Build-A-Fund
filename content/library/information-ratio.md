---
title: The information ratio and the Fundamental Law
section: theory
order: 5
summary: Reward per unit of active risk, and why both skill and the number of independent bets matter.
related: [tracking-error, estimation-error, buffett-bet]
sources:
  - {title: "Grinold, R. C. (1989). The Fundamental Law of Active Management. Journal of Portfolio Management 15(3), 30-37", url: "https://www.pm-research.com/content/iijpormgmt/15/3/30", accessed: 2026-10-09}
---
## The information ratio

The **information ratio** (IR) is the extra return a fund earns over its benchmark divided by
its tracking error. It is the active-management version of the Sharpe ratio: how much you are
paid for each unit of risk you take by being different.

## The Fundamental Law of Active Management

Richard Grinold showed in 1989 that, under simplifying assumptions, the information ratio a
manager can achieve is approximately

$$IR \approx IC \times \sqrt{BR}.$$

- **IC** (information coefficient) is skill: the correlation between your forecasts and what
  actually happens.
- **BR** (breadth) is the number of **independent** bets you make each year.

The lesson: a small edge applied to many independent decisions can beat a big edge applied to a
few. Ten bets that are really one theme (say, ten AI shares) count as close to **one** bet,
not ten. Grinold presented the law as an approximation and a strategic guide, not a precise
formula.

## Why to be careful with it

Expected active return is among the hardest numbers in finance to estimate. A few good years can
come from luck as easily as skill, so a high historical IR over a short window says little about
the future. *Estimation error* explains why.

## In this app

*Against a benchmark* shows the information ratio implied by your fund's historical averages,
with a warning about how unreliable it is.

## Show me the maths

With active weights $a$, expected returns $\mu$ and covariance $\Sigma$:

$$IR = \frac{a^\top \mu}{\sqrt{a^\top \Sigma a}}.$$

For example, an IC of 0.05 applied to 100 independent bets a year gives $IR \approx 0.05 \times 10 = 0.5$;
the same skill applied to 4 bets gives $0.05 \times 2 = 0.1$.
