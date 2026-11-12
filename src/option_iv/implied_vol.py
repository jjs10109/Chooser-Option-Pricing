"""Market quote validation and IV label generation."""

import numpy as np
from .pricing import implied_vol
from .features import FEATURES


def labels(df):
    df = df.copy()
    values = []
    reasons = []
    for row in df.itertuples():
        try:
            if not (
                0 <= row.bid <= row.ask
                and row.ask > 0
                and row.t > 0
                and row.volume >= 0
                and row.open_interest >= 0
            ):
                raise ValueError("invalid quote, maturity or liquidity")
            if not np.isfinite(
                [getattr(row, x) for x in FEATURES] + [row.spot, row.strike, row.mid]
            ).all():
                raise ValueError(
                    "missing/stale inputs or insufficient trailing history"
                )
            vol = implied_vol(
                row.mid,
                s=row.spot,
                k=row.strike,
                t=row.t,
                r=row.r,
                q=row.q,
                kind=row.kind,
                style=row.style,
            )
            values.append(vol)
            reasons.append("ok")
        except (ValueError, OverflowError) as exc:
            values.append(np.nan)
            reasons.append(str(exc))
    df["implied_volatility"] = values
    df["label_status"] = reasons
    return df
