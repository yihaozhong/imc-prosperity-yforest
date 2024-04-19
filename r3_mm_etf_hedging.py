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
        self.humidity_history = []
        self.sunlight_history = []
        self.position_limits = {
            'CHOCOLATE': 250,
            'STRAWBERRIES': 350,
            'ROSES': 60,
            'GIFT_BASKET': 60,
            'ORCHIDS': 100,
            'STARFRUIT': 20,
            'AMETHYSTS': 20
        }

    def compute_mid_price(self, sell_orders, buy_orders):
        if sell_orders and buy_orders:
            best_ask_price = min(sell_orders)
            best_bid_price = max(buy_orders)
            return (best_ask_price + best_bid_price) / 2
        else:
            return None

    def calculate_fair_value(self, product_prices):
        return int(4 * product_prices['CHOCOLATE'] + 6 * product_prices['STRAWBERRIES'] + product_prices['ROSES'] + 375)

    def calculate_sunlight_hours(self, rate, timestamp):
        timestep = 12.0 / 10000.0
        hours_passed = timestamp * timestep
        remaining_hours = 12 - hours_passed
        total_sunlight_estimate = rate * hours_passed + rate * remaining_hours
        return total_sunlight_estimate

    def analyse_humidity(self, humidity):
        self.humidity_history.append(humidity)

        if len(self.humidity_history) < 2:
            return 'hold'

        # Compare the last two humidity readings
        recent_change = self.humidity_history[-1] - self.humidity_history[-2]

        if 60 <= humidity <= 80:
            return 'hold'
        elif humidity > 80:
            return 'long' if recent_change > 0 else 'short'
        elif humidity < 60:
            return 'long' if recent_change < 0 else 'short'

    def run(self, state: TradingState):
        logger.print("traderData: " + state.traderData)
        logger.print("Observations: " + str(state.observations))

        result = {}
        product_prices = {}

        target_symbols = ['CHOCOLATE', 'STRAWBERRIES', 'ROSES']

        for product in target_symbols:

            order_depth: OrderDepth = state.order_depths[product]

            if order_depth:
                best_ask_price = min(order_depth.sell_orders.keys())
                best_bid_price = max(order_depth.buy_orders.keys())
                mid_price = (best_ask_price + best_bid_price) / 2
                product_prices[product] = mid_price

        fair_value = self.calculate_fair_value(product_prices)

        net_position = 0
        mid_prices = {}
        components = ['CHOCOLATE', 'STRAWBERRIES', 'ROSES']
        for comp in components:
            order_depth: OrderDepth = state.order_depths[product]
            mid_prices[comp] = self.compute_mid_price(
                order_depth.sell_orders, order_depth.buy_orders)

        for product in state.order_depths:
            position_limit = self.position_limits[product]
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if not order_depth:
                continue

            current_inventory = state.position.get(product, 0)

            if product == 'AMETHYSTS':
                best_ask = min(order_depth.sell_orders.keys())
                best_bid = max(order_depth.buy_orders.keys())
                mid_price = (best_ask + best_bid) / 2

                position = state.position.get(product, 0)
                position_limit = self.position_limits[product]

                if position > 0.5 * position_limit:
                    ask_price = int(mid_price + 1)
                    ask_size = int(min(10, position_limit - position))
                    if ask_size > 0:
                        orders.append(Order(product, ask_price, -ask_size))
                elif position < -0.5 * position_limit:
                    bid_price = int(mid_price - 1)
                    bid_size = int(min(10, position_limit + position))
                    if bid_size > 0:
                        orders.append(Order(product, bid_price, bid_size))
                else:
                    ask_price = int(mid_price + 2)
                    bid_price = int(mid_price - 2)
                    ask_size = bid_size = 10
                    orders.append(Order(product, ask_price, -ask_size))
                    orders.append(Order(product, bid_price, bid_size))

            elif product == 'ORCHIDS':
                current_sunlight = state.observations.conversionObservations["ORCHIDS"].sunlight
                current_humidity = state.observations.conversionObservations["ORCHIDS"].humidity

                # Determine trade action based on sunlight
                sunlight_hours = self.calculate_sunlight_hours(
                    current_sunlight, state.timestamp)
                # 2500 is your average sunlight per hour threshold
                sunlight_action = 'short' if sunlight_hours < 7 * 2500 else 'hold'

                # Determine trade action based on humidity
                humidity_action = self.analyse_humidity(current_humidity)

                # Combine actions from sunlight and humidity analysis
                if sunlight_action == 'short' or humidity_action == 'short':
                    trade_action = 'short'
                elif sunlight_action == 'long' or humidity_action == 'long':
                    trade_action = 'long'
                else:
                    trade_action = 'hold'

                # log sunlight and humidity analysis, and trade action
                logger.print("Sunlight: ", sunlight_action)
                logger.print("Humidity: ", humidity_action)
                logger.print("Trade action: ", trade_action)

                if trade_action != 'hold':

                    if trade_action == 'short':

                        best_bid = max(order_depth.buy_orders.keys())
                        bid_size = min(
                            5, position_limit + current_inventory)
                        if bid_size > 0:
                            orders.append(
                                Order(product, best_bid, bid_size))
                    elif trade_action == 'long':

                        best_ask = min(order_depth.sell_orders.keys())
                        ask_size = min(
                            5, position_limit - current_inventory)
                        if ask_size > 0:
                            orders.append(
                                Order(product, best_ask, -ask_size))

            elif product != 'GIFT_BASKET':
                # Calculate the current inventory
                current_inventory = state.position.get(product, 0)
                net_position += current_inventory
                inventory_factor = current_inventory / position_limit

                # Calculate mid-price
                best_ask_price = min(order_depth.sell_orders.keys())
                best_bid_price = max(order_depth.buy_orders.keys())
                mid_price = (best_ask_price + best_bid_price) / 2

                # Calculate order book imbalance
                total_bid_volume = sum(order_depth.buy_orders.values())
                total_ask_volume = sum(order_depth.sell_orders.values())
                book_imbalance = 0  # Default value in case of no volume
                if total_bid_volume + total_ask_volume > 0:
                    book_imbalance = (total_bid_volume - total_ask_volume) / \
                        (total_bid_volume + total_ask_volume)

                # Incorporate inventory factor and order book imbalance into spread calculation
                target_spread = mid_price * \
                    (0.0001 + 0.0001 * inventory_factor - 0.0005 * book_imbalance)
                bid_price = mid_price - target_spread
                ask_price = mid_price + target_spread

                logger.print("Buy Order depth : " + str(len(order_depth.buy_orders)) +
                             ", Sell order depth : " + str(len(order_depth.sell_orders)))

                if len(order_depth.sell_orders) != 0:
                    best_ask, best_ask_amount = list(
                        order_depth.sell_orders.items())[0]

                    ask_size = min(position_limit -
                                   current_inventory, best_ask_amount)
                    if ask_price > best_ask:
                        # logger.print("BUY", str(ask_size) + "x", best_ask)
                        orders.append(
                            Order(product, best_ask, ask_size))

                if len(order_depth.buy_orders) != 0:
                    best_bid, best_bid_amount = list(
                        order_depth.buy_orders.items())[0]

                    bid_size = max(1, min(current_inventory +
                                          position_limit, best_bid_amount))

                    if bid_price > best_bid_price:
                        # logger.print("SELL", str(bid_size) + "x", best_bid)
                        orders.append(
                            Order(product, best_bid, bid_size))

            elif product == 'GIFT_BASKET':
                logger.print("fair_value: ", fair_value)
                logger.print("net_position: ", net_position)
                best_ask, best_ask_amount = list(
                    order_depth.sell_orders.items())[0]
                best_bid, best_bid_amount = list(
                    order_depth.buy_orders.items())[0]
                gift_mid_price = (best_ask + best_bid) / 2

                mid_prices['GIFT_BASKET'] = gift_mid_price
               # if net_position > 0:

               #     hedge_size = min(
               #         net_position, position_limit - current_inventory)
               #     if hedge_size > 0:

               #         orders.append(
               #             Order(product, best_ask, -hedge_size))
               # elif net_position < 0:
               #     # If net position is negative, we want to buy the GIFT_BASKET
               #     hedge_size = min(-net_position,
               #                      position_limit + current_inventory)
               #     if hedge_size > 0:

               #         orders.append(
               #             Order(product, best_bid, hedge_size))
                # if mid_prices['GIFT_BASKET'] > fair_value:
                #     # The GIFT_BASKET is overvalued, so we should consider selling
                #     size_to_sell = min(
                #         -order_depth.sell_orders[min(order_depth.sell_orders)],
                #         self.position_limits['GIFT_BASKET'] -
                #         position_limit
                #     )
                #     if size_to_sell > 0:
                #         orders.append(Order('GIFT_BASKET', min(
                #             order_depth.sell_orders), -size_to_sell))
                # elif mid_prices['GIFT_BASKET'] < fair_value:
                #     # The GIFT_BASKET is undervalued
                #     size_to_buy = min(
                #         order_depth.buy_orders[max(
                #             order_depth.buy_orders)],
                #         self.position_limits['GIFT_BASKET'] +
                #         position_limit
                #     )
                #     if size_to_buy > 0:
                #         orders.append(Order('GIFT_BASKET', max(
                #             order_depth.buy_orders), size_to_buy))
                self.sunlight_history.append(
                    state.observations.conversionObservations["ORCHIDS"].sunlight)

                recent_change = 0
                if len(self.sunlight_history) > 1:
                    recent_change = self.sunlight_history[-1] - \
                        self.sunlight_history[-2]

                if recent_change > 0:
                    # place best price buy order
                    orders.append(
                        Order('GIFT_BASKET', best_bid, best_bid_amount))

                elif recent_change < 0:
                    # place best price sell order
                    orders.append(
                        Order('GIFT_BASKET', best_ask, -best_ask_amount))

            result[product] = orders

        traderData = ""
        conversions = 1
        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData
