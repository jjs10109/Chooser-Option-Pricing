# IV research data contract

## Inputs (CSV, UTF-8)
All times are explicit UTC timestamps. Rates, yield and IV are annual decimal units (0.04 = 4%); VIX is index points. Prices and dividends are per share, same currency. One underlying/contract adjustment convention throughout. No split-adjusted stock spot against unadjusted option strikes.

- options.csv: quote_time, expiry, symbol, strike, kind (call/put), style (american/european), bid, ask, volume, open_interest. Expiry is the actual expiry timestamp. Bid/ask are synchronized with stock spot; stale quotes must be removed upstream.
- stocks.csv: available_at, symbol, spot (unadjusted tradable spot), feature_close (split/dividend adjusted historical close). One row per symbol and timestamp, daily sampling. Historical adjusted series must be reconstructed point-in-time where corporate actions would revise features. available_at must be after close when using closing prices.
- macro.csv: available_at, r, vix, term_spread. Each row is a complete snapshot published by available_at. r is a continuously compounded maturity-appropriate rate (flat curve baseline); term_spread uses consistent tenors. Use release dates and original vintages, never observation dates or revised values masquerading as historical knowledge.
- dividends.csv: symbol, ex_date, known_at, amount. Empty table with headers is valid. One row per event; no duplicate/revised events. Ingest revisions as point-in-time snapshots upstream. The pipeline uses paid trailing-365-day dividends known at the quote divided by spot. This is an estimate of continuous q, not a forecast of announced cash payments.

## Rules
Backward as-of only: stock tolerance 4 calendar days, macro tolerance 7. Strict application-specific timestamp synchronization remains the adapter's responsibility; tolerances are not evidence of freshness. Missing histories/invalid quotes are excluded with label_status. No invented values, vendor IV target substitution, forward fill from future, or historical-option download claims from current chains. Feature histories need 21 prior closes. Do not change units silently.

## Cash-dividend extension
pricing.price accepts cash_dividends=[(year_fraction, amount)] with q=0. It uses an escrowed-dividend approximation and rounds ex dates to CRR steps; it is not an exact jump tree. Supply only schedules known at quote time; projected payments must be derived solely from past events. The production CSV pipeline deliberately uses continuous q. Validate grid convergence and alternate discrete-dividend engines before using this approximation for labels near ex dates.

## Original API adapter
The integrated collector is option_iv.collect. Preserve original_api endpoint defaults. pricing_spot is an optional positive underlying mark supplied with the option quote; when present it overrides daily stock spot for inversion and moneyness. Vendor updated must match requested New York session. Collector macro and dividend available_at values are explicit conservative assumptions recorded in provenance.json, not verified publication dates. Never describe this adapter output as certified point-in-time data.
