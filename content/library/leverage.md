---
title: Leverage and margin calls
section: theory
order: 6
summary: Borrowing to invest multiplies gains and losses, and lenders can force you to sell at the worst moment.
related: [ltcm, risk-contribution, diversification]
sources:
  - {title: "U.S. SEC, Investor Bulletin: Understanding Margin Accounts", url: "https://www.investor.gov/news-alerts/investor-bulletins/investor-bulletin-understanding-margin-accounts", accessed: 2026-10-09}
---
## What leverage does

**Leverage** means investing borrowed money as well as your own. With R10 000 of your own and
R10 000 borrowed you hold R20 000 of shares: **2× leverage**. Every move in the shares is doubled
in your own money:

| The shares move | Your R10 000 at 2× | Your R10 000 at 4× |
|---|---|---|
| +10% | +20% | +40% |
| −10% | −20% | −40% |
| −25% | −50% | **−100%** (wiped out) |
| −50% | **−100%** (wiped out) | wiped out, and you owe the lender |

At 2× a 50% fall wipes you out; at 4× a 25% fall does. A leveraged fund has to survive moves that
an unleveraged one can simply wait out. Interest on the loan is a cost every year, whatever happens.

## Margin calls and forced selling

Lenders protect themselves. In a **margin account** your broker lends against your portfolio, and
if its value falls too far you get a **margin call**: add money, or the broker sells your holdings
to cover the loan. The U.S. SEC's investor bulletin warns that margin increases your purchasing
power but also exposes you to the potential for larger losses.

Forced selling is the real danger. It happens *after* prices have fallen, locks the loss in, and
when many leveraged investors sell at once it pushes prices down further, triggering more calls.
LTCM in 1998 is the classic example.

## Show me the maths

With leverage $L$ (holdings ÷ own capital), borrowing cost $c$ and asset return $r$, the return on
your own money is $L\,r - (L-1)\,c$. You are wiped out when $r \le -1/L$ (ignoring interest).
Volatility scales with leverage too: $\sigma_{\text{own}} = L\,\sigma$.
