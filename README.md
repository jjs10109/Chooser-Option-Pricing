# JPM Implied Volatility Lab

A modular **Python** research project with an offline sample and a local presentation dashboard.

**Market option prices → CRR / BSM inversion → implied volatility labels → ML prediction → price and smile/skew evaluation.**

The project was migrated from the original desktop `option_pricing.ipynb`. The original file remains unchanged in its original location. This repository uses Python modules and does not require Jupyter. All four original data interfaces and option-chain filters are preserved; credentials are loaded from a local `.env` file.

## 1. Quick start

Open PowerShell in the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dashboard]"
# Generate and evaluate the offline sample without API access:
.\.venv\Scripts\python main.py sample
# Start the local presentation dashboard:
.\.venv\Scripts\python main.py dashboard
```

Visit `http://127.0.0.1:8501`. The dashboard switches between the real JPM snapshot and the synthetic sample. Select a quote date, expiration and call/put side to explore IV curves, prediction scatter plots, three-fold model comparisons, stock/VIX/rate history, data provenance and label audits. The dashboard reads local files only: reloading the page does not consume API credits or send API keys to the browser. It is implemented entirely in Python in `frontend/app.py`.

The existing local `.env` has already been populated from the original file. On another computer, copy `.env.example` to `.env` and supply your own credentials:

```text
ALPHA_VANTAGE_API_KEY=
FRED_API_KEY=
MARKETDATA_TOKEN=
```

Preserve the existing local `.env`. Environment variables take precedence over values in that file. Keep credentials out of version control.

## 2. Refresh data through today

```powershell
# Default: request through today in New York, using a 42-calendar-day option window:
.\.venv\Scripts\python main.py refresh
# Reproduce the current presentation window:
.\.venv\Scripts\python main.py refresh --start 2026-10-01 --end 2026-11-12
# Refresh stock and macro caches; saved historical option-chain snapshots are reused:
.\.venv\Scripts\python main.py refresh --start 2026-10-01 --refresh-cache
# Rebuild labels and model evaluations from existing real CSV files:
.\.venv\Scripts\python main.py train --data data/market --output reports/market
# Run automated tests without calling live APIs:
.\.venv\Scripts\python -m unittest discover -s tests -v
```

`refresh` downloads data and runs the model pipeline. It uses the original 12-second request interval and reuses cached files. Vendor quotas, historical-access limits and publication delays can affect availability. Each option snapshot must match its requested New York trading session. Unavailable dates are recorded in `collection_audit.csv`; current quotes and synthetic observations are never substituted for missing history. Downloading does not purchase a subscription.

**The requested cutoff and the latest available observation are separate dates.** An unfinished current-day stock session is excluded. Treasury, VIX, stock and option data can have different latest dates. Each download writes `data/market/provenance.json`, including the requested cutoff, download time, actual latest observations by source and accepted option counts. `data/SNAPSHOT.md` records the completed download.

Stock, dividend and macro requests include 400 calendar days before the option window to support trailing-365-day dividend yield and rolling volatility features. The current presentation's option window starts on October 1, 2026. Expand the window within your account's access limits when more history is needed. This snapshot does not contain all option history since 2018.

## 3. Original APIs: sources and uses

| Original interface | Request and key parameters | Returned data | Use and units | Authentication |
| --- | --- | --- | --- | --- |
| yfinance / Yahoo Finance | `yf.download("JPM", start, end, auto_adjust=False, progress=False)` | Open, High, Low, Close, Adj Close, Volume | Unadjusted spot and adjusted-close returns; prices in USD/share | No API key |
| yfinance dividends | `yf.Ticker("JPM").history(..., auto_adjust=False, actions=True)` | Paid Dividends | Trailing annual cash dividends / spot, estimating q | No API key |
| Alpha Vantage | `GET https://www.alphavantage.co/query`; `function=TREASURY_YIELD`, `interval=daily`, `maturity=3month/2year/5year/7year/10year/30year` | Daily Treasury yields at six maturities | Raw values are percentages; 3m becomes `log1p(yield/100)` as a flat continuous-rate approximation; 10y minus 3m is the term spread | `ALPHA_VANTAGE_API_KEY`, query parameter `apikey` |
| FRED / St. Louis Fed | `GET https://api.stlouisfed.org/fred/series/observations`; `series_id=VIXCLS`, `file_type=json`, `observation_start`, `observation_end` | Daily VIX close observations | Macro feature in VIX index points | `FRED_API_KEY`, query parameter `api_key` |
| MarketData | `GET https://api.marketdata.app/v1/options/chain/JPM/`; `date`, `dte=30`, `monthly=true`, `strikeLimit=5`, `minBid=0.05`, `nonstandard=false` | Side, strike, expiration, bid, ask, mid, volume, OI, underlyingPrice, updated, and vendor IV/Greeks when supplied | Bid/ask midpoint is inverted for American IV; accompanying underlyingPrice supplies pricing spot; vendor IV/Greeks are excluded from labels and model features | `MARKETDATA_TOKEN`, Bearer authorization header |

