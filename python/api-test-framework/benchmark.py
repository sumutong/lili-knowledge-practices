#!/usr/bin/env python3
"""HTTP 性能压测工具"""
import asyncio
import time
from dataclasses import dataclass, field

import aiohttp


@dataclass
class BenchmarkResult:
    total_requests: int = 0
    success: int = 0
    failed: int = 0
    latencies: list[float] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def rps(self) -> float:
        return self.total_requests / max(self.duration, 0.001)

    def percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_lats = sorted(self.latencies)
        idx = int(len(sorted_lats) * p / 100)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]

    def report(self) -> str:
        return f"""
╔══════════════════════════════════╗
║       HTTP 压测报告              ║
╠══════════════════════════════════╣
║  总请求:    {self.total_requests:>8}          ║
║  成功:      {self.success:>8}          ║
║  失败:      {self.failed:>8}          ║
║  耗时:      {self.duration:>7.2f}s        ║
║  QPS:       {self.rps:>8.1f}          ║
║  P50:       {self.percentile(50):>7.0f}ms        ║
║  P90:       {self.percentile(90):>7.0f}ms        ║
║  P99:       {self.percentile(99):>7.0f}ms        ║
║  最大延迟:  {max(self.latencies):>7.0f}ms   ║
║  平均延迟:  {sum(self.latencies)/max(len(self.latencies),1):>7.0f}ms        ║
╚══════════════════════════════════╝
"""


class HTTPBench:
    def __init__(self, concurrency: int = 10):
        self.concurrency = concurrency

    async def run(self, url: str, total_requests: int = 100,
                  method: str = "GET", json_data: dict = None) -> BenchmarkResult:
        result = BenchmarkResult()
        result.start_time = time.perf_counter()
        sem = asyncio.Semaphore(self.concurrency)

        async def _request(session: aiohttp.ClientSession):
            async with sem:
                start = time.perf_counter()
                try:
                    if method == "GET":
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            await resp.read()
                            if resp.status < 500:
                                result.success += 1
                            else:
                                result.failed += 1
                    elif method == "POST":
                        async with session.post(url, json=json_data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            await resp.read()
                            if resp.status < 500:
                                result.success += 1
                            else:
                                result.failed += 1
                except Exception:
                    result.failed += 1
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    result.latencies.append(latency_ms)
                    result.total_requests += 1

        async with aiohttp.ClientSession() as session:
            tasks = [_request(session) for _ in range(total_requests)]
            await asyncio.gather(*tasks)

        result.end_time = time.perf_counter()
        return result


async def main():
    bench = HTTPBench(concurrency=20)
    print("开始压测...")
    result = await bench.run("https://httpbin.org/get", total_requests=100)
    print(result.report())


if __name__ == "__main__":
    asyncio.run(main())
