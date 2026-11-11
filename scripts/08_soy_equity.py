"""Equity curve: soybean intraday fade, Rule A (trade only when |US move| >= 1 sigma).

Signal (known before the DCE open on CN day t+1): z = US soybean close-to-close return on day t divided by
its trailing 60-day vol (through day t-1). If |z| >= 1, take position -sign(z) in DCE soybean No.1
at the open of CN day t+1, exit at the close. 1x notional, no compounding, 2 ticks round-trip cost.
Window: --start (default 2010-01-01, after the post-2009 decay of the overreaction) -> day before the
DCE night session (2014-12-26). Not tradable in this form afterwards. Signals use pre-start data only as
trailing warm-up (backward-looking), trades and P&L start at --start.

Outputs: docs/figures/6_soy_equity_{light,dark}.png, output/tables/soy_ruleA_daily.csv
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.align import joint
from src.data import CN_NIGHT_START, load

import argparse

ap = argparse.ArgumentParser()
ap.add_argument("--start", default="2010-01-01")
args = ap.parse_args()
START = pd.Timestamp(args.start)
ROOT = Path(__file__).resolve().parents[1]
DOCS, TAB = ROOT / "docs" / "figures", ROOT / "output" / "tables"

cnr, usr, cn, _ = load("soybeans")
cnr = cnr[cn["volume"].reindex(cnr.index) >= 2000]
end = pd.Timestamp(CN_NIGHT_START["soybeans"]) - pd.Timedelta(days=1)
j = joint(cnr, usr).loc[:end]
u = j.US_D
z = u / u.rolling(60, min_periods=40).std().shift(1)
med = u.expanding(250).median()
cost = 2 / cn["open"].reindex(j.index)
pos_a = (-np.sign(z) * (z.abs() >= 1)).shift(1)
pos_b = -np.sign(u - med).shift(1)
d = pd.DataFrame({"pos_A": pos_a, "CN_IN": j.CN_IN, "cost": cost})
d["A_gross"] = pos_a * j.CN_IN
d["A_net"] = d.A_gross - pos_a.abs() * cost
d["base_net"] = pos_b * j.CN_IN - pos_b.abs() * cost
d = d.loc[START:].dropna(subset=["pos_A", "CN_IN"])
d[["A_gross", "A_net", "base_net"]] = d[["A_gross", "A_net", "base_net"]].fillna(0)
d.to_csv(TAB / "soy_ruleA_daily.csv")
# buy & hold the underlying: long DCE soybean main contract, close-to-close on the DCE calendar.
# Roll days (contract switch in the Sina series) are set to 0 ~ a roll-adjusted hold; no costs.
bh = cnr["D"].loc[d.index[0]:end].fillna(0)


def summary(p, pos):
    trades = p[pos != 0]
    t = sm.OLS(trades.values, np.ones(len(trades))).fit(cov_type="HAC", cov_kwds={"maxlags": 5}).tvalues[0]
    yrs = (p.index[-1] - p.index[0]).days / 365.25
    eq = p.cumsum()
    return dict(trades=len(trades), per_year=len(trades) / yrs, bp_trade=1e4 * trades.mean(), t=t,
                hit=(trades > 0).mean(), ann_bp=1e4 * p.sum() / yrs,
                sharpe=p.mean() / p.std() * np.sqrt(len(p) / yrs), maxdd_bp=1e4 * (eq - eq.cummax()).min())


S = {"A": summary(d.A_net, d.pos_A), "base": summary(d.base_net, d.base_net.where(d.base_net == 0, 1)),
     "bh": summary(bh, pd.Series(1, index=bh.index))}
for k, v in S.items():
    print(k, {a: round(b, 2) for a, b in v.items()})
yearly = d.groupby(d.index.year).agg(trades=("pos_A", lambda x: int((x != 0).sum())),
                                     ruleA_net_pct=("A_net", lambda x: 100 * x.sum()),
                                     baseline_net_pct=("base_net", lambda x: 100 * x.sum()))
yearly["buyhold_pct"] = 100 * bh.groupby(bh.index.year).sum()
print(yearly.round(1).to_string())

THEMES = {
    "light": dict(surf="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#8f8e8a", grid="#e4e3df",
                  s1="#2a78d6", s2="#eb6834", s3="#1baf7a", dd="#e34948"),
    "dark": dict(surf="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#8f8e8a", grid="#383835",
                 s1="#3987e5", s2="#d95926", s3="#199e70", dd="#e66767"),
}
for theme, t in THEMES.items():
    plt.rcParams.update({"figure.facecolor": t["surf"], "axes.facecolor": t["surf"], "savefig.facecolor": t["surf"],
                         "axes.edgecolor": t["grid"], "axes.labelcolor": t["ink2"], "xtick.color": t["ink2"],
                         "ytick.color": t["ink2"], "text.color": t["ink"], "axes.spines.top": False,
                         "axes.spines.right": False, "axes.spines.left": False, "axes.grid": True,
                         "axes.grid.axis": "y", "grid.color": t["grid"], "legend.frameon": False,
                         "font.family": "sans-serif", "xtick.labelsize": 8.5, "ytick.labelsize": 8.5})
    fig, (ax, axd) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    fig.subplots_adjust(top=0.78, bottom=0.12, left=0.08, right=0.97, hspace=0.08)
    fig.text(0.012, 0.975, "Soybean intraday fade, Rule A: trade only after a ≥1σ US move", fontsize=14,
             fontweight="bold", va="top")
    fig.text(0.012, 0.92, "DCE soybean open→close, against the prior CBOT move. Net of 2 ticks, 1× notional, cumulative % "
             f"(log).\nFrom {START:%b %Y} (after the overreaction decayed) to Dec 2014, when the DCE night session started.", fontsize=9.5,
             color=t["ink2"], va="top")
    eqA, eqB = 100 * d.A_net.cumsum(), 100 * d.base_net.cumsum()
    ax.plot(eqB.index, eqB.values, color=t["muted"], lw=1.4, label="benchmark: same fade, every day, US vs its median (net)")
    eqH = 100 * bh.cumsum()
    ax.plot(eqH.index, eqH.values, color=t["s3"], lw=1.4, label="buy & hold DCE soybeans (close-to-close, no costs)")
    ax.plot(eqA.index, eqA.values, color=t["s1"], lw=2.2, label="Rule A: |US move| ≥ 1σ (net)")
    ax.axhline(0, color=t["ink2"], lw=0.8)

    ax.set_ylabel("cumulative return, %")
    ax.legend(loc="upper left", fontsize=8.5)
    a = S["A"]
    ax.text(0.55, 0.45, f"Rule A: {a['trades']} trades ({a['per_year']:.0f}/yr) · {a['bp_trade']:+.1f} bp/trade "
            f"(t {a['t']:.1f})\nhit {100 * a['hit']:.0f}% · {a['ann_bp'] / 100:+.1f}%/yr · Sharpe {a['sharpe']:.2f} · "
            f"max DD {a['maxdd_bp'] / 100:.1f}%", transform=ax.transAxes, fontsize=8.5, color=t["ink"], va="top")
    for y, r in yearly.iterrows():
        ax.text(pd.Timestamp(f"{y}-07-01"), ax.get_ylim()[0], f"{y}: {r.ruleA_net_pct:+.1f}%", ha="center",
                va="bottom", fontsize=7.5, color=t["ink2"])
    dd = eqA - eqA.cummax()
    axd.fill_between(dd.index, dd.values, 0, color=t["dd"], alpha=0.35, lw=0)
    axd.plot(dd.index, dd.values, color=t["dd"], lw=1)
    axd.set_ylabel("drawdown, %")
    axd.xaxis.set_major_locator(mdates.YearLocator())
    axd.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axd.tick_params(axis="x", length=0)
    b, h = S["base"], S["bh"]
    fig.text(0.08, 0.012, f"Benchmark (every-day median-split fade): {b['ann_bp'] / 100:+.1f}%/yr, Sharpe {b['sharpe']:.2f}, max DD "
             f"{b['maxdd_bp'] / 100:.1f}%. Buy & hold: {h['ann_bp'] / 100:+.1f}%/yr, Sharpe {h['sharpe']:.2f}, max DD "
             f"{h['maxdd_bp'] / 100:.1f}%.\nIn-sample research result: the start date and rule were chosen after "
             "seeing this period.", fontsize=8, color=t["ink2"])
    fig.savefig(DOCS / f"6_soy_equity_{theme}.png", dpi=170)
    plt.close(fig)
print("saved")
