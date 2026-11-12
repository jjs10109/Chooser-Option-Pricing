"""Deterministic, shareable offline sample data; never represented as market data."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from .pricing import price


def make_sample(output="data/sample"):
    p = Path(output)
    p.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=75, tz="UTC") + pd.Timedelta(hours=21)
    spots = 100 * np.exp(np.cumsum(rng.normal(0, 0.008, len(dates))))
    pd.DataFrame(
        {"available_at": dates, "symbol": "DEMO", "spot": spots, "feature_close": spots}
    ).to_csv(p / "stocks.csv", index=False)
    pd.DataFrame(
        {
            "available_at": dates - pd.Timedelta(hours=1),
            "r": 0.04,
            "vix": 20.0,
            "term_spread": -0.005,
        }
    ).to_csv(p / "macro.csv", index=False)
    pd.DataFrame(columns=["symbol", "ex_date", "known_at", "amount"]).to_csv(
        p / "dividends.csv", index=False
    )
    rows = []
    expiry = dates[-1] + pd.Timedelta(days=90)
    for date, s in zip(dates, spots):
        for k in [85, 95, 100, 105, 115]:
            t = (expiry - date).total_seconds() / (365 * 86400)
            iv = 0.22 + 0.5 * np.log(k / s) ** 2 - 0.12 * np.log(k / s)
            mid = price(s, k, t, 0.04, 0, iv, style="european")
            rows.append(
                dict(
                    quote_time=date,
                    expiry=expiry,
                    symbol="DEMO",
                    strike=k,
                    kind="call",
                    style="european",
                    bid=max(0.001, mid - 0.01),
                    ask=mid + 0.01,
                    volume=100,
                    open_interest=1000,
                )
            )
    pd.DataFrame(rows).to_csv(p / "options.csv", index=False)
    (p / "provenance.json").write_text(
        json.dumps(
            {
                "dataset_kind": "synthetic demonstration; not market observations",
                "seed": 42,
                "generator": "BSM European quotes with prescribed smile",
                "sources": [],
                "requested_through": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return p
