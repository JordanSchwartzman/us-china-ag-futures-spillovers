"""Data fetch + cleaning for US (yfinance) and CN (Sina main-continuous via akshare) ag futures."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

COMMODITIES = {
    #           CN Sina symbol, US yfinance ticker, paper start
    "soybeans": ("A0", "ZS=F", "1999-01-01"),
    "wheat": ("WH0", "ZW=F", "2003-03-31"),
    "corn": ("C0", "ZC=F", "2003-03-31"),
    "sugar": ("SR0", "SB=F", "2006-01-01"),
}
PAPER_END = "2014-08-25"
# First CN night session per product (daily 'open' after this = 21:00 Beijing night open,
# which falls inside the US trading day -> OV/IN decomposition no longer comparable).
CN_NIGHT_START = {"soybeans": "2014-12-26", "sugar": "2014-12-12", "corn": "2019-03-29", "wheat": None}


def fetch_cn(sym: str, refresh=False) -> pd.DataFrame:
    f = RAW / f"cn_{sym}.parquet"
    if f.exists() and not refresh:
        return pd.read_parquet(f)
    import akshare as ak

    d = ak.futures_zh_daily_sina(symbol=sym)
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index().astype(float)
    d.to_parquet(f)
    return d


def fetch_us(tkr: str, refresh=False) -> pd.DataFrame:
    f = RAW / f"us_{tkr.replace('=', '_')}.parquet"
    if f.exists() and not refresh:
        return pd.read_parquet(f)
    import yfinance as yf

    d = yf.download(tkr, start="1999-01-01", auto_adjust=False, progress=False, multi_level_index=False)
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].astype(float)
    d.to_parquet(f)
    return d


def _clean(d: pd.DataFrame) -> pd.DataFrame:
    d = d[(d["open"] > 0) & (d["close"] > 0)].dropna(subset=["open", "close"])
    return d[~d.index.duplicated()]


def cn_roll_days(d: pd.DataFrame, oi_jump=0.35, limit=0.065) -> pd.Series:
    """Sina main-continuous switches (and sometimes flaps back and forth between) contracts
    without adjustment. Flag a switch when ANY of:
      * open interest of the reported contract jumps > oi_jump,
      * |close-to-close| exceeds the exchange daily price limit (~4-6% for these products),
      * a moderate OI jump (>10%) coincides with an overnight gap > 3%."""
    oi = d["hold"].replace(0, np.nan)
    j = np.log(oi / oi.shift()).abs()
    r = np.log(d["close"] / d["close"].shift()).abs()
    ov = np.log(d["open"] / d["close"].shift()).abs()
    flag = (j > np.log(1 + oi_jump)) | (r > limit) | ((j > np.log(1.10)) & (ov > 0.03))
    return flag.fillna(False)


def flap_days(d: pd.DataFrame, big=0.05) -> pd.Series:
    """Continuous-series artefact: a large move that is almost exactly reversed next day
    (series switched contract and switched back). Flags both days."""
    r = np.log(d["close"] / d["close"].shift())
    nxt = r.shift(-1)
    f = (r.abs() > big) & (nxt.abs() > 0.8 * big) & (np.sign(r) != np.sign(nxt)) & ((r + nxt).abs() < 0.35 * r.abs())
    return (f | f.shift(1, fill_value=False)).fillna(False)


def returns(d: pd.DataFrame, roll: pd.Series | None = None) -> pd.DataFrame:
    """Daily (Eq.4), overnight and intraday (Eq.5) log returns on the market's own calendar."""
    out = pd.DataFrame(index=d.index)
    out["D"] = np.log(d["close"] / d["close"].shift())
    out["OV"] = np.log(d["open"] / d["close"].shift())
    out["IN"] = np.log(d["close"] / d["open"])
    if {"high", "low"} <= set(d.columns):
        # open printed outside the day's range = bad open tick -> OV/IN unusable (D is fine)
        bad_open = (d["open"] > d["high"] * 1.0001) | (d["open"] < d["low"] * 0.9999)
        out.loc[bad_open, ["OV", "IN"]] = np.nan
    if roll is not None:
        # D and OV straddle the contract switch; IN is within one contract
        out.loc[roll.reindex(out.index, fill_value=False), ["D", "OV"]] = np.nan
    return out.iloc[1:]


def load(commodity: str, refresh=False, drop_rolls=True, min_cn_volume=0):
    """Return (cn_returns, us_returns, cn_raw, us_raw) on each market's own calendar."""
    cn_sym, us_tkr, _ = COMMODITIES[commodity]
    cn = _clean(fetch_cn(cn_sym, refresh))
    us = _clean(fetch_us(us_tkr, refresh))
    if min_cn_volume:
        cn = cn[cn["volume"] >= min_cn_volume]
    roll = (cn_roll_days(cn) | flap_days(cn)) if drop_rolls else None
    us_roll = flap_days(us) if drop_rolls else None
    return returns(cn, roll), returns(us, us_roll), cn, us
