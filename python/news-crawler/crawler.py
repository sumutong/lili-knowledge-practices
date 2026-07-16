#!/usr/bin/env python3
"""
多线程新闻爬虫 + 情感分析系统
依赖: pip install requests beautifulsoup4 jieba snownlp matplotlib pandas
"""
import concurrent.futures
import json
import logging
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import jieba
import matplotlib.pyplot as plt
import pandas as pd
import requests
from bs4 import BeautifulSoup
from snownlp import SnowNLP

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("NewsCrawler")

# ─── 数据模型 ─────────────────────────────────────────────
@dataclass
class Article:
    title: str
    url: str
    content: str = ""
    source: str = ""
    publish_time: Optional[datetime] = None
    sentiment_score: float = 0.0
    sentiment_label: str = ""
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content[:200],
            "source": self.source,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "keywords": self.keywords,
        }


# ─── 基础爬虫类 ───────────────────────────────────────────
class BaseCrawler:
    """爬虫基类：封装请求、重试、User-Agent 轮换"""

    HEADERS = [
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Safari/605.1.15"
            )
        },
    ]
    TIMEOUT = 15
    MAX_RETRIES = 3

    def __init__(self, name: str):
        self.name = name
        self.session = requests.Session()
        self._header_idx = 0

    def _rotate_headers(self) -> dict:
        self._header_idx = (self._header_idx + 1) % len(self.HEADERS)
        return self.HEADERS[self._header_idx]

    def fetch(self, url: str) -> Optional[str]:
        """带重试的页面抓取"""
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.get(
                    url,
                    headers=self._rotate_headers(),
                    timeout=self.TIMEOUT,
                )
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            except requests.RequestException as e:
                logger.warning(f"[{self.name}] 请求失败 (attempt {attempt+1}): {e}")
                time.sleep(2 ** attempt)
        logger.error(f"[{self.name}] 放弃请求: {url}")
        return None


# ─── 具体爬虫实现 ─────────────────────────────────────────
class HackerNewsCrawler(BaseCrawler):
    """Hacker News 爬虫"""

    BASE = "https://news.ycombinator.com/"

    def crawl(self, limit: int = 10) -> list[Article]:
        html = self.fetch(self.BASE)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        articles: list[Article] = []
        for row in soup.select("tr.athing")[:limit]:
            title_el = row.select_one("td.title span.titleline a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")
            if url.startswith("item?"):
                url = self.BASE + url
            articles.append(
                Article(title=title, url=url, source="HackerNews")
            )
        return articles


class ZhihuDailyCrawler(BaseCrawler):
    """知乎日报爬虫"""

    BASE = "https://news-at.zhihu.com/api/4/news/latest"

    def crawl(self, limit: int = 10) -> list[Article]:
        html = self.fetch(self.BASE)
        if not html:
            return []
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return []
        articles: list[Article] = []
        for story in data.get("stories", [])[:limit]:
            articles.append(
                Article(
                    title=story.get("title", ""),
                    url=story.get("url", f"https://daily.zhihu.com/story/{story['id']}"),
                    source="知乎日报",
                )
            )
        return articles


