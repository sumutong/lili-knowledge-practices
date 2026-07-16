# WebSocket 实时聊天室 (Go)

基于 gorilla/websocket 的多房间实时聊天应用，带 Web 前端。

## 功能
- ✅ 实时消息广播
- ✅ 多房间支持
- ✅ 用户上下线通知
- ✅ Ping/Pong 心跳保活
- ✅ Web 聊天界面
- ✅ 并发安全

## 运行
```bash
# 安装依赖
go mod tidy

# 启动
go run .

# 打开浏览器
# http://localhost:8080
```

## 连接参数
```
ws://localhost:8080/ws?username=Alice&room=公共大厅
```

## 技术要点
- `gorilla/websocket` 升级 HTTP→WS
- `goroutine` 读写分离
- `channel` 消息队列
- Ping/Pong 心跳机制
