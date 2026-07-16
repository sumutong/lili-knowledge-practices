#!/usr/bin/env python3
"""
销售数据分析报表系统
依赖: pip install pandas matplotlib seaborn openpyxl jinja2
"""
import os
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import seaborn as sns
from jinja2 import Template

sns.set_theme(style="whitegrid", palette="Set2", font="sans-serif")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["figure.dpi"] = 150
OUTPUT_DIR = Path("./analysis_output")


class DataLoader:
    @staticmethod
    def from_csv(path: str, **kwargs) -> pd.DataFrame:
        return pd.read_csv(path, **kwargs)

    @staticmethod
    def from_excel(path: str, sheet_name: str = 0, **kwargs) -> pd.DataFrame:
        return pd.read_excel(path, sheet_name=sheet_name, **kwargs)

    @staticmethod
    def generate_sample_data(n: int = 1000) -> pd.DataFrame:
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=n, freq="D")
        categories = np.random.choice(["电子产品", "服装", "食品", "家居", "书籍"], n)
        regions = np.random.choice(["华北", "华东", "华南", "西部", "华中"], n)
        channels = np.random.choice(["线上", "线下", "直播带货"], n, p=[0.5, 0.3, 0.2])
        base_price = np.random.lognormal(mean=4, sigma=1, size=n)
        quantity = np.random.randint(1, 20, n)
        discount = np.random.choice([0, 0.1, 0.2, 0.3, 0.5], n, p=[0.5, 0.2, 0.15, 0.1, 0.05])
        df = pd.DataFrame({
            "date": dates, "category": categories, "region": regions, "channel": channels,
            "unit_price": np.round(base_price, 2), "quantity": quantity, "discount": discount,
        })
        df["revenue"] = df["unit_price"] * df["quantity"] * (1 - df["discount"])
        df["cost"] = df["revenue"] * np.random.uniform(0.4, 0.7, n)
        df["profit"] = df["revenue"] - df["cost"]
        df["profit_margin"] = df["profit"] / df["revenue"]
        return df


class SalesAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._preprocess()

    def _preprocess(self):
        if "date" in self.df.columns:
            self.df["date"] = pd.to_datetime(self.df["date"])
            self.df["year"] = self.df["date"].dt.year
            self.df["month"] = self.df["date"].dt.month
            self.df["quarter"] = self.df["date"].dt.quarter
            self.df["weekday"] = self.df["date"].dt.day_name()

    def overview(self) -> dict:
        df = self.df
        return {
            "total_revenue": df["revenue"].sum(),
            "total_profit": df["profit"].sum(),
            "avg_profit_margin": df["profit_margin"].mean(),
            "total_orders": len(df),
            "avg_order_value": df["revenue"].mean(),
            "date_range": (
                df["date"].min().strftime("%Y-%m-%d"),
                df["date"].max().strftime("%Y-%m-%d"),
            ) if "date" in df.columns else ("N/A", "N/A"),
        }

    def revenue_by_category(self) -> pd.DataFrame:
        return (
            self.df.groupby("category")
            .agg(revenue=("revenue", "sum"), profit=("profit", "sum"),
                 orders=("revenue", "count"), avg_margin=("profit_margin", "mean"))
            .sort_values("revenue", ascending=False)
        )

    def revenue_trend(self, freq: str = "M") -> pd.DataFrame:
        if "date" not in self.df.columns:
            return pd.DataFrame()
        return (
            self.df.set_index("date").resample(freq)[["revenue", "profit"]].sum().reset_index()
        )

    def channel_analysis(self) -> pd.DataFrame:
        if "channel" not in self.df.columns:
            return pd.DataFrame()
        return (
            self.df.groupby("channel")
            .agg(revenue=("revenue", "sum"), orders=("revenue", "count"),
                 avg_order=("revenue", "mean"))
            .sort_values("revenue", ascending=False)
        )

    def region_heatmap(self) -> pd.DataFrame:
        if "region" not in self.df.columns or "category" not in self.df.columns:
            return pd.DataFrame()
        return pd.crosstab(self.df["region"], self.df["category"],
                           values=self.df["revenue"], aggfunc="sum", normalize="index")


