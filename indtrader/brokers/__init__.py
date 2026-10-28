from indtrader.brokers.base import Broker, Holding, Order, OrderResult

__all__ = ["Broker", "Holding", "Order", "OrderResult", "make_broker"]


def make_broker(settings) -> Broker:
    name = settings.broker.name
    if name == "paper":
        from indtrader import data
        from indtrader.brokers.paper import PaperBroker

        return PaperBroker(settings.broker.paper_state_file, settings.risk.capital, settings.cost_model,
                           price_fn=data.last_price)
    if name == "zerodha":
        from indtrader.brokers.zerodha import ZerodhaBroker

        return ZerodhaBroker()
    if name == "openalgo":
        from indtrader.brokers.openalgo_broker import OpenAlgoBroker

        return OpenAlgoBroker(settings.broker.openalgo_host, settings.broker.strategy_tag)
    raise ValueError(f"unknown broker {name!r}")
