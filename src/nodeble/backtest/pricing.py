# -*- coding: utf-8 -*-
"""Black-Scholes option pricing for backtest simulation."""
import math
from scipy.stats import norm

RISK_FREE_RATE = 0.05


def bs_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes European option price.

    Args:
        S: underlying price
        K: strike price
        T: time to expiry in years (DTE / 365)
        r: risk-free rate
        sigma: annualized volatility
        option_type: "call" or "put"
    """
    if T <= 0:
        if option_type == "call":
            return max(S - K, 0.0)
        else:
            return max(K - S, 0.0)

    if sigma <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)

    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes delta.

    Returns:
        Call delta: 0 to 1
        Put delta: -1 to 0
    """
    if T <= 0 or sigma <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))

    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1.0


def find_strike_for_delta(
    S: float, T: float, r: float, sigma: float,
    target_delta: float, option_type: str,
) -> float:
    """Binary search for strike where |BS delta| ~ target_delta.

    target_delta should be positive (e.g., 0.15 for a 15-delta option).
    Returns strike rounded to nearest $1.
    """
    if option_type == "put":
        low, high = S * 0.5, S
        for _ in range(100):
            mid = (low + high) / 2
            d = abs(bs_delta(S, mid, T, r, sigma, "put"))
            if d < target_delta:
                low = mid   # too far OTM, move strike closer to ATM (higher)
            else:
                high = mid  # too close to ATM, move strike further OTM (lower)
        return round(mid)
    else:
        low, high = S, S * 1.5
        for _ in range(100):
            mid = (low + high) / 2
            d = bs_delta(S, mid, T, r, sigma, "call")
            if d > target_delta:
                low = mid
            else:
                high = mid
        return round(mid)
