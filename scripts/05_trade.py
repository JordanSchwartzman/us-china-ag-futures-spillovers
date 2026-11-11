"""Can the paper's findings be traded with daily bars?

T1  "US-signal CN intraday": signal = US daily return on day t vs its *expanding past* median /
    deciles; trade CN open(t+1) -> close(t+1). The paper's negative intraday CQ at the median
    (Tab V) implies FADE: short CN after a US up day, long after a US down day.
    Valid only before CN night sessions (afterwards the CN 'open' is printed during US day t).
T1g "fade CN opening gap": position = -sign(CN overnight gap at open t+1), held to close.
    Gap is known at entry. Tradable in both eras (post night-session it is the 15:00->21:00 gap).
T2  CN daily return -> US day-session: NOT backtestable with yfinance (its 'open' is the 19:00 CT
    electronic open, which precedes the CN session). Reported as statistic only (Tab VI).

Costs: 1 tick per side (round trip 2 ticks) on CN.  Usage: python scripts/05_trade.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.align import joint
from src.data import CN_NIGHT_START, COMMODITIES, load
from src.plots import AQUA, BLUE, INK2, ORANGE, plt

OUT = Path(__file__).resolve().parents[1] / "output"
TICK = {"soybeans": 1.0, "wheat": 1.0, "corn": 1.0, "sugar": 1.0}  # RMB/ton min price move
MIN_VOL = 2000
WARMUP = 250


def stats_row(pnl: pd.Series, label: str) -> dict:
    p = pnl.dropna()
    p = p[p != 0]
    if len(p) < 30:
        return {"strategy": label, "n": len(p)}
    nw = sm.OLS(p.values, np.ones(len(p))).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    per_year = len(p) / ((p.index[-1] - p.index[0]).days / 365.25)
    return {"strategy": label, "n": len(p), "mean_bp": 1e4 * p.mean(), "hit": (p > 0).mean(),
            "t_NW": nw.tvalues[0], "sharpe": p.mean() / p.std() * np.sqrt(per_year),
            "start": p.index[0].date(), "end": p.index[-1].date()}


rows, curves = [], {}
for c in COMMODITIES:
    cnr, usr, cn, us = load(c)
    cnr = cnr[cn["volume"].reindex(cnr.index) >= MIN_VOL]
    j = joint(cnr, usr)
    night = CN_NIGHT_START[c]
    # --- signals (all information available before CN open of the trade day)
    us_d = j["US_D"]
    past_med = us_d.expanding(WARMUP).median()
    past_q10 = us_d.expanding(WARMUP).quantile(0.1)
    past_q90 = us_d.expanding(WARMUP).quantile(0.9)
    # trade day = next joint row (CN day t+1); shift signals forward by 1
    sig_med = -np.sign(us_d - past_med).shift(1)
    sig_tail = ((us_d <= past_q10).astype(float) - (us_d >= past_q90).astype(float)).shift(1)  # long after US crash, short after spike
    sig_tail = sig_tail.where(sig_tail != 0)
    sig_lag2 = -np.sign(us_d - past_med).shift(2)  # look-ahead audit: one extra day stale
    in_ret = j["CN_IN"]
    cost = 2 * TICK[c] / cn["open"].reindex(j.index)
    gap = j["CN_OV"]
    sig_gap = -np.sign(gap)

    eras = {"pre-night": (None, night)} if night else {"pre-night": (None, None)}
    if night:
        eras["post-night"] = (night, None)
    for era, (a, b) in eras.items():
        sl = slice(a, pd.Timestamp(b) - pd.Timedelta(days=1) if b else None)
        if era == "pre-night":
            for lab, s in (("T1 fade US (median split)", sig_med), ("T1 fade US (tails only)", sig_tail),
                           ("T1 audit: signal 1 day stale", sig_lag2)):
                g = (s * in_ret).loc[sl]
                n = (s * in_ret - s.abs() * cost).loc[sl]
                rows.append({"commodity": c, "era": era, **stats_row(g, lab + " [gross]")})
                rows.append({"commodity": c, "era": era, **stats_row(n, lab + " [net]")})
                if lab.startswith("T1 fade US (median"):
                    curves[(c, "T1 net")] = n.dropna().cumsum()
        g = (sig_gap * in_ret).loc[sl]
        n = (sig_gap * in_ret - sig_gap.abs() * cost).loc[sl]
        rows.append({"commodity": c, "era": era, **stats_row(g, "T1g fade CN gap [gross]")})
        rows.append({"commodity": c, "era": era, **stats_row(n, "T1g fade CN gap [net]")})
        curves[(c, f"T1g net {era}")] = n.dropna().cumsum()
    # attribution: does the US signal add anything beyond the CN gap? (pre-night, OLS with HAC)
    pre = j.loc[: pd.Timestamp(night) - pd.Timedelta(days=1)] if night else j
    X = pd.DataFrame({"US_D_t": pre["US_D"].shift(1), "CN_gap": pre["CN_OV"]}).dropna()
    y = pre["CN_IN"].reindex(X.index)
    m = y.notna()
    fit = sm.OLS(y[m], sm.add_constant(X[m])).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    print(f"\n{c}: CN_IN(t+1) ~ US_D(t) + CN_gap(t+1)  [pre-night]\n",
          pd.DataFrame({"coef": fit.params, "t": fit.tvalues}).round(4).to_string())

res = pd.DataFrame(rows)
res.to_csv(OUT / "tables" / "trade_results.csv", index=False)
pd.set_option("display.width", 200)
print("\n", res.round(3).to_string(index=False))

# equity curves (net, cumulative log return, 1x notional)
fig, axes = plt.subplots(1, 4, figsize=(14, 3.6), sharey=False)
for ax, c in zip(axes, COMMODITIES):
    for key, col, lab in (((c, "T1 net"), BLUE, "T1 fade US (median split)"),
                          ((c, "T1g net pre-night"), ORANGE, "T1g fade gap (pre-night)"),
                          ((c, "T1g net post-night"), AQUA, "T1g fade gap (post-night)")):
        if key in curves and len(curves[key]):
            ax.plot(curves[key].index, curves[key].values, color=col, lw=2, label=lab)
    ax.axhline(0, color=INK2, lw=0.6)
    if CN_NIGHT_START[c]:
        ax.axvline(pd.Timestamp(CN_NIGHT_START[c]), color=INK2, lw=0.8, ls=":")
    ax.set_title(c)
    ax.set_ylabel("cum. log return, net of 2 ticks")
axes[0].legend(loc="upper left")
fig.suptitle("CN intraday strategies — net equity (dotted line = CN night sessions start)", color=INK2, fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "figs" / "trade_equity.png", dpi=140)
print("saved")
