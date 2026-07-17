// ─── src/generator.js ─────────────────────────────────────
const fs = require('fs').promises
const fsSync = require('fs')
const path = require('path')
const matter = require('gray-matter')
const { marked } = require('marked')
const nunjucks = require('nunjucks')
const chokidar = require('chokidar')
const { minify } = require('html-minifier-terser')
const { Feed } = require('feed')
const { LiveReloadServer } = require('./live-reload')

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: false,
  highlight: function (code, lang) {
    // 简单的语法高亮（生产环境可用 highlight.js）
    return `<pre><code class="language-${lang || 'plaintext'}">${escapeHtml(code)}</code></pre>`
  },
})

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

class StaticSiteGenerator {
  constructor(config = {}) {
    this.config = {
      sourceDir: config.sourceDir || 'src',
      outputDir: config.outputDir || 'dist',
      postsDir: config.postsDir || 'posts',
      pagesDir: config.pagesDir || 'pages',
      templatesDir: config.templatesDir || 'templates',
      assetsDir: config.assetsDir || 'assets',
      publicDir: config.publicDir || 'public',
      site: {
        title: config.site?.title || 'My Blog',
        description: config.site?.description || '',
        url: config.site?.url || 'https://example.com',
        author: config.site?.author || 'Anonymous',
        language: config.site?.language || 'zh-CN',
      },
      postsPerPage: config.postsPerPage || 10,
      dateFormat: config.dateFormat || 'YYYY-MM-DD',
      minifyHtml: config.minifyHtml ?? true,
      generateRSS: config.generateRSS ?? true,
      generateSitemap: config.generateSitemap ?? true,
    }

    this.env = null
    this.posts = []
    this.pages = []
    this.tags = new Map()
  }

  /** 初始化 */
  async init() {
    // 设置模板引擎
    const templatePath = path.resolve(this.config.sourceDir, this.config.templatesDir)
    this.env = nunjucks.configure(templatePath, {
      autoescape: true,
      noCache: process.env.NODE_ENV === 'development',
      watch: false,
    })

    // 注册自定义过滤器
    this.env.addFilter('date', (str, format) => {
      const d = new Date(str)
      return d.toISOString().slice(0, 10)
    })

    this.env.addFilter('limit', (arr, count) => arr?.slice(0, count) || [])

    this.env.addFilter('excerpt', (html, length = 200) => {
      const text = html?.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim() || ''
      return text.length > length ? text.slice(0, length) + '...' : text
    })

    this.env.addFilter('tagUrl', (tag) => `/tags/${encodeURIComponent(tag.toLowerCase())}/`)

    // 注册全局变量
    this.env.addGlobal('site', this.config.site)
    this.env.addGlobal('now', new Date())
  }

