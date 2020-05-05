from function import *
import json, time
import websocket, os, sys
import hmac, hashlib
from datetime import datetime, timedelta
from api import Rest_api
import numpy as np
from collections import deque


class Live_data():
    def __init__(self):
        # 初始化Websocket
        depth_address = "wss://ftx.com/ws/"
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(depth_address, on_message=self.on_message, on_error=self.on_error, on_close=self.on_close)
        self.ws.on_open = self.on_open
        self.key = ''
        self.secret = ''
        self.subaccount = None                                      # 主帳戶填None
        self.ftx_service = websocket.WebSocketApp(self.key, self.secret, depth_address)
        self.ticker = 'BTC-PERP'
        self.set_qty = 0.0                                          # 設定下單量，顆數爲單位
        self.bids = np.array([], dtype='float64')                   # orderbook
        self.asks = np.array([], dtype='float64')
        self.bids_length = 0
        self.asks_length = 0                                            
        self.open_position = 0                                      # 部位多空
        self.entry_price = 0.0                                      # 存進場價格
        self.qty = 0.0                                              # 交易所部位
        self.profit_buff = 0.0002                                   # 操作價差
        self.increment = 0.0                                        # 商品的tick大小
        self.ra = Rest_api()                                        # REST API
        self.min_update = False
        self.active_orders = False
        self.canceled = False
        self.last_order = datetime.now()
        self.value = 0.0
        self.margin = 0.0
        self.danger_zone = 0.2
        self.dangerious = False
        self.pause = False

    # 啓動
    def run(self):
        self.ws.run_forever(ping_interval=60, ping_timeout=5)

    # WebSocket回傳
    def on_message(self, message):
        # 更新tick價格，判斷進場
        if 'partial' in message and 'orderbook' in message and "bids" in message and "asks" in message:
            self.build_order_book(message)
            
        elif 'update' in message and 'orderbook' in message and "bids" in message and "asks" in message:
            self.update_order_book(message)

        # 成交回報後，才更新部位資訊
        if 'fills' in message and 'data' in message and 'fee' in message:
            with ThreadPoolExecutor() as executor:
                executor.submit(self.execution_managing, message)

        # pass
        if x > self.last_order + timedelta(seconds=3) and self.active_orders and not self.canceled:
            self.canceled = True
            with ThreadPoolExecutor() as executor:
                executor.submit(self.ra.cancel_orders, self.ticker)
        if x > self.last_order + timedelta(seconds=6) and self.active_orders and self.canceled:
            self.active_orders = False
            self.canceled = False

    def on_error(self, error):
        self.ra.cancel_orders(self.ticker)
        print("Websocket連接錯誤，%s" % (error))
        
 
    def on_close(self):
        print("Websocket連接關閉，5秒後重新連接！")
        sys.exit(0)

    def on_open(self):
        print("Websocket連接建立成功！")
        print("資料回填中...")
        self.subscribe_auth_parts()
        self.subscribe_order_book(self.ticker)
        self._init()
        self.positions_managing(True)
        print('部位資料回填完成！')
        self.min_managing()
    
    def subscribe_order_book(self, symbol):
        tradeStr = json.dumps({"op": "subscribe","channel":"orderbook", "market":"{}".format(symbol)})
        self.ws.send(tradeStr)

    def subscribe_auth_parts(self):
        ts = int(time.time() * 1000)
        signature = hmac.new(self.secret.encode(), f'{ts}websocket_login'.encode(), digestmod=hashlib.sha256).hexdigest()
        tradeStr = json.dumps({"op": "login","args": {"key":self.key, "sign":signature, "time":ts, "subaccount":self.subaccount}})
        self.ws.send(tradeStr)
        tradeStr = json.dumps({"op": "subscribe","channel": "fills"})
        self.ws.send(tradeStr)

    def build_order_book(self, message):
        dataset = json.loads(message)
        self.bids = np.array(dataset['data']['bids'])
        self.bids_length = len(self.bids)
        self.asks = np.array(dataset['data']['asks'])   
        self.asks_length = len(self.asks)

    def update_order_book(self, message):
        dataset = json.loads(message)
        bids = dataset['data']['bids']
        asks = dataset['data']['asks']
        if len(bids) > 0:
            for bid_change in bids:
                bid_price = bid_change[0]
                bid_qty = bid_change[1]
                bid_T = self.bids.T
                bid_idx = np.where(bid_T[0]==bid_price)
                if len(bid_idx[0]) ==0:  # 原本沒有這個價格
                    bid_insert_idx = np.where(bid_T[0] > bid_price)
                    if len(bid_insert_idx[0]) == 0: # 沒有買價比他大，表示爲最高買價
                        self.bids = np.insert(self.bids, 0, [bid_price, bid_qty], axis=0)
                        if len(self.bids) > self.bids_length:
                            self.bids = self.bids[:self.bids_length]
                    else:  # 前後有價格
                        self.bids = np.insert(self.bids, bid_insert_idx[0][-1]+1, [bid_price, bid_qty], axis=0)
                        if len(self.bids) > self.bids_length:
                            self.bids = self.bids[:self.bids_length]
                else:
                    if bid_qty == 0.0:
                        self.bids = np.delete(self.bids, bid_idx[0][0], axis=0)
                    else:
                        self.bids[bid_idx[0][0]][1] = bid_qty
        if len(asks) > 0:
            for ask_change in asks:
                ask_price = ask_change[0]
                ask_qty = ask_change[1]
                ask_T = self.asks.T
                ask_idx = np.where(ask_T[0]==ask_price)
                if len(ask_idx[0]) ==0:  # 原本沒有這個價格
                    ask_insert_idx = np.where(ask_T[0] < ask_price)
                    if len(ask_insert_idx[0]) == 0: # 沒有賣價比他小，表示爲最低賣價
                        self.asks = np.insert(self.asks, 0, [ask_price, ask_qty], axis=0)
                        if len(self.asks) > self.asks_length:
                            self.asks = self.asks[:self.asks_length]
                    else:  # 前後有價格
                        self.asks = np.insert(self.asks, ask_insert_idx[0][-1]+1, [ask_price, ask_qty], axis=0)
                        if len(self.asks) > self.asks_length:
                            self.asks = self.asks[:self.asks_length]
                else:
                    if ask_qty == 0.0:
                        self.asks = np.delete(self.asks, ask_idx[0][0], axis=0)
                    else:
                        self.asks[ask_idx[0][0]][1] = ask_qty

        if not self.active_orders:
            self.active_orders = True
            if not self.dangerious:
                if not self.pause:
                    book_monitor(self.ra, self.ticker, self.bids, self.asks, self.increment, self.open_position, self.entry_price,
                        self.qty, self.set_qty, self.profit_buff)
            else:  # 低 margin 緊急處理
                self.dangerious = emergency(self.ra, self.ticker, self.bids, self.asks, self.increment, self.open_position, self.set_qty, self.dangerious)
            self.last_order = datetime.now()
    
    def _init(self):
        reqs = self.ra.list_markets()
        for req in reqs:
            symbol = str(req['name'])
            if symbol == self.ticker:
                self.increment = float(req['priceIncrement'])
                price = float(req['price'])
        reqss = self.ra.get_account_info()
        self.value = reqss['collateral']
        self.set_qty = round(0.1 * self.value / price, 4)

    def execution_managing(self, message):      # 成交是dict
        dataset = json.loads(message)
        obj = dataset['data']
        symbol = str(obj['market'])
        side = str(obj['side'])
        price = str(obj['price'])
        qty = str(obj['size'])
        ty = str(obj['liquidity'])
        if ty == 'taker':                       # 可能在速度盤，可能在減倉，暫停掛單都是好的
            self.pause = True
        print('{} | {} {} {}-order executed at {} with {} !'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        side, symbol, ty, price, qty))
        self.positions_managing(False)          # 利用api更新部位
        self._init()                            # 更新下單基準量

    def positions_managing(self, initial=False):
        dataset = self.ra.get_positions()
        for obj in dataset:
            symbol = str(obj['future'])
            if symbol == self.ticker:
                true_qty = float(obj["netSize"])
                if true_qty < 0 :
                    self.open_position = -1
                    self.entry_price = float(obj["recentAverageOpenPrice"])
                    self.qty = abs(true_qty)
                elif true_qty > 0:
                    self.open_position = 1
                    self.entry_price = float(obj["recentAverageOpenPrice"])
                    self.qty = abs(true_qty)
                elif true_qty == 0:
                    self.open_position = 0
                    self.entry_price = 0.0
                    self.qty = 0.0

    def min_managing(self):  # 這邊再把暫停打開
        reqs = self.ra.get_account_info()
        self.margin = reqs['marginFraction']
        if self.margin == None:
            self.margin = 0.0
            self.dangerious = False
            self.pause = False
        else:
            if self.margin <= self.danger_zone:
                self.dangerious = True
                self.pause = True
            else:
                self.dangerious = False
                self.pause = False
        self.value = reqs['collateral']
        print('{} | {} 部位: {} 價格: {}'.format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
            self.ticker, self.open_position*self.qty,
            round(self.entry_price, 2)))
        print(' '*19+ ' | 市值: {} USD | 維持: {} %'.format(round(self.value,2), round(self.margin*100,2)))
    

if __name__ == "__main__":
    # pass

    
