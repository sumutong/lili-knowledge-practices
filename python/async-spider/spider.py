#!/usr/bin/env python3
"""
高性能异步爬虫框架
依赖: pip install aiohttp aiodns lxml beautifulsoup4
"""
import asyncio
import hashlib
import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AsyncSpider")

# ─── 配置 ─────────────────────────────────────────────────
@dataclass
class SpiderConfig:
    start_urls: list[str] = field(default_factory=list)
    concurrency: int = 10
    request_delay: float = 0.1
    max_retries: int = 3
    timeout: int = 30
    headers: dict = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (compatible; AsyncSpider/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    proxy_pool: list[str] = field(default_factory=list)
    allowed_domains: set[str] = field(default_factory=set)
    max_depth: int = 3
    output_dir: str = "./spider_output"


@dataclass
class CrawlResult:
    url: str
    status: int = 0
    html: str = ""
    headers: dict = field(default_factory=dict)
    elapsed: float = 0.0
    error: str = ""
    depth: int = 0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class URLFrontier:
    def __init__(self):
        self._queue: deque = deque()
        self._seen: set[str] = set()
        self._lock = asyncio.Lock()

    async def push(self, url: str, depth: int = 0) -> bool:
        parsed = urlparse(url)
        normalized = urlunparse(parsed._replace(fragment=""))
        async with self._lock:
            if normalized in self._seen:
                return False
            self._seen.add(normalized)
            self._queue.append((normalized, depth))
            return True

    async def pop(self) -> Optional[tuple[str, int]]:
        async with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    async def __aiter__(self) -> AsyncIterator[tuple[str, int]]:
        while True:
            item = await self.pop()
            if item is None:
                break
            yield item

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def seen_count(self) -> int:
        return len(self._seen)


class Parser:
    @staticmethod
    def extract_links(html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("javascript:") or href.startswith("#"):
                continue
            absolute = urljoin(base_url, href)
            links.append(absolute)
        return links

    @staticmethod
    def extract_text(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return re.sub(r"\n\s*\n", "\n", text)

    @staticmethod
    def extract_title(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else ""

    @staticmethod
    def extract_structured(html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data = {
            "title": Parser.extract_title(html),
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
            "links": Parser.extract_links(html, ""),
            "images": [
                img.get("src", "") for img in soup.find_all("img", src=True)
            ],
            "meta": {
                meta.get("name", meta.get("property", "")): meta.get("content", "")
                for meta in soup.find_all("meta")
                if meta.get("name") or meta.get("property")
            },
        }
        return data


class AsyncSpider:
    def __init__(self, config: SpiderConfig):
        self.config = config
        self.frontier = URLFrontier()
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.results: list[CrawlResult] = []
        self._proxy_idx = 0
        self._stats = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
        }

    def _next_proxy(self) -> Optional[str]:
        if not self.config.proxy_pool:
            return None
        proxy = self.config.proxy_pool[self._proxy_idx % len(self.config.proxy_pool)]
        self._proxy_idx += 1
        return proxy

    async def _fetch(self, url: str) -> CrawlResult:
        start = time.perf_counter()
        last_error = ""
        for attempt in range(self.config.max_retries):
            try:
                proxy = self._next_proxy()
                connector = None
                if proxy:
                    connector = aiohttp.TCPConnector(ssl=False)
                async with self.session.get(
                    url,
                    headers=self.config.headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    proxy=proxy,
                    connector=connector,
                ) as resp:
                    html = await resp.text()
                    elapsed = time.perf_counter() - start
                    return CrawlResult(
                        url=url, status=resp.status, html=html,
                        headers=dict(resp.headers), elapsed=elapsed,
                    )
            except asyncio.TimeoutError:
                last_error = f"Timeout ({self.config.timeout}s)"
            except aiohttp.ClientError as e:
                last_error = f"HTTP: {e}"
            except Exception as e:
                last_error = str(e)
            if attempt < self.config.max_retries - 1:
                backoff = 2 ** attempt
                await asyncio.sleep(backoff)
        return CrawlResult(
            url=url, elapsed=time.perf_counter() - start,
            error=f"Max retries ({self.config.max_retries}): {last_error}",
        )

    async def _worker(self, worker_id: int):
        async for url, depth in self.frontier:
            async with self.semaphore:
                logger.debug(f"[Worker-{worker_id}] Crawling: {url} (depth={depth})")
                result = await self._fetch(url)
                result.depth = depth
                self.results.append(result)
                if result.ok:
                    self._stats["success"] += 1
                    if depth < self.config.max_depth:
                        new_links = Parser.extract_links(result.html, url)
                        for link in new_links:
                            parsed = urlparse(link)
                            domain = parsed.netloc
                            if self.config.allowed_domains and domain not in self.config.allowed_domains:
                                continue
                            await self.frontier.push(link, depth + 1)
                else:
                    self._stats["failed"] += 1
                    logger.warning(f"Failed: {url} — {result.error}")
                if self.config.request_delay > 0:
                    await asyncio.sleep(self.config.request_delay)

    async def crawl(self) -> list[CrawlResult]:
        self._stats["start_time"] = time.perf_counter()
        for url in self.config.start_urls:
            await self.frontier.push(url, depth=0)
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrency * 2,
            limit_per_host=10,
            ttl_dns_cache=300,
        )
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as self.session:
            self.semaphore = asyncio.Semaphore(self.config.concurrency)
            workers = [
                asyncio.create_task(self._worker(i))
                for i in range(self.config.concurrency)
            ]
            await asyncio.gather(*workers)
        elapsed = time.perf_counter() - self._stats["start_time"]
        logger.info(
            f"爬取完成: {self._stats['success']} 成功, "
            f"{self._stats['failed']} 失败, "
            f"总耗时 {elapsed:.2f}s, "
            f"({self._stats['success'] / max(elapsed, 0.001):.1f} 页/秒)"
        )
        return self.results

    def save_results(self):
        output = Path(self.config.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        for result in self.results:
            if result.ok and result.html:
                url_hash = hashlib.md5(result.url.encode()).hexdigest()[:12]
                filepath = output / f"{url_hash}.html"
                filepath.write_text(result.html, encoding="utf-8")
        index = [
            {
                "url": r.url, "status": r.status,
                "title": Parser.extract_title(r.html) if r.ok else "",
                "elapsed": round(r.elapsed, 3), "depth": r.depth, "error": r.error,
            }
            for r in self.results
        ]
        (output / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"结果已保存到 {output.absolute()}")


async def main():
    config = SpiderConfig(
        start_urls=["https://httpbin.org/"],
        concurrency=5,
        request_delay=0.2,
        max_retries=2,
        max_depth=1,
        allowed_domains={"httpbin.org"},
        output_dir="./spider_output",
    )
    spider = AsyncSpider(config)
    results = await spider.crawl()
    spider.save_results()
    print(f"\n=== 爬取统计 ===")
    print(f"总 URL: {len(results)}")
    print(f"成功: {sum(1 for r in results if r.ok)}")
    print(f"失败: {sum(1 for r in results if not r.ok)}")


if __name__ == "__main__":
    asyncio.run(main())
