"""Explicit point-in-time feature allowlist; excludes option prices and IV."""

FEATURES = [
    "return_1d",
    "rv_20d",
    "r",
    "q",
    "vix",
    "term_spread",
    "log_moneyness",
    "t",
    "volume",
    "open_interest",
    "is_put",
    "is_american",
]

import numpy as np


def build_features(data):
    df = data.copy().sort_index()

    # ==========================================
    # Base series
    # ==========================================

    # Use adjusted close to calculate historical returns
    log_ret = np.log(df["jpm_adj_close"]).diff()

    # VIX change
    vix_change = df["vix"].pct_change(fill_method=None)

    # Treasury yield change
    treasury_10y_change = df["treasury_10y"].diff()

    # ==========================================
    # 1-3. Return Features
    # ==========================================

    # One-day return
    df["ret_1d"] = df["jpm_adj_close"].pct_change(1, fill_method=None)

    # Five-day cumulative return
    df["ret_5d"] = df["jpm_adj_close"].pct_change(5, fill_method=None)

    # Twenty-day cumulative return
    df["ret_20d"] = df["jpm_adj_close"].pct_change(20, fill_method=None)

    # ==========================================
    # 4-5. Realized Volatility
    # ==========================================

    # Five-day annualized realized volatility
    df["rv_5d"] = log_ret.rolling(5).std() * np.sqrt(252)

    # Twenty-day annualized realized volatility
    df["rv_20d"] = log_ret.rolling(20).std() * np.sqrt(252)

    # ==========================================
    # 6. Parkinson Volatility
    # ==========================================

    # High-Low information
    hl_squared = np.log(df["jpm_high"] / df["jpm_low"]) ** 2

    df["parkinson_vol_20d"] = np.sqrt(
        (252 / (4 * np.log(2))) * hl_squared.rolling(20).mean()
    )

    # ==========================================
    # 7. VIX
    # ==========================================

    df["vix_level"] = df["vix"]

    # ==========================================
    # 8. JPM / VIX Correlation
    # ==========================================

    df["corr_jpm_vix_20d"] = log_ret.rolling(20).corr(vix_change)

    # ==========================================
    # 9. JPM / 10Y Treasury Correlation
    # ==========================================

    df["corr_jpm_10y_20d"] = log_ret.rolling(20).corr(treasury_10y_change)

    # ==========================================
    # 10. Yield Curve
    # ==========================================

    df["term_spread_10y_3m"] = df["treasury_10y"] - df["treasury_3m"]

    return df
