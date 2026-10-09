---
title: Benchmarks, active weights and tracking error
section: theory
order: 4
summary: How to measure how different your fund is from simply buying the market, and how much risk that difference carries.
related: [information-ratio, risk-contribution, buffett-bet]
sources:
  - {title: "Grinold, R. C. (1989). The Fundamental Law of Active Management. Journal of Portfolio Management 15(3), 30-37", url: "https://www.pm-research.com/content/iijpormgmt/15/3/30", accessed: 2026-10-09}
---
## Benchmarks

A **benchmark** is what you'd hold if you made no choices at all: for a South African share
fund, usually the JSE Top 40 or All Share index. It answers the question "compared with what?"
A fund that returned 12% sounds good until you learn its benchmark returned 15%.

## Active weights

Wherever your fund differs from the benchmark you have an **active bet**. Your active weight in
a holding is your weight minus the benchmark's weight. Holding 10% in Naspers when the index
holds 8% is a +2% active weight (an *overweight*); holding none of a share the index holds at
3% is a −3% active weight (an *underweight*). Active weights always add up to zero.

## Tracking error

**Tracking error** is the volatility of the *difference* between your return and the
benchmark's. A tracking error of 4% means that in roughly two years out of three, your fund
would land within about 4 percentage points of the benchmark (if the differences were roughly
normal). An index fund aims for close to zero.

It is a separate risk from the market's own. You can be very close to the market (low tracking
error) and still lose a lot in a crash, or far from it and still have low total volatility.

## The tracking-error budget

Just as total risk splits into each holding's contribution, tracking error splits into each
bet's contribution. When one bet takes most of the budget, your result against the benchmark
mostly depends on that single call.

## In this app

*Against a benchmark* shows your active weights, tracking error, each bet's share of it, and two
rules of thumb professionals use to size bets.

## Show me the maths

With active weights $a = w_F - w_B$ and covariance $\Sigma$:

$$TE = \sqrt{a^\top \Sigma a}, \qquad \text{share of TE variance from bet } i = \frac{a_i (\Sigma a)_i}{a^\top\Sigma a}.$$
