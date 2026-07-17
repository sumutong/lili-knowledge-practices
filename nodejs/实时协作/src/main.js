// ─── server.js ── 主服务入口 ───────────────────────────────
const express = require('express')
const http = require('http')
const { Server } = require('socket.io')
const cors = require('cors')
const { createAdapter } = require('@socket.io/redis-adapter')
const { createClient } = require('redis')
const { WhiteboardManager } = require('./managers/whiteboard')
const { RoomManager } = require('./managers/room')

const app = express()
const server = http.createServer(app)
const io = new Server(server, {
  cors: { origin: '*', methods: ['GET', 'POST'] },
  pingTimeout: 60000,
  pingInterval: 25000,
  maxHttpBufferSize: 1e6, // 1MB
})

// Redis 适配器（多节点扩展）
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379'
const pubClient = createClient({ url: REDIS_URL })
const subClient = pubClient.duplicate()
Promise.all([pubClient.connect(), subClient.connect()])
  .then(() => {
    io.adapter(createAdapter(pubClient, subClient))
    console.log('Redis 适配器已连接')
  })
  .catch(err => console.warn('Redis 不可用，使用内存模式:', err.message))

// 中间件
app.use(cors())
app.use(express.json())
app.use(express.static('public'))

// 管理器
const roomManager = new RoomManager()
const whiteboardManager = new WhiteboardManager()

// ─── Socket.IO 连接处理 ───────────────────────────────────
io.use(async (socket, next) => {
  const { username, roomId } = socket.handshake.query
  if (!username || !roomId) {
    return next(new Error('缺少 username 或 roomId'))
  }
  socket.data.username = username
  socket.data.roomId = roomId
  socket.data.userId = socket.id
  socket.data.color = getRandomColor()
  next()
})

io.on('connection', async (socket) => {
  const { roomId, username, userId, color } = socket.data
  console.log(`[+] ${username} 加入房间 ${roomId} (${userId})`)

  // 加入房间
  socket.join(roomId)
  roomManager.addUser(roomId, { userId, username, color })
  await whiteboardManager.ensureRoom(roomId)

  // 通知其他用户
  socket.to(roomId).emit('user:joined', { userId, username, color })
  // 发送当前房间状态
  socket.emit('room:state', {
    users: roomManager.getUsers(roomId),
    elements: await whiteboardManager.getElements(roomId),
    cursorPositions: roomManager.getCursors(roomId),
  })

  // ── 绘图元素操作 ──────────────────────────────────────
  socket.on('element:add', async (element) => {
    element.id = generateId()
    element.userId = userId
    element.username = username
    element.timestamp = Date.now()
    await whiteboardManager.addElement(roomId, element)
    socket.to(roomId).emit('element:add', element)
  })

  socket.on('element:update', async ({ id, updates }) => {
    await whiteboardManager.updateElement(roomId, id, updates)
    socket.to(roomId).emit('element:update', { id, updates, userId })
  })

  socket.on('element:remove', async (id) => {
    await whiteboardManager.removeElement(roomId, id)
    socket.to(roomId).emit('element:remove', id)
  })

  socket.on('elements:batch', async (elements) => {
    const processed = elements.map(el => ({
      ...el, id: el.id || generateId(), userId, username, timestamp: Date.now(),
    }))
    await whiteboardManager.addElements(roomId, processed)
    socket.to(roomId).emit('elements:batch', processed)
  })

  // ── 光标同步 ──────────────────────────────────────────
  socket.on('cursor:move', (position) => {
    roomManager.updateCursor(roomId, userId, position)
    socket.to(roomId).emit('cursor:move', { userId, position })
  })

  // ── 文本编辑区同步 ────────────────────────────────────
  socket.on('text:update', (data) => {
    socket.to(roomId).emit('text:update', { userId, ...data })
  })

  // ── 撤销/重做广播 ─────────────────────────────────────
  socket.on('undo', () => {
    socket.to(roomId).emit('undo', userId)
  })
  socket.on('redo', () => {
    socket.to(roomId).emit('redo', userId)
  })

  // ── 画布清除 ──────────────────────────────────────────
  socket.on('canvas:clear', async () => {
    await whiteboardManager.clearRoom(roomId)
    io.to(roomId).emit('canvas:clear', { userId, username })
  })

  // ── 聊天消息 ──────────────────────────────────────────
  socket.on('chat:message', (text) => {
    const msg = { id: generateId(), userId, username, text, timestamp: Date.now() }
    io.to(roomId).emit('chat:message', msg)
  })

  // ── 断开连接 ──────────────────────────────────────────
  socket.on('disconnect', () => {
    roomManager.removeUser(roomId, userId)
    roomManager.removeCursor(roomId, userId)
    io.to(roomId).emit('user:left', { userId, username })
    console.log(`[-] ${username} 离开房间 ${roomId}`)
  })
})

// ─── REST API ──────────────────────────────────────────────
// 房间列表
app.get('/api/rooms', (req, res) => {
  res.json({ rooms: roomManager.listRooms() })
})

// 房间详情
app.get('/api/rooms/:roomId', async (req, res) => {
  const { roomId } = req.params
  res.json({
    users: roomManager.getUsers(roomId),
    elementsCount: await whiteboardManager.countElements(roomId),
  })
})

// 导出白板数据
app.get('/api/rooms/:roomId/export', async (req, res) => {
  const { roomId } = req.params
  const elements = await whiteboardManager.getElements(roomId)
  res.json({ roomId, elements, exportedAt: new Date().toISOString() })
})

// ─── 启动 ──────────────────────────────────────────────────
const PORT = process.env.PORT || 3000
server.listen(PORT, () => {
  console.log(`🖌️  协作白板服务运行在 http://localhost:${PORT}`)
})
