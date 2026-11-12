# Verification report — November 12, 2026

## Conclusion

Both complete pipelines reran successfully, all 12 tests passed, and all saved-results consistency checks passed. This verifies execution, internal consistency and the checked numerical behavior. It does not independently certify vendor prices, macro publication times, future forecasting accuracy or trading profitability.

## Data and labels

- Real snapshot: 290 option observations across 29 sessions; all 290 labels are numerically identifiable under the chosen pricing assumptions.
- No duplicate contracts or missing joined inputs were found in this snapshot.
- All joined stock and macro availability timestamps precede or equal their option quote timestamps. Macro timestamps remain conservative assumptions, so this does not prove strict point-in-time availability.
- Requested cutoff: November 12. Actual latest observations remain stock November 11, options/VIX November 10, Treasury November 9. The November 11 option request was unavailable (HTTP 402).
- Maximum price error when saved IV is repriced: $0.0000011019 per share.
- A full 290-row 200-to-800-step CRR inversion check found a maximum absolute IV change of 0.00041376363736800315 (0.041376 volatility percentage points). The reusable audit also checks 200/400/800 steps on 12 evenly selected rows by default.

## Held-out results

Pooled across all three chronological folds: 210 held-out observations per model. IV MAE/RMSE below are expressed in volatility percentage points, not decimal IV. Price MAE is USD/share.

| Model | IV MAE (volatility pp) | IV RMSE (volatility pp) | Price MAE (USD/share) |
| --- | ---: | ---: | ---: |
| linear | 10.314 | 12.018 | 3.509 |
| random_forest | 2.497 | 3.120 | 0.940 |
| xgboost | 2.847 | 3.300 | 1.058 |

Observable 20-day RV baseline IV MAE on the same held-out contracts: 6.529 volatility percentage points.

The tree models outperform this simple RV baseline in the current sample. Linear Regression performs worse than that baseline, so it should be presented as an unsuccessful baseline for this window. There was no test-set tuning in this verification pass. These are short-window contemporaneous-IV results, not next-day forecasts.

## Data quality limitations

- Mean bid/ask spread divided by midpoint: 10.74%.
- Maximum relative spread: 33.16%.
- Ten quotes have relative spreads above 20%; eight have zero volume; six have zero open interest. These counts may overlap.
- These quotes remain in the baseline to preserve the original API sample. Numeric label acceptance does not mean a quote is liquid or executable.
- A larger history, broader chain, explicit liquidity-policy sensitivity, verified macro release timestamps/vintages, and an independent final holdout are required for stronger predictive claims.
- Continuous trailing dividend yield and flat rates are model assumptions. The optional discrete-dividend function remains an approximation.

## Code readability

All 19 Python files now use standard four-space indentation and expanded statements. Black checked every file. .editorconfig and .vscode/settings.json enforce a four-column Tab width, consistent spaces, disabled automatic indentation detection, and visible indentation guides. Tabs and spaces are not mixed.

## Reproduce

```powershell
.\.venv\Scripts\python main.py sample
.\.venv\Scripts\python main.py train
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m option_iv.audit --data data/market --reports reports/market
```

The audit saves validation.json and crr_convergence_audit.csv under reports/market. Use --convergence-rows 290 for a full-row repeat of the grid sensitivity check. Tests include an independent scalar CRR implementation compared with the vectorized pricer. No new vendor API request was needed for this verification.
