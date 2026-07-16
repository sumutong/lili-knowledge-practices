# RESTful API 实战 (Go)

纯标准库实现的 RESTful CRUD API，包含中间件、JSON 序列化、优雅关闭。

## 功能
- ✅ CRUD 操作 (GET/POST/PUT/DELETE)
- ✅ 日志中间件
- ✅ CORS 跨域支持
- ✅ 并发安全 (sync.RWMutex)
- ✅ 优雅关闭 (Graceful Shutdown)
- ✅ 健康检查端点

## 运行
```bash
# 启动服务
go run . 

# 自定义端口
PORT=9090 go run .
```

## API 测试
```bash
# 健康检查
curl http://localhost:8080/health

# 获取任务列表
curl http://localhost:8080/api/tasks

# 创建任务
curl -X POST http://localhost:8080/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"学习Go"}'

# 更新任务
curl -X PUT http://localhost:8080/api/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"completed":true}'

# 删除任务
curl -X DELETE http://localhost:8080/api/tasks/1
```

## 技术要点
- `net/http` 标准路由
- `encoding/json` 序列化
- `sync.RWMutex` 并发安全
- `signal.Notify` 优雅关闭