# ─── 内容提取器 ───────────────────────────────────────────
class ContentExtractor:
    """通用正文提取 —— 基于 readability-lxml 思路的简化版"""

    @staticmethod
    def extract(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        # 移除脚本和样式
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        # 优先从常见内容区提取
        candidates = soup.select(
            "article, main, .post-content, .article-content, .entry-content, #content"
        )
        if candidates:
            text = " ".join(candidates[0].stripped_strings)
        else:
            text = " ".join(soup.stripped_strings)
        # 清洗
        text = re.sub(r"\s+", " ", text).strip()
        return text


# ─── 情感分析器 ───────────────────────────────────────────
class SentimentAnalyzer:
    """基于 SnowNLP 的中文情感分析"""

    @staticmethod
    def analyze(text: str) -> tuple[float, str]:
        if not text or len(text) < 10:
            return 0.5, "neutral"
        try:
            s = SnowNLP(text)
            score = s.sentiments  # 0-1, 越接近 1 越正面
        except Exception:
            score = 0.5

        if score > 0.6:
            label = "positive"
        elif score < 0.4:
            label = "negative"
        else:
            label = "neutral"
        return round(score, 4), label


# ─── 关键词提取器 ─────────────────────────────────────────
class KeywordExtractor:
    """基于 jieba + TF-IDF 的关键词提取"""

    STOP_WORDS = set(
        "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 "
        "会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 而 为 所以 因为 "
        "可以 这个 那个 如果 虽然 但是 然后 之后 还是 我们 他们 她们 它们 啊 吧 呢 吗".split()
    )

    @staticmethod
    def extract(text: str, topk: int = 5) -> list[str]:
        if not text:
            return []
        words = jieba.cut(text)
        filtered = [
            w for w in words
            if len(w) >= 2 and w not in KeywordExtractor.STOP_WORDS
        ]
        counter = Counter(filtered)
        return [w for w, _ in counter.most_common(topk)]


# ─── 可视化报告 ───────────────────────────────────────────
class ReportGenerator:
    """生成情感分布图和 HTML 报告"""

    @staticmethod
    def generate(articles: list[Article], output_dir: str = "./output"):
        os.makedirs(output_dir, exist_ok=True)
        df = pd.DataFrame([a.to_dict() for a in articles])

        # 情感分布饼图
        sentiment_counts = df["sentiment_label"].value_counts()
        colors = {"positive": "#4CAF50", "neutral": "#FFC107", "negative": "#F44336"}
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        wedges, texts, autotexts = ax1.pie(
            sentiment_counts,
            labels=sentiment_counts.index,
            colors=[colors.get(l, "#999") for l in sentiment_counts.index],
            autopct="%1.1f%%",
            startangle=90,
        )
        ax1.set_title("情感分布", fontsize=14)

        # 来源分布条形图
        source_counts = df["source"].value_counts()
        bars = ax2.bar(source_counts.index, source_counts.values, color="#2196F3")
        ax2.set_title("新闻来源分布", fontsize=14)
        ax2.set_ylabel("数量")
        for bar in bars:
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.3,
                str(int(bar.get_height())),
                ha="center",
                va="bottom",
            )

        plt.tight_layout()
        chart_path = os.path.join(output_dir, "report_chart.png")
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info(f"图表已保存: {chart_path}")

        # HTML 报告
        html_path = os.path.join(output_dir, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(
                f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>新闻爬虫分析报告</title>
    <style>
        body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; border-bottom: 3px solid #2196F3; padding-bottom: 10px; }}
        .article {{ background: white; border-radius: 8px; padding: 15px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .title {{ font-size: 16px; font-weight: bold; color: #1976D2; }}
        .source {{ color: #666; font-size: 12px; }}
        .sentiment {{ padding: 2px 8px; border-radius: 12px; font-size: 12px; color: white; }}
        .positive {{ background: #4CAF50; }} .negative {{ background: #F44336; }} .neutral {{ background: #FFC107; color: #333; }}
        .keywords {{ margin-top: 5px; }}
        .kw {{ display: inline-block; background: #E3F2FD; padding: 2px 8px; border-radius: 10px; margin: 2px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>📊 新闻爬虫分析报告</h1>
    <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 共 {len(articles)} 篇文章</p>
    <img src="report_chart.png" style="max-width:100%; border-radius:8px;">
    <h2>📰 文章列表</h2>"""
            )
            for a in articles:
                label_css = a.sentiment_label
                kws = "".join(
                    f'<span class="kw">{kw}</span>' for kw in a.keywords
                )
                f.write(
                    f"""<div class="article">
    <div class="title"><a href="{a.url}" target="_blank">{a.title}</a></div>
    <div class="source">{a.source} | <span class="sentiment {label_css}">{a.sentiment_label} ({a.sentiment_score})</span></div>
    <div class="keywords">{kws}</div>
</div>"""
                )
            f.write("</body></html>")
        logger.info(f"HTML 报告已保存: {html_path}")


# ─── 主流程 ───────────────────────────────────────────────
def main():
    start = time.perf_counter()
    crawlers = [
        HackerNewsCrawler("HackerNews"),
        ZhihuDailyCrawler("ZhihuDaily"),
    ]

    # 并发抓取标题
    all_articles: list[Article] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(c.crawl): c for c in crawlers}
        for future in concurrent.futures.as_completed(futures):
            crawler = futures[future]
            try:
                result = future.result()
                all_articles.extend(result)
                logger.info(f"[{crawler.name}] 获取 {len(result)} 篇文章")
            except Exception as e:
                logger.error(f"[{crawler.name}] 异常: {e}")

    logger.info(f"共获取 {len(all_articles)} 篇文章，开始内容提取...")

    # 并发提取正文 + 分析
    extractor = ContentExtractor()
    sentiment = SentimentAnalyzer()
    keyword_ext = KeywordExtractor()
    base_crawler = BaseCrawler("fetcher")

    def process_article(article: Article) -> Article:
        if article.content:
            return article
        html = base_crawler.fetch(article.url)
        if html:
            article.content = extractor.extract(html)
            article.sentiment_score, article.sentiment_label = sentiment.analyze(
                article.content
            )
            article.keywords = keyword_ext.extract(article.content, topk=5)
        return article

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(process_article, all_articles))

    # 生成报告
    ReportGenerator.generate(all_articles, output_dir="./output/crawl_report")
    elapsed = time.perf_counter() - start
    logger.info(f"✅ 全部完成，耗时 {elapsed:.2f}s")

    # 输出摘要
    for a in all_articles[:5]:
        print(f"\n📰 {a.title}")
        print(f"   {a.source} | {a.sentiment_label} ({a.sentiment_score})")
        print(f"   关键词: {', '.join(a.keywords)}")

    with open("./output/crawl_report/articles.json", "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in all_articles], f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
