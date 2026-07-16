# 定时任务调度器 (Go)

基于 robfig/cron 的企业级定时任务调度器，支持 Cron 表达式和秒级精度。

## 功能
- ✅ Cron 表达式解析（秒级精度）
- ✅ 动态添加/删除任务
- ✅ 任务执行日志
- ✅ HTTP API 查看任务列表
- ✅ 下次执行时间预览

## 运行
```bash
go mod tidy
go run .
```

## Cron 表达式格式（6字段）
```
秒 分 时 日 月 周
*  *  *  *  *  *

示例:
0 */5 * * * *    — 每5分钟
0 0 2 * * *      — 每天凌晨2点
0 0 0 * * 1      — 每周一凌晨
0 30 9 1 * *     — 每月1号9:30
```

## API
```bash
# 查看所有任务
curl http://localhost:8080/api/jobs

# 健康检查
curl http://localhost:8080/health
```

## 技术要点
- `robfig/cron/v3` 定时调度
- `sync.RWMutex` 并发安全
- `cron.WithSeconds()` 秒级调度
