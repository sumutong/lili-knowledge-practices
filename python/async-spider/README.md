# 高性能异步爬虫框架

基于 `asyncio` + `aiohttp` 构建的高并发爬虫框架，支持并发控制、请求重试、代理池、自动解析。

## 特性
- 异步并发控制（信号量机制）
- URL 去重与优先级队列
- 请求重试（指数退避）
- 代理池轮询
- 链接自动发现（可配置深度）
- 结构化数据提取
- 结果输出（HTML + JSON 索引）

## 运行

```bash
pip install -r requirements.txt
python spider.py
```
