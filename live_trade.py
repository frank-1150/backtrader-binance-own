import datetime as dt
import json
import time
import backtrader as bt
import numpy as np

from backtrader_binance import BinanceStore


class GridStrategy(bt.Strategy):
    params = (
        ('fixed_amount', 30),
        ('size_up_list', [1, 1.2, 2.5, 5.5, 11.9, 26.6]),
        ('grid', [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]),
        ('take_profit', 0.006),
        ('sma_period', 60),
    )

    def __init__(self, plot_save_folder='plots'):
        self.grid_start_price = None
        self.current_asset = 0
        self.plot_save_folder = plot_save_folder
        self.time_list = []
        self.pnl_list = []
        self.position_size_list = []
        self.position_price_list = []
        self.net_worth_list = []
        self.base_asset_price_list = []
        self.sma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.sma_period)

    def next(self):
        # 记录当前价格和相对于grid_start_price的涨跌幅
        current_price = self.data.close[0]
        print(f'当前时间：{self.data.datetime.datetime()}，当前价格：{current_price}')
        self.print_open_orders()
        if self.grid_start_price is not None:
            percent = (current_price - self.grid_start_price) / self.grid_start_price
            print(f'grid_start_price: {self.grid_start_price}, 相对于grid_start_price的涨跌幅：{percent:.2%}')

        # 如果当前没有资产
        if self.position.size == 0:
            # 检查是否有未成交的买单
            if not self.broker.get_orders_open():
                # 开始状态，计算过去20个周期内的平均close价格，以此为grid_start_price
                self.grid_start_price = np.mean(self.sma[0])
                self.grid_start_price = min(self.grid_start_price, self.data.close[0])
                print(f'开始状态, grid_start_price: {self.grid_start_price}')
                # 挂出买入单
                for grid_percent in self.params.grid:
                    buy_price = self.grid_start_price * (1 - grid_percent)
                    amount = self.params.fixed_amount * self.params.size_up_list[self.params.grid.index(grid_percent)]
                    qty = amount / buy_price
                    buy_order = self.buy(price=buy_price, exectype=bt.Order.Limit, size=qty)
                    print(f'遍历挂出买入单：{buy_order.price}，数量：{buy_order.size}')
                    time.sleep(0.5)
                self.print_open_orders()

        # 如果当前有资产
        else:
            # 展示成本价和盈亏比例
            print(f'当前成本价：{self.position.price}，当前盈亏比例：{(current_price - self.position.price) / self.position.price:.2%}')
            # 如果有买单和卖单，不需要操作
            # if self.get_open_orders():
            #     return

            # # 如果只有卖单，等待资金释放
            # elif self.current_asset.sell_order is not None:
            #     return

            # # 如果只有买单，卖出资产
            # elif self.current_asset.buy_order is not None:
            #     self.sell(size=self.current_asset.size, price=self.data.close * 1.006, exectype=bt.Order.Limit)
        # 记录当前时间
        # self.time_list.append(self.data.datetime.datetime())
        # self.position_size_list.append(self.position.size if self.position else 0)
        # self.position_price_list.append(self.position.price if self.position else None)
        # pnl = self.broker.get_value() - self.broker.startingcash
        # self.pnl_list.append(pnl)
        # self.net_worth_list.append(self.broker.get_value())
        # self.base_asset_price_list.append(self.data.close[0])
    def print_open_orders(self):
        for ord in self.broker.get_orders_open():
            print('当前的挂单:', ord.price, ord.size, 'isbuy=', ord.isbuy(), 'issell=', ord.issell())

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                print(f"买单成交{order.binance_order['symbol']}，买入价格：{order.executed.price}，买入数量：{order.executed.size}，买入时间：{self.data.datetime.datetime()}")
                # 撤掉已有的卖单
                for ord in self.broker.get_orders_open():
                    # print('当前的挂单:', ord.price, ord.size, 'isbuy=', ord.isbuy(), 'issell=', ord.issell())
                    if ord.issell() and ord.binance_order['symbol'] == order.binance_order['symbol']:
                        print(f'撤掉已有的卖单：{ord}')
                        self.cancel(ord)
                        time.sleep(0.25)
                # 买单成交，挂出止盈卖单
                self.current_asset += order.executed.size
                
                # if self.position.size == self.current_asset:
                sell_price = self.position.price * (1 + self.params.take_profit)
                sell_order = self.sell(price=sell_price, exectype=bt.Order.Limit, size=self.position.size)
                self.print_open_orders()
                print(f'挂出止盈卖单：{sell_price}，数量：{sell_order.size}, current_asset: {self.current_asset}')
                    # print(f'买入成交，撤销所有卖单，挂出新的止盈后，当前的挂单')
                    # self.print_open_orders()
                # else:
                #     print(f'多个买单成交, current_asset: {self.current_asset}, 当前成交order size: {order.executed.size}，position size: {self.position.size}')
            elif order.issell():
                # 卖单成交，清仓成功, 重置grid_start_price，撤掉所有未成交的单
                print(f'卖单成交，清仓成功, 重置grid_start_price，撤掉所有未成交的单：{order.executed.price}，数量：{order.executed.size}，清仓时间：{self.data.datetime.datetime()}')
                self.grid_start_price = None
                for ord in self.broker.get_orders_open():
                    print(f'撤掉所有未成交的单：{ord}')
                    self.cancel(ord)
                    time.sleep(0.5)
                self.current_asset = 0
                print(f'卖出成交，撤销所有单，当前的挂单')
                self.print_open_orders()
                # print(f'清仓成功，清仓价格：{order.executed.price}，清仓数量：{order.executed.size}，清仓时间：{self.data.datetime.datetime()}')

    def notify_trade(self, trade):
        print(f'交易完成，交易价格：{trade.price}，交易数量：{trade.size}，交易时间：{self.data.datetime.datetime()}')

if __name__ == '__main__':
    cerebro = bt.Cerebro(quicknotify=True)
    # 从本地api_key.json中读取api_key和api_secret
    with open('api_key.json', 'r') as f:
        file = json.load(f)
        api_key = file['api_key']
        api_secret = file['api_secret']

    print("got api key and secret")
    store = BinanceStore(
        api_key=api_key,
        api_secret=api_secret,
        coin_refer='ROSE',
        coin_target='USDT',
        testnet=False,
        type='future')
    broker = store.getbroker()
    cerebro.setbroker(broker)
    print('set broker')

    from_date = dt.datetime.utcnow() - dt.timedelta(minutes=65)
    data = store.getdata(
        timeframe_in_minutes=1,
        start_date=from_date)

    cerebro.addstrategy(GridStrategy)
    cerebro.adddata(data)
    cerebro.run()
