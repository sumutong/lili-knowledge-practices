# 订单微服务

FastAPI + SQLAlchemy + Redis 构建的高性能订单 CRUD 微服务。

## 特性
- 完整 CRUD 接口
- 发件箱模式（Outbox Pattern）
- Redis 缓存（带失效策略）
- 依赖注入
- 请求计时中间件
- 自动 OpenAPI 文档

## 运行

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

访问 http://localhost:8001/docs 查看 API 文档。
