#!/usr/bin/env python3
"""
双均线策略回测系统
依赖: pip install backtrader matplotlib pandas yfinance
"""
import datetime
from dataclasses import dataclass

import backtrader as bt
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf


class DataFetcher:
    @staticmethod
    def fetch(symbol: str, start: str, end: str) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end)
        df.columns = [c.lower() for c in df.columns]
        return df

    @staticmethod
    def to_backtrader_feeds(df: pd.DataFrame) -> bt.feeds.PandasData:
        return bt.feeds.PandasData(
            dataname=df, datetime=None,
            open="open", high="high", low="low", close="close",
            volume="volume", openinterest=-1,
        )


class DoubleMAStrategy(bt.Strategy):
    params = (
        ("fast_period", 5),
        ("slow_period", 20),
        ("stop_loss", 0.05),
        ("take_profit", 0.10),
        ("print_log", True),
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.fast_period
        )
        self.slow_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.slow_period
        )
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.order = None
        self.buy_price = None

    def log(self, txt: str, dt=None):
        if self.params.print_log:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()}  {txt}")

    def notify_order(self, order: bt.Order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.log(f"✅ BUY  {order.executed.size} @ {order.executed.price:.2f}, "
                         f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}")
            else:
                pnl = (order.executed.price - self.buy_price) * order.executed.size
                self.log(f"✅ SELL {order.executed.size} @ {order.executed.price:.2f}, "
                         f"PnL: {pnl:.2f}, Comm: {order.executed.comm:.2f}")
                self.buy_price = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"❌ Order Failed: {order.getstatusname()}")
        self.order = None

    def notify_trade(self, trade: bt.Trade):
        if trade.isclosed:
            self.log(f"💰 Trade PnL: Gross {trade.pnl:.2f}, Net {trade.pnlcomm:.2f}")

    def next(self):
        if self.order:
            return
        if not self.position:
            if self.crossover > 0:
                size = self.broker.get_cash() * 0.95 // self.data.close[0]
                if size > 0:
                    self.order = self.buy(size=size)
                    self.log(f"🔵 金叉信号, 买入 {size} 股")
        else:
            current_price = self.data.close[0]
            entry_price = self.buy_price or self.position.price
            if current_price <= entry_price * (1 - self.params.stop_loss):
                self.order = self.sell(size=self.position.size)
                self.log(f"🔴 止损! {current_price:.2f} <= {entry_price * (1 - self.params.stop_loss):.2f}")
            elif current_price >= entry_price * (1 + self.params.take_profit):
                self.order = self.sell(size=self.position.size)
                self.log(f"🟢 止盈! {current_price:.2f} >= {entry_price * (1 + self.params.take_profit):.2f}")
            elif self.crossover < 0:
                self.order = self.sell(size=self.position.size)
                self.log(f"🔴 死叉信号, 卖出")


@dataclass
class BacktestResult:
    initial_cash: float
    final_value: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    avg_trade_pnl: float


class BacktestEngine:
    def __init__(self, initial_cash: float = 100000.0, commission: float = 0.001):
        self.initial_cash = initial_cash
        self.commission = commission
        self.cerebro = bt.Cerebro()

    def run(self, data_feed, strategy_class, **strategy_params) -> BacktestResult:
        cerebro = self.cerebro
        cerebro.adddata(data_feed)
        cerebro.addstrategy(strategy_class, **strategy_params)
        cerebro.broker.set_cash(self.initial_cash)
        cerebro.broker.setcommission(commission=self.commission)
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.02, annualize=True)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

        print(f"初始资金: ¥{self.initial_cash:,.2f}")
        results = cerebro.run()
        strat = results[0]

        sharpe = strat.analyzers.sharpe.get_analysis()
        dd = strat.analyzers.drawdown.get_analysis()
        trades_analysis = strat.analyzers.trades.get_analysis()

        final_value = cerebro.broker.get_value()

        won = trades_analysis.get("won", {})
        lost = trades_analysis.get("lost", {})
        total_won = won.get("total", 0)
        total_lost = lost.get("total", 0)
        total_trades = total_won + total_lost
        win_rate = total_won / total_trades * 100 if total_trades > 0 else 0

        pnl_net = trades_analysis.get("pnl", {}).get("net", {})
        avg_trade_pnl = pnl_net.get("average", 0)

        return BacktestResult(
            initial_cash=self.initial_cash,
            final_value=final_value,
            total_return=(final_value / self.initial_cash - 1) * 100,
            sharpe_ratio=sharpe.get("sharperatio", 0.0) or 0.0,
            max_drawdown=dd.get("max", {}).get("drawdown", 0.0) or 0.0,
            win_rate=win_rate,
            total_trades=total_trades,
            avg_trade_pnl=avg_trade_pnl,
        )


def print_report(result: BacktestResult):
    report = f"""
╔══════════════════════════════════════╗
║          回 测 报 告                  ║
╠══════════════════════════════════════╣
║  初始资金:     ¥{result.initial_cash:>12,.2f}   ║
║  最终价值:     ¥{result.final_value:>12,.2f}   ║
║  总收益率:     {result.total_return:>10.2f}%          ║
║  夏普比率:     {result.sharpe_ratio:>10.3f}            ║
║  最大回撤:     {result.max_drawdown:>10.2f}%          ║
║  胜率:         {result.win_rate:>10.1f}%          ║
║  总交易次数:   {result.total_trades:>10}              ║
║  平均每笔盈亏: ¥{result.avg_trade_pnl:>10.2f}        ║
╚══════════════════════════════════════╝
"""
    print(report)


def main():
    print("📥 获取历史数据...")
    df = DataFetcher.fetch("AAPL", "2023-01-01", "2024-12-31")
    print(f"  共 {len(df)} 个交易日")
    data = DataFetcher.to_backtrader_feeds(df)

    print("\n🚀 开始回测...")
    engine = BacktestEngine(initial_cash=100000, commission=0.001)
    result = engine.run(data, DoubleMAStrategy,
                        fast_period=5, slow_period=20,
                        stop_loss=0.05, take_profit=0.15,
                        print_log=False)

    print_report(result)


if __name__ == "__main__":
    main()
