import unittest
from unittest.mock import patch, Mock
import pandas as pd
from option_iv import original_api as api
from option_iv.collect import normalize_chain


class AdapterTests(unittest.TestCase):
    def test_original_chain_parameters(self):
        response = Mock(status_code=203)
        response.json.return_value = {
            "s": "ok",
            "optionSymbol": ["X"],
            "side": ["call"],
            "strike": [100],
            "iv": [0.3],
        }
        with patch.object(api.requests, "get", return_value=response) as get:
            result = api.fetch_jpm_option_chain("2025-09-15")
        self.assertEqual(
            get.call_args.kwargs["params"],
            {
                "date": "2025-09-15",
                "dte": 30,
                "monthly": "true",
                "strikeLimit": 5,
                "minBid": 0.05,
                "nonstandard": "false",
            },
        )
        self.assertIn("iv", result)

    def test_normalization_and_stale_quote(self):
        updated = int(pd.Timestamp("2025-09-15T20:00:00Z").timestamp())
        expiry = int(pd.Timestamp("2025-10-17T00:00:00Z").timestamp())
        frame = pd.DataFrame(
            {
                "updated": [updated],
                "expiration": [expiry],
                "side": ["call"],
                "strike": [100],
                "bid": [2],
                "ask": [3],
                "volume": [5],
                "openInterest": [10],
                "underlyingPrice": [101],
            }
        )
        out = normalize_chain(frame, "2025-09-15")
        self.assertEqual(out.expiry.iloc[0], pd.Timestamp("2025-10-17T20:00:00Z"))
        self.assertEqual(out.pricing_spot.iloc[0], 101)
        self.assertNotIn("iv", out)
        self.assertTrue(normalize_chain(frame, "2025-09-16").empty)

    def test_errors_do_not_expose_credentials(self):
        import requests

        with patch.object(
            api.requests, "get", side_effect=requests.ConnectionError("secret-url")
        ):
            with self.assertRaises(RuntimeError) as error:
                api.fetch_vix()
        self.assertNotIn("secret-url", str(error.exception))

    def test_collector_roundtrip(self):
        import tempfile
        from pathlib import Path
        from option_iv.collect import collect
        from option_iv.data import load

        dates = pd.bdate_range("2026-08-01", "2026-10-30")
        stock = pd.DataFrame(
            {
                "jpm_close": 100.0,
                "jpm_adj_close": [100 + i * 0.1 for i in range(len(dates))],
                "jpm_high": 102.0,
                "jpm_low": 98.0,
            },
            index=dates,
        )

        def treasury(maturity, col):
            return pd.DataFrame({col: 4.0}, index=dates)

        def chain(date):
            return pd.DataFrame(
                {
                    "updated": [pd.Timestamp(date + "T20:00:00Z").timestamp()],
                    "expiration": [pd.Timestamp("2026-12-18T00:00:00Z").timestamp()],
                    "side": ["call"],
                    "strike": [100],
                    "bid": [4],
                    "ask": [4.2],
                    "volume": [10],
                    "openInterest": [100],
                    "underlyingPrice": [110.0],
                }
            )

        ticker = Mock()
        ticker.history.return_value = pd.DataFrame(
            {"Dividends": [0.0] * len(dates)},
            index=dates.tz_localize("America/New_York"),
        )
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(api, "fetch_jpm", return_value=stock),
            patch.object(api, "fetch_treasury", side_effect=treasury),
            patch.object(
                api, "fetch_vix", return_value=pd.DataFrame({"vix": 20.0}, index=dates)
            ),
            patch.object(api, "fetch_jpm_option_chain", side_effect=chain),
            patch("option_iv.collect.yf.Ticker", return_value=ticker),
            patch.object(api, "START_DATE"),
            patch.object(api, "END_DATE"),
            patch.object(api, "ALPHA_VANTAGE_API_KEY", "test"),
            patch.object(api, "FRED_API_KEY", "test"),
            patch.object(api, "MARKETDATA_TOKEN", "test"),
        ):
            folder = collect(
                "2026-10-01",
                "2026-10-30",
                Path(temp) / "raw",
                Path(temp) / "cache",
                pause=0,
            )
            df = load(folder)
            self.assertTrue((df.spot == 110).all())
            self.assertTrue((df.stock_available_at < df.quote_time).all())
            self.assertTrue((df.macro_available_at < df.quote_time).all())
            self.assertIn("ret_5d", df)
