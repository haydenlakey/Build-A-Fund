---
title: "2022: when shares and bonds fell together"
section: case
group: Inflation and rates
order: 3
years: "2022"
summary: US inflation reached 9.1%, the Federal Reserve raised rates from near zero to over 4%, and US shares and bonds both lost heavily in the same year. The usual cushion, bonds rising when shares fall, failed.
lesson: Bonds usually offset shares when growth is the worry, but not when inflation and rising interest rates are. A fund that relies on bonds as its only shock absorber is exposed to exactly this kind of year.
related: [diversification, estimation-error, risk-contribution, march-2020]
chart:
  kind: prices
  title: S&P 500 ETF, long US Treasury ETF, Satrix 40 and SA government bonds, all in rand, 2022
  tickers: [SPY, TLT, STX40.JO, STXGOV.JO]
  start: 2021-12-31
  end: 2022-12-30
  names: {SPY: "S&P 500 ETF (SPY) in rand", TLT: "Long US Treasury ETF (TLT) in rand", STX40.JO: "Satrix 40", STXGOV.JO: "Satrix SA government bond ETF"}
  source: "Weekly total-return closes from Yahoo Finance (the app's price data), US ETFs converted to rand at USD/ZAR, rebased to 100 on 31 December 2021."
sources:
  - {title: "U.S. Bureau of Labor Statistics: Consumer Price Index news release, June 2022 (published 13 July 2022)", url: "https://www.bls.gov/news.release/archives/cpi_07132022.htm", accessed: 2026-10-11}
  - {title: "Federal Reserve press release (16 March 2022): FOMC statement", url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm", accessed: 2026-10-11}
  - {title: "Federal Reserve press release (14 December 2022): FOMC statement", url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20221214a.htm", accessed: 2026-10-11}
  - {title: "Yahoo Finance price history (adjusted closes): SPY, TLT, AGG, STX40.JO, STXGOV.JO", url: "https://finance.yahoo.com/quote/SPY/history/", accessed: 2026-10-11}
---
## What happened

After the pandemic, prices in the US rose fast. The US Bureau of Labor Statistics reported that consumer
prices rose **9.1% in the 12 months to June 2022**, "the largest 12-month increase since the period ending
November 1981".

The Federal Reserve responded by raising interest rates. On **16 March 2022** it raised its target range for
the federal funds rate to **¼ to ½ percent**; by **14 December 2022** it had reached **4¼ to 4½ percent**.

## Why shares and bonds fell together

A bond pays fixed amounts of money in the future. When interest rates rise, new bonds pay more, so existing
bonds lose value, and the longer the bond the bigger the fall. Higher rates also make future company profits
worth less today, which hits shares, especially those valued on profits expected far in the future.

So in 2022 the same cause pushed both down. Total returns for the year in US dollars (Yahoo Finance adjusted
closes):

| | 2022, in US dollars | 2022, in rand (app data) |
|---|---|---|
| S&P 500 ETF (SPY) | **−18.2%** | **−12.9%** |
| Long US Treasury ETF (TLT) | **−31.2%** | **−26.8%** |
| Broad US bond ETF (AGG) | **−13.0%** | |
| Satrix 40 | | **about 0%** |
| Satrix SA government bond ETF | | **−2.8%** |

The rand weakened from **R15.89 to R16.92** per dollar over the year, which softened the dollar losses for a
South African investor. South African shares and bonds were roughly flat in 2022.

## Who was hurt

Investors who held the traditional "balanced" mix of shares and bonds, and especially those who relied on
**long-dated bonds** to protect them when shares fell. In 2022 that protection lost money too.

## The lesson for a fund builder

- **Correlations change with the cause of the shock.** In a growth scare (US Treasuries in March 2020) bonds
  can rise as shares fall; in an inflation shock both can fall.
- **Know what each holding protects against.** In rand, what held up in 2022 was priced in a different
  economy or currency: South African shares and bonds, and the dollar itself.
- **Estimated correlations come from the past.** A covariance matrix built on years when bonds and shares moved
  opposite ways will understate how they can move together in a year like 2022.
