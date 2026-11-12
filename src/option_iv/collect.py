"""Original vendor APIs -> cached raw responses -> IV pipeline CSVs.
python -m option_iv.collect --start 2025-09-01 --end 2025-09-30
"""

import argparse
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from . import original_api as api


def next_day_available(index):
    # Conservative end-of-following-day assumption, not verified release timing.
    return pd.DatetimeIndex(pd.to_datetime(index)).tz_localize(None).tz_localize(
        "UTC"
    ) + pd.Timedelta(days=1, hours=23, minutes=59)


def normalize_chain(chain, date):
    if chain.empty:
        return pd.DataFrame()
    needed = {
        "updated",
        "expiration",
        "side",
        "strike",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "underlyingPrice",
    }
    if needed - set(chain):
        raise ValueError("MarketData response missing required fields")
    out = chain.rename(columns={"side": "kind", "openInterest": "open_interest"}).copy()
    out["quote_time"] = pd.to_datetime(out.updated, unit="s", utc=True)
    # Vendor expiry is a Unix date; interpret date as US equity close, with DST.
    expiry_dates = pd.to_datetime(out.expiration, unit="s", utc=True).dt.strftime(
        "%Y-%m-%d"
    )
    out["expiry"] = (
        (pd.to_datetime(expiry_dates) + pd.Timedelta(hours=16))
        .dt.tz_localize("America/New_York")
        .dt.tz_convert("UTC")
    )
    session = out.quote_time.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    out = out[session == date].copy()
    out["symbol"] = "JPM"
    out["style"] = "american"
    # Use the underlying mark supplied alongside the option, rather than stale daily close.
    out["pricing_spot"] = pd.to_numeric(out.underlyingPrice, errors="coerce")
    return out[
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
            "pricing_spot",
        ]
    ]


