# Data catalog

`sample/` contains deterministic synthetic CSVs and provenance for offline reproduction; it is committed with the code. `market/` contains actual API data downloaded locally and is ignored by Git. `vendor/` contains original cached responses and all original notebook features. Read SNAPSHOT.md for the actual latest observation dates, not just the requested cutoff.

| CSV | Columns | Units / meaning |
| --- | --- | --- |
| options.csv | quote_time, expiry, symbol, strike, kind, style, bid, ask, volume, open_interest, optional pricing_spot | UTC times; USD/share; volume/OI in contracts; pricing_spot is vendor simultaneous underlying mark |
| stocks.csv | available_at, symbol, spot, feature_close, optional original trailing features | spot is unadjusted USD; feature_close is adjusted close used for returns |
| macro.csv | available_at, r, vix, term_spread | annual decimal r/spread; VIX index points |
| dividends.csv | symbol, ex_date, known_at, amount | cash dividend USD/share; only past paid events known by quote can enter q |
| collection_audit.csv | date, vendor_rows, validated_rows, status | real-data date coverage and rejected/stale/unavailable requests |
| provenance.json | source list, cutoff, timestamp, latest observations, assumptions | synthetic provenance explicitly states the generator and seed |

All input timestamps have an explicit timezone and are normalized to UTC. Missing quotes are not generated. Failed label rows remain in reports/*/labels_audit.csv. Missing macro observations are carried only from past observations before the conservative availability lag; no future backfill.

For licensing and confidentiality, the true market snapshot is local and excluded from version control; the synthetic sample is the portable presentation fixture. Do not describe synthetic CSVs as downloaded JPM data. No key, token, URL containing credentials or response headers belong in these folders.
