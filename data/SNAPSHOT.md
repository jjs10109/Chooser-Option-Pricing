# Download snapshot

Requested through **2026-11-12** (America/New_York).
Downloaded at: 2026-11-12T03:35:57.890333-05:00.

Option window: 2026-10-01 to 2026-11-10; 29 sessions / 290 rows.

| Source / series | Latest actual observation |
| --- | --- |
| stocks | 2026-11-11 |
| vix | 2026-11-10 |
| treasury_3m | 2026-11-09 |
| treasury_2y | 2026-11-09 |
| treasury_5y | 2026-11-09 |
| treasury_7y | 2026-11-09 |
| treasury_10y | 2026-11-09 |
| treasury_30y | 2026-11-09 |
| options | 2026-11-10 |
| last_paid_dividend | 2026-10-06 |

## Coverage audit

date,vendor_rows,validated_rows,status

2026-10-01,10,10,ok

2026-10-02,10,10,ok

2026-10-05,10,10,ok

2026-10-06,10,10,ok

2026-10-07,10,10,ok

2026-10-08,10,10,ok

2026-10-09,10,10,ok

2026-10-12,10,10,ok

2026-10-13,10,10,ok

2026-10-14,10,10,ok

2026-10-15,10,10,ok

2026-10-16,10,10,ok

2026-10-19,10,10,ok

2026-10-20,10,10,ok

2026-10-21,10,10,ok

2026-10-22,10,10,ok

2026-10-23,10,10,ok

2026-10-26,10,10,ok

2026-10-27,10,10,ok

2026-10-28,10,10,ok

2026-10-29,10,10,ok

2026-10-30,10,10,ok

2026-11-02,10,10,ok

2026-11-03,10,10,ok

2026-11-04,10,10,ok

2026-11-05,10,10,ok

2026-11-06,10,10,ok

2026-11-09,10,10,ok

2026-11-10,10,10,ok

2026-11-11,0,0,MarketData HTTP 402: requested historical date unavailable for this account


At download time it was early morning in New York. No completed November 12 daily stock session existed. The November 11 option request was rejected with HTTP 402 and was excluded; November 10 is the latest validated option day. Treasury and VIX dates are the latest nonmissing observations actually returned, not invented publication dates.

Data is real API data under data/market and data/vendor, kept local. The separate data/sample fixture is synthetic and portable.

All 290 market quotes produced IV labels. Three models completed all three chronological folds. Conservative macro availability assumptions and historical revision limitations still apply.