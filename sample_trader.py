'''
Even more importantly, the TradingState will contain a per product overview of all the outstanding buy and sell orders (also called “quotes”) originating from the bots. 

'''

from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string


class Sample_Trader:
    def run(self, state: TradingState):
        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))

        result = list()

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = list()

            acceptable_price = 10  # a hardcoded threshold

            if len(order_depth.sell_orders) != 0:
                best_ask, best_ask_amount = list(
                    order_depth.sell_orders.items())[0]
                if int(best_ask) < acceptable_price:
                    print("BUY", str(-best_ask_amount) + "x", best_ask)
                    orders.append(Order(product, best_ask, -best_ask_amount))

            if len(order_depth.buy_orders) != 0:
                best_bid, best_bid_amount = list(order_depth.items())[0]
                if int(best_bid) > acceptable_price:
                    print("SELL", str(best_bid_amount) + "x", best_bid)
                    orders.append(Order(product, best_bid, -best_bid_amount))

            result[product] = orders

        # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        traderData = "SAMPLE"

        conversions = 1
        return result
