"""Minimal mock broker for unit tests.

Returns configurable canned data. Order placement records calls
for assertion in tests but never touches a real API.
"""
from dataclasses import dataclass, field


@dataclass
class MockSegment:
    cash_available_for_trade: float = 100_000.0
    net_liquidation: float = 200_000.0


@dataclass
class MockAssets:
    segments: dict = field(default_factory=lambda: {"S": MockSegment()})


@dataclass
class MockBrief:
    identifier: str = ""
    bid_price: float = 0.0
    ask_price: float = 0.0
    delta: float = 0.0
    latest_price: float = 0.0


@dataclass
class MockOrder:
    status: str = "FILLED"


class MockBroker:
    """Test double implementing BrokerAdapter protocol."""

    def __init__(self):
        self.orders_placed: list[dict] = []
        self.orders_cancelled: list[int] = []
        self._next_order_id = 1000
        self._order_statuses: dict[int, str] = {}
        self._stock_prices: dict[str, float] = {}
        self._option_analyses: list = []
        self._option_chains: dict[str, list[dict]] = {}
        self._option_expirations: dict[str, list[dict]] = {}
        self._option_briefs: dict[str, MockBrief] = {}
        self._assets = MockAssets()

    def get_option_analysis(self, symbols):
        return self._option_analyses

    def get_stock_price(self, symbol):
        return self._stock_prices.get(symbol, 100.0)

    def get_option_expirations(self, symbol):
        return self._option_expirations.get(symbol, [])

    def get_option_chain(self, symbol, expiry, option_filter=None):
        key = f"{symbol}_{expiry}"
        return self._option_chains.get(key, [])

    def get_option_briefs(self, identifiers):
        return [self._option_briefs.get(i, MockBrief(identifier=i)) for i in identifiers]

    def place_option_market_order(self, identifier, action, quantity):
        order_id = self._next_order_id
        self._next_order_id += 1
        self.orders_placed.append({
            "identifier": identifier, "action": action,
            "quantity": quantity, "order_id": order_id,
        })
        self._order_statuses[order_id] = "FILLED"
        return order_id

    def get_order(self, order_id):
        status = self._order_statuses.get(order_id, "FILLED")
        return MockOrder(status=status)

    def cancel_order(self, order_id):
        self.orders_cancelled.append(order_id)

    def get_open_orders(self, sec_type="OPT"):
        return []

    def get_assets(self):
        return self._assets

    def get_positions(self, sec_type="OPT"):
        return []
