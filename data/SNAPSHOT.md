# Current download snapshot

## Current data coverage and presentation note

The requested option window is **2025-11-12 to 2026-11-12**. The current dataset contains **1,000 option quotes across 100 of 251 expected trading sessions** (39.8% coverage). **151 sessions are missing.**

MarketData returned HTTP 429 on **2026-02-26**. Previously downloaded later-date snapshots were recovered from the local cache, so the latest included option date is **2026-11-10** even though intervening dates remain missing. A recent final timestamp does not imply continuous coverage.

This is an **incomplete historical sample with substantial calendar gaps**, not a complete one-year backtest. Model evaluation uses chronological folds over the available observations; fold lengths represent observed sessions rather than equally long continuous calendar windows. Results should be presented as a demonstration of the pricing, IV inversion and machine-learning workflow. They do not establish year-round performance, next-day forecasting accuracy or trading profitability.

To complete the window, check MarketData credits and rate-limit reset details, then rerun the original refresh command. Cached dates will be reused; no missing market observations are synthesized.

```powershell
.\.venv\Scripts\python main.py refresh --start 2025-11-12 --end 2026-11-12
```

### Suggested presentation wording

> We requested one year of JPM option data. API access limits interrupted collection, leaving 100 of 251 expected trading sessions and 1,000 option quotes. The dataset combines an earlier historical segment with previously cached recent dates and has substantial gaps. The reported results evaluate our workflow on the available observations; they are not a complete one-year backtest.