def collect(
    start, end, output="data/market", cache="data/vendor", pause=12.0, refresh=False
):
    now = datetime.now(ZoneInfo("America/New_York"))
    if pd.Timestamp(end).date() > now.date():
        raise ValueError("end cannot be after today in New York")
    if pd.Timestamp(end) < pd.Timestamp(start):
        raise ValueError("end before start")
    for name in ["ALPHA_VANTAGE_API_KEY", "FRED_API_KEY", "MARKETDATA_TOKEN"]:
        if not getattr(api, name):
            raise ValueError(f"Missing {name} in local .env")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    raw = Path(cache)
    raw.mkdir(parents=True, exist_ok=True)
    api.START_DATE = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    api.END_DATE = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    def cached(name, fn):
        path = raw / f"{name}_{api.START_DATE}_{api.END_DATE}.csv"
        if path.exists() and not refresh:
            return pd.read_csv(path, index_col=0, parse_dates=True)
        print(f"Downloading {name}...", flush=True)
        data = fn()
        data.to_csv(path)
        if name.startswith("treasury_"):
            time.sleep(pause)
        return data

    stock = cached("jpm", api.fetch_jpm)
    # Daily close features cannot use an unfinished current session.
    if (now.hour, now.minute) < (16, 15):
        stock = stock[stock.index.date < now.date()]
    stock = stock[stock.index.date <= pd.Timestamp(end).date()]
    if stock.empty:
        raise ValueError("No completed stock sessions returned")
    yields = []
    for maturity, col in api.TREASURY_MATURITIES.items():
        yields.append(cached(col, lambda m=maturity, c=col: api.fetch_treasury(m, c)))
    treasury = pd.concat(yields, axis=1).sort_index()
    vix = cached("vix", api.fetch_vix)
    combined = stock.join(treasury, how="left").join(vix, how="left")
    combined.to_csv(raw / "jpm_treasury_vix_combined.csv")
    from .features import build_features

    features = build_features(combined)
    features.to_csv(raw / "original_features.csv")
    stocks = pd.DataFrame(
        {
            "available_at": next_day_available(stock.index),
            "symbol": "JPM",
            "spot": stock.jpm_close.to_numpy(),
            "feature_close": stock.jpm_adj_close.to_numpy(),
        }
    )
    # Carry original trailing stock features into the same availability-aware join.
    for col in ["ret_5d", "ret_20d", "rv_5d", "parkinson_vol_20d"]:
        stocks[col] = features[col].to_numpy()
    stocks.to_csv(out / "stocks.csv", index=False)
    # Fill only backward in observation time, then apply a conservative publication lag.
    macro = treasury.join(vix, how="outer").sort_index().ffill()
    macro = pd.DataFrame(
        {
            "available_at": next_day_available(macro.index),
            "r": np.log1p(macro.treasury_3m.to_numpy() / 100),
            "vix": macro.vix.to_numpy(),
            "term_spread": (macro.treasury_10y - macro.treasury_3m).to_numpy() / 100,
        }
    ).dropna()
    macro.to_csv(out / "macro.csv", index=False)

    def dividends():
        history = yf.Ticker("JPM").history(
            start=api.START_DATE, end=api.END_DATE, auto_adjust=False, actions=True
        )
        return history[["Dividends"]]

    div = cached("dividends", dividends)
    div = div[div.Dividends > 0]
    ex = pd.DatetimeIndex(pd.to_datetime(div.index, utc=True)).normalize()
    pd.DataFrame(
        {
            "symbol": "JPM",
            "ex_date": ex,
            "known_at": ex + pd.Timedelta(days=1),
            "amount": div.Dividends.to_numpy(),
        }
    ).to_csv(out / "dividends.csv", index=False)
    chains = []
    audit = []
    rate_limited_at = None
    # Actual stock sessions avoid weekend/holiday API calls.
    sessions = stock.loc[start:end].index
    for session in sessions:
        date = session.strftime("%Y-%m-%d")
        path = raw / f"chain_{date}.csv"
        if path.exists():
            chain = pd.read_csv(path)
        else:
            if rate_limited_at is not None:
                audit.append(
                    {
                        "date": date,
                        "vendor_rows": 0,
                        "validated_rows": 0,
                        "status": "not_requested_after_http_429",
                    }
                )
                continue
            print(f"Downloading JPM option chain {date}...", flush=True)
            try:
                chain = api.fetch_jpm_option_chain(date)
            except RuntimeError as exc:
                audit.append(
                    {
                        "date": date,
                        "vendor_rows": 0,
                        "validated_rows": 0,
                        "status": str(exc),
                    }
                )
                pd.DataFrame(audit).to_csv(out / "collection_audit.csv", index=False)
                # Preserve completed dates, and surface unavailable/plan-limited dates.
                time.sleep(pause)
                if "429" in str(exc):
                    rate_limited_at = date
                    print(
                        f"WARNING: MarketData returned HTTP 429 on {date}. No further network requests will be made; existing later-date caches will still be included.",
                        flush=True,
                    )
                continue
            if not chain.empty:
                chain.to_csv(path, index=False)
            time.sleep(pause)
        frame = normalize_chain(chain, date)
        audit.append(
            {
                "date": date,
                "vendor_rows": len(chain),
                "validated_rows": len(frame),
                "status": "ok" if not frame.empty else "empty_or_stale",
            }
        )
        pd.DataFrame(audit).to_csv(out / "collection_audit.csv", index=False)
        if not frame.empty:
            chains.append(frame)
    pd.DataFrame(audit).to_csv(out / "collection_audit.csv", index=False)
    if not chains:
        raise ValueError(
            "No dated historical chains returned; inspect vendor access and date range"
        )
    pd.concat(chains, ignore_index=True).to_csv(out / "options.csv", index=False)
    options = pd.read_csv(out / "options.csv")
    manifest = {
        "sources": ["yfinance", "Alpha Vantage", "FRED VIXCLS", "MarketData"],
        "start": start,
        "end": end,
        "requested_through": end,
        "downloaded_at": now.isoformat(),
        "timezone": "America/New_York",
        "latest_observations": {
            "stocks": str(stock.index.max().date()),
            "vix": str(vix.dropna().index.max().date()),
            **{col: str(treasury[col].dropna().index.max().date()) for col in treasury},
            "options": str(
                pd.to_datetime(options.quote_time, utc=True)
                .dt.tz_convert("America/New_York")
                .max()
                .date()
            ),
            "last_paid_dividend": str(ex.max().date()) if len(ex) else None,
        },
        "download_status": (
            "incomplete_rate_limited"
            if rate_limited_at
            else (
                "complete"
                if all(item["status"] == "ok" for item in audit)
                else "incomplete_unavailable_dates"
            )
        ),
        "rate_limited_at": rate_limited_at,
        "expected_sessions": len(sessions),
        "missing_sessions": sum(item["status"] != "ok" for item in audit),
        "option_rows": len(options),
        "option_sessions": int(options.quote_time.nunique()),
        "macro_timing": "assumed end of following day; not certified point-in-time vintages",
        "stock_timing": "prior session features; chain underlying mark for pricing",
        "dividends": "paid dividends, known_at conservatively next day",
        "rate": "log1p(3m yield / 100), flat continuous-rate approximation",
        "dataset_kind": "real market data; local presentation snapshot",
        "completeness": "inspect collection_audit.csv; unavailable dates are not fabricated",
    }
    (out / "provenance.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    if manifest["download_status"] != "complete":
        print(
            f"WARNING: Download is incomplete: {manifest['option_sessions']}/{manifest['expected_sessions']} sessions, {manifest['missing_sessions']} missing. Requested through {end}; latest included quote {manifest['latest_observations']['options']}. Training will use only the available subset. See collection_audit.csv and provenance.json.",
            flush=True,
        )
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--output", default="data/market")
    p.add_argument("--pause", type=float, default=12.0)
    p.add_argument("--refresh", action="store_true")
    a = p.parse_args()
    try:
        print(collect(a.start, a.end, a.output, pause=a.pause, refresh=a.refresh))
    except Exception as exc:
        raise SystemExit(
            f"Collection failed ({type(exc).__name__}); check credentials, plan, timestamps and cached data. No keys printed."
        ) from None
