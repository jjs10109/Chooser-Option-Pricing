"""Date-grouped expanding splits and within-expiry surface evaluation."""

import numpy as np
import pandas as pd


def date_splits(df, folds=3, gap_days=1):
    dates = pd.Index(sorted(df.quote_time.dt.floor("D").unique()))
    if len(dates) < 12:
        raise ValueError("at least 12 distinct quote dates required")
    blocks = np.array_split(dates, folds + 1)
    for block in blocks[1:]:
        start = block[0]
        end = block[-1]
        train = np.flatnonzero(
            df.quote_time.dt.floor("D") < start - pd.Timedelta(days=gap_days)
        )
        test = np.flatnonzero(df.quote_time.dt.floor("D").between(start, end))
        if len(train) and len(test):
            yield train, test


def write_surface_reports(result, out):
    # A single held-out date/expiry/kind/style curve per model; never mix surfaces.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = ["symbol", "quote_time", "expiry", "kind", "style"]
    candidates = result.groupby(keys).size().sort_values()
    key = candidates.index[-1]
    curve = result
    for col, val in zip(keys, key):
        curve = curve[curve[col] == val]
    fig, ax = plt.subplots()
    actual = curve.drop_duplicates("strike").sort_values("log_moneyness")
    ax.plot(actual.log_moneyness, actual.implied_volatility, "ko-", label="market IV")
    for name, g in curve.groupby("model"):
        g = g.sort_values("log_moneyness")
        ax.plot(g.log_moneyness, g.predicted_iv, ".-", label=name)
    ax.set(xlabel="log(K/S)", ylabel="annualized IV", title=str(key))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "smile.png")
    plt.close(fig)
    curve_metrics = []
    for key, g in result.groupby(keys + ["model"]):
        g = g.sort_values("log_moneyness")
        if g.strike.nunique() < 3:
            continue
        x = g.log_moneyness.to_numpy()
        actual = np.polyfit(x, g.implied_volatility, 2)
        predicted = np.polyfit(x, g.predicted_iv, 2)
        curve_metrics.append(
            dict(
                zip(keys + ["model"], key),
                skew_error=float(predicted[1] - actual[1]),
                curvature_error=float(2 * (predicted[0] - actual[0])),
            )
        )
    pd.DataFrame(curve_metrics).to_csv(out / "surface_metrics.csv", index=False)
