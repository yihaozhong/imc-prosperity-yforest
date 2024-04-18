from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string

import json
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions,
            "",
            "",
        ]))

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(self.to_json([
            self.compress_state(state, self.truncate(
                state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append(
                [listing["symbol"], listing["product"], listing["denomination"]])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [
                order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append([
                    trade.symbol,
                    trade.price,
                    trade.quantity,
                    trade.buyer,
                    trade.seller,
                    trade.timestamp,
                ])

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sunlight,
                observation.humidity,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value

        return value[:max_length - 3] + "..."


logger = Logger()


class Trader:
    def __init__(self):
        self.position_limits = {
            'CHOCOLATE': 500,
            'STRAWBERRIES': 600,
            'ROSES': 250,
            'GIFT_BASKET': 200
        }

    def calculate_fair_value(self, product_prices):
        return 4 * product_prices['CHOCOLATE'] + 6 * product_prices['STRAWBERRIES'] + product_prices['ROSES']

    def run(self, state: TradingState):
        logger.print("traderData: " + state.traderData)
        logger.print("Observations: " + str(state.observations))

        result = {}
        product_prices = {}

        target_symbols = ['CHOCOLATE', 'STRAWBERRIES', 'ROSES', 'GIFT_BASKET']

        for product in target_symbols:
            if product == 'GIFT_BASKET':
                continue

            order_depth: OrderDepth = state.order_depths[product]

            if order_depth:
                best_ask_price = min(order_depth.sell_orders.keys())
                best_bid_price = max(order_depth.buy_orders.keys())
                mid_price = (best_ask_price + best_bid_price) / 2
                product_prices[product] = mid_price

        fair_value = self.calculate_fair_value(product_prices)

        net_position = 0

        for product in target_symbols:
            position_limit = self.position_limits[product]
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if not order_depth:
                continue

            current_inventory = state.position.get(product, 0)

            if product != 'GIFT_BASKET':
                net_position += current_inventory

                best_ask_price = min(order_depth.sell_orders.keys())
                best_bid_price = max(order_depth.buy_orders.keys())

                bid_size = min(10, position_limit - current_inventory)
                ask_size = min(10, position_limit + current_inventory)

                if bid_size > 0:
                    orders.append(Order(product, best_bid_price, bid_size))
                if ask_size > 0:
                    orders.append(Order(product, best_ask_price, -ask_size))

            else:
                if fair_value is None:
                    continue

                best_ask_price, best_ask_amount = min(
                    order_depth.sell_orders.items())
                best_bid_price, best_bid_amount = max(
                    order_depth.buy_orders.items())
                mid_price = (best_ask_price + best_bid_price) / 2

                if mid_price < fair_value:
                    hedge_size = min(-net_position, best_ask_amount,
                                     position_limit - current_inventory)
                    if hedge_size > 0:
                        orders.append(
                            Order(product, best_ask_price, hedge_size))

                elif mid_price > fair_value:
                    hedge_size = min(net_position, best_bid_amount,
                                     position_limit + current_inventory)
                    if hedge_size > 0:
                        orders.append(
                            Order(product, best_bid_price, -hedge_size))

            result[product] = orders

        traderData = ""
        conversions = 1
        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData
