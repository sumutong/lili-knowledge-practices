# Rust Web API 实战

基于 Actix-web 框架的 RESTful API 服务，实现完整的用户 CRUD 操作。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/users` | 用户列表 |
| POST | `/api/v1/users` | 创建用户 |
| GET | `/api/v1/users/{id}` | 获取用户 |
| PUT | `/api/v1/users/{id}` | 更新用户 |
| DELETE | `/api/v1/users/{id}` | 删除用户 |

## 技术栈

- `actix-web` — 高性能 Web 框架
- `serde` — 序列化/反序列化
- `uuid` — 唯一 ID 生成
- `chrono` — 时间处理

## 运行

```bash
cd web-api
cargo run
# 服务启动在 http://127.0.0.1:8080
```

## 测试

```bash
# 健康检查
curl http://127.0.0.1:8080/api/v1/health

# 创建用户
curl -X POST http://127.0.0.1:8080/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"name":"张三","email":"zhang@example.com"}'

# 获取用户列表
curl http://127.0.0.1:8080/api/v1/users
```
