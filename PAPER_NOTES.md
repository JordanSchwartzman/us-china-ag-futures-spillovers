# Jiang, Su, Todorova & Roca (2016): "Spillovers and Directional Predictability with a Cross-Quantilogram Analysis: The Case of U.S. and Chinese Agricultural Futures"
*Journal of Futures Markets* 36(12):1231–1255. DOI 10.1002/fut.21779

## 1. Page-by-page

| pp. | Section | What's there |
|---|---|---|
| 1231–33 | Abstract / Intro | Daily, overnight, intraday and rolling return spillovers between US (CBOT, ICE) and Chinese (DCE, ZCE) futures for soybeans, wheat, corn, sugar. Three contributions: (1) first application of the Han-Linton-Oka-Whang (2014) cross-quantilogram to commodities; (2) splits close-to-close returns into overnight (close→open) and intraday (open→close), adjusting for non-overlapping hours; (3) auto-quantilograms (are returns driven by self or by the other market?) plus a rolling 2-year cross-quantilogram. |
| 1233–34 | §2 Literature | Most prior work is *volatility* spillover (MGARCH, VAR, VECM, BEKK, wavelets). It mostly finds the US leads China. For stocks, lagged US returns predict foreign markets (Rapach et al. 2013; Ye 2014). |
| 1234–37 | §3 Background | Fig 1: consumption, with China the #1 consumer of soy and wheat. Tab I: CN imports over 60% of its soy (most from the US). Tab II: US share of CN imports is soy 42%, wheat 29%, corn 84%, sugar ~0%. Over 70% of US futures participants are institutional, while over 90% of CN participants are individuals. Fig 2: prices co-move. **Hypothesis:** a stronger daily spillover US→CN than CN→US. |
| 1238–39 | §4.1 Method | Cross-quantilogram, Eq 1–2; portmanteau Q, Eq 3; stationary bootstrap CIs (details below). |
| 1239–42 | §4.2 Data | Beijing Bric Agricultural Info; daily open and close of continuous front contracts, rolled in the month before expiry; zero/missing prices deleted; log returns, both markets open (Tab III). Fig 3 timing. Eq 5 decomposition. Tab IV descriptive statistics. |
| 1243–45 | §5.1 Bilateral | Figs 4/5: lags 1–20, α ∈ {.1,.5,.9}, same quantile in both markets. Lag 1 is significant in both directions and nothing after it. US→CN is stronger, mainly soy and sugar. |
| 1245–47 | §5.2 Auto-QL | Figs 6/7. US auto-quantilogram ≈ 0. CN has a small negative lag-1 value at the median. So the predictability comes from the *other* market. |
| 1247–50 | §5.3 Decomposition | Tab V (US→CN): the CN **overnight** CQ is about 2× daily; CN intraday is ≈0 or significantly **negative** at the median (reversal). Tab VI (CN→US): mixed; for soy the US intraday leg dominates. |
| 1250–53 | §5.4 Rolling, §5.5 Discussion | Figs 8–11: 2-year windows rolled yearly. The effect is strongest in the GFC, especially the lower tail. Explanation: CN retail investors react to US information; the intraday reversal corrects overreaction at the open. |
| 1253–55 | §6 Conclusion, refs | Short-lived (1-day) bi-directional dependence, stronger US→CN, carried by the CN overnight return. |

## 2. What is tested
H0 for each commodity, direction, quantile pair α=(α1,α2) and lag k: **ρ_α(k)=0**. That is, whether one market is above or below its α2-quantile at t−k does *not* help predict whether the other market is above or below its α1-quantile at t. The portmanteau test covers k=1..p jointly (p=20). It is directional, quantile-specific, and nonparametric (it uses only the hit processes).

## 3. How it is tested
- ψ_a(u) = 1[u<0] − a. q̂_i(α_i) = unconditional sample quantile.
- **Eq 2:** ρ̂_α(k) = Σ_{t=k+1}^T ψ_{α1}(x1_t − q̂1) ψ_{α2}(x2_{t−k} − q̂2) / sqrt(Σψ²_{α1} · Σψ²_{α2})
- **Eq 3:** Q̂^(p) = T(T+2) Σ_{k=1}^p ρ̂²(k) / (T−k)
- **Inference:** Politis-Romano stationary bootstrap of the pairs {(x1_t, x2_{t−k})}. Block lengths are geometric with mean 1/γ, γ chosen by the Patton-Politis-White (2009) rule. Wrap-around is circular. B=1000. The 95% CI "for no predictability" is centered at 0, i.e. the quantiles of ρ* − ρ̂.
- **Variables:** x1 = CN, x2 = US for the US→CN direction (and swapped for CN→US).
- **Timing (Fig 3, GMT):** CN trades 01:00–07:00 and the US floor trades 13:00–17:15.
  - US→CN lag 1 = (R_US,t → R_CN,t+1)
  - CN→US lag 1 = (R_CN,t → R_US,t), i.e. the US series is shifted by one day so both directions are 12-hour impacts.