class ChartEngine:
    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.charts: dict[str, str] = {}

    def _save(self, name: str) -> str:
        path = self.output_dir / f"{name}.png"
        plt.tight_layout()
        plt.savefig(path, bbox_inches="tight")
        plt.close()
        self.charts[name] = str(path)
        return str(path)

    def bar_revenue_by_category(self, analyzer: SalesAnalyzer):
        data = analyzer.revenue_by_category()
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].barh(data.index, data["revenue"] / 10000, color=sns.color_palette("Set2"))
        axes[0].set_title("各类别收入（万元）")
        axes[0].set_xlabel("收入（万元）")
        axes[0].invert_yaxis()
        bars = axes[1].bar(data.index, data["avg_margin"] * 100, color=sns.color_palette("Set3"))
        axes[1].set_title("各类别平均利润率 (%)")
        axes[1].set_ylabel("利润率 (%)")
        axes[1].tick_params(axis="x", rotation=45)
        for bar, val in zip(bars, data["avg_margin"]):
            axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                         f"{val*100:.1f}%", ha="center", fontsize=9)
        return self._save("category_revenue")

    def line_trend(self, analyzer: SalesAnalyzer):
        trend = analyzer.revenue_trend("M")
        if trend.empty:
            return None
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(trend["date"], trend["revenue"] / 10000, "o-",
                label="收入", color="#2ecc71", linewidth=2, markersize=4)
        ax.plot(trend["date"], trend["profit"] / 10000, "s--",
                label="利润", color="#e74c3c", linewidth=2, markersize=4)
        ax.fill_between(trend["date"], 0, trend["revenue"] / 10000, alpha=0.1, color="#2ecc71")
        ax.set_title("月度收入与利润趋势", fontsize=14, fontweight="bold")
        ax.set_xlabel("日期")
        ax.set_ylabel("金额（万元）")
        ax.legend(loc="upper left")
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f万"))
        fig.autofmt_xdate()
        return self._save("revenue_trend")

    def pie_channel(self, analyzer: SalesAnalyzer):
        data = analyzer.channel_analysis()
        if data.empty:
            return None
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        axes[0].pie(data["revenue"], labels=data.index, autopct="%1.1f%%",
                    colors=sns.color_palette("Set2"), startangle=90, explode=(0.02, 0.02, 0.02))
        axes[0].set_title("各渠道收入占比")
        axes[1].pie(data["orders"], labels=data.index, autopct="%1.1f%%",
                    colors=sns.color_palette("Set3"), startangle=90, explode=(0.02, 0.02, 0.02))
        axes[1].set_title("各渠道订单量占比")
        return self._save("channel_pie")

    def heatmap_region(self, analyzer: SalesAnalyzer):
        data = analyzer.region_heatmap()
        if data.empty:
            return None
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(data * 100, annot=True, fmt=".1f", cmap="YlOrRd",
                    linewidths=0.5, cbar_kws={"label": "收入占比 (%)"}, ax=ax)
        ax.set_title("地区 × 品类 收入热力图 (%)", fontsize=14, fontweight="bold")
        return self._save("region_heatmap")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
               max-width: 1100px; margin: auto; padding: 40px 20px;
               background: #f8f9fa; color: #333; }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #2c3e50; margin: 30px 0 15px; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 15px; margin: 20px 0; }
        .kpi { background: white; border-radius: 8px; padding: 20px; text-align: center;
               box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .kpi .label { font-size: 0.85em; color: #7f8c8d; margin-bottom: 8px; }
        .kpi .value { font-size: 1.8em; font-weight: 700; color: #2c3e50; }
        img { max-width: 100%; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); margin: 15px 0; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0;
                background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ecf0f1; }
        th { background: #3498db; color: white; font-weight: 600; }
        tr:hover { background: #f8f9fa; }
        .footer { text-align: center; color: #95a5a6; margin-top: 40px; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>{{ title }}</h1>
    <p>生成时间: {{ generated_at }}</p>
    <h2>📊 核心指标</h2>
    <div class="kpi-grid">
        {% for kpi in kpis %}
        <div class="kpi"><div class="label">{{ kpi.label }}</div><div class="value">{{ kpi.value }}</div></div>
        {% endfor %}
    </div>
    <h2>📈 收入趋势</h2>
    <img src="{{ trend_chart }}" alt="收入趋势">
    <h2>🏷️ 品类分析</h2>
    <img src="{{ category_chart }}" alt="品类分析">
    {{ category_table }}
    <h2>📡 渠道分析</h2>
    <img src="{{ channel_chart }}" alt="渠道分析">
    <h2>🗺️ 地区热力图</h2>
    <img src="{{ heatmap_chart }}" alt="地区热力图">
    <div class="footer"><p>自动生成于 {{ generated_at }} | Python 数据分析实战</p></div>
</body>
</html>
"""


class ReportGenerator:
    def __init__(self, analyzer: SalesAnalyzer, charts: ChartEngine):
        self.analyzer = analyzer
        self.charts = charts

    def generate_html(self, title: str = "销售数据分析报告") -> str:
        overview = self.analyzer.overview()
        kpis = [
            {"label": "总营收", "value": f"¥{overview['total_revenue']:,.0f}"},
            {"label": "总利润", "value": f"¥{overview['total_profit']:,.0f}"},
            {"label": "平均利润率", "value": f"{overview['avg_profit_margin']:.1%}"},
            {"label": "总订单数", "value": f"{overview['total_orders']:,}"},
            {"label": "客单价", "value": f"¥{overview['avg_order_value']:,.2f}"},
        ]
        category_df = self.analyzer.revenue_by_category()
        category_table = category_df.to_html(float_format=lambda x: f"{x:,.2f}" if abs(x) > 1 else f"{x:.2%}")
        template = Template(HTML_TEMPLATE)
        html = template.render(
            title=title, generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            kpis=kpis,
            trend_chart=os.path.basename(self.charts.charts.get("revenue_trend", "")),
            category_chart=os.path.basename(self.charts.charts.get("category_revenue", "")),
            category_table=category_table,
            channel_chart=os.path.basename(self.charts.charts.get("channel_pie", "")),
            heatmap_chart=os.path.basename(self.charts.charts.get("region_heatmap", "")),
        )
        path = OUTPUT_DIR / "report.html"
        path.write_text(html, encoding="utf-8")
        return str(path)

    def generate_markdown(self) -> str:
        overview = self.analyzer.overview()
        lines = [
            "# 销售数据分析报告",
            f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n## 核心指标",
            f"\n| 指标 | 数值 |",
            f"|------|------|",
            f"| 总营收 | ¥{overview['total_revenue']:,.0f} |",
            f"| 总利润 | ¥{overview['total_profit']:,.0f} |",
            f"| 平均利润率 | {overview['avg_profit_margin']:.1%} |",
            f"| 总订单数 | {overview['total_orders']:,} |",
            f"| 客单价 | ¥{overview['avg_order_value']:,.2f} |",
            f"\n## 品类分析\n",
            self.analyzer.revenue_by_category().to_markdown(floatfmt=",.2f"),
        ]
        channel = self.analyzer.channel_analysis()
        if not channel.empty:
            lines.append(f"\n## 渠道分析\n")
            lines.append(channel.to_markdown(floatfmt=",.2f"))
        lines.append(f"\n## 可视化图表\n")
        for name, path in self.charts.charts.items():
            lines.append(f"![{name}]({os.path.basename(path)})")
        md = "\n".join(lines)
        path = OUTPUT_DIR / "report.md"
        path.write_text(md, encoding="utf-8")
        return str(path)


def main():
    print("=" * 60)
    print("  销售数据分析报表系统")
    print("=" * 60)
    print("\n[1/5] 加载数据...")
    df = DataLoader.generate_sample_data(500)
    print(f"  已加载 {len(df)} 条记录")
    print("[2/5] 执行分析...")
    analyzer = SalesAnalyzer(df)
    overview = analyzer.overview()
    print(f"  总营收: ¥{overview['total_revenue']:,.0f}")
    print(f"  总利润: ¥{overview['total_profit']:,.0f}")
    print("[3/5] 生成图表...")
    charts = ChartEngine()
    charts.bar_revenue_by_category(analyzer)
    charts.line_trend(analyzer)
    charts.pie_channel(analyzer)
    charts.heatmap_region(analyzer)
    for name, path in charts.charts.items():
        print(f"  ✅ {name}.png")
    print("[4/5] 生成报告...")
    reporter = ReportGenerator(analyzer, charts)
    html_path = reporter.generate_html()
    md_path = reporter.generate_markdown()
    print(f"  HTML: {html_path}")
    print(f"  Markdown: {md_path}")
    print("\n[5/5] 品类收入排名:")
    print(analyzer.revenue_by_category().to_markdown(floatfmt=",.2f"))
    print(f"\n✅ 完成！报告目录: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
