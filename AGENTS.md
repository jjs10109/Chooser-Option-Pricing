# Repository guidance

Read README.md and SKILL.md before changes. Preserve any working vendor API adapters and credential loading. Never commit keys, .env files or licensed option history.

Target is market-implied volatility, not realized volatility. Keep pricing conventions identical between inversion and repricing. Treat failures as audited exclusions. All option contracts on a quote day must stay in one fold. Fit transformations on training data only. Data availability timestamps and macro vintages must be point-in-time; never backward-fill future observations. No market mid, bid, ask or vendor IV in model features.

Run the synthetic demo, unittest discovery and complete pipeline after numerical or alignment changes. Check CRR convergence before interpreting real results. Do not claim synthetic metrics represent trading performance. Do not spawn agents or change external services without user authorization.

The project is Python-only: do not add notebooks. main.py is the command entry point; frontend/app.py is a local read-only presentation app. data/sample is the committed synthetic offline fixture; data/market and data/vendor are actual local-only downloads. Keep source freshness in provenance and data/SNAPSHOT.md; do not call requested cutoff the latest observation date.

Use four-space indentation for all Python files, as configured by .editorconfig. Keep verification findings in VALIDATION.md; use option_iv.audit to recompute results without API calls.
