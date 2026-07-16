# 微服务 API 网关 (Go)

纯 Go 实现的 API 网关：反向代理、负载均衡、服务注册、令牌桶限流。

## 功能
- ✅ 反向代理（路径路由）
- ✅ 轮询负载均衡（健康检查）
- ✅ 服务注册/发现
- ✅ 令牌桶限流
- ✅ 管理 API（注册/查看服务）
- ✅ 熔断降级（Bad Gateway 处理）

## 运行
```bash
go run .
```

## 架构
```
客户端 → 网关(:8080) → /api/user-service/* → user-service(:8081, :8082)
                      → /api/order-service/* → order-service(:8083)
                      → /admin/* → 管理API
```

## API
```bash
# 查看已注册服务
curl http://localhost:8080/admin/services

# 注册新服务
curl -X POST http://localhost:8080/admin/register \
  -H "Content-Type: application/json" \
  -d '{"id":"svc-1","name":"payment-service","host":"localhost","port":8084}'

# 代理请求（需要后端服务运行）
curl http://localhost:8080/api/user-service/health
```

## 技术要点
- `net/http/httputil` 反向代理
- 轮询负载均衡 (Round Robin)
- 令牌桶算法限流
- `sync.RWMutex` 服务注册表
- 路径路由解析 `/api/<service>/<path>`
