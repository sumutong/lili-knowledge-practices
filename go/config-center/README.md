# 配置中心 (Go)

轻量级配置中心：支持 JSON/YAML 多格式、热加载、环境变量覆盖、配置变更订阅。

## 功能
- ✅ JSON / YAML 双格式支持
- ✅ 热加载（文件监控 + 手动触发）
- ✅ 环境变量覆盖
- ✅ 配置变更订阅（channel 通知）
- ✅ 配置版本管理
- ✅ HTTP API（查看/重载）

## 运行
```bash
go mod tidy
go run .

# 自定义配置文件
CONFIG_PATH=./config.yaml go run .
```

## API
```bash
# 查看当前配置
curl http://localhost:8080/api/config

# 手动触发重载
curl -X POST http://localhost:8080/api/config/reload
```

## 环境变量覆盖
```bash
export SERVER_PORT=9090
export DB_HOST=prod-db.example.com
export DB_PASSWORD=prod-secret
export REDIS_HOST=cache.example.com
```

## 技术要点
- `gopkg.in/yaml.v3` YAML 解析
- `sync.RWMutex` 并发安全读
- Channel 发布/订阅模式
- 环境变量优先级覆盖
- 文件轮询热加载
