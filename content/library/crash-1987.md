---
title: "Black Monday: the 1987 crash"
section: case
group: Shocks
order: 1
years: "1987"
summary: On 19 October 1987 the Dow Jones Industrial Average fell 22.6% in a single day. Automatic selling by "portfolio insurance" sped the crash up. Yet less than two years later US shares were back above their pre-crash highs.
lesson: Markets can fall far further in a day than a normal-distribution model expects, and strategies that sell automatically as prices fall can make the fall worse. A fund that doesn't have to sell can wait for the recovery; one that does locks in the loss.
related: [march-2020, leverage, estimation-error, diversification]
chart:
  kind: points
  title: S&P 500 index, January 1987 to September 1989 (closes every second Friday, plus 16 and 19 October 1987)
  series: S&P 500
  unit: Index points
  source: "Yahoo Finance, ^GSPC daily closes (price index, dividends not included), read 2026-10-13. Every second Friday, plus the closes on Friday 16 and Monday 19 October 1987."
  points: [[1987-01-02, 246.45], [1987-01-16, 266.28], [1987-01-30, 274.08], [1987-02-13, 279.70], [1987-02-27, 284.20], [1987-03-13, 289.89], [1987-03-27, 296.13], [1987-04-10, 292.49], [1987-04-24, 281.52], [1987-05-08, 293.37], [1987-05-22, 282.16], [1987-06-05, 293.45], [1987-06-19, 306.97], [1987-07-03, 305.63], [1987-07-17, 314.59], [1987-07-31, 318.66], [1987-08-14, 333.99], [1987-08-28, 327.04], [1987-09-11, 321.98], [1987-09-25, 320.16], [1987-10-09, 311.07], [1987-10-16, 282.70], [1987-10-19, 224.84], [1987-10-23, 248.22], [1987-11-06, 250.41], [1987-11-20, 242.00], [1987-12-04, 223.92], [1987-12-18, 249.16], [1988-01-01, 247.08], [1988-01-15, 252.05], [1988-01-29, 257.07], [1988-02-12, 257.63], [1988-02-26, 262.46], [1988-03-11, 264.94], [1988-03-25, 258.51], [1988-04-08, 269.43], [1988-04-22, 260.14], [1988-05-06, 257.48], [1988-05-20, 253.02], [1988-06-03, 266.45], [1988-06-17, 270.68], [1988-07-01, 271.78], [1988-07-15, 272.05], [1988-07-29, 272.02], [1988-08-12, 262.55], [1988-08-26, 259.68], [1988-09-09, 266.84], [1988-09-23, 269.76], [1988-10-07, 278.07], [1988-10-21, 283.66], [1988-11-04, 276.31], [1988-11-18, 266.47], [1988-12-02, 271.81], [1988-12-16, 276.29], [1988-12-30, 277.72], [1989-01-13, 283.87], [1989-01-27, 293.82], [1989-02-10, 292.02], [1989-02-24, 287.13], [1989-03-10, 292.88], [1989-03-24, 288.98], [1989-04-07, 297.16], [1989-04-21, 309.61], [1989-05-05, 307.61], [1989-05-19, 321.24], [1989-06-02, 325.52], [1989-06-16, 321.35], [1989-06-30, 317.98], [1989-07-14, 331.84], [1989-07-28, 342.15], [1989-08-11, 344.74], [1989-08-25, 350.52], [1989-09-08, 348.76], [1989-09-22, 347.05]]
sources:
  - {title: "Donald Bernhardt and Marshall Eckblad, Stock Market Crash of 1987 (Federal Reserve History)", url: "https://www.federalreservehistory.org/essays/stock-market-crash-of-1987", accessed: 2026-10-13}
  - {title: "Yahoo Finance price history: S&P 500 index (^GSPC)", url: "https://finance.yahoo.com/quote/%5EGSPC/history/", accessed: 2026-10-13}
---
## What happened

US shares had a spectacular 1987. **By late August the Dow Jones Industrial Average had gained 44% in seven
months**, "stoking concerns of an asset bubble" (Federal Reserve History). In mid-October the news turned: the
US government reported a larger-than-expected trade deficit and the dollar fell.

On **Monday 19 October 1987**, "Black Monday", stock markets in and around Asia were already falling before New
York opened. The Dow "crashed at the opening bell and eventually finished down **508 points, or 22.6 percent**".
It was "the first contemporary global financial crisis": in the most severe case, **New Zealand's stock market
fell 60%** (Federal Reserve History).

On Yahoo Finance's figures, the broader **S&P 500** closed at 282.70 on Friday 16 October and 224.84 on Monday
19 October, a fall of **20.5% in one day**. From its August high of 336.77 to its low of 223.92 on 4 December, it
fell **34%**.

## Why it fell so fast: selling that feeds on itself

A popular new product, **portfolio insurance**, used futures and options to limit an investor's losses by
selling as prices fell. The Fed's history says it "accelerated the crash's pace as initial losses led to further
rounds of selling", and quotes the economist Robert Shiller: "An initial price decline starts a vicious circle by
causing portfolio insurers to sell."

Each investor's rule made sense on its own: sell a little more as the market falls. But when many investors
follow the same rule at once, their selling pushes prices down further, which triggers more selling. Investors
trading on borrowed money faced the same spiral: as prices fell, their accounts could go negative, leading to
**forced sales** (Federal Reserve History).

## How a 22.6% day looks to a statistician

From January 1985 to September 1987 the S&P 500's daily returns had a standard deviation of about **0.85%**
(computed by the app from Yahoo's daily closes). The 20.5% fall on 19 October was about **24 standard
deviations** below the average day. A normal-distribution model treats a move that size as essentially impossible.
It happened anyway. This is why the app's risk measures include **historical**
and **simulated** versions, not just the normal one, and why risk estimated from calm years can understate
what a crash can do.

## What the authorities did

On 20 October, Fed Chairman Alan Greenspan said the Fed "affirmed today its readiness to serve as a source of
liquidity to support the economic and financial system". Behind the scenes, the Fed encouraged banks to keep
lending, and the ten largest New York banks nearly doubled their lending to securities firms that week. After the
crash, exchanges introduced **circuit breakers** that halt trading after very large falls; today the New York
Stock Exchange pauses when the S&P 500 is down 7%, 13% and 20% (Federal Reserve History).

## And then it turned

"In just two trading sessions, the DJIA gained back 288 points, or 57 percent, of the total Black Monday downturn",
and "less than two years later, US stock markets surpassed their pre-crash highs" (Federal Reserve History).
On Yahoo's data, the S&P 500 first closed above its August 1987 high on 26 July 1989.

## Who was hurt

Investors who sold in the panic, or who were forced to sell because they had borrowed, locked in the losses. Those
who held on and didn't need the money saw their shares recover within two years (before dividends, which added
to the recovery).

## The lesson for a fund builder

- **Crashes are bigger than the bell curve predicts.** Look at the historical and stress-test measures, not just
  volatility.
- **Automatic selling rules can make a fall worse** when many people follow the same rule.
- **Not having to sell is a form of protection.** Borrowed money and money needed soon both remove that option.