Original function names remain available in `src/option_iv/original_api.py`: `fetch_jpm`, `fetch_treasury`, `fetch_all_treasury`, `fetch_vix`, `fetch_jpm_option_chain` and `main`. Importing the module makes no network requests. `collect.py` handles caching, timestamp normalization, unit conversion and provenance. Original vendor-response CSVs are cached in `data/vendor`.

The original notebook's ten feature calculations are preserved in `features.build_features` and saved to `data/vendor/original_features.csv`. Additional trailing stock-only features enter the regressors when available. The original correlations involving VIX and Treasury yields remain available for research; observation-date correlations are not automatically treated as verified release-time-safe inputs.

Official references: [yfinance download](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html), [yfinance history](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html), [Alpha Vantage](https://www.alphavantage.co/documentation/), [FRED observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [FRED vintage / real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html), [MarketData chain](https://dev.marketdata.app/sdk-php/classes/MarketDataApp-Endpoints-Options.html), and [MarketData data freshness](https://github.com/MarketDataApp/documentation/blob/main/api/universal-parameters/mode.md).

## 4. Project structure

```text
main.py                         # Unified command entry point
frontend/app.py                 # Python-only local Streamlit presentation
.streamlit/config.toml          # Dashboard theme and local server settings
src/option_iv/
    cli.py                      # sample / refresh / train / dashboard
    original_api.py             # Four original vendor interfaces
    collect.py                  # Downloads, caching, timestamps, provenance
    data.py                     # Schema validation and backward as-of joins
    features.py                 # Feature allowlist and original calculations
    dividends.py                # Yield estimated from known paid dividends
    pricing.py                  # BSM / CRR, cash-dividend approximation, inversion
    implied_vol.py              # Per-quote IV labels and rejection reasons
    models.py                   # Linear Regression / Random Forest / XGBoost
    evaluation.py               # Date splits and smile/skew/curvature evaluation
    pipeline.py                 # Labeling, training and output orchestration
    sample.py                   # Reproducible synthetic sample generator
scripts/make_demo.py             # Compatibility entry point for sample generation
data/
    sample/                     # Shareable offline synthetic CSV fixture
    market/                     # Local real snapshot, audit and provenance
    vendor/                     # Local original response caches and features
    processed/                  # Intermediate checks
    README.md                   # Data schema and units
    SNAPSHOT.md                 # Actual latest observations by source
reports/sample/                  # Portable offline sample evaluation
reports/market/                  # Local real-data evaluation
tests/                          # Pricing, inversion, timing and adapter tests
README.md / AGENTS.md / SKILL.md
pyproject.toml / requirements-lock.txt
```

`data/raw` and `data/demo` contain earlier local results retained for compatibility; current commands use the folders above. The repository contains no `.ipynb` files. The original desktop notebook has not been modified.

## 5. Sample data and real data

- **`data/sample`:** A deterministic synthetic fixture with seed 42, 75 dates and five strikes: 375 European call quotes generated with BSM and a prescribed smile. It supports a complete offline demonstration and does not represent JPM market performance.
- **`data/market`:** Real JPM stock, macro, dividend and option snapshots downloaded using the original APIs for local presentation. See `SNAPSHOT.md` for coverage.
- **`data/vendor`:** Original response CSVs and caches. Vendor IV and Greeks may be present here to preserve supplied fields; model labels are independently inverted from market prices.

Real market data and original caches remain local and are ignored by Git. The synthetic fixture is shareable with the repository. The presentation runs locally. Check your data license before publishing real quotes; this project does not grant redistribution rights.

## 6. Pricing, IV labels and dividends

For each market quote, the target is `y = implied_volatility`, obtained by solving `PricingModel(sigma) - market_mid = 0`. European quotes use BSM with a continuous dividend yield; American quotes use CRR. At every CRR node, the discounted risk-neutral continuation value is compared with immediate exercise and the larger value is retained.

`rv_20d` is an input feature, not an IV label substitute. The solver uses a finite volatility bracket. Invalid quotes, missing inputs, unidentifiable roots and out-of-bracket prices remain visible as rejected rows. They are never silently replaced with realized volatility or vendor IV. CRR uses 200 steps by default; assess 200/400/800-step sensitivity before interpreting real-chain results.

The default yield estimate is `q = known paid dividends over the trailing 365 days / spot at the quote`. Dividend availability is conservatively assumed to be the following day. Continuous dividends do not eliminate early exercise: American puts and sufficiently high-yield calls can still exercise early.

`pricing.price(..., cash_dividends=[(year_fraction, amount)], q=0)` exposes an additional escrowed-dividend approximation. Ex-dividend dates are mapped to the tree grid. It is not an exact discrete-jump dividend model and is not used for default label generation.

Despite the repository name, this phase learns IV from vanilla options. A chooser contract requires a separately specified choice date, payoff and pricing engine; the current American vanilla pricer is not a chooser pricer.

## 7. Features, timing and evaluation

Default features include one-day return, 20-day realized volatility, r, q, VIX, term spread, log(K/S), year-fraction maturity, volume, open interest and put/American flags. Available original five-/20-day returns, five-day RV and 20-day Parkinson volatility are also included. **Bid, ask, mid, vendor IV and Greeks are excluded from X.**

Features use backward as-of joins with `available_at <= quote_time`, a four-calendar-day stock tolerance and a seven-day macro tolerance. Future observations are never backfilled into earlier quotes. The option response's underlyingPrice supplies pricing spot; daily stock features use a conservative lag until the end of the following day.

Macro APIs currently provide observation dates rather than verified publication timestamps. The collector assumes availability at the end of the following day. That lag cannot eliminate historical revisions, unknown release times or adjustments to historical stock prices. Verified publication times and historical vintages are still required before claiming a strict no-look-ahead backtest. Liquidity fields must also reflect information available at the quote time.

Three expanding-window folds keep all contracts on the same quote day together. Training precedes testing with a one-calendar-day gap. Imputation and scaling are fit on training data only. Parameters are fixed rather than tuned on test folds. The task is contemporaneous IV estimation, not next-day forecasting or a trading-return backtest. Model selection needs an independent final holdout and nested date validation; forecasting additionally requires horizon-appropriate purging.

Each run writes:

| File | Contents |
| --- | --- |
| `labels_audit.csv` | All rows, IV labels and label_status |
| `out_of_time_predictions.csv` | Per-quote held-out IV predictions and repriced options |
| `metrics.csv` | Per-model/fold IV MAE, RMSE, price MAE and split dates |
| `surface_metrics.csv` | Quadratic skew/curvature errors within symbol, quote, expiry, side and style |
| `smile.png` | Actual and predicted IV for one held-out contract slice |
| `run.json` | Feature list, row counts, pricing configuration and data provenance |

IV is an annualized decimal: 0.01 equals one volatility percentage point. Price MAE is USD/share, without the 100-share contract multiplier. Curves compare the same expiration and option side. Short windows, few strikes, low vega and early-exercise plateaus limit interpretation.

## 8. Validation and troubleshooting

Tests cover the BSM reference price and put-call parity, CRR convergence and early exercise, IV round trips, dividend availability, isolation from future macro data, a full collector-to-loader round trip, original API parameters and stale-quote filtering. `requirements-lock.txt` records the tested environment; reproduce it with `python -m pip install -r requirements-lock.txt`.

- **HTTP 402:** Check the MarketData plan, historical range and latest accessible session. The existing account has rejected requests beyond one year and an unavailable recent session.
- **HTTP 429:** Check credits, reuse caches and retry later. The collector does not retry indefinitely.
- **Fewer than 12 valid quote days:** Expand the window or inspect `labels_audit.csv`; retain chronological splitting.
- **Streamlit missing:** Install `.[dashboard]` using the same `.venv`.
- **Port already in use:** Run `python main.py dashboard --port 8502`.
- **NumPy/pandas timedelta deprecation warnings:** The tested combination runs successfully; these warnings do not by themselves indicate a failed download.

The original APIs do not guarantee a complete, unbiased point-in-time dataset. Interpret results using the recorded provenance and actual data quality.

## 9. Completed snapshot: November 12, 2026

The download requested data through November 12, 2026 in New York. Actual latest observations were November 11 for stock prices, November 10 for VIX and valid option quotes, and November 9 for all six Treasury maturities. The option window begins October 1: 29 sessions and 290 quotes, all successfully inverted and evaluated with three models across three chronological folds. The November 11 option request returned HTTP 402 and is marked unavailable in the audit. The download ran early in the morning, before a November 12 closing observation existed.

The offline sample contains 375 quotes. Its first 20 dates lack sufficient trailing RV history, so 100 rows are excluded with an audit reason and 275 labels are valid. `reports/sample` includes portable presentation results. All 11 core tests, both complete pipelines, and dashboard dataset/call-put switching checks passed.

## 10. Recheck results and editor indentation

All Python files use four-space indentation with multi-line statements expanded for readability. `.editorconfig` and `.vscode/settings.json` set a Tab key width of four columns, disable automatic indentation detection, and show indentation guides. Python indentation is stored as spaces consistently; tabs and spaces are not mixed.

Reproduce the saved-results audit without downloading data:

```powershell
.\.venv\Scripts\python -m option_iv.audit --data data/market --reports reports/market
```

The audit checks quote coverage and duplicates, input-to-label consistency, timestamp ordering, IV repricing, chronological folds, and independently recomputed saved metrics. It also reports CRR 200/400/800-step sensitivity on 12 evenly selected rows, an observable RV baseline and liquidity/spread diagnostics. Increase `--convergence-rows` to 290 to repeat the full current-snapshot convergence check. Outputs are `validation.json` and `crr_convergence_audit.csv` in the chosen reports directory. See VALIDATION.md for findings and interpretation limits.

The verification pass reran both complete pipelines and all 12 tests, including a separate scalar-tree implementation checked against the vectorized CRR engine. Passing numerical and consistency checks does not establish market-data accuracy or future forecasting performance.
