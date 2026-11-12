"""API functions migrated from the original option_pricing.ipynb.
Original endpoints, filtering defaults and response fields are preserved.
No network request runs on import. Credentials live in ignored .env.
"""

import os
import time
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
START_DATE = "2018-01-01"
END_DATE = "2026-10-31"
OUT_DIR = "data/vendor"
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
MARKETDATA_TOKEN = os.getenv("MARKETDATA_TOKEN", "")
OPTION_URL = "https://api.marketdata.app/v1/options/chain/JPM/"


TREASURY_MATURITIES = {
    "3month": "treasury_3m",
    "2year": "treasury_2y",
    "5year": "treasury_5y",
    "7year": "treasury_7y",
    "10year": "treasury_10y",
    "30year": "treasury_30y",
}


def safe_get(*args, **kwargs):
    try:
        response = requests.get(*args, **kwargs)
    except requests.RequestException:
        raise RuntimeError(
            "Vendor connection failed; request details suppressed to protect credentials"
        ) from None
    if response.status_code not in (200, 203):
        if response.status_code == 402 and "marketdata.app" in args[0]:
            raise RuntimeError(
                "MarketData HTTP 402: requested historical date is unavailable for this account; check date range, freshness and plan"
            )
        raise RuntimeError(
            f"Vendor HTTP {response.status_code}; check credentials, plan and quota"
        )
    return response


def fetch_jpm():
    df = yf.download(
        "JPM",
        start=START_DATE,
        end=END_DATE,
        auto_adjust=False,
        progress=False,
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"

    df = df.rename(  # adj
        columns={
            "Open": "jpm_open",
            "High": "jpm_high",
            "Low": "jpm_low",
            "Close": "jpm_close",
            "Adj Close": "jpm_adj_close",
            "Volume": "jpm_volume",
        }
    )

    return df[
        [
            "jpm_open",
            "jpm_high",
            "jpm_low",
            "jpm_close",
            "jpm_adj_close",
            "jpm_volume",
        ]
    ]


def fetch_treasury(maturity, column_name):
    response = safe_get(
        "https://www.alphavantage.co/query",
        params={
            "function": "TREASURY_YIELD",
            "interval": "daily",
            "maturity": maturity,
            "apikey": ALPHA_VANTAGE_API_KEY,
        },
        timeout=30,
    )

    js = response.json()

    # Check that the API returned data
    if "data" not in js:
        raise RuntimeError(
            "Alpha Vantage returned no Treasury data (check key, plan or rate limit)"
        )

    df = pd.DataFrame(js["data"])

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    df[column_name] = pd.to_numeric(
        df["value"],
        errors="coerce",
    )

    df = df.dropna(subset=["date"]).set_index("date")[[column_name]].sort_index()

    # Remove duplicate dates returned by the API
    df = df[~df.index.duplicated(keep="last")]

    # Use explicit boolean date filtering instead of partial string slicing
    start = pd.Timestamp(START_DATE)
    end = pd.Timestamp(END_DATE)

    df = df[(df.index >= start) & (df.index <= end)]

    return df


def fetch_all_treasury():
    data = []

    for maturity, column_name in TREASURY_MATURITIES.items():
        print(f"Fetching {maturity} Treasury yield")

        data.append(
            fetch_treasury(
                maturity=maturity,
                column_name=column_name,
            )
        )

        time.sleep(12)

    return pd.concat(data, axis=1).sort_index()


def fetch_vix():
    response = safe_get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": "VIXCLS",
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": START_DATE,
            "observation_end": END_DATE,
        },
        timeout=30,
    )

    payload = response.json()
    if "observations" not in payload:
        raise RuntimeError("FRED returned no observations (check key or quota)")
    df = pd.DataFrame(payload["observations"])

    df["date"] = pd.to_datetime(df["date"])
    df["vix"] = pd.to_numeric(
        df["value"],
        errors="coerce",
    )

    return df.set_index("date")[["vix"]]


def fetch_jpm_option_chain(date):

    params = {
        "date": date,
        "dte": 30,
        "monthly": "true",
        "strikeLimit": 5,
        "minBid": 0.05,
        "nonstandard": "false",
    }

    headers = {"Authorization": f"Bearer {MARKETDATA_TOKEN}"}

    response = safe_get(
        OPTION_URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    if response.status_code not in (200, 203):
        raise RuntimeError(
            f"MarketData HTTP {response.status_code} (check token, plan or quota)"
        )

    js = response.json()

    if js.get("s") != "ok":
        return pd.DataFrame()

    columns = [
        "optionSymbol",
        "underlying",
        "expiration",
        "side",
        "strike",
        "dte",
        "bid",
        "ask",
        "mid",
        "last",
        "volume",
        "openInterest",
        "underlyingPrice",
        "iv",
        "delta",
        "gamma",
        "theta",
        "vega",
        "updated",
    ]

    data_dict = {c: js[c] for c in columns if c in js}

    out = pd.DataFrame(data_dict)

    out["date"] = pd.to_datetime(date)

    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    jpm = fetch_jpm()
    treasury = fetch_all_treasury()
    vix = fetch_vix()

    combined = (
        jpm.join(treasury, how="left").join(vix, how="left").loc[START_DATE:END_DATE]
    )

    combined.to_csv(
        os.path.join(
            OUT_DIR,
            "jpm_treasury_vix_combined.csv",
        ),
        encoding="utf-8-sig",
    )

    print(combined.head())
    print(combined.tail())

    return combined
