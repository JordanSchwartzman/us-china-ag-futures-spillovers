"""Render the README story charts (light + dark) into docs/figures/.

Reads the tables written by 02_replicate.py (paper + oos tags); recomputes the corn T1 curve
from data (fetching it if not cached). Usage: python scripts/06_readme_figures.py
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
from matplotlib.patches import FancyBboxPatch

from src.align import joint
from src.data import load

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
DOCS = ROOT / "docs" / "figures"
DOCS.mkdir(parents=True, exist_ok=True)

THEMES = {
    "light": dict(surf="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#8f8e8a", grid="#e4e3df",
                  s1="#2a78d6", s2="#eb6834", s3="#1baf7a", neutral="#d6d5d0"),
    "dark": dict(surf="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#8f8e8a", grid="#383835",
                 s1="#3987e5", s2="#d95926", s3="#199e70", neutral="#4a4a46"),
}


def style(t):
    plt.rcParams.update({
        "figure.facecolor": t["surf"], "axes.facecolor": t["surf"], "savefig.facecolor": t["surf"],
        "axes.edgecolor": t["grid"], "axes.labelcolor": t["ink2"], "xtick.color": t["ink2"],
        "ytick.color": t["ink2"], "text.color": t["ink"], "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.labelsize": 9, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "axes.spines.top": False,
        "axes.spines.right": False, "axes.spines.left": False, "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": t["grid"], "grid.linewidth": 0.7, "axes.axisbelow": True, "legend.frameon": False,
        "legend.fontsize": 8.5, "font.family": "sans-serif", "axes.titlelocation": "left",
    })


def headline(fig, t, title, sub):
    fig.text(0.012, 0.975, title, fontsize=14, fontweight="bold", color=t["ink"], va="top")
    fig.text(0.012, 0.915, sub, fontsize=9.5, color=t["ink2"], va="top")


# ------------------------------------------------------------------ data for the charts
paper = pd.read_csv(TAB / "paper" / "tab5_6_decomposed.csv")
oos = pd.read_csv(TAB / "oos" / "tab5_6_decomposed.csv")

cnr, usr, cn, _ = load("corn")
cnr = cnr[cn["volume"].reindex(cnr.index) >= 2000]
j = joint(cnr, usr).loc[:"2019-03-28"]  # corn night session starts 2019-03-29
u = j["US_D"]
sig = -np.sign(u - u.expanding(250).median()).shift(1)
pnl = (sig * j["CN_IN"]).dropna()
pnl = pnl[pnl.index >= "2006-01-01"]
CUT = pd.Timestamp("2014-08-25")


def seg_stats(p):
    p = p[p != 0]
    t = sm.OLS(p.values, np.ones(len(p))).fit(cov_type="HAC", cov_kwds={"maxlags": 5}).tvalues[0]
    return 1e4 * p.mean(), t, len(p)


ins = seg_stats(pnl[pnl.index <= CUT])
outs = seg_stats(pnl[pnl.index > CUT])


# ------------------------------------------------------------------ 1. timing diagram
def fig_timing(t):
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.subplots_adjust(top=0.8, bottom=0.12, left=0.02, right=0.98)
    headline(fig, t, "Why the overnight effect can't be traded with daily bars",
             "Trading hours in GMT (US shown in summer time). US news lands while China is closed, so it shows up in China's next open.")
    h = 0.26

    def box(x0, x1, y, color, label, fill=True):
        ax.add_patch(FancyBboxPatch((x0, y - h / 2), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.07",
                                    fc=color if fill else "none", ec=color, lw=1.6, zorder=3))
        ax.text((x0 + x1) / 2, y, label, ha="center", va="center", fontsize=8.5, zorder=4,
                color="white" if fill else color, fontweight="bold")

    def bracket(x0, x1, y, color, label):
        ax.annotate("", xy=(x0, y), xytext=(x1, y), arrowprops=dict(arrowstyle="<->", color=color, lw=1.2))
        ax.text((x0 + x1) / 2, y - 0.07, label, ha="center", va="top", fontsize=7.8, color=color)

    eras = {"2005–2014\n(paper era)": 2.05, "2015 onward\n(night sessions)": 0.75}
    for lab, y in eras.items():
        cn_y, us_y = y, y - 0.34
        box(1, 7, cn_y, t["s1"], "China day")
        box(25, 31, cn_y, t["s1"], "China day (t+1)")
        box(13.5, 18.25, us_y, t["s2"], "US day (CBOT)")
        night = y < 1.5
        if night:
            box(13, 15, cn_y, t["s1"], "night", fill=False)
            bracket(7, 13, us_y - 0.3, t["muted"], "CN overnight return")
            bracket(13, 31, us_y - 0.3, t["s3"], "CN intraday return  (now contains the US day)")
        else:
            bracket(7, 25, us_y - 0.3, t["muted"], "CN overnight return  (contains the US day)")
            bracket(25, 31, us_y - 0.3, t["s3"], "CN intraday return")
        ax.text(-0.6, cn_y, "China", ha="right", va="center", fontsize=8, color=t["ink2"])
        ax.text(-0.6, us_y, "US", ha="right", va="center", fontsize=8, color=t["ink2"])
        ax.text(-2.6, y + 0.25, lab.replace("\n", " "), ha="left", va="center", fontsize=9.5, color=t["ink"],
                fontweight="bold")
    ax.axhline(1.2, xmin=0.0, color=t["grid"], lw=0.8)
    ax.set_yticks([])
    ax.set_xticks([1, 7, 13, 18.25, 25, 31], ["01:00", "07:00", "13:00", "18:15", "01:00\n+1d", "07:00\n+1d"])
    ax.set_xlim(-2.8, 32)
    ax.set_ylim(-0.05, 2.45)
    ax.grid(False)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    return fig


# ------------------------------------------------------------------ 2. finding + regime shift
def fig_regime(t):
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.4), sharey=True)
    fig.subplots_adjust(top=0.74, bottom=0.23, left=0.07, right=0.99, wspace=0.08)
    headline(fig, t, "US → China spillover: real, and it moved when China changed its trading hours",
             "Lag-1 cross-quantilogram at the median (US day t → CN day t+1). Hollow = not significant at 5%.")
    comps = [("OV", "Overnight"), ("D", "Daily"), ("IN", "Intraday")]
    x = np.arange(3)
    w = 0.36
    for ax, c in zip(axes, ("soybeans", "sugar", "corn")):
        for k, (df, col, lab) in enumerate(((paper, t["s1"], "2005–2014 (paper era)"),
                                            (oos, t["s2"], "2014–2026 (out of sample)"))):
            s = df[(df.table == "V") & (df.commodity == c) & (df.alpha == 0.5)].set_index("component")
            vals = [s.loc[cc, "rho"] for cc, _ in comps]
            sigs = [bool(s.loc[cc, "sig"]) for cc, _ in comps]
            xs = x + (k - 0.5) * w
            ax.bar(xs, vals, width=w * 0.9, color=[col if g else "none" for g in sigs], edgecolor=col,
                   lw=1.5, label=lab, zorder=3)
            for xi, v in zip(xs, vals):
                ax.text(xi, v + (0.012 if v >= 0 else -0.012), f"{v:+.2f}", ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=7.5, color=t["ink2"])
        ax.axhline(0, color=t["ink2"], lw=0.8)
        ax.set_xticks(x, [n for _, n in comps])
        ax.set_title(c.capitalize())
        ax.tick_params(axis="x", length=0)
    axes[0].set_ylabel("lag-1 ρ (US → CN)")
    axes[0].set_ylim(-0.22, 0.6)
    axes[0].legend(loc="upper right")
    fig.text(0.07, 0.025, "Paper era: the US move is in CN's overnight return and CN's intraday partly reverses it (−). "
             "After night sessions, the intraday share turns positive\n(soy and sugar from Dec 2014; corn's night session only began in Mar 2019, so its post-2014 bars mix both regimes).", fontsize=8.5, color=t["ink2"])
    return fig


# ------------------------------------------------------------------ 3. the trade
def fig_trade(t):
    fig, ax = plt.subplots(figsize=(10, 4.3))
    fig.subplots_adjust(top=0.76, bottom=0.16, left=0.08, right=0.98)
    headline(fig, t, "The tradable leg had an edge in-sample, then went to zero",
             "Corn: fade CN intraday (open→close, t+1) against the US move on day t. Gross of costs, 1× notional.")
    eq = pnl.cumsum()
    ax.axvspan(CUT, eq.index[-1], color=t["neutral"], alpha=0.35, lw=0, zorder=0)
    ax.plot(eq.index, eq.values, color=t["s1"], lw=2, zorder=3)
    ax.axhline(0, color=t["ink2"], lw=0.8)
    ax.axvline(CUT, color=t["ink2"], lw=0.8, ls=":")
    y_top = eq.max()
    ax.text(pd.Timestamp("2006-03-01"), y_top * 0.97,
            f"Paper era 2006–2014\n{ins[0]:.1f} bp/day, t = {ins[1]:.1f}  (n={ins[2]:,})",
            fontsize=9, color=t["ink"], va="top")
    ax.text(CUT + pd.Timedelta(days=60), y_top * 0.45,
            f"Out of sample 2014–2019\n{outs[0]:.1f} bp/day, t = {outs[1]:.2f}  (n={outs[2]:,})",
            fontsize=9, color=t["ink"], va="top", fontweight="bold")
    ax.set_ylabel("cumulative log return")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", length=0)
    fig.text(0.08, 0.015, "Corn is the clean test: no CN night session until Mar 2019, so the same trade can be run after the\n"
             "paper's data ends. Costs (≈10 bp round trip) make it negative in both periods.",
             fontsize=8, color=t["ink2"])
    return fig


# ------------------------------------------------------------------ 4. replication fidelity
def fig_fidelity(t):
    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    fig.subplots_adjust(top=0.82, bottom=0.11, left=0.13, right=0.97)
    headline(fig, t, "Replication matches the published numbers",
             "Each dot is one lag-1 cell from the paper's Tables V and VI (72 total).")
    ax.grid(True, axis="both")
    lim = (-0.2, 0.55)
    ax.plot(lim, lim, color=t["muted"], lw=1, ls="--", zorder=1)
    for tab, col, lab in (("V", t["s1"], "Table V: US → CN"), ("VI", t["s2"], "Table VI: CN → US")):
        s = paper[paper.table == tab]
        r = np.corrcoef(s.paper_rho, s.rho)[0, 1]
        ax.scatter(s.paper_rho, s.rho, s=42, color=col, edgecolor=t["surf"], lw=1.2, zorder=3,
                   label=f"{lab}  (r = {r:.2f})")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("paper's ρ (Jiang et al. 2016)")
    ax.set_ylabel("this replication's ρ")
    ax.text(0.33, 0.29, "y = x", color=t["muted"], fontsize=8, rotation=38)
    ax.legend(loc="upper left")
    return fig


FIGS = {"1_timing": fig_timing, "2_regime_shift": fig_regime, "3_trade_oos": fig_trade, "4_replication": fig_fidelity}
for theme, t in THEMES.items():
    style(t)
    for name, fn in FIGS.items():
        fig = fn(t)
        fig.savefig(DOCS / f"{name}_{theme}.png", dpi=170)
        plt.close(fig)
print("wrote", sorted(p.name for p in DOCS.glob("*.png")))
print(f"corn T1 gross: in-sample {ins[0]:.2f}bp t={ins[1]:.2f} n={ins[2]} | OOS {outs[0]:.2f}bp t={outs[1]:.2f} n={outs[2]}")
