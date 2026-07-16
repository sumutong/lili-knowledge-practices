# 容器化部署实战 (Go)

多阶段 Docker 构建、健康检查、环境变量配置、Docker Compose 编排。

## 功能
- ✅ 多阶段 Docker 构建（镜像 < 10MB）
- ✅ Docker HEALTHCHECK 健康检查
- ✅ 环境变量配置
- ✅ 优雅关闭 (Graceful Shutdown)
- ✅ Docker Compose 编排
- ✅ 静态编译 (CGO_ENABLED=0)

## 本地运行
```bash
go run .
```

## Docker 部署
```bash
# 构建镜像
docker build -t go-docker-app .

# 运行容器
docker run -p 8080:8080 -e APP_ENV=production go-docker-app

# Docker Compose
docker-compose up -d
```

## API
```bash
curl http://localhost:8080/health
curl http://localhost:8080/info
curl http://localhost:8080/config
```

## 技术要点
- 多阶段构建 (builder + alpine)
- `-ldflags="-s -w"` 减小体积
- `FROM scratch` / `alpine` 最小镜像
- `HEALTHCHECK` 容器自检
- `docker-compose.yml` 服务编排
