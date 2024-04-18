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
            'CHOCOLATE': 250,
            'STRAWBERRIES': 350,
            'ROSES': 60,
            'GIFT_BASKET': 60,

        }

    def calculate_fair_value(self, product_prices):
        return 4 * product_prices['CHOCOLATE'] + 6 * product_prices['STRAWBERRIES'] + product_prices['ROSES']

    def run(self, state: TradingState):
        # Only method required. It takes all buy and sell orders for all symbols as an input, and outputs a list of orders to be sent
        logger.print("traderData: " + state.traderData)
        logger.print("Observations: " + str(state.observations))
        result = {}

        product_prices = {}

        for product in ['CHOCOLATE', 'STRAWBERRIES', 'ROSES']:
            order_depth: OrderDepth = state.order_depths[product]
            if order_depth:
                best_ask_price = min(order_depth.sell_orders.keys())
                best_bid_price = max(order_depth.buy_orders.keys())
                mid_price = (best_ask_price + best_bid_price) / 2
                product_prices[product] = mid_price
        fair_value = self.calculate_fair_value(product_prices)

        for product in state.order_depths:
            if product not in self.position_limits:
                continue
            position_limit = self.position_limits[product]
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if not order_depth:
                continue

            # Calculate the current inventory
            current_inventory = state.position.get(product, 0)
            inventory_factor = current_inventory / position_limit

            # Calculate mid-price
            best_ask_price = min(order_depth.sell_orders.keys())
            best_bid_price = max(order_depth.buy_orders.keys())
            mid_price = (best_ask_price + best_bid_price) / 2

            if product != 'GIFT_BASKET':
                # Calculate target spread based on inventory level and market conditions
                inventory_factor = current_inventory / position_limit
                target_spread = mid_price * \
                    (0.001 + 0.001 * inventory_factor)  # Example calculation

                # Calculate bid and ask prices
                bid_price = mid_price - target_spread
                ask_price = mid_price + target_spread

                if len(order_depth.sell_orders) != 0:
                    best_ask, best_ask_amount = list(
                        order_depth.sell_orders.items())[0]

                    ask_size = max(
                        1, min(position_limit - current_inventory, best_ask_amount//10))
                    if ask_price > best_ask:
                        # logger.print("BUY", str(ask_size) + "x", best_ask)
                        orders.append(
                            Order(product, best_ask, best_ask_amount))

                if len(order_depth.buy_orders) != 0:
                    best_bid, best_bid_amount = list(
                        order_depth.buy_orders.items())[0]

                    bid_size = max(1, min(current_inventory +
                                          position_limit, best_bid_amount//10))

                    if bid_price > best_bid_price:
                        # logger.print("SELL", str(bid_size) + "x", best_bid)
                        orders.append(
                            Order(product, best_bid, best_bid_amount))

            else:
                if mid_price is None:
                    continue

                best_ask_price, best_ask_amount = min(
                    order_depth.sell_orders.items())
                best_bid_price, best_bid_amount = max(
                    order_depth.buy_orders.items())

                # If the GIFT_BASKET is undervalued, buy it; if it's overvalued, sell it.
                if mid_price < fair_value:
                    # Calculate how much of GIFT_BASKET we can buy without exceeding the limit
                    size_to_buy = min(
                        position_limit - current_inventory, best_ask_amount)
                    if size_to_buy > 0:
                        best_ask_price = min(order_depth.sell_orders.keys())
                        orders.append(
                            Order(product, best_ask_price, size_to_buy))
                elif mid_price > fair_value:
                    # Calculate how much of GIFT_BASKET we can sell without exceeding the limit
                    size_to_sell = min(current_inventory +
                                       position_limit, best_bid_amount)
                    if size_to_sell > 0:
                        best_bid_price = max(order_depth.buy_orders.keys())
                        orders.append(
                            Order(product, best_bid_price, -size_to_sell))

            result[product] = orders

        # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        traderData = "SAMPLE"

        conversions = 1
        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData
