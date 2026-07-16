# 双均线策略回测系统

使用 Backtrader 构建的量化回测框架，实现双均线交叉策略，含资金管理、滑点、手续费模拟。

## 特性
- 双均线交叉策略（金叉买入/死叉卖出）
- 止损/止盈风险管理
- 夏普比率、最大回撤分析
- 胜率统计
- 参数优化（网格搜索）

## 运行

```bash
pip install -r requirements.txt
python strategy.py
```
