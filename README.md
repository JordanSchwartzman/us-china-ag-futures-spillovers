# US ↔ China agricultural futures spillovers: replicating Jiang et al. (2016)

This repo replicates the results and tests the tradability of:

> Jiang, Su, Todorova & Roca (2016). *Spillovers and Directional Predictability with a Cross-Quantilogram Analysis: The Case of U.S. and Chinese Agricultural Futures.* Journal of Futures Markets 36(12), 1231–1255. doi:10.1002/fut.21779

The paper itself isn't included because of copyright.

- **[REPORT.md](REPORT.md)** has the findings: the replication vs the paper, the out-of-sample check from 2014 to 2026, and the trade tests.
- **[PAPER_NOTES.md](PAPER_NOTES.md)** has the page-by-page summary, the method, the data, and the paper's target numbers.

## Headline
- The replication matches the paper's Table V (US→CN, lag 1) at correlation 0.97 and Table VI at 0.81.
- The US→CN spillover sits in the CN overnight return, which you can't trade from daily bars.
- The intraday-fade leg had an edge in the paper era (t ≈ 3–5 gross). It has **≈0 edge out of sample**: corn from 2014 to 2019 earns 0.1 bp/day with t = 0.05.
- After CN night sessions began (Dec 2014), the intraday spillover flipped from negative to positive. That's the shift the trading-hours change predicts.

## Run
```bash
pip install -r requirements.txt
python tests/test_quantilogram.py
python scripts/01_fetch.py                    # caches data to data/raw/
python scripts/02_replicate.py                # paper sample, about 3 min at B=1000
python scripts/02_replicate.py --start 2014-09-01 --end "" --tag oos --commodities soybeans,corn,sugar --min_cn_volume 2000
python scripts/03_rolling.py
python scripts/05_trade.py
```
Data: Chinese futures come from Sina main-continuous via akshare (2005 onward); US futures come from Yahoo Finance. `REPORT.md` lists the data caveats.

`src/quantilogram.py` is a standalone numba implementation of the cross-quantilogram and portmanteau test (Han, Linton, Oka & Whang), with stationary-bootstrap inference.
