"""Shared matplotlib style (reference palette: slot1 blue = estimate, slot2 orange = paper, gray = null band)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, BAND, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#8f8e8a", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.titlesize": 10, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "font.family": "sans-serif", "legend.frameon": False,
    "legend.fontsize": 7,
})


def cq_bars(ax, res, title, paper_lag1=None):
    lags = res["lags"]
    sig = res["sig"]
    ax.bar(lags, res["rho"], width=0.55, color=[BLUE if s else "#a9c7ec" for s in sig], zorder=3)
    ax.plot(lags, res["lo"], ls="--", lw=1, color=BAND)
    ax.plot(lags, res["hi"], ls="--", lw=1, color=BAND)
    ax.axhline(0, color=INK2, lw=0.6)
    if paper_lag1 is not None:
        ax.scatter([1], [paper_lag1], marker="D", s=26, color=ORANGE, zorder=4, label="paper lag-1")
    ax.set_title(title)
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.set_xlabel("lag (trading days)")
