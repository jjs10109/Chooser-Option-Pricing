"""CSV adapter. All timestamps are UTC and represent information availability."""

from pathlib import Path
import numpy as np
import pandas as pd
from .dividends import trailing_yields


def read_csv(path, required, dates):
    df = pd.read_csv(path)
    missing = set(required) - set(df)
    if missing:
        raise ValueError(f"{path}: missing {sorted(missing)}")
    for col in dates:
        if (
            not df[col]
            .astype(str)
            .str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
            .all()
        ):
            raise ValueError(f"{path}: {col} needs explicit timezone")
        df[col] = pd.to_datetime(df[col], utc=True, errors="raise", format="ISO8601")
    return df


def load(folder):
    folder = Path(folder)
    options = read_csv(
        folder / "options.csv",
        [
            "quote_time",
            "expiry",
            "symbol",
            "strike",
            "kind",
            "style",
            "bid",
            "ask",
            "volume",
            "open_interest",
        ],
        ["quote_time", "expiry"],
    )
    if options.empty:
        raise ValueError("options.csv contains no quotes")
    stocks = read_csv(
        folder / "stocks.csv",
        ["available_at", "symbol", "spot", "feature_close"],
        ["available_at"],
    )
    macro = read_csv(
        folder / "macro.csv",
        ["available_at", "r", "vix", "term_spread"],
        ["available_at"],
    )
    div = read_csv(
        folder / "dividends.csv",
        ["symbol", "ex_date", "known_at", "amount"],
        ["ex_date", "known_at"],
    )
    if (
        stocks.duplicated(["symbol", "available_at"]).any()
        or macro.duplicated("available_at").any()
    ):
        raise ValueError("duplicate availability timestamps")
    if options.duplicated(
        ["symbol", "quote_time", "expiry", "strike", "kind", "style"]
    ).any():
        raise ValueError("duplicate contracts")
    for col in ["r", "vix", "term_spread"]:
        if not np.isfinite(macro[col]).all():
            raise ValueError("nonfinite macro data")
    stocks = stocks.sort_values(["symbol", "available_at"])
    if (stocks[["spot", "feature_close"]] <= 0).any().any():
        raise ValueError("invalid stock prices")
    # Trailing adjusted-close returns, available only at their recorded publication time.
    stocks["return_1d"] = stocks.groupby("symbol").feature_close.transform(
        lambda x: np.log(x).diff()
    )
    stocks["rv_20d"] = stocks.groupby("symbol").return_1d.transform(
        lambda x: x.rolling(20, min_periods=20).std() * np.sqrt(252)
    )
    frames = []
    for symbol, opt in options.groupby("symbol"):
        st = (
            stocks[stocks.symbol == symbol]
            .drop(columns="symbol")
            .rename(columns={"available_at": "stock_available_at"})
        )
        merged = pd.merge_asof(
            opt.sort_values("quote_time"),
            st.sort_values("stock_available_at"),
            left_on="quote_time",
            right_on="stock_available_at",
            direction="backward",
            tolerance=pd.Timedelta("4d"),
        )
        frames.append(merged)
    df = pd.concat(frames, ignore_index=True)
    macro = macro.rename(columns={"available_at": "macro_available_at"})
    df = pd.merge_asof(
        df.sort_values("quote_time"),
        macro.sort_values("macro_available_at"),
        left_on="quote_time",
        right_on="macro_available_at",
        direction="backward",
        tolerance=pd.Timedelta("7d"),
    )
    if "pricing_spot" in df:
        df["spot"] = pd.to_numeric(df["pricing_spot"], errors="coerce")
    df["q"] = trailing_yields(df, div)
    df["t"] = (df.expiry - df.quote_time).dt.total_seconds() / (365 * 86400)
    df["log_moneyness"] = np.log(df.strike / df.spot)
    df["is_put"] = (df.kind == "put").astype(int)
    df["is_american"] = (df["style"] == "american").astype(int)
    df["mid"] = (df.bid + df.ask) / 2
    return df
