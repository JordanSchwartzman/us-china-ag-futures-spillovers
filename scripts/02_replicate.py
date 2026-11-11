"""Replicate Jiang et al. (2016): Tab III/IV, Figs 4-7, Tab V/VI, alpha-grid (fn 9).

Usage: python scripts/02_replicate.py [--B 1000] [--end 2014-08-25] [--tag paper]
"""
import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats

from src.align import cn_to_us, joint, us_to_cn
from src.data import COMMODITIES, PAPER_END, load
from src.paper_targets import ALPHAS, PAPER_N, TAB_V, TAB_V_NS, TAB_VI, TAB_VI_NS
from src.plots import BLUE, INK2, ORANGE, cq_bars, plt
from src.quantilogram import quantilogram_test

ap = argparse.ArgumentParser()
ap.add_argument("--B", type=int, default=1000)
ap.add_argument("--start", default=None)
ap.add_argument("--end", default=PAPER_END)
ap.add_argument("--tag", default="paper")
ap.add_argument("--min_cn_volume", type=float, default=0)
ap.add_argument("--commodities", default="soybeans,wheat,corn,sugar")
args = ap.parse_args()

OUT = Path(__file__).resolve().parents[1] / "output"
FIG, TAB = OUT / "figs" / args.tag, OUT / "tables" / args.tag
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)
LAGS = range(1, 21)

data = {}
SKIP_SHORT = 300
desc_rows, samp_rows = [], []
for c, (_, _, pstart) in COMMODITIES.items():
    if c not in args.commodities.split(","):
        continue
    cnr, usr, cn_raw, _ = load(c)
    if args.min_cn_volume:
        cnr = cnr[cn_raw["volume"].reindex(cnr.index) >= args.min_cn_volume]
    j = joint(cnr, usr, start=args.start or pstart, end=args.end or None)
    if len(j) < SKIP_SHORT:
        print("skip", c, "only", len(j), "liquid joint days"); continue
    data[c] = j
    samp_rows.append({"commodity": c, "start": j.index[0].date(), "end": j.index[-1].date(), "N": len(j),
                      "paper_N": PAPER_N[c], "CN roll days dropped": int(j["CN_D"].isna().sum())})
    for m in ("CN", "US"):
        x = j[f"{m}_D"].dropna()
        desc_rows.append({"commodity": c, "market": m, "mean": x.mean(), "median": x.median(), "min": x.min(),
                          "max": x.max(), "sd": x.std(), "skew": stats.skew(x), "exkurt": stats.kurtosis(x)})
pd.DataFrame(samp_rows).to_csv(TAB / "tab3_sample.csv", index=False)
pd.DataFrame(desc_rows).to_csv(TAB / "tab4_descriptive.csv", index=False)
print(pd.DataFrame(samp_rows).to_string(index=False))
print(pd.DataFrame(desc_rows).round(5).to_string(index=False))

# ---------------------------------------------------------------- Figs 4-7 (lags 1..20)
specs = {
    "fig4_us_to_cn": ("US→CN daily spillover", lambda j: us_to_cn(j), TAB_V, "D"),
    "fig5_cn_to_us": ("CN→US daily spillover", lambda j: cn_to_us(j), TAB_VI, "D"),
    "fig6_auto_us": ("Auto-quantilogram, US", lambda j: (j["US_D"].to_numpy(), j["US_D"].to_numpy()), None, None),
    "fig7_auto_cn": ("Auto-quantilogram, CN", lambda j: (j["CN_D"].to_numpy(), j["CN_D"].to_numpy()), None, None),
}
long_rows = []
for name, (title, fn, target, comp) in specs.items():
    fig, axes = plt.subplots(len(data), 3, figsize=(10, 2.5 * len(data)), sharey=True, squeeze=False)
    for i, c in enumerate(data):
        x1, x2 = fn(data[c])
        for k, a in enumerate(ALPHAS):
            r = quantilogram_test(x1, x2, a, a, lags=LAGS, B=args.B, seed=11 * i + k)
            paper = target[c][comp][k] if target else None
            cq_bars(axes[i, k], r, f"{c}  α={a}", paper)
            for L, rho, lo, hi, s, Q, Qp in zip(r["lags"], r["rho"], r["lo"], r["hi"], r["sig"], r["Q"], r["Q_p"]):
                long_rows.append({"test": name, "commodity": c, "alpha": a, "lag": L, "rho": rho, "lo": lo,
                                  "hi": hi, "sig": s, "Q_cum": Q, "Q_p": Qp, "block_len": r["block_len"]})
    axes[0, 0].legend(loc="upper right") if target else None
    fig.suptitle(f"{title} — cross-quantilogram, lags 1–20, 95% stationary-bootstrap null band (B={args.B})",
                 fontsize=10, color=INK2)
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=140)
    plt.close(fig)
    print("saved", name)
long = pd.DataFrame(long_rows)
long.to_csv(TAB / "figs4_7_quantilograms.csv", index=False)

