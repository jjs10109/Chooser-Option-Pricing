# JPM Implied Volatility Lab

**A quantitative research pipeline for learning the implied-volatility structure of JPM equity options.**

The project combines numerical option pricing with supervised regression: market quotes are inverted into implied-volatility labels, then stock, option and macroeconomic features are used to estimate those labels on later quote dates. A local Streamlit dashboard makes the pricing assumptions, volatility curves, model comparisons and data coverage inspectable.

**Stack:** Python · NumPy · pandas · SciPy · scikit-learn · XGBoost · Streamlit · Plotly

## Research question

Can nonlinear regressors estimate the cross-sectional structure of market-implied volatility more accurately than a linear baseline when evaluated on later dates?

The target is **implied volatility inferred from market prices**. Historical realized volatility is an explanatory feature. The current task estimates contemporaneous IV across dates; next-day forecasting and trading-strategy evaluation are outside the implemented scope.

## Methodology

```text
JPM option quotes ──→ Bid/ask midpoint ──→ CRR / BSM inversion ──→ IV labels
                                                                     │
Stock history + dividends + Treasury yields + VIX ──→ Aligned features │
                                                        │            │
                                                        └─────┬──────┘
                                                              ↓
                                   Linear Regression / Random Forest / XGBoost
                                                              ↓
                                   Chronological evaluation + smile/skew analysis
```

### Pricing and label construction

- **American options:** a Cox–Ross–Rubinstein tree compares immediate exercise with discounted risk-neutral continuation at every node.
- **European options:** Black–Scholes–Merton with a continuous dividend yield.
- **IV inversion:** bracketed numerical root finding solves `model_price(sigma) = market_mid`. Invalid or unidentifiable observations retain explicit rejection reasons.
- **Dividends:** the default continuous yield is trailing-365-day known paid dividends divided by spot. An optional escrowed cash-dividend approximation is available for sensitivity analysis.

The production label pipeline uses a 200-step CRR tree. The validation tool compares 200/400/800-step inversions. Pricing and repricing use the same exercise and dividend conventions.

### Features and evaluation

Features include trailing returns, realized volatility, Parkinson volatility, log moneyness, time to expiration, volume, open interest, Treasury rates, the term spread, VIX and dividend yield. Market option prices, vendor IV and Greeks are excluded from model inputs.

Three expanding-window folds keep every contract from a quote day in the same group. Training dates precede test dates with a one-calendar-day gap; imputation and scaling are fit only on training observations. Evaluation covers IV MAE/RMSE, repricing MAE and within-expiry smile, skew and curvature comparisons.

Backward as-of joins enforce `available_at <= quote_time`. Stock features are conservatively lagged, and the accompanying option-chain underlying mark supplies pricing spot. Macro availability uses an explicit following-day assumption; verified historical release timestamps and vintages remain an open data-quality requirement.

## Results

The current experiment contains **1,000 JPM option quotes across 100 trading sessions**, with **750 held-out observations per model** across three chronological folds. The following metrics are pooled from the saved out-of-time predictions:

| Model | IV MAE (volatility pp) | IV RMSE (volatility pp) | Price MAE (USD/share) |
| --- | ---: | ---: | ---: |
| Linear Regression | 4.117 | 4.903 | 1.489 |
| Random Forest | **2.701** | **3.346** | **0.948** |
| XGBoost | 2.811 | 3.444 | 0.989 |

One volatility percentage point equals 0.01 in annualized decimal IV. Price errors are per share, before the option-contract multiplier.

Both tree ensembles outperform the linear baseline on this sample. Random Forest has the lowest pooled errors, although performance varies by fold. These are descriptive results from an incomplete historical sample; they do not establish performance on an untouched final holdout or future market regimes.

### Coverage and interpretation

The requested window is **November 12, 2025–November 12, 2026**. Available observations cover **100 of 251 expected sessions (39.8%)**, leaving **151 missing sessions**. An API quota/rate-limit response interrupted collection; previously cached recent dates were retained. The latest included option quote is November 10, 2026, but the intervening calendar coverage is discontinuous.

Accordingly, the experiment is **not a complete one-year backtest**. Folds contain equal groups of observed dates rather than equally long continuous calendar windows. Other limitations include a narrow near-the-money chain, bid/ask uncertainty, estimated dividends, a flat-rate approximation and unverified macro publication vintages. More history, liquidity-filter sensitivity, verified point-in-time inputs and an independent final holdout are needed for stronger predictive claims.

