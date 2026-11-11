"""Numbers transcribed from Jiang et al. (2016) Tables V and VI (lag-1 CQ, same quantile both markets)."""
ALPHAS = (0.1, 0.5, 0.9)
# TAB_V[commodity][component] = (rho@.1, rho@.5, rho@.9);  US daily -> CN component
TAB_V = {
    "soybeans": {"D": (.2292, .1680, .1969), "OV": (.4343, .4592, .3961), "IN": (.0014, -.1158, -.0210)},
    "wheat":    {"D": (.0708, .0937, .0844), "OV": (.2923, .3305, .2715), "IN": (.0013, -.0811, -.0117)},
    "corn":     {"D": (.0967, .0643, .0707), "OV": (.2826, .3456, .2392), "IN": (-.0096, -.1059, -.0317)},
    "sugar":    {"D": (.1734, .1740, .1449), "OV": (.3444, .4521, .3729), "IN": (-.0033, -.0680, -.0204)},
}
# CN daily -> US component
TAB_VI = {
    "soybeans": {"D": (.1533, .1487, .1439), "OV": (.0941, .0954, .1128), "IN": (.1315, .1285, .1159)},
    "wheat":    {"D": (.0751, .0816, .0414), "OV": (.0757, .0275, .0588), "IN": (.0621, .0643, .0414)},
    "corn":     {"D": (.0701, .1111, .0751), "OV": (.0701, .0512, .0523), "IN": (.0523, .0935, .0751)},
    "sugar":    {"D": (.1050, .0871, .0764), "OV": (.1458, .0943, .0936), "IN": (.0650, .0665, .0308)},
}
# Significance flags (False = not significant in paper)
TAB_V_NS = {("soybeans", "IN", .1), ("soybeans", "IN", .9), ("wheat", "IN", .1), ("wheat", "IN", .9),
            ("corn", "IN", .1), ("corn", "IN", .9), ("sugar", "IN", .1), ("sugar", "IN", .9)}
TAB_VI_NS = {("wheat", "D", .9), ("wheat", "OV", .5), ("sugar", "IN", .9)}
PAPER_N = {"soybeans": 3566, "wheat": 2552, "corn": 2504, "sugar": 1943}
