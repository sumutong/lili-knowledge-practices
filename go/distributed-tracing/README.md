# 分布式链路追踪 (Go)

OpenTelemetry + OTLP + Jaeger 实现分布式链路追踪，演示 Span、上下文传播、HTTP 中间件集成。

## 功能
- ✅ OpenTelemetry SDK 集成
- ✅ OTLP HTTP Exporter
- ✅ Jaeger 可视化
- ✅ HTTP 中间件自动追踪
- ✅ Span 属性/事件/状态
- ✅ 上下文传播 (W3C TraceContext)
- ✅ 模拟微服务调用链

## 快速启动
```bash
# 1. 启动 Jaeger
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# 2. 启动应用
go mod tidy
go run .
```

## 测试
```bash
# 查询用户（含缓存→DB→通知 完整链路）
curl http://localhost:8080/api/user?id=1

# 创建订单（含库存→支付→消息 子Span）
curl -X POST http://localhost:8080/api/order

# 查看 Trace ID
curl -v http://localhost:8080/api/user 2>&1 | grep X-Trace-ID
```

## Jaeger UI
```
http://localhost:16686
```

## 追踪链路示例
```
HTTP GET /api/user (500ms)
├── cache.get (5ms) — 缓存未命中
├── db.query (30ms) — PostgreSQL SELECT
└── http.client (50ms) — 通知服务调用
```

## 技术要点
- `go.opentelemetry.io/otel` 核心 API
- `otlptracehttp` OTLP 导出器
- `TraceContext` W3C 传播
- `AlwaysSample` 全量采样
- `SpanKindServer/Client` 语义约定
