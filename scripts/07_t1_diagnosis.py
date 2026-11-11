"""Why did the tradable leg (T1: fade CN intraday after the US move) lose its edge?

1. Yearly reversal slope  CN_IN(t+1) ~ US_D(t)  per commodity, pre-night-session years.
2. Pooled conditioning (vol units): US-vol regime, US-move size, US-explained vs residual gap.
3. Rule variants designed from the mechanism (A: |z|>=1, B: size ~ z, C: A + alive switch), gross/net.
4. Modern-structure pilot (night-session era): US move after CN night close (15:00 UTC -> US close)
   vs CN 09:00 day-session open gap and 09:00->15:00 return. Free data: ~8 months of CN 60m bars.

Outputs: output/tables/t1_*.csv, docs/figures/5_t1_decay_{light,dark}.png
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.align import joint
from src.data import CN_NIGHT_START, load

ROOT = Path(__file__).resolve().parents[1]
TAB, DOCS, INTRA = ROOT / "output" / "tables", ROOT / "docs" / "figures", ROOT / "data" / "intraday"
INTRA.mkdir(parents=True, exist_ok=True)
H = dict(cov_type="HAC", cov_kwds={"maxlags": 5})
COMMS = ["soybeans", "wheat", "corn", "sugar"]


def prenight(c):
    cnr, usr, cn, _ = load(c)
    cnr = cnr[cn["volume"].reindex(cnr.index) >= 2000]
    end = CN_NIGHT_START[c]
    j = joint(cnr, usr).loc[: pd.Timestamp(end) - pd.Timedelta(days=1) if end else None].copy()
    return j, cn


def tstat_mean(p):
    p = p.dropna()
    p = p[p != 0]
    return sm.OLS(p.values, np.ones(len(p))).fit(**H).tvalues[0], p


# ------------------------------------------------------------------ 1. yearly slopes
yearly = []
for c in COMMS:
    j, _ = prenight(c)
    j["US_prev"] = j.US_D.shift(1)
    k = j.dropna(subset=["US_prev", "CN_IN", "CN_OV"])
    for y, g in k.groupby(k.index.year):
        if len(g) < 100:
            continue
        X = sm.add_constant(g.US_prev)
        f = sm.OLS(g.CN_IN, X).fit(**H)
        po = sm.OLS(g.CN_OV, X).fit(**H)
        yearly.append(dict(commodity=c, year=y, n=len(g), slope=f.params.iloc[1], se=f.bse.iloc[1],
                           t=f.tvalues.iloc[1], passthru=po.params.iloc[1],
                           reversal_share=f.params.iloc[1] / po.params.iloc[1]))
yearly = pd.DataFrame(yearly)
yearly.to_csv(TAB / "t1_yearly_reversal.csv", index=False)

# ------------------------------------------------------------------ 2. pooled conditioning
frames = []
for c in COMMS:
    j, _ = prenight(c)
    j["usvol"] = j.US_D.rolling(60, min_periods=40).std().shift(2)  # through US day t-1
    j["usvol_rank"] = j.usvol.expanding(120).rank(pct=True)
    j["z"] = j.US_D.shift(1) / j.usvol
    j["cnvol"] = j.CN_D.rolling(60, min_periods=40).std().shift(1)
    j["IN_n"], j["OV_n"] = j.CN_IN / j.cnvol, j.CN_OV / j.cnvol
    frames.append(j.dropna(subset=["CN_IN", "CN_OV", "usvol_rank", "z", "cnvol"]))
P = pd.concat(frames).sort_index()
cond = []
for era, g in (("2006-09", P.loc["2006":"2009"]), ("2010-night", P.loc["2010":])):
    def sl(m, label):
        f = sm.OLS(g[m].IN_n, sm.add_constant(g[m].z)).fit(**H)
        cond.append(dict(era=era, subset=label, slope=f.params.iloc[1], t=f.tvalues.iloc[1], n=int(m.sum())))
    sl(g.z.notna(), "all")
    sl(g.usvol_rank < 1 / 3, "US vol low third")
    sl((g.usvol_rank >= 1 / 3) & (g.usvol_rank < 2 / 3), "US vol mid third")
    sl(g.usvol_rank >= 2 / 3, "US vol high third")
    gh = sm.OLS(g.OV_n, sm.add_constant(g.z)).fit()
    gg = g.assign(gap_hat=gh.fittedvalues, gap_res=gh.resid)
    m = sm.OLS(gg.IN_n, sm.add_constant(gg[["gap_hat", "gap_res"]])).fit(**H)
    cond.append(dict(era=era, subset="IN on US-explained gap", slope=m.params["gap_hat"], t=m.tvalues["gap_hat"], n=len(gg)))
    cond.append(dict(era=era, subset="IN on residual gap", slope=m.params["gap_res"], t=m.tvalues["gap_res"], n=len(gg)))
cond = pd.DataFrame(cond)
cond.to_csv(TAB / "t1_conditioning.csv", index=False)

# ------------------------------------------------------------------ 3. rule variants
rules = []
for c in COMMS:
    j, cn = prenight(c)
    u = j.US_D
    z = u / u.rolling(60, min_periods=40).std().shift(1)
    med = u.expanding(250).median()
    cost = 2 / cn["open"].reindex(j.index)
    x, y = u.shift(1), j.CN_IN
    r = lambda s: s.rolling(500, min_periods=250)
    var = r(x).var()
    b = (r(x * y).mean() - r(x).mean() * r(y).mean()) / var
    rsd = (r(y).var() - b**2 * var).clip(lower=0) ** 0.5
    alive = ((b / (rsd / np.sqrt(var * 500))) < -1.0).shift(1).astype(float)
    pos = {"base: median split": -np.sign(u - med).shift(1),
           "A: |z|>=1 only": (-np.sign(z) * (z.abs() >= 1)).shift(1),
           "B: size=clip(z,±2)/2": (-(z.clip(-2, 2)) / 2).shift(1),
           "C: A + alive switch": (-np.sign(z) * (z.abs() >= 1)).shift(1) * alive}
    for lab, p in pos.items():
        g, n = p * y, p * y - p.abs() * cost
        for era, s in (("2006-09", slice("2006", "2009")), ("2010-night", slice("2010", None))):
            tg, pg = tstat_mean(g.loc[s])
            tn, pn = tstat_mean(n.loc[s])
            rules.append(dict(commodity=c, rule=lab, era=era, n=len(pn), gross_bp=1e4 * pg.mean(), t_gross=tg,
                              net_bp=1e4 * pn.mean(), t_net=tn))
rules = pd.DataFrame(rules)
rules.to_csv(TAB / "t1_rule_variants.csv", index=False)

# ------------------------------------------------------------------ 4. modern-structure pilot
PAIRS = {"soybean A/ZS": ("A0", "ZS=F"), "soymeal M/ZM": ("M0", "ZM=F"), "soyoil Y/ZL": ("Y0", "ZL=F"),
         "corn C/ZC": ("C0", "ZC=F"), "sugar SR/SB": ("SR0", "SB=F")}


def intraday(cs, ut):
    fc, fu = INTRA / f"cn_{cs}_60m.parquet", INTRA / f"us_{ut.replace('=', '_')}_60m.parquet"
    if not fc.exists():
        import akshare as ak
        c = ak.futures_zh_minute_sina(symbol=cs, period="60")
        c["dt"] = pd.to_datetime(c.datetime)
        c[["open", "close"]] = c[["open", "close"]].astype(float)
        c.to_parquet(fc)
    if not fu.exists():
        import yfinance as yf
        u = yf.download(ut, period="730d", interval="60m", progress=False, multi_level_index=False, auto_adjust=False)
        u.index = u.index.tz_convert("UTC")
        u.to_parquet(fu)
    return pd.read_parquet(fc), pd.read_parquet(fu)


pilot, panels = [], []
for name, (cs, ut) in PAIRS.items():
    c, u = intraday(cs, ut)
    u = u.copy()
    u["date"], u["h"] = u.index.normalize().tz_localize(None), u.index.hour
    us_late = np.log(u[u.h < 20].groupby("date").Close.last() / u[u.h == 14].groupby("date").Close.last())
    c = c.copy()
    c["d"], c["hm"] = c.dt.dt.normalize(), c.dt.dt.strftime("%H:%M")
    df = pd.DataFrame({"D_open": c[c.hm == "10:00"].set_index("d").open,
                       "D_close": c[c.hm == "15:00"].set_index("d").close}).dropna()
    nc = c[c.hm == "23:00"].set_index("d").close
    nidx = nc.index.values
    df["X"] = pd.to_datetime([nidx[nidx < d].max() if (nidx < d).any() else pd.NaT for d in df.index.values])
    df = df.dropna(subset=["X"])
    df = df[(df.index.to_series() - df.X).dt.days <= 4]
    df["gap"] = np.log(df.D_open / nc.reindex(df.X).values)
    df["IN"] = np.log(df.D_close / df.D_open)
    df["US_late"] = us_late.reindex(df.X).values
    df = df.dropna()
    pt = sm.OLS(df.gap, sm.add_constant(df.US_late)).fit(**H)
    rv = sm.OLS(df.IN, sm.add_constant(df.US_late)).fit(**H)
    pilot.append(dict(pair=name, n=len(df), start=df.index[0].date(), end=df.index[-1].date(),
                      passthru=pt.params.iloc[1], t_passthru=pt.tvalues.iloc[1],
                      IN_on_US=rv.params.iloc[1], t_IN_on_US=rv.tvalues.iloc[1]))
    panels.append(df.assign(pair=name, IN_z=df.IN / df.IN.std(), US_z=df.US_late / df.US_late.std()))
pilot = pd.DataFrame(pilot)
pilot.to_csv(TAB / "t1_modern_pilot.csv", index=False)
PP = pd.concat(panels).reset_index(names="d")
pf = sm.OLS(PP.IN_z, sm.add_constant(PP.US_z)).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(PP.d)[0]})
pooled_modern = (pf.params.iloc[1], pf.bse.iloc[1], len(PP))
# legacy pooled slope in the same standardized units (sd-of-IN on sd-of-US), for the chart
legacy_std = []
for era, g in (("2006–09", P.loc["2006":"2009"]), ("2010–night", P.loc["2010":])):
    gz = g.assign(IN_z=g.IN_n / g.IN_n.std(), US_z=g.z / g.z.std())
    f = sm.OLS(gz.IN_z, sm.add_constant(gz.US_z)).fit(**H)
    legacy_std.append((era, f.params.iloc[1], f.bse.iloc[1], len(gz)))

print(yearly.pivot(index="year", columns="commodity", values="slope").round(3).to_string())
print("\n", cond.round(3).to_string(index=False))
print("\n", rules.round(2).to_string(index=False))
print("\n", pilot.round(3).to_string(index=False))
print(f"\npooled modern slope (std units) {pooled_modern[0]:+.3f} ± {1.96 * pooled_modern[1]:.3f} n={pooled_modern[2]}")
print("legacy pooled (std units):", [(e, round(s, 3), round(1.96 * se, 3)) for e, s, se, _ in legacy_std])

# ------------------------------------------------------------------ chart
THEMES = {
    "light": dict(surf="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#8f8e8a", grid="#e4e3df",
                  cols=["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"]),
    "dark": dict(surf="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#8f8e8a", grid="#383835",
                 cols=["#3987e5", "#d95926", "#199e70", "#9085e9"]),
}
for theme, t in THEMES.items():
    plt.rcParams.update({"figure.facecolor": t["surf"], "axes.facecolor": t["surf"], "savefig.facecolor": t["surf"],
                         "axes.edgecolor": t["grid"], "axes.labelcolor": t["ink2"], "xtick.color": t["ink2"],
                         "ytick.color": t["ink2"], "text.color": t["ink"], "axes.spines.top": False,
                         "axes.spines.right": False, "axes.spines.left": False, "axes.grid": True,
                         "axes.grid.axis": "y", "grid.color": t["grid"], "legend.frameon": False,
                         "font.family": "sans-serif", "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlelocation": "left", "xtick.labelsize": 8.5, "ytick.labelsize": 8.5})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [2.3, 1]})
    fig.subplots_adjust(top=0.76, bottom=0.17, left=0.06, right=0.99, wspace=0.18)
    fig.text(0.012, 0.975, "Why the intraday fade died: China's open stopped overreacting around 2010",
             fontsize=14, fontweight="bold", va="top")
    fig.text(0.012, 0.915, "Slope of CN day-session return on the prior US move. Negative = CN open overshoots, "
             "then reverses (the edge). 0 = priced correctly.", fontsize=9.5, color=t["ink2"], va="top")
    for col, c in zip(t["cols"], COMMS):
        s = yearly[yearly.commodity == c]
        a1.plot(s.year, s.slope, color=col, lw=2, marker="o", ms=5, label=c, zorder=3)
    a1.axhline(0, color=t["ink2"], lw=0.8)
    a1.axvspan(2009.5, 2018.6, color=t["grid"], alpha=0.35, lw=0, zorder=0)
    a1.text(2010.0, a1.get_ylim()[0] * 0.92, "after 2010: ≈60% smaller\n(soybeans decay least)", fontsize=8,
            color=t["ink2"], va="bottom")
    a1.set_title("Pre-night-session era, by year")
    a1.set_ylabel("slope (log-return on log-return)")
    a1.legend(loc="lower right", ncol=2, fontsize=8.5)
    a1.set_xticks(range(2005, 2020, 2))
    # right: standardized pooled slopes, legacy vs modern pilot
    labs = [e for e, *_ in legacy_std] + ["2026 pilot\n(09:00 open)"]
    vals = [s for _, s, _, _ in legacy_std] + [pooled_modern[0]]
    errs = [1.96 * se for _, _, se, _ in legacy_std] + [1.96 * pooled_modern[1]]
    ns = [n for *_, n in legacy_std] + [pooled_modern[2]]
    cols = [t["cols"][0], t["cols"][0], t["cols"][1]]
    a2.errorbar(range(3), vals, yerr=errs, fmt="none", ecolor=t["muted"], elinewidth=1.4, capsize=4, zorder=2)
    a2.scatter(range(3), vals, s=60, color=cols, zorder=3, edgecolor=t["surf"], lw=1.2)
    for i, (v, n) in enumerate(zip(vals, ns)):
        a2.text(i + 0.12, v, f"{v:+.2f}\nn={n:,}", fontsize=8, color=t["ink2"], va="center")
    a2.axhline(0, color=t["ink2"], lw=0.8)
    a2.set_xticks(range(3), labs, fontsize=8.5)
    a2.set_xlim(-0.5, 2.8)
    a2.set_title("Pooled, standardized (±95% CI)")
    fig.text(0.06, 0.03, "Pilot: US move after CN night close (15:00 UTC → US close) vs CN 09:00→15:00, five DCE/ZCE–CBOT/ICE "
             "pairs, Mar–Nov 2026. The open now absorbs the US move without overshooting.", fontsize=8, color=t["ink2"])
    fig.savefig(DOCS / f"5_t1_decay_{theme}.png", dpi=170)
    plt.close(fig)
print("saved charts")
