"""Fetch + cache raw data; print coverage and roll diagnostics."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from src.data import COMMODITIES, load, cn_roll_days

for c in COMMODITIES:
    cnr, usr, cn, us = load(c, refresh="--refresh" in sys.argv)
    roll = cn_roll_days(cn)
    rr = np.log(cn.close / cn.close.shift())
    print(f"{c:9s} CN {cn.index[0].date()}..{cn.index[-1].date()} n={len(cn)}  US {us.index[0].date()}..{us.index[-1].date()} n={len(us)}")
    print(f"{'':9s} CN roll days/yr={roll.sum()/(len(cn)/245):.1f}  |r| on roll days median={rr[roll].abs().median():.4f} vs other={rr[~roll].abs().median():.4f}"
          f"  CN zero-return frac={(rr==0).mean():.3f}")
