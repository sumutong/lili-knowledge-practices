// ─── app.js ───────────────────────────────────────────────
require('dotenv').config()
const express = require('express')
const mongoose = require('mongoose')
const session = require('express-session')
const MongoStore = require('connect-mongo')
const flash = require('connect-flash')
const methodOverride = require('method-override')
const path = require('path')
const { marked } = require('marked')
const createError = require('http-errors')

const app = express()
const PORT = process.env.PORT || 3000

// ─── 数据库连接 ─────────────────────────────────────────
mongoose.connect(process.env.MONGO_URI || 'mongodb://localhost:27017/blog')
  .then(() => console.log('MongoDB 已连接'))
  .catch(err => console.error('MongoDB 连接失败:', err))

// ─── 中间件 ─────────────────────────────────────────────
app.set('view engine', 'ejs')
app.set('views', path.join(__dirname, 'views'))
app.use(express.static(path.join(__dirname, 'public')))
app.use(express.urlencoded({ extended: true }))
app.use(express.json())
app.use(methodOverride('_method'))
app.use(session({
  secret: process.env.SESSION_SECRET || 'blog-secret-key',
  resave: false,
  saveUninitialized: false,
  store: MongoStore.create({ mongoUrl: process.env.MONGO_URI }),
  cookie: { maxAge: 7 * 24 * 60 * 60 * 1000 },
}))
app.use(flash())

// 全局变量中间件
app.use((req, res, next) => {
  res.locals.user = req.session.user || null
  res.locals.success = req.flash('success')
  res.locals.error = req.flash('error')
  res.locals.moment = require('moment')
  res.locals.moment.locale('zh-cn')
  next()
})

// ─── 路由 ───────────────────────────────────────────────
app.use('/', require('./routes/index'))
app.use('/posts', require('./routes/posts'))
app.use('/auth', require('./routes/auth'))
app.use('/admin', require('./routes/admin'))
app.use('/api', require('./routes/api'))

// ─── 错误处理 ───────────────────────────────────────────
app.use((req, res, next) => next(createError(404)))
app.use((err, req, res, next) => {
  res.status(err.status || 500)
  res.render('error', { message: err.message, error: process.env.NODE_ENV === 'development' ? err : {} })
})

app.listen(PORT, () => console.log(`博客运行在 http://localhost:${PORT}`))
