"""Recheck saved data, labels, split integrity and reported model errors."""

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .data import load
from .evaluation import date_splits
from .pricing import price, implied_vol


def audit(data="data/market", reports="reports/market", convergence_rows=12):
    folder = Path(reports)
    frame = load(data).reset_index(drop=True)
    labels = pd.read_csv(folder / "labels_audit.csv")
    predictions = pd.read_csv(folder / "out_of_time_predictions.csv")
    metrics = pd.read_csv(folder / "metrics.csv")
    valid = labels[labels.label_status == "ok"].copy()
    checks = {}
    checks["audit_covers_all_input_rows"] = len(frame) == len(labels)
    checks["no_duplicate_contracts"] = not frame.duplicated(
        ["symbol", "quote_time", "expiry", "strike", "kind", "style"]
    ).any()
    checks["valid_quotes"] = bool(
        (
            (frame.bid >= 0)
            & (frame.ask >= frame.bid)
            & (frame.mid > 0)
            & (frame.t > 0)
            & (frame.strike > 0)
            & (frame.spot > 0)
        ).all()
    )
    checks["available_timestamps_precede_quotes"] = bool(
        (
            (frame.stock_available_at <= frame.quote_time)
            & (frame.macro_available_at <= frame.quote_time)
        ).all()
    )
    checks["labels_match_input_order"] = bool(
        np.allclose(frame.mid, labels.mid)
        and np.allclose(frame.spot, labels.spot)
        and np.allclose(frame.strike, labels.strike)
    )
    repricing = []
    for row in valid.itertuples():
        args = dict(
            s=row.spot,
            k=row.strike,
            t=row.t,
            r=row.r,
            q=row.q,
            kind=row.kind,
            style=row.style,
        )
        repricing.append(abs(price(sigma=row.implied_volatility, **args) - row.mid))
    max_repricing = max(repricing)
    checks["iv_roundtrip_within_one_cent"] = max_repricing < 0.01
    valid_times = pd.to_datetime(valid.quote_time, utc=True)
    split_frame = valid.copy()
    split_frame["quote_time"] = valid_times
    recomputed = []
    split_ok = True
    for fold, (train, test) in enumerate(date_splits(split_frame), 1):
        expected = split_frame.iloc[test]
        actual = predictions[predictions.fold == fold]
        for name, part in actual.groupby("model"):
            split_ok &= set(pd.to_datetime(part.quote_time, utc=True)) == set(
                expected.quote_time
            )
            split_ok &= len(part) == len(test)
            split_ok &= split_frame.iloc[train].quote_time.max() < pd.to_datetime(
                part.quote_time, utc=True
            ).min() - pd.Timedelta(days=1)
            errors = part.predicted_iv - part.implied_volatility
            values = dict(
                fold=fold,
                model=name,
                iv_mae=float(abs(errors).mean()),
                iv_rmse=float(np.sqrt((errors**2).mean())),
                price_mae=float(abs(part.predicted_price - part.mid).mean()),
            )
            saved = metrics[(metrics.fold == fold) & (metrics.model == name)].iloc[0]
            checks[f"metrics_fold_{fold}_{name}"] = all(
                np.isclose(values[c], saved[c], atol=1e-10)
                for c in ["iv_mae", "iv_rmse", "price_mae"]
            )
            recomputed.append(values)
    checks["chronological_date_groups_and_gap"] = bool(split_ok)
    convergence = []
    for index in np.unique(
        np.linspace(0, len(valid) - 1, min(convergence_rows, len(valid)), dtype=int)
    ):
        row = valid.iloc[index]
        args = dict(
            s=row.spot,
            k=row.strike,
            t=row.t,
            r=row.r,
            q=row.q,
            kind=row.kind,
            style=row["style"],
        )
        iv400 = implied_vol(row.mid, steps=400, **args)
        iv800 = implied_vol(row.mid, steps=800, **args)
        convergence.append(
            dict(
                quote_time=row.quote_time,
                strike=row.strike,
                kind=row.kind,
                iv200=row.implied_volatility,
                iv400=iv400,
                iv800=iv800,
                absolute_iv_shift=abs(iv800 - row.implied_volatility),
            )
        )
    table = pd.DataFrame(convergence)
    table.to_csv(folder / "crr_convergence_audit.csv", index=False)
    # Report model and simple observable-RV baseline on the same held-out rows.
    summaries = []
    for model, part in predictions.groupby("model"):
        errors = part.predicted_iv - part.implied_volatility
        summaries.append(
            dict(
                model=model,
                n=len(part),
                iv_mae=float(abs(errors).mean()),
                iv_rmse=float(np.sqrt((errors**2).mean())),
                price_mae=float(abs(part.predicted_price - part.mid).mean()),
            )
        )
    unique = predictions.drop_duplicates(
        ["fold", "symbol", "quote_time", "expiry", "strike", "kind", "style"]
    )
    rv_error = unique.rv_20d - unique.implied_volatility
    spread = (frame.ask - frame.bid) / frame.mid
    quality = {
        "mean_relative_bid_ask_spread": float(spread.mean()),
        "maximum_relative_bid_ask_spread": float(spread.max()),
        "quotes_with_spread_over_20_percent": int((spread > 0.2).sum()),
        "quotes_with_zero_volume": int((frame.volume == 0).sum()),
        "quotes_with_zero_open_interest": int((frame.open_interest == 0).sum()),
    }
    report = {
        "checks": {k: bool(v) for k, v in checks.items()},
        "all_mechanical_checks_pass": all(checks.values()),
        "data_quality": quality,
        "rows": len(frame),
        "accepted_labels": len(valid),
        "max_label_repricing_error_usd_per_share": float(max_repricing),
        "convergence_rows": len(table),
        "max_absolute_iv_shift_200_to_800": float(table.absolute_iv_shift.max()),
        "pooled_held_out_metrics": summaries,
        "rv_20d_baseline_iv_mae": float(abs(rv_error).mean()),
        "limitations": [
            "Macro availability timestamps are assumptions, not verified publication times/vintages.",
            "Only a short window and a narrow chain are covered; results do not establish forecasting or trading performance.",
            "Midpoint inversion does not validate executable prices or independently verify vendor observations.",
            "IV convergence is sampled; labels remain model-dependent under continuous dividend yield.",
        ],
    }
    (folder / "validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/market")
    parser.add_argument("--reports", default="reports/market")
    parser.add_argument("--convergence-rows", type=int, default=12)
    args = parser.parse_args()
    result = audit(args.data, args.reports, args.convergence_rows)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["all_mechanical_checks_pass"] else 1)
