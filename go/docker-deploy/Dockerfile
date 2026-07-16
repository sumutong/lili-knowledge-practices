# 多阶段构建 — 最终镜像 < 10MB
FROM golang:1.23-alpine AS builder

WORKDIR /build

# 利用 Go 模块缓存
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# 静态编译，移除调试信息
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app .

# ─── 运行阶段 ─────────────────────────────────────────────
FROM alpine:3.19

RUN apk add --no-cache ca-certificates tzdata && \
    adduser -D -g '' appuser

COPY --from=builder /app /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

ENV APP_ENV=production
ENV APP_VERSION=1.0.0
ENV PORT=8080

ENTRYPOINT ["/app"]
