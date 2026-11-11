"""Cross-market alignment following Fig. 3 of Jiang et al. (2016).

Both series are put on the joint calendar (days both markets trade). Then:
  US -> CN, lag k :  x1 = CN_{t+k}, x2 = US_t        (US day t precedes CN day t+1 by ~8h)
  CN -> US, lag k :  x1 = US_{t+k-1}, x2 = CN_t      (CN day t precedes US day t by ~6h)
cross_quantilogram(x1, x2, ., ., k) uses pairs (x1_t, x2_{t-k}); to get the CN->US
"lag 1 = same date" convention x1_t = US_{t-1}, so pair (x1_t, x2_{t-k}) = (US_{s+k-1}, CN_s).
"""
from __future__ import annotations

import pandas as pd


def joint(cn: pd.DataFrame, us: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    j = cn.add_prefix("CN_").join(us.add_prefix("US_"), how="inner")
    if start:
        j = j.loc[start:]
    if end:
        j = j.loc[:end]
    return j


def us_to_cn(j: pd.DataFrame, cn_col="CN_D", us_col="US_D"):
    """(x1, x2) arrays such that lag k = US_t -> CN_{t+k}."""
    return j[cn_col].to_numpy(), j[us_col].to_numpy()


def cn_to_us(j: pd.DataFrame, us_col="US_D", cn_col="CN_D"):
    """(x1, x2) arrays such that lag k = CN_t -> US_{t+k-1}  (lag 1 = same date)."""
    return j[us_col].shift(1).to_numpy(), j[cn_col].to_numpy()
