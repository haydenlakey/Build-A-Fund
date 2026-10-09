---
title: Estimation error
section: theory
order: 8
summary: Why expected returns are the least reliable number in finance, and what that means for every chart in this app.
related: [efficient-frontier, information-ratio, diversification]
sources:
  - {title: "Merton, R. C. (1980). On Estimating the Expected Return on the Market: An Exploratory Investigation. NBER Working Paper 444, published in the Journal of Financial Economics 8", url: "https://www.nber.org/papers/w0444", accessed: 2026-10-09}
---
## Risk is easy to measure, return is not

Ask "how much does this share swing?" and a few years of weekly prices give a decent answer.
Ask "what return does it earn on average?" and even decades of data leave a wide range. Robert
Merton studied how hard it is to estimate the market's expected return in 1980.

The reason is arithmetic. The uncertainty in an average return shrinks only with the square
root of the number of **years** observed. Sampling more often (weekly instead of monthly)
doesn't help much, because the average return is pinned down by the start and end prices.
Volatility estimates, by contrast, do improve with more frequent data.

## How big is the problem?

For a share that swings 20% a year, the standard error of its average annual return is:

| Years of data | Standard error of the average |
|---|---|
| 5 | ±8.9% a year |
| 10 | ±6.3% a year |
| 25 | ±4.0% a year |

So with five years of data, a share that "returned 15% a year" is consistent with a true
expected return anywhere from about −3% to 33% (two standard errors either side). That is why
this app shrinks historical averages toward a prior and prints a ± range under expected return.

## What it means for a fund builder

- Treat any expected return, including the ones in this app, as a rough guess.
- Be wary of optimisers: they lean hardest on exactly the numbers that are least reliable.
- Diversification relies mostly on volatilities and correlations, which are measured far better.

## Show me the maths

With annual volatility $\sigma$ and $T$ years of data, the standard error of the mean annual
return is approximately $\sigma/\sqrt{T}$, whatever the sampling frequency: $0.2/\sqrt{5} \approx 8.9\%$.
