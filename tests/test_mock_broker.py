from mock_broker import MockBroker
from nodeble.core.broker import BrokerAdapter


def test_mock_broker_implements_protocol():
    broker = MockBroker()
    assert isinstance(broker, BrokerAdapter)


def test_mock_broker_tracks_orders():
    broker = MockBroker()
    oid = broker.place_option_market_order("TSLA  260327P00250000", "SELL", 1)
    assert len(broker.orders_placed) == 1
    assert broker.get_order(oid).status == "FILLED"