  /** 收集所有文章 */
  async collectPosts() {
    const postsDir = path.resolve(this.config.sourceDir, this.config.postsDir)
    this.posts = []
    this.tags.clear()

    // 递归遍历
    async function walk(dir) {
      const entries = await fs.readdir(dir, { withFileTypes: true })
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          await walk(fullPath)
        } else if (entry.name.endsWith('.md') || entry.name.endsWith('.markdown')) {
          const content = await fs.readFile(fullPath, 'utf-8')
          const { data, content: body } = matter(content)

          // 如果不包含 frontmatter，跳过
          if (!data.title) continue

          const slug = data.slug
            || entry.name.replace(/\.(md|markdown)$/, '')
            || data.title.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')

          const post = {
            title: data.title,
            slug,
            date: data.date ? new Date(data.date) : new Date(),
            updated: data.updated ? new Date(data.updated) : undefined,
            author: data.author || this.config.site.author,
            tags: data.tags || [],
            category: data.category,
            draft: data.draft || false,
            summary: data.summary || '',
            cover: data.cover || '',
            rawContent: body,
            sourcePath: fullPath,
          }

          this.posts.push(post)

          // 收集标签
          for (const tag of post.tags) {
            if (!this.tags.has(tag)) this.tags.set(tag, [])
            this.tags.get(tag).push(post)
          }
        }
      }
    }

    try {
      await walk.call(this, postsDir)
    } catch (err) {
      console.warn(`Posts directory not found: ${postsDir}`)
    }

    // 排除草稿，按日期排序
    this.posts = this.posts
      .filter(p => !p.draft)
      .sort((a, b) => b.date - a.date)

    console.log(`📝 Collected ${this.posts.length} posts, ${this.tags.size} tags`)
  }

  /** 收集页面 */
  async collectPages() {
    const pagesDir = path.resolve(this.config.sourceDir, this.config.pagesDir)
    this.pages = []

    try {
      const entries = await fs.readdir(pagesDir, { withFileTypes: true })
      for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith('.njk')) continue
        const name = entry.name.replace('.njk', '')
        this.pages.push({ name, slug: name === 'index' ? '' : name, template: `${name}.njk` })
      }
    } catch {
      console.warn(`Pages directory not found: ${pagesDir}`)
    }
  }

  /** 构建单个页面 */
  async renderPage(template, data) {
    const html = this.env.render(template, {
      ...data,
      site: this.config.site,
      posts: this.posts,
      tags: [...this.tags.entries()].map(([name, posts]) => ({ name, count: posts.length })),
      env: process.env.NODE_ENV || 'development',
    })

    if (this.config.minifyHtml) {
      return minify(html, {
        collapseWhitespace: true,
        removeComments: true,
        minifyCSS: true,
        minifyJS: true,
        removeOptionalTags: false,
      })
    }

    return html
  }

  /** 写入文件 */
  async writeFile(relativePath, content, createDir = true) {
    const fullPath = path.resolve(this.config.outputDir, relativePath)
    if (createDir) {
      await fs.mkdir(path.dirname(fullPath), { recursive: true })
    }
    await fs.writeFile(fullPath, content)
  }

  /** 完整构建 */
  async build() {
    console.log('🏗️ Building static site...')
    const startTime = Date.now()

    await this.init()
    await this.collectPosts()
    await this.collectPages()

    // 清理输出目录
    await fs.rm(this.config.outputDir, { recursive: true, force: true })
    await fs.mkdir(this.config.outputDir, { recursive: true })

    let fileCount = 0

    // 1. 首页
    for (let page = 1; page <= Math.ceil(this.posts.length / this.config.postsPerPage); page++) {
      const start = (page - 1) * this.config.postsPerPage
      const pagePosts = this.posts.slice(start, start + this.config.postsPerPage)

      const html = await this.renderPage('index.njk', {
        title: page === 1 ? this.config.site.title : `第${page}页 - ${this.config.site.title}`,
        pagePosts,
        currentPage: page,
        totalPages: Math.ceil(this.posts.length / this.config.postsPerPage),
        isHome: true,
        pagination: {
          prevPage: page > 1 ? page - 1 : null,
          nextPage: page < Math.ceil(this.posts.length / this.config.postsPerPage) ? page + 1 : null,
        },
      })

      const outPath = page === 1 ? 'index.html' : `page/${page}/index.html`
      await this.writeFile(outPath, html)
      fileCount++
    }

    // 2. 文章详情页
    for (const post of this.posts) {
      // 渲染 Markdown
      const htmlContent = marked.parse(post.rawContent)

      // 获取前后文章（上下篇）
      const idx = this.posts.indexOf(post)
      const prevPost = idx > 0 ? this.posts[idx - 1] : null
      const nextPost = idx < this.posts.length - 1 ? this.posts[idx + 1] : null

      const html = await this.renderPage('post.njk', {
        title: post.title,
        post: { ...post, htmlContent },
        prevPost,
        nextPost,
        description: post.summary || post.rawContent.slice(0, 160),
      })

      await this.writeFile(`${post.slug}/index.html`, html)
      fileCount++
    }

    // 3. 标签页
    for (const [tagName, tagPosts] of this.tags) {
      const html = await this.renderPage('tag.njk', {
        title: `标签: ${tagName}`,
        tagName,
        tagPosts,
      })
      await this.writeFile(`tags/${encodeURIComponent(tagName.toLowerCase())}/index.html`, html)
      fileCount++
    }

    // 4. 标签归档页
    {
      const html = await this.renderPage('tags.njk', {
        title: '标签',
      })
      await this.writeFile('tags/index.html', html)
      fileCount++
    }

    // 5. 自定义页面
    for (const page of this.pages) {
      const html = await this.renderPage(page.template, {
        title: page.name.charAt(0).toUpperCase() + page.name.slice(1),
      })
      await this.writeFile(`${page.slug}/index.html`, html)
      fileCount++
    }

    // 6. 静态资源复制
    await this.copyAssets()

    // 7. RSS Feed
    if (this.config.generateRSS) {
      await this.generateRSS()
    }

    // 8. Sitemap
    if (this.config.generateSitemap) {
      await this.generateSitemap()
    }

    const duration = ((Date.now() - startTime) / 1000).toFixed(2)
    console.log(`✅ Generated ${fileCount} files in ${duration}s -> ${this.config.outputDir}`)
  }

  /** 复制静态资源 */
  async copyAssets() {
    const assetsSrc = path.resolve(this.config.sourceDir, this.config.assetsDir)
    const assetsDest = path.resolve(this.config.outputDir, this.config.assetsDir)
    const publicSrc = path.resolve(this.config.sourceDir, this.config.publicDir)

    try {
      await fs.cp(assetsSrc, assetsDest, { recursive: true })
    } catch { /* 忽略 */ }

    try {
      // public 目录直接复制到根
      const entries = await fs.readdir(publicSrc, { withFileTypes: true })
      for (const entry of entries) {
        const src = path.join(publicSrc, entry.name)
        const dest = path.join(this.config.outputDir, entry.name)
        await fs.cp(src, dest, { recursive: true })
      }
    } catch { /* 忽略 */ }
  }

  /** 生成 RSS */
  async generateRSS() {
    const feed = new Feed({
      title: this.config.site.title,
      description: this.config.site.description,
      id: this.config.site.url,
      link: this.config.site.url,
      language: this.config.site.language,
      favicon: `${this.config.site.url}/favicon.ico`,
      copyright: `All rights reserved ${new Date().getFullYear()}`,
      author: {
        name: this.config.site.author,
        link: this.config.site.url,
      },
    })

    for (const post of this.posts.slice(0, 20)) {
      feed.addItem({
        title: post.title,
        id: `${this.config.site.url}/${post.slug}/`,
        link: `${this.config.site.url}/${post.slug}/`,
        description: post.summary,
        content: marked.parse(post.rawContent),
        date: post.date,
        author: [{ name: post.author }],
        category: post.tags.map(tag => ({ name: tag })),
      })
    }

    await this.writeFile('feed.xml', feed.rss2())
  }

  /** 生成站点地图 */
  async generateSitemap() {
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    xml += `  <url><loc>${this.config.site.url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n`
    xml += `  <url><loc>${this.config.site.url}/tags/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>\n`

    for (const post of this.posts) {
      xml += `  <url><loc>${this.config.site.url}/${post.slug}/</loc><lastmod>${post.date.toISOString()}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>\n`
    }

    for (const [tagName] of this.tags) {
      xml += `  <url><loc>${this.config.site.url}/tags/${encodeURIComponent(tagName.toLowerCase())}/</loc><changefreq>weekly</changefreq><priority>0.5</priority></url>\n`
    }

    xml += '</urlset>'

    await this.writeFile('sitemap.xml', xml)
  }

  /** 开发模式：文件监听 + 热更新 */
  async watch() {
    console.log('👀 Watching for changes...')

    const sourcePath = path.resolve(this.config.sourceDir)
    let buildTimeout

    const watcher = chokidar.watch(sourcePath, {
      ignored: /(^|[\/\\])\../, // 忽略隐藏文件
      persistent: true,
      ignoreInitial: true,
    })

    watcher.on('all', async (event, filePath) => {
      const relPath = path.relative(sourcePath, filePath)
      console.log(`  File ${event}: ${relPath}`)

      // 防抖：300ms 内多次变化只构建一次
      clearTimeout(buildTimeout)
      buildTimeout = setTimeout(async () => {
        try {
          await this.build()
        } catch (err) {
          console.error('Build error:', err.message)
        }
      }, 300)
    })

    await this.build()

    // 启动开发服务器
    const server = new LiveReloadServer({
      root: this.config.outputDir,
      port: 8080,
    })
    server.start()

    console.log('🔗 Dev server: http://localhost:8080')
  }
}

module.exports = { StaticSiteGenerator }
