"""Vanilla pricing, continuous yield, and an escrowed cash-dividend approximation."""

import math
import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr


def price(
    s, k, t, r, q, sigma, kind="call", style="american", steps=200, cash_dividends=()
):
    if kind not in {"call", "put"} or style not in {"american", "european"}:
        raise ValueError("invalid kind/style")
    if (
        not all(math.isfinite(x) for x in (s, k, t, r, q, sigma))
        or min(s, k, t, sigma) <= 0
    ):
        raise ValueError(
            "positive finite spot, strike, maturity and volatility required"
        )
    sign = 1 if kind == "call" else -1
    divs = [(a, b) for a, b in cash_dividends if 0 < a <= t]
    if divs and q != 0:
        raise ValueError("use cash dividends OR continuous yield")
    if style == "european" and not divs:
        d1 = (math.log(s / k) + (r - q + sigma * sigma / 2) * t) / (
            sigma * math.sqrt(t)
        )
        d2 = d1 - sigma * math.sqrt(t)
        return float(
            sign
            * (
                s * math.exp(-q * t) * ndtr(sign * d1)
                - k * math.exp(-r * t) * ndtr(sign * d2)
            )
        )
    if steps < 2:
        raise ValueError("at least two steps required")
    dt = t / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    if not 0 <= p <= 1:
        raise ValueError("invalid CRR probability; increase steps or volatility floor")
    # Escrowed dividends: recombining risky component plus remaining cash PV.
    # Exercise is checked immediately before dividend events rounded to grid.
    events = {}
    for a, b in divs:
        if b < 0:
            raise ValueError("negative dividend")
        j = max(1, min(steps, round(a / dt)))
        events[j] = events.get(j, 0) + b
    base = s - sum(b * math.exp(-r * j * dt) for j, b in events.items())
    if base <= 0:
        raise ValueError("dividend PV exceeds spot")

    def nodes(i):
        remaining = sum(
            b * math.exp(-r * (j - i) * dt) for j, b in events.items() if j >= i
        )
        return base * u ** np.arange(i, -i - 1, -2) + remaining

    v = np.maximum(sign * (nodes(steps) - k), 0)
    for i in range(steps - 1, -1, -1):
        v = math.exp(-r * dt) * (p * v[:-1] + (1 - p) * v[1:])
        if style == "american":
            v = np.maximum(v, np.maximum(sign * (nodes(i) - k), 0))
    return float(v[0])


def implied_vol(market_price, **kwargs):
    """Bracketed inversion; failures are explicit, never replaced by realized vol."""
    if not math.isfinite(market_price) or market_price <= 0:
        raise ValueError("invalid market price")
    # A CRR tree has a finite-step probability constraint at low sigma.
    t = kwargs["t"]
    steps = kwargs.get("steps", 200)
    floor = max(1e-4, abs(kwargs["r"] - kwargs["q"]) * math.sqrt(t / steps) * 1.001)
    lo = price(sigma=floor, **kwargs)
    hi = price(sigma=5.0, **kwargs)
    if not lo + 1e-7 < market_price < hi - 1e-7:
        raise ValueError("price outside identifiable volatility bracket")
    return brentq(
        lambda vol: price(sigma=vol, **kwargs) - market_price, floor, 5.0, xtol=1e-7
    )
