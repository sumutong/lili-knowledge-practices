// ─── server.js ── 主服务入口 ───────────────────────────────
require('dotenv').config()
const express = require('express')
const cors = require('cors')
const helmet = require('helmet')
const morgan = require('morgan')
const { MinioClient } = require('./storage/minio')
const { FileService } = require('./services/file')
const { uploadRouter } = require('./routes/upload')
const { fileRouter } = require('./routes/file')
const { chunkRouter } = require('./routes/chunk')
const { thumbnailRouter } = require('./routes/thumbnail')
const { errorHandler } = require('./middleware/error')

const app = express()
const PORT = process.env.PORT || 3000

// 中间件
app.use(helmet())
app.use(cors({ origin: process.env.CORS_ORIGIN || '*', credentials: true }))
app.use(morgan('short'))
app.use(express.json({ limit: '10mb' }))
app.use(express.urlencoded({ extended: true }))

// 静态文件预览
app.use('/preview', express.static(process.env.UPLOAD_DIR || './uploads'))

// 初始化 MinIO
const minioClient = new MinioClient({
  endPoint: process.env.MINIO_ENDPOINT || 'localhost',
  port: parseInt(process.env.MINIO_PORT || '9000'),
  useSSL: process.env.MINIO_USE_SSL === 'true',
  accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
  secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin',
})

const fileService = new FileService(minioClient)

// 路由
app.use('/api/upload', uploadRouter(fileService))
app.use('/api/files', fileRouter(fileService))
app.use('/api/chunks', chunkRouter(fileService))
app.use('/api/thumbnails', thumbnailRouter(fileService))

// 健康检查
app.get('/api/health', async (req, res) => {
  const storageOk = await minioClient.healthCheck()
  res.json({ status: 'ok', storage: storageOk ? 'ok' : 'error', timestamp: new Date().toISOString() })
})

// 错误处理
app.use(errorHandler)

// 优雅关闭
const server = app.listen(PORT, () => {
  console.log(`📁 文件服务运行在 http://localhost:${PORT}`)
})

process.on('SIGTERM', () => {
  server.close(() => process.exit(0))
})
