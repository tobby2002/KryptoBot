import logging
import os
from collections import defaultdict
from . import order
from . import market_watcher
import ccxt
# TODO: Replace when updated
# Has been updated but need to test
from ..ccxt_shim.cryptopia import cryptopia
ccxt.cryptopia = cryptopia


logger = logging.getLogger(__name__)

markets = []


class Market:
    """An object that allows a specific strategy to interface with an exchange,
    This includes functionality to contain and update TA indicators as well as the latest OHLCV data
    This also handles the API key for authentication, as well as methods to place orders"""

    def __init__(self, exchange, base_currency, quote_currency, strategy):
        self.exchange_name = exchange
        exchange = getattr(ccxt, exchange)
        self.base_balance = None
        self.strategy = strategy
        self.api_key = None
        self.secret_key = None
        self.exchange = exchange({'apiKey': self.api_key, 'secret': self.secret_key, })
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.analysis_pair = '{}/{}'.format(self.base_currency, self.quote_currency)
        self.signals = []
        self.ohlcv_id = defaultdict(int)
        self.indicators = defaultdict(list)
        self.candles = defaultdict(list)
        self.latest_candle = defaultdict(list)  # allows for order simulations based on historical ohlcv data
        markets.append(self)

    def add_session(self, session):
        self.session = session

    def add_keys(self, keys):
        try:
            if self.exchange_name in keys:
                self.api_key = keys[self.exchange_name]['key']
                self.secret_key = keys[self.exchange_name]['secret']
                self.exchange = self.exchange({'apiKey': self.api_key, 'secret': self.secret_key, })
        except:
            logger.error("Invalid api keys")

    def update(self, interval, candle):
        """Notify all indicators subscribed to the interval of a new candle"""
        self.latest_candle[interval] = candle
        self.candles[interval].append(candle)
        self.do_ta_calculations(interval, candle)

    def do_ta_calculations(self, interval, candle):
        """update TA indicators applied to market"""
        for indicator in self.indicators[interval]:
            indicator.next_calculation(candle)

    def apply_indicator(self, indicator):
        """Add indicator to list of indicators listening to market's candles"""
        self.indicators[indicator.interval].append(indicator)

    def limit_buy(self, quantity, price):
        """Place a limit buy order"""
        try:
            self.strategy.send_message("Executed buy of " + str(quantity) + " " + self.base_currency + " for " + str(price) + " " + self.quote_currency)
            return order.Order(self, "buy", "limit", quantity, price, self.session)
        except:
            self.strategy.send_message("Error creating buy order")
            logger.error("Error creating buy order")

    def limit_sell(self, quantity, price):
        """Place a limit sell order"""
        try:
            self.strategy.send_message("Executed sell of " + str(quantity) + " " + self.base_currency + " for " + str(price) + " " + self.quote_currency)
            return order.Order(self, "sell", "limit", quantity, price, self.session)
        except:
            self.strategy.send_message("Error creating sell order")
            logger.error("Error creating sell order")

    def get_wallet_balance(self):
        """Get wallet balance for quote currency"""
        try:
            logger.info(self.exchange.fetch_balance())
            return self.exchange.fetch_balance()
        except:
            logger.error("Not logged in properly")

    def get_best_bid(self):
        orderbook = self.exchange.fetch_order_book(self.analysis_pair)
        return orderbook['bids'][0][0] if len(orderbook['bids']) > 0 else None

    def get_best_ask(self):
        orderbook = self.exchange.fetch_order_book(self.analysis_pair)
        return orderbook['asks'][0][0] if len(orderbook['asks']) > 0 else None

    def get_historical_candles(self, interval, candle_limit=None):
        if len(self.candles[interval]) == 0:
            self.candles[interval] = market_watcher.get_market_watcher(self.exchange.id, self.base_currency, self.quote_currency, interval).get_historical_candles()
        if candle_limit is None:
            return self.candles[interval]
        else:
            return self.candles[interval][-candle_limit:]

    def get_candle_date_range(self, interval, start_date, end_date):
        self.candles[interval] = market_watcher.get_market_watcher(
            self.exchange.id,
            self.base_currency,
            self.quote_currency,
            interval
        ).get_candle_date_range(
            start_date,
            end_date
        )
        return self.candles[interval]
