from api import Rest_api
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import time
from math import exp


def emergency(ra, ticker, bids, asks, increment, open_position, set_qty, dangerious):
    bid_T = bids.T
    ask_T = asks.T
    market_limit = 0.002
    emergency_qty = set_qty
    if open_position > 0:
        dangerious = False
        price = bid_T[0][0] * (1 - market_limit)  # 範圍市價
        with ThreadPoolExecutor() as executor:
            executor.submit(ra.place_order, ticker, 'sell', emergency_qty, price)
    elif open_position < 0:  # 市價平倉，減少風險
        dangerious = False
        price = ask_T[0][0] * (1 + market_limit)    # 範圍市價
        with ThreadPoolExecutor() as executor:
            executor.submit(ra.place_order, ticker, 'buy', emergency_qty, price)
    return dangerious

def book_monitor(ra, ticker, bids, asks, increment, open_position, entry_price, qty, set_qty, profit_buff):
    discount = exp(-0.05 * qty / set_qty)
    bid_T = bids.T
    ask_T = asks.T
    mid_price = (ask_T[0][0] + bid_T[0][0]) / 2
    ticks = int(mid_price * profit_buff / increment) + 1
    extra = ticks - discount * ticks
    if open_position == 0:
        bid_price = bid_T[0][0] - ticks * increment
        ask_price = ask_T[0][0] + ticks * increment
        bid_qty, ask_qty = set_qty, set_qty
        with ThreadPoolExecutor() as executor:
            executor.submit(ra.place_order, ticker, 'buy', bid_qty, bid_price)
            executor.submit(ra.place_order, ticker, 'sell', ask_qty, ask_price)

    elif open_position > 0: 
        bid_price = bid_T[0][0] - (ticks + extra) * increment
        ask_price = ask_T[0][0] + (ticks + 1) * increment
        bid_qty = set_qty * discount
        if ask_T[0][0] <= entry_price:  # 虧損中
            ask_qty = set_qty
            with ThreadPoolExecutor() as executor:
                executor.submit(ra.place_order, ticker, 'buy', bid_qty, bid_price)
                executor.submit(ra.place_order, ticker, 'sell', ask_qty, ask_price)
        else:
            ask_qty = qty
            with ThreadPoolExecutor() as executor:
                executor.submit(ra.place_order, ticker, 'buy', bid_qty, bid_price)
                executor.submit(ra.place_order, ticker, 'sell', ask_qty, ask_price)
                

    elif open_position < 0:
        bid_price = bid_T[0][0] - (ticks + 1) * increment
        ask_price = ask_T[0][0] + (ticks + extra) * increment
        ask_qty = set_qty * discount
        if bid_T[0][0] >= entry_price:  # 虧損中
            bid_qty = set_qty
            with ThreadPoolExecutor() as executor:
                executor.submit(ra.place_order, ticker, 'buy', bid_qty, bid_price)
                executor.submit(ra.place_order, ticker, 'sell', ask_qty, ask_price)
        else:
            bid_qty = qty
            with ThreadPoolExecutor() as executor:
                executor.submit(ra.place_order, ticker, 'buy', bid_qty, bid_price)
                executor.submit(ra.place_order, ticker, 'sell', ask_qty, ask_price)
                
        
                