## Data sources

| Provider | API / request | Data and role |
| --- | --- | --- |
| yfinance / Yahoo Finance | `yf.download("JPM", auto_adjust=False)`; `Ticker.history(actions=True)` | OHLCV, adjusted-close returns and paid dividends |
| Alpha Vantage | `GET https://www.alphavantage.co/query`, `function=TREASURY_YIELD`, `interval=daily` | Treasury yields at 3 months and 2, 5, 7, 10 and 30 years; rate and term-spread features |
| FRED / St. Louis Fed | `GET https://api.stlouisfed.org/fred/series/observations`, `series_id=VIXCLS` | Daily VIX observations |
| MarketData | `GET https://api.marketdata.app/v1/options/chain/JPM/` | Historical bid/ask quotes, underlying marks, timestamps and liquidity fields |

The option-chain request uses `dte=30`, `monthly=true`, `strikeLimit=5`, `minBid=0.05` and `nonstandard=false`. Treasury percentages are converted to decimal units; the pricing rate uses `log1p(3m_yield / 100)` as a flat continuous-rate approximation. Stock, macro and dividend requests include 400 calendar days of lookback for rolling features and dividend estimates.

Downloads are cached and accompanied by per-session audits and provenance. Requested cutoffs and actual latest observations are recorded separately. Missing quotes are never replaced with current chains or synthetic values.

## Reproduce the project

Python 3.10+ is required. From the repository root, the offline demonstration can be reproduced without API credentials:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dashboard]"
.\.venv\Scripts\python main.py sample
.\.venv\Scripts\python main.py dashboard
```

Open [the local dashboard](http://127.0.0.1:8501) to inspect IV smiles, prediction errors, market context and provenance. The dashboard reads local files and supports both real and synthetic datasets.

For market-data collection, configure `.env` using `.env.example`:

```text
ALPHA_VANTAGE_API_KEY=
FRED_API_KEY=
MARKETDATA_TOKEN=
```

```powershell
# Request a historical window and evaluate the available observations.
.\.venv\Scripts\python main.py refresh --start 2025-11-12 --end 2026-11-12

# Evaluate an existing local market snapshot.
.\.venv\Scripts\python main.py train

# Run tests and inspect saved-result consistency.
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m option_iv.audit --data data/market --reports reports/market
```

Historical access and completeness depend on provider permissions and quotas. After HTTP 429, collection stops further network requests, retains available caches and marks the snapshot incomplete.

## Architecture

```text
main.py                     Command-line entry point
frontend/app.py             Read-only research dashboard
src/option_iv/
    original_api.py         Vendor API adapters
    collect.py              Cached collection, normalization and provenance
    data.py                 Schema validation and time alignment
    features.py             Feature construction and input allowlist
    dividends.py            Historical dividend-yield estimation
    pricing.py              Pricing engines and numerical inversion
    implied_vol.py          Quote validation and IV labels
    models.py               Regression baselines
    evaluation.py           Chronological splits and surface diagnostics
    pipeline.py             End-to-end experiment orchestration
    audit.py                Saved-result and numerical consistency checks
    sample.py               Deterministic offline sample generator
data/sample/                Shareable synthetic fixture
reports/sample/             Reproducible sample results
tests/                      Pricing, timing and API-adapter tests
```

Real-data snapshots and vendor caches remain local under `data/market` and `data/vendor`; credentials and market downloads are excluded from version control. The committed synthetic fixture is clearly identified and supports offline review. Results include row-level label audits, held-out predictions, fold metrics, surface diagnostics and run metadata.

Tests cover BSM reference values and put-call parity, CRR convergence and early exercise, IV round trips, dividend availability, isolation from future macro observations, API parsing and cache behavior after rate limiting. The audit tool independently recomputes saved metrics and checks label repricing, date grouping and grid sensitivity.

## Scope and further work

The implemented research stage prices vanilla equity options and learns their implied volatility. The repository name includes “Chooser,” but a chooser payoff and selection-time pricing engine are not implemented.

Further work includes continuous historical coverage, verified macro vintages, bid/ask-implied IV intervals, liquidity-aware evaluation, discrete-dividend model comparison and nested time-based model selection with a final untouched test period.

See [the data catalog](data/README.md), [current snapshot coverage](data/SNAPSHOT.md) and [the data contract](SKILL.md) for supporting detail.