- **Eq 5:** R^D = ln(C_t/C_{t−1}) = ln(O_t/C_{t−1}) [OV] + ln(C_t/O_t) [IN].
- **Rolling:** 2-year windows, start year advanced 1 year at a time, through 2013–14.

## 4. Data
| | Paper sample | N |
|---|---|---|
| Soybeans | 1999-01-01 → 2014-08-25 | 3566 |
| Wheat | 2003-03-31 → 2014-08-25 | 2552 |
| Corn | 2003-03-31 → 2014-08-25 | 2504 |
| Sugar | 2006-01-01 → 2014-08-25 | 1943 |

CN contracts: DCE soybean No.1 (A), DCE corn (C), ZCE strong wheat (WS/WH), ZCE white sugar (SR). US contracts: CBOT soy (ZS), CBOT corn (ZC), CBOT SRW wheat (ZW), ICE sugar #11 (SB).

### Tab IV target (daily returns)
| | CN mean | CN sd | CN skew | CN kurt | US mean | US sd | US skew | US kurt |
|---|---|---|---|---|---|---|---|---|
| Soy | 0.00011 | 0.01181 | 0.296 | 5.40 | 0.00032 | 0.01687 | −0.750 | 6.37 |
| Wheat | 0.00014 | 0.01190 | 0.902 | 38.11 | −0.000002 | 0.02185 | 0.093 | 1.95 |
| Corn | 0.00008 | 0.01191 | 0.142 | 38.93 | 0.00037 | 0.01921 | −0.150 | 2.95 |
| Sugar | −0.00014 | 0.01305 | −0.657 | 10.99 | 0.00006 | 0.02206 | −0.254 | 3.25 |

### Tab V target: lag-1 CQ, US daily → CN {D, OV, IN}, α_US = α_CN (* = significant at 5%)
| | α | D | OV | IN |
|---|---|---|---|---|
| Soy | .1 / .5 / .9 | .2292* / .1680* / .1969* | .4343* / .4592* / .3961* | .0014 / −.1158* / −.0210 |
| Wheat | .1 / .5 / .9 | .0708* / .0937* / .0844* | .2923* / .3305* / .2715* | .0013 / −.0811* / −.0117 |
| Corn | .1 / .5 / .9 | .0967* / .0643* / .0707* | .2826* / .3456* / .2392* | −.0096 / −.1059* / −.0317 |
| Sugar | .1 / .5 / .9 | .1734* / .1740* / .1449* | .3444* / .4521* / .3729* | −.0033 / −.0680* / −.0204 |

### Tab VI target: lag-1 CQ, CN daily → US {D, OV, IN}
| | α | D | OV | IN |
|---|---|---|---|---|
| Soy | .1 / .5 / .9 | .1533* / .1487* / .1439* | .0941* / .0954* / .1128* | .1315* / .1285* / .1159* |
| Wheat | .1 / .5 / .9 | .0751* / .0816* / .0414 | .0757* / .0275 / .0588* | .0621* / .0643* / .0414 |
| Corn | .1 / .5 / .9 | .0701* / .1111* / .0751* | .0701* / .0512* / .0523* | .0523* / .0935* / .0751* |
| Sugar | .1 / .5 / .9 | .1050* / .0871* / .0764* | .1458* / .0943* / .0936* | .0650* / .0665* / .0308 |

Null 95% bands are roughly ±0.04–0.06 throughout.

## 5. Can it be traded?
- The strongest effect (US_t → CN overnight t+1) is **not tradable from daily bars**: the US session t happens *inside* CN's close(t)→open(t+1) gap. You'd have to trade CN at 17:15 GMT, when CN is closed (pre-Dec-2014; there was no night session then).
- **T1:** CN intraday t+1 (open→close) after the US_t quantile. The paper finds this is negative at the median, a reversal of the overnight overreaction. This is tradable: the signal is known about 8h before the CN open.
- **T2:** US intraday t (day-session open→close) after the CN_t quantile. Significant for soy (~.13). Tradable in principle: CN closes 07:00 GMT, the US floor opens 13:00 GMT. It needs the true 8:30 CT day-session open, which yfinance doesn't provide.
- **After 2014:** CN night sessions (21:00 Beijing ≈ 13:00 GMT) overlap US trading hours, so the 2016-era timing structure no longer holds.
