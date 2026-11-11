"""Pilot: how ZCE sugar (SR) absorbs ICE sugar #11 (SB) moves in the night-session era.

Uses free hourly bars (Sina keeps ~8 months of ZCE 60m bars; yfinance ~2 years of ICE hourly), cached in
data/intraday/ by scripts/07_t1_diagnosis.py (fetched here if missing).

Timeline per evening X (UTC): ZCE day close 07:00 -> ICE trades from ~07:30 -> ZCE night open 13:00
-> ZCE night close 15:00 -> ICE close ~17:00-18:00 -> ZCE day session next morning.

Tests
  pass-through : ZCE night-open gap      ~ ICE move from ICE open to 13:00 UTC (known at ZCE night open)
  carry        : ZCE night open -> close ~ same ICE move   (does China keep drifting with ICE?)
  overlap      : ZCE night open -> close ~ ICE 13:00->15:00 (simultaneous co-movement, not tradable)
  carry trade  : if |ICE move| >= 1 sd, go with it at ZCE night open; exit night close / next day close.
Output: output/tables/sugar_overlap_pilot.csv
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
INTRA = ROOT / "data" / "intraday"
INTRA.mkdir(parents=True, exist_ok=True)
H = dict(cov_type="HAC", cov_kwds={"maxlags": 3})

fc, fu = INTRA / "cn_SR0_60m.parquet", INTRA / "us_SB_F_60m.parquet"
if not fc.exists():
    import akshare as ak
    c = ak.futures_zh_minute_sina(symbol="SR0", period="60")
    c["dt"] = pd.to_datetime(c.datetime)
    c[["open", "close"]] = c[["open", "close"]].astype(float)
    c.to_parquet(fc)
if not fu.exists():
    import yfinance as yf
    u = yf.download("SB=F", period="730d", interval="60m", progress=False, multi_level_index=False, auto_adjust=False)
    u.index = u.index.tz_convert("UTC")
    u.to_parquet(fu)
c, u = pd.read_parquet(fc), pd.read_parquet(fu)

# ZCE bars are labeled by end time (Beijing); night bars 22:00/23:00 belong to the evening of date X
c["d"], c["hm"] = c.dt.dt.normalize(), c.dt.dt.strftime("%H:%M")
day_close = c[c.hm == "15:00"].set_index("d").close   # 15:00 Beijing = 07:00 UTC
n_open = c[c.hm == "22:00"].set_index("d").open       # 21:00 Beijing = 13:00 UTC
n_close = c[c.hm == "23:00"].set_index("d").close     # 23:00 Beijing = 15:00 UTC
d_open = c[c.hm == "10:00"].set_index("d").open       # next morning 09:00 Beijing

# ICE hourly bars are labeled by start time (UTC)
u = u.copy()
u["date"], u["h"], u["m"] = u.index.normalize().tz_localize(None), u.index.hour, u.index.minute
us_open = u.groupby("date").Open.first()                             # first ICE price after ZCE day close
us13 = u[(u.h == 12) & (u.m == 0)].groupby("date").Close.last()      # 13:00 UTC
us15 = u[(u.h == 14) & (u.m == 0)].groupby("date").Close.last()      # 15:00 UTC

df = pd.DataFrame({"cn_close": day_close, "n_open": n_open, "n_close": n_close}).dropna()
dd = d_open.index.values
df["nd"] = pd.to_datetime([dd[dd > x].min() if (dd > x).any() else pd.NaT for x in df.index.values])
df = df.dropna(subset=["nd"])
df = df[(df.nd - df.index.to_series()).dt.days <= 4]
df["next_close"] = day_close.reindex(df.nd).values
df["US_A"] = np.log(us13 / us_open).reindex(df.index).values
df["US_B"] = np.log(us15 / us13).reindex(df.index).values
df["CN_gap"] = np.log(df.n_open / df.cn_close)
df["CN_night"] = np.log(df.n_close / df.n_open)
df["CN_to_dayclose"] = np.log(df.next_close / df.n_open)
df = df.dropna(subset=["US_A", "CN_gap", "CN_night"])

rows = []


def reg(name, y, x):
    m = df[[y, x]].dropna()
    f = sm.OLS(m[y], sm.add_constant(m[x])).fit(**H)
    rows.append(dict(test=name, slope=f.params.iloc[1], t=f.tvalues.iloc[1], n=len(m)))


reg("pass-through: ZCE night-open gap ~ ICE move before it", "CN_gap", "US_A")
reg("carry: ZCE night open->night close ~ ICE move before it", "CN_night", "US_A")
reg("carry: ZCE night open->next day close ~ ICE move before it", "CN_to_dayclose", "US_A")
reg("overlap (simultaneous): ZCE night ~ ICE 13->15 UTC", "CN_night", "US_B")

z = df.US_A / df.US_A.std()
sig = np.sign(df.US_A) * (z.abs() >= 1)
for lab, y in (("carry trade |ICE|>=1sd, exit night close", "CN_night"),
               ("carry trade |ICE|>=1sd, exit next day close", "CN_to_dayclose")):
    p = (sig * df[y])[sig != 0].dropna()
    net = p - 2 / df.n_open.reindex(p.index)
    rows.append(dict(test=lab, n=len(p), gross_bp=1e4 * p.mean(), t=p.mean() / p.std() * np.sqrt(len(p)),
                     net_bp=1e4 * net.mean(), hit=(net > 0).mean()))

out = pd.DataFrame(rows)
out.to_csv(ROOT / "output" / "tables" / "sugar_overlap_pilot.csv", index=False)
print(f"nights: {len(df)}  ({df.index[0].date()} -> {df.index[-1].date()})")
print(out.round(3).to_string(index=False))
