import math
from nodeble.backtest.pricing import bs_price, bs_delta, find_strike_for_delta


def test_bs_call_price_atm():
    """ATM call with 30 DTE should have reasonable price."""
    price = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert 8.0 < price < 18.0


def test_bs_put_price_atm():
    """ATM put with 30 DTE should have reasonable price."""
    price = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert 8.0 < price < 18.0


def test_bs_call_price_otm():
    """OTM call should be cheaper than ATM."""
    atm = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    otm = bs_price(S=500.0, K=520.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert otm < atm


def test_bs_put_price_otm():
    """OTM put should be cheaper than ATM."""
    atm = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    otm = bs_price(S=500.0, K=480.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert otm < atm


def test_bs_price_zero_time():
    """At expiration, option = intrinsic value."""
    price = bs_price(S=500.0, K=490.0, T=0.0001, r=0.05, sigma=0.20, option_type="call")
    assert abs(price - 10.0) < 0.5
    price = bs_price(S=500.0, K=510.0, T=0.0001, r=0.05, sigma=0.20, option_type="call")
    assert price < 0.5


def test_bs_delta_call_atm():
    """ATM call delta should be ~0.50."""
    delta = bs_delta(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert 0.45 < delta < 0.60


def test_bs_delta_put_atm():
    """ATM put delta should be ~-0.50."""
    delta = bs_delta(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert -0.60 < delta < -0.45


def test_bs_delta_otm_call():
    """OTM call delta should be small positive."""
    delta = bs_delta(S=500.0, K=530.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert 0.0 < delta < 0.25


def test_bs_delta_otm_put():
    """OTM put delta should be small negative."""
    delta = bs_delta(S=500.0, K=470.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert -0.25 < delta < 0.0


def test_find_strike_for_delta_put():
    """Find OTM put strike for delta -0.15."""
    strike = find_strike_for_delta(
        S=500.0, T=30/365, r=0.05, sigma=0.20,
        target_delta=0.15, option_type="put",
    )
    actual_delta = abs(bs_delta(S=500.0, K=strike, T=30/365, r=0.05, sigma=0.20, option_type="put"))
    assert abs(actual_delta - 0.15) < 0.02
    assert strike < 500.0
    assert strike == round(strike)


def test_find_strike_for_delta_call():
    """Find OTM call strike for delta 0.15."""
    strike = find_strike_for_delta(
        S=500.0, T=30/365, r=0.05, sigma=0.20,
        target_delta=0.15, option_type="call",
    )
    actual_delta = bs_delta(S=500.0, K=strike, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert abs(actual_delta - 0.15) < 0.02
    assert strike > 500.0
    assert strike == round(strike)
