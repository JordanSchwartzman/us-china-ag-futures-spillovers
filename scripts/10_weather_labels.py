"""Corn Belt weather-stress index from NOAA CPC 6-10 / 8-14 day outlooks (as issued), 2012-2018.

Source: https://ftp.cpc.ncep.noaa.gov/GIS/us_tempprcpfcst/  (free; archive starts in 2012)
  - Jan-Sep 2012 format: separate files <prod>abv_YYYYMMDD.zip / <prod>bel_YYYYMMDD.zip, nested probability
    contours, probability in field 'label'.
  - Later format: <prod>_YYYYMMDD.zip with fields Prob and Cat ('Above'/'Below'/'Normal').
Outlooks are issued ~3pm ET (after the CBOT close, before the DCE open), so the issue of day t is public
before China trades on day t+1.

Score at a point for one product: P = probability of the category whose highest contour contains the point;
  temp: +(P-33.3)/66.7 if Above, -(...) if Below, 0 otherwise   (hot = +)
  prcp: -(P-33.3)/66.7 if Above, +(...) if Below, 0 otherwise   (dry = +)
Stress S_t = mean over the Corn Belt points of (temp + prcp), averaged over the 6-10 and 8-14 day products.
Positive = hotter/drier than normal = bullish for soybeans.

Output: data/weather/cpc_cornbelt_daily.csv (date, S_610, S_814, S)
Downloads are cached in data/weather/cpc/. Run with: python -I scripts/10_weather_labels.py [start] [end]  (default 2012-01-01 2018-12-31)
"""
import io
import re
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import shapefile
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "weather" / "cpc"
CACHE.mkdir(parents=True, exist_ok=True)
BASE = "https://ftp.cpc.ncep.noaa.gov/GIS/us_tempprcpfcst/"
import sys
START = sys.argv[1] if len(sys.argv) > 1 else "2012-01-01"
END = sys.argv[2] if len(sys.argv) > 2 else "2018-12-31"
MONTHS = range(3, 11)  # March-October (season Jun-Aug + room for revisions and robustness)

# Corn Belt soybean points (lat, lon)
POINTS = {"Des Moines IA": (41.59, -93.62), "Springfield IL": (39.80, -89.64), "Mankato MN": (44.16, -94.00),
          "Indianapolis IN": (39.77, -86.16), "Lincoln NE": (40.81, -96.70), "Columbus OH": (39.96, -83.00),
          "Columbia MO": (38.95, -92.33), "Sioux Falls SD": (43.55, -96.73)}
PTS = {k: Point(lon, lat) for k, (lat, lon) in POINTS.items()}


def listing():
    html = urllib.request.urlopen(BASE, timeout=60).read().decode()
    return set(re.findall(r'href="([^"?/][^"]+\.zip)"', html))


def fetch(name):
    f = CACHE / name
    if f.exists() and f.stat().st_size > 500:
        return f
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(BASE + name, timeout=60).read()
            if len(data) > 500:
                f.write_bytes(data)
                return f
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def read_polys(path):
    zf = zipfile.ZipFile(path)
    shp = [n for n in zf.namelist() if n.lower().endswith(".shp")][0][:-4]
    r = shapefile.Reader(shp=io.BytesIO(zf.read(shp + ".shp")), dbf=io.BytesIO(zf.read(shp + ".dbf")))
    fields = [f[0] for f in r.fields[1:]]
    out = []
    for sr in r.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        try:
            geom = shape(sr.shape.__geo_interface__)
        except Exception:
            continue
        out.append((geom, rec))
    return out


def point_prob(polys, pt, cat=None):
    """Highest probability among polygons containing pt (optionally only those of category cat)."""
    best_p, best_cat = 0.0, None
    for geom, rec in polys:
        p = float(rec["Prob"]) if "Prob" in rec else float(str(rec.get("label", "0")).strip() or 0)
        c = rec.get("Cat", cat)
        if c not in ("Above", "Below"):
            continue
        if p > best_p and geom.contains(pt):
            best_p, best_cat = p, c
    return best_p, best_cat


def score(p, cat, kind):
    if cat is None or p <= 33.3:
        return 0.0
    s = (p - 33.3) / 66.7
    s = s if cat == "Above" else -s
    return s if kind == "temp" else -s  # prcp: Above (wet) is negative stress


def day_scores(files_for_day):
    """files_for_day: {(lead, kind): [paths...]} -> mean stress per lead"""
    res = {}
    for (lead, kind), paths in files_for_day.items():
        if len(paths) == 1:  # new format, one file with Cat
            polys = read_polys(paths[0])
            vals = [score(*point_prob(polys, pt), kind) for pt in PTS.values()]
        else:  # old format: abv + bel
            pa = read_polys(paths[0])
            pb = read_polys(paths[1])
            vals = []
            for pt in PTS.values():
                p_a, _ = point_prob(pa, pt, "Above")
                p_b, _ = point_prob(pb, pt, "Below")
                vals.append(score(p_a, "Above", kind) if p_a >= p_b else score(p_b, "Below", kind))
        res[(lead, kind)] = float(np.mean(vals))
    return res


def main():
    names = listing()
    days = [d for d in pd.date_range(START, END) if d.month in MONTHS]
    plan = {}
    for d in days:
        ds = d.strftime("%Y%m%d")
        for lead in ("610", "814"):
            for kind in ("temp", "prcp"):
                new = f"{lead}{kind}_{ds}.zip"
                old = (f"{lead}{kind}abv_{ds}.zip", f"{lead}{kind}bel_{ds}.zip")
                if new in names:
                    plan[(d, lead, kind)] = [new]
                elif old[0] in names and old[1] in names:
                    plan[(d, lead, kind)] = list(old)
    todo = sorted({n for v in plan.values() for n in v})
    print(f"{len(plan)} day-products, {len(todo)} files to fetch (cached ones skipped)")
    with ThreadPoolExecutor(max_workers=4) as ex:
        paths = dict(zip(todo, ex.map(fetch, todo)))
    rows = []
    for d in days:
        fd = {}
        for lead in ("610", "814"):
            for kind in ("temp", "prcp"):
                v = plan.get((d, lead, kind))
                if v and all(paths.get(n) for n in v):
                    fd[(lead, kind)] = [paths[n] for n in v]
        if len(fd) < 4:
            continue
        try:
            sc = day_scores(fd)
        except Exception as e:
            print("skip", d.date(), repr(e)[:80])
            continue
        s610 = sc[("610", "temp")] + sc[("610", "prcp")]
        s814 = sc[("814", "temp")] + sc[("814", "prcp")]
        rows.append(dict(date=d.date(), S_610=s610, S_814=s814, S=(s610 + s814) / 2,
                         temp_610=sc[("610", "temp")], prcp_610=sc[("610", "prcp")]))
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data" / "weather" / "cpc_cornbelt_daily.csv", index=False)
    print(f"wrote {len(out)} days: {out.date.min()} -> {out.date.max()}")
    print(out.assign(year=pd.to_datetime(out.date).dt.year).groupby("year").S.describe().round(3))


if __name__ == "__main__":
    main()