# ---------------------------------------------------------------- Tab V / VI (lag 1, decomposed)
rows = []
for c, j in data.items():
    for comp in ("D", "OV", "IN"):
        for k, a in enumerate(ALPHAS):
            for tab, (x1, x2), tgt, ns in (
                ("V", us_to_cn(j, cn_col=f"CN_{comp}", us_col="US_D"), TAB_V, TAB_V_NS),
                ("VI", cn_to_us(j, us_col=f"US_{comp}", cn_col="CN_D"), TAB_VI, TAB_VI_NS),
            ):
                r = quantilogram_test(x1, x2, a, a, lags=[1], B=args.B, seed=1000 + k)
                rows.append({"table": tab, "commodity": c, "component": comp, "alpha": a,
                             "rho": r["rho"][0], "lo": r["lo"][0], "hi": r["hi"][0], "sig": bool(r["sig"][0]),
                             "paper_rho": tgt[c][comp][k], "paper_sig": (c, comp, a) not in ns})
tv = pd.DataFrame(rows)
tv["diff"] = tv["rho"] - tv["paper_rho"]
tv["sign_match"] = np.sign(tv["rho"]) == np.sign(tv["paper_rho"])
tv["sig_match"] = tv["sig"] == tv["paper_sig"]
tv.to_csv(TAB / "tab5_6_decomposed.csv", index=False)
for t in ("V", "VI"):
    sub = tv[tv.table == t]
    print(f"\nTable {t}:")
    print(sub.drop(columns="table").round(4).to_string(index=False))
    print(f"  sign match {sub.sign_match.mean():.0%}  sig match {sub.sig_match.mean():.0%}  "
          f"MAE {sub['diff'].abs().mean():.3f}  corr(mine,paper) {np.corrcoef(sub.rho, sub.paper_rho)[0,1]:.3f}")

# paper-vs-mine scatter
fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
for ax, t, ttl in zip(axes, ("V", "VI"), ("Tab V: US daily → CN {D,OV,IN}", "Tab VI: CN daily → US {D,OV,IN}")):
    sub = tv[tv.table == t]
    for comp, mk in (("D", "o"), ("OV", "s"), ("IN", "^")):
        s = sub[sub.component == comp]
        ax.scatter(s.paper_rho, s.rho, marker=mk, s=36, color=BLUE if comp != "IN" else ORANGE,
                   edgecolor="white", lw=0.8, label=comp, zorder=3)
    lim = [-0.2, 0.55]
    ax.plot(lim, lim, color=INK2, lw=0.8, ls=":")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("paper lag-1 ρ"); ax.set_ylabel("replication lag-1 ρ"); ax.set_title(ttl)
    ax.legend(title="component", loc="upper left")
fig.tight_layout(); fig.savefig(FIG / "tab5_6_paper_vs_mine.png", dpi=140); plt.close(fig)

# ---------------------------------------------------------------- footnote 9: 5x5 alpha grid, lag 1
grid_a = (0.1, 0.3, 0.5, 0.7, 0.9)
fig, axes = plt.subplots(2, len(data), figsize=(3.3 * len(data), 6.4), squeeze=False)
for col, (c, j) in enumerate(data.items()):
    for row, (lab, fn) in enumerate((("US→CN", us_to_cn), ("CN→US", cn_to_us))):
        x1, x2 = fn(j)
        M = np.zeros((5, 5)); S = np.zeros((5, 5), bool)
        for a_i, a1 in enumerate(grid_a):
            for b_i, a2 in enumerate(grid_a):
                r = quantilogram_test(x1, x2, a1, a2, lags=[1], B=min(args.B, 500), seed=a_i * 5 + b_i)
                M[a_i, b_i], S[a_i, b_i] = r["rho"][0], r["sig"][0]
        ax = axes[row, col]
        im = ax.imshow(M, cmap="RdBu_r", vmin=-.3, vmax=.3, origin="lower")
        for a_i in range(5):
            for b_i in range(5):
                ax.text(b_i, a_i, f"{M[a_i,b_i]:.2f}{'*' if S[a_i,b_i] else ''}", ha="center", va="center",
                        fontsize=6.5, color="#0b0b0b")
        ax.set_xticks(range(5), grid_a); ax.set_yticks(range(5), grid_a); ax.grid(False)
        ax.set_xlabel(f"α of predictor ({lab.split('→')[0]}, day t)")
        ax.set_ylabel(f"α of target ({lab.split('→')[1]})")
        ax.set_title(f"{c}: {lab}")
fig.colorbar(im, ax=axes, shrink=0.6, label="lag-1 ρ")
fig.suptitle("Lag-1 cross-quantilogram over all quantile pairs (* = outside 95% null band)", color=INK2, fontsize=10)
fig.savefig(FIG / "fn9_alpha_grid.png", dpi=140, bbox_inches="tight"); plt.close(fig)
print("done")
