"""Does the China intraday reversal differ when the big US move was weather-driven?

Usage: python scripts/11_weather_ruleA.py [soybeans|corn]   (default soybeans)

Rules fixed before looking at results:
  Weather revision  dS_t = S(issued on US day t, ~3pm ET) - S(previous issuance). Public before DCE opens t+1.
  Season            primary Jun-Aug; robustness May-Sep.
  Weather-driven    in season AND sign(dS_t) == sign(US return t) AND |dS_t| >= 67th pct of in-season |dS|.
  Primary test      in-season days: CN_IN(t+1) ~ US_D(t) + US_D(t) x W(t) + W(t)   (HAC). Two-sided.
  Secondary         Rule A trades (|z| >= 1, fade at DCE open t+1, exit close) split by W, gross and net.
US returns are roll-adjusted (see the roll fix below).
Window: 2012-03 (start of the free CPC archive) -> the day before the commodity's DCE night session
(soybeans 2014-12-25, corn 2019-03-28).
Step 0 validates the index: in season, dS_t should line up with the same-day CBOT soybean return.
Outputs: output/tables/weather_ruleA_*.csv
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from src.align import joint
from src.data import CN_NIGHT_START, load

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
H = dict(cov_type="HAC", cov_kwds={"maxlags": 5})

# ------------------------------------------------------------------ data
w = pd.read_csv(ROOT / "data" / "weather" / "cpc_cornbelt_daily.csv", parse_dates=["date"]).set_index("date")
w["dS"] = w.S.diff()
w.loc[w.index.to_series().diff().dt.days > 4, "dS"] = np.nan  # no revision across archive gaps / season breaks
w["dS_610"] = w.S_610.diff()

COMM = sys.argv[1] if len(sys.argv) > 1 else "soybeans"
print(f"=== {COMM} ===")
cnr, usr, cn, us = load(COMM)
cnr = cnr[cn["volume"].reindex(cnr.index) >= 2000]
end = pd.Timestamp(CN_NIGHT_START[COMM]) - pd.Timedelta(days=1)
j = joint(cnr, usr).loc[:end]
# Roll fix: Yahoo's continuous series switches contracts on the first trading day >= 15th of each expiry month;
# on that day use the US open->close return so the contract-switch gap is not mistaken for a big US move.
EXP_MONTHS = {"corn": [3, 5, 7, 9, 12], "soybeans": [1, 3, 5, 7, 8, 9, 11]}[COMM]
_sw = pd.Series(False, index=us.index)
for (_y, _m), _g in pd.Series(us.index, index=us.index).groupby([us.index.year, us.index.month]):
    if _m in EXP_MONTHS and (_g.dt.day >= 15).any():
        _sw.loc[_g[_g.dt.day >= 15].iloc[0]] = True
_oc = np.log(us.close / us.open)
u = j.US_D.where(~_sw.reindex(j.index, fill_value=False), _oc.reindex(j.index))
z = u / u.rolling(60, min_periods=40).std().shift(1)
# US-day frame: row t = US day t; the trade happens on the next joint row (CN day t+1)
d = pd.DataFrame({"US_D": u, "z": z, "next_IN": j.CN_IN.shift(-1),
                  "next_cost": (2 / cn["open"].reindex(j.index)).shift(-1)})
d = d.join(w[["S", "dS", "dS_610"]], how="left").loc["2012-03-01":]
d["m"] = d.index.month

# ------------------------------------------------------------------ step 0: does the index carry weather news?
print(f"STEP 0  validation: same-day US {COMM} return ~ forecast revision dS (issued that afternoon)")
val = []
for lab, months in (("Jun-Aug", [6, 7, 8]), ("May-Sep", [5, 6, 7, 8, 9]), ("Mar-Apr + Oct (off-season)", [3, 4, 10])):
    g = d[d.m.isin(months)].dropna(subset=["dS", "US_D"])
    f = sm.OLS(g.US_D, sm.add_constant(g.dS)).fit(**H)
    val.append(dict(season=lab, n=len(g), corr=g.US_D.corr(g.dS), slope=f.params.iloc[1], t=f.tvalues.iloc[1]))
val = pd.DataFrame(val)
print(val.round(3).to_string(index=False))
val.to_csv(TAB / f"weather_{COMM}_validation.csv", index=False)

# ------------------------------------------------------------------ labels
def label(df, months, q=2 / 3, col="dS"):
    ins = df.m.isin(months) & df[col].notna()
    thr = df.loc[ins, col].abs().quantile(q)
    W = ins & (np.sign(df[col]) == np.sign(df.US_D)) & (df[col].abs() >= thr)
    return W.astype(float).where(ins), thr


def primary(df, months, q=2 / 3, col="dS"):
    W, thr = label(df, months, q, col)
    g = df.assign(W=W).dropna(subset=["W", "US_D", "next_IN"])
    X = sm.add_constant(pd.DataFrame({"US_D": g.US_D, "US_DxW": g.US_D * g.W, "W": g.W}))
    f = sm.OLS(g.next_IN, X).fit(**H)
    return dict(n=len(g), n_weather=int(g.W.sum()), thr=thr,
                slope_nonweather=f.params["US_D"], t_nonweather=f.tvalues["US_D"],
                diff_weather=f.params["US_DxW"], t_diff=f.tvalues["US_DxW"],
                slope_weather=f.params["US_D"] + f.params["US_DxW"])


def trades(df, months, q=2 / 3, col="dS"):
    W, _ = label(df, months, q, col)
    g = df.assign(W=W)
    big = g[(g.z.abs() >= 1) & g.next_IN.notna() & g.W.notna()]
    pos = -np.sign(big.z)
    big = big.assign(gross=pos * big.next_IN, net=pos * big.next_IN - big.next_cost)
    rows = {}
    for lab, s in (("weather-driven", big[big.W == 1]), ("not weather-driven", big[big.W == 0])):
        rows[lab] = dict(n=len(s), gross_bp=1e4 * s.gross.mean(), net_bp=1e4 * s.net.mean(),
                         t_gross=s.gross.mean() / s.gross.std() * np.sqrt(len(s)) if len(s) > 2 else np.nan,
                         hit=(s.net > 0).mean())
    a, b = big[big.W == 1].gross, big[big.W == 0].gross
    p = stats.ttest_ind(a, b, equal_var=False).pvalue if len(a) > 2 and len(b) > 2 else np.nan
    return rows, p


print("\nPRIMARY  in-season days: CN intraday(t+1) ~ US move(t), and how much it changes on weather-driven days")
prim = []
for lab, months, q, col in (("Jun-Aug, top third (primary)", [6, 7, 8], 2 / 3, "dS"),
                            ("May-Sep, top third", [5, 6, 7, 8, 9], 2 / 3, "dS"),
                            ("Jun-Aug, top half", [6, 7, 8], 0.5, "dS"),
                            ("Jun-Aug, top 20%", [6, 7, 8], 0.8, "dS"),
                            ("Jun-Aug, 6-10 day only", [6, 7, 8], 2 / 3, "dS_610")):
    prim.append(dict(spec=lab, **primary(d, months, q, col)))
prim = pd.DataFrame(prim)
print(prim.round(4).to_string(index=False))
prim.to_csv(TAB / f"weather_{COMM}_primary.csv", index=False)

print("\nSECONDARY  Rule A trades (|z|>=1, fade), split by label")
sec = []
for lab, months, q, col in (("Jun-Aug, top third (primary)", [6, 7, 8], 2 / 3, "dS"),
                            ("May-Sep, top third", [5, 6, 7, 8, 9], 2 / 3, "dS")):
    rows, p = trades(d, months, q, col)
    for k, v in rows.items():
        sec.append(dict(spec=lab, group=k, **v, p_diff_gross=p))
sec = pd.DataFrame(sec)
print(sec.round(3).to_string(index=False))
sec.to_csv(TAB / f"weather_{COMM}_trades.csv", index=False)

# context: all Rule A trades in the window, by season
big = d[(d.z.abs() >= 1) & d.next_IN.notna()]
pos = -np.sign(big.z)
big = big.assign(net=pos * big.next_IN - big.next_cost, gross=pos * big.next_IN,
                 season=np.where(big.m.isin([6, 7, 8]), "Jun-Aug", "other months"))
print("\nCONTEXT  all Rule A trades in the window, by season")
print(big.groupby("season").agg(n=("net", "size"), gross_bp=("gross", lambda x: 1e4 * x.mean()),
                                net_bp=("net", lambda x: 1e4 * x.mean())).round(1).to_string())
