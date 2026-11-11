"""Figs 8-11: rolling 2-year lag-1 cross-quantilogram, start year advanced by 1.

Runs through the latest data (out-of-sample after the paper's 2014-08-25 end, marked on the chart).
Usage: python scripts/03_rolling.py [--B 1000] [--window 2]
"""
import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import pandas as pd
from matplotlib.ticker import MaxNLocator

from src.align import cn_to_us, joint, us_to_cn
from src.data import COMMODITIES, load
from src.paper_targets import ALPHAS
from src.plots import BAND, BLUE, INK2, ORANGE, plt
from src.quantilogram import quantilogram_test

ap = argparse.ArgumentParser()
ap.add_argument("--B", type=int, default=1000)
ap.add_argument("--window", type=int, default=2)
ap.add_argument("--min_cn_volume", type=float, default=2000)
args = ap.parse_args()
OUT = Path(__file__).resolve().parents[1] / "output"
(OUT / "figs" / "rolling").mkdir(parents=True, exist_ok=True)

rows = []
for c, (_, _, pstart) in COMMODITIES.items():
    cnr, usr, cn, _ = load(c)
    # drop days where the CN contract is effectively untraded (matters for wheat after ~2015)
    liquid = cn["volume"].reindex(cnr.index) >= args.min_cn_volume
    cnr = cnr[liquid]
    j_all = joint(cnr, usr, start=pstart)
    y0, y1 = j_all.index[0].year, j_all.index[-1].year
    for Y in range(y0, y1 - args.window + 2):
        j = j_all.loc[f"{Y}-01-01":f"{Y + args.window - 1}-12-31"]
        if len(j) < 250:
            continue
        for lab, fn in (("US→CN", us_to_cn), ("CN→US", cn_to_us)):
            x1, x2 = fn(j)
            for k, a in enumerate(ALPHAS):
                r = quantilogram_test(x1, x2, a, a, lags=[1], B=args.B, seed=Y * 10 + k)
                rows.append({"commodity": c, "direction": lab, "start_year": Y, "alpha": a, "n": len(j),
                             "rho": r["rho"][0], "lo": r["lo"][0], "hi": r["hi"][0], "sig": bool(r["sig"][0])})
    print(c, "done", y0, y1)
df = pd.DataFrame(rows)
df.to_csv(OUT / "tables" / "rolling_lag1.csv", index=False)

for c in COMMODITIES:
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.6), sharey=True)
    for i, lab in enumerate(("US→CN", "CN→US")):
        for k, a in enumerate(ALPHAS):
            s = df[(df.commodity == c) & (df.direction == lab) & (df.alpha == a)]
            ax = axes[i, k]
            ax.fill_between(s.start_year, s.lo, s.hi, color=BAND, alpha=0.18, lw=0, label="95% null band")
            ax.plot(s.start_year, s.rho, color=BLUE, lw=2, zorder=3)
            ax.scatter(s.start_year, s.rho, s=22, zorder=4, color=[BLUE if q else "white" for q in s.sig],
                       edgecolor=BLUE, lw=1.2, label="lag-1 ρ (filled = significant)")
            ax.axvline(2013, color=ORANGE, lw=1, ls=":")
            ax.axhline(0, color=INK2, lw=0.6)
            ax.set_title(f"{lab}  α={a}")
            ax.set_xlabel("start year of 2-yr window")
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[0, 2].text(2013.2, axes[0, 2].get_ylim()[1] * 0.9, "paper sample ends", color=ORANGE, fontsize=7)
    axes[0, 0].legend(loc="lower left")
    fig.suptitle(f"Rolling {args.window}-year lag-1 cross-quantilogram — {c}", color=INK2, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "figs" / "rolling" / f"rolling_{c}.png", dpi=140)
    plt.close(fig)

summ = df.assign(era=lambda d: d.start_year.map(lambda y: "paper (≤2013)" if y <= 2013 else "OOS (≥2014)"))
print(summ.groupby(["commodity", "direction", "era"]).agg(mean_rho=("rho", "mean"), frac_sig=("sig", "mean"))
      .round(3).to_string())
