"""python -m option_iv.pipeline --data data/raw --output reports"""

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from .data import load
from .pricing import implied_vol, price

from .features import FEATURES
from .models import make_models


from .implied_vol import labels


from .evaluation import date_splits, write_surface_reports


def run(folder, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    labeled = labels(load(folder))
    labeled.to_csv(out / "labels_audit.csv", index=False)
    df = labeled[labeled.label_status == "ok"].reset_index(drop=True)
    if df.empty:
        raise ValueError("No valid IV labels; inspect labels_audit.csv")
    feature_cols = FEATURES + [
        c
        for c in ["ret_5d", "ret_20d", "rv_5d", "parkinson_vol_20d"]
        if c in df and df[c].notna().any()
    ]
    models = make_models()
    scores = []
    predictions = []
    for fold, (train, test) in enumerate(date_splits(df), 1):
        for name, model in models.items():
            model.fit(df.iloc[train][feature_cols], df.iloc[train].implied_volatility)
            pred = np.clip(model.predict(df.iloc[test][feature_cols]), 0.001, 5.0)
            part = df.iloc[test].copy()
            part["predicted_iv"] = pred
            part["model"] = name
            part["fold"] = fold
            part["predicted_price"] = [
                price(
                    s=r.spot,
                    k=r.strike,
                    t=r.t,
                    r=r.r,
                    q=r.q,
                    sigma=v,
                    kind=r.kind,
                    style=r.style,
                )
                for r, v in zip(part.itertuples(), pred)
            ]
            scores.append(
                {
                    "fold": fold,
                    "model": name,
                    "train_end": str(df.iloc[train].quote_time.max()),
                    "test_start": str(part.quote_time.min()),
                    "n_train": len(train),
                    "n_test": len(test),
                    "iv_mae": mean_absolute_error(part.implied_volatility, pred),
                    "iv_rmse": float(
                        np.sqrt(mean_squared_error(part.implied_volatility, pred))
                    ),
                    "price_mae": mean_absolute_error(part.mid, part.predicted_price),
                }
            )
            predictions.append(part)
    result = pd.concat(predictions, ignore_index=True)
    result.to_csv(out / "out_of_time_predictions.csv", index=False)
    pd.DataFrame(scores).to_csv(out / "metrics.csv", index=False)
    write_surface_reports(result, out)
    (out / "run.json").write_text(
        json.dumps(
            {
                "features": feature_cols,
                "rows": len(labeled),
                "accepted": len(df),
                "crr_steps": 200,
                "dividend_mode": "trailing continuous yield",
                "task": "contemporaneous IV estimation; not next-day forecasting",
                "data_provenance": (
                    json.loads(
                        (Path(folder) / "provenance.json").read_text(encoding="utf-8")
                    )
                    if (Path(folder) / "provenance.json").exists()
                    else {"status": "external CSV timing must be verified"}
                ),
            },
            indent=2,
        )
    )
    return pd.DataFrame(scores)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/raw")
    p.add_argument("--output", default="reports")
    args = p.parse_args()
    print(run(args.data, args.output).to_string(index=False))
