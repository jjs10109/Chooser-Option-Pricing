"""Trailing paid-dividend continuous yield estimator, point-in-time filtered."""

import pandas as pd


def trailing_yields(df, div):
    yields = []
    for row in df.itertuples():
        past = div[
            (div.symbol == row.symbol)
            & (div.known_at <= row.quote_time)
            & (div.ex_date <= row.quote_time)
            & (div.ex_date > row.quote_time - pd.Timedelta(days=365))
        ]
        yields.append(past.amount.sum() / row.spot)
    return yields
