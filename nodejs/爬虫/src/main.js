// ─── src/crawler-engine.js ────────────────────────────────
const { EventEmitter } = require('events')
const { URL } = require('url')
const { requestQueue } = require('./queue')
const { dedup } = require('./dedup')
const { proxyPool } = require('./proxy-pool')
const { fetchPage } = require('./fetcher')
const { extractLinks } = require('./extractors/link-extractor')
const { BrowserPool } = require('./browser-pool')

class CrawlerEngine extends EventEmitter {
  constructor(options = {}) {
    super()
    this.options = {
      concurrency: options.concurrency || 3,
      maxDepth: options.maxDepth || 3,
      maxPages: options.maxPages || 1000,
      delay: options.delay || 1000,           // 请求间隔 ms
      randomDelay: options.randomDelay || 500, // 随机延迟 ±
      timeout: options.timeout || 30000,
      retries: options.retries || 3,
      userAgent: options.userAgent || 'Mozilla/5.0 (compatible; CrawlerBot/1.0)',
      respectRobotsTxt: options.respectRobotsTxt ?? true,
      followRedirect: options.followRedirect ?? true,
      allowedDomains: options.allowedDomains || [],
      blockedPatterns: options.blockedPatterns || [
        /\.(pdf|zip|rar|tar|gz|exe|apk|mp4|avi)$/i,
        /\/cdn-cgi\//,
        /\/wp-admin\//,
      ],
    }

    this.stats = {
      visited: 0,
      failed: 0,
      skipped: 0,
      totalTime: 0,
      startTime: 0,
    }

    this.active = 0
    this.browserPool = options.useBrowser ? new BrowserPool({ maxBrowsers: 2 }) : null
  }

  async crawl(startUrls, handler) {
    if (!Array.isArray(startUrls)) startUrls = [startUrls]
    this.stats.startTime = Date.now()

    for (const url of startUrls) {
      requestQueue.enqueue({ url, depth: 0, referrer: null })
    }

    this.emit('start', { urls: startUrls })

    // 并发控制
    const workers = Array(this.options.concurrency)
      .fill(null)
      .map(() => this.worker(handler))

    await Promise.all(workers)

    this.emit('done', { stats: this.stats })
    return this.stats
  }

  async worker(handler) {
    while (requestQueue.size() > 0 || this.active > 0) {
      // 检查上限
      if (this.stats.visited >= this.options.maxPages) break

      const item = requestQueue.dequeue()
      if (!item) {
        // 无任务时等待
        await this.sleep(500)
        continue
      }

      this.active++

      try {
        await this.processItem(item, handler)
      } catch (err) {
        this.emit('error', { url: item.url, error: err.message })
        this.stats.failed++

        // 重试
        if (item.retries < this.options.retries) {
          requestQueue.enqueue({ ...item, retries: (item.retries || 0) + 1 })
        }
      } finally {
        this.active--
      }

      // 限速延迟
      const delay = this.options.delay + Math.random() * this.options.randomDelay * 2 - this.options.randomDelay
      await this.sleep(Math.max(0, delay))
    }
  }

  async processItem(item, handler) {
    const { url, depth, referrer } = item

    // 检查域名限制
    if (!this.isAllowed(url)) {
      this.stats.skipped++
      return
    }

    // 去重检查
    const normalizedUrl = this.normalizeUrl(url)
    if (dedup.has(normalizedUrl)) {
      this.stats.skipped++
      return
    }
    dedup.add(normalizedUrl)

    // 遵循 robots.txt
    if (this.options.respectRobotsTxt && !(await this.checkRobots(url))) {
      this.stats.skipped++
      return
    }

    // 获取代理
    const proxy = proxyPool.getProxy()

    // 决定使用静态还是动态抓取
    const needsBrowser = item.useBrowser || this.options.useBrowser || false
    const { html, headers, status } = needsBrowser
      ? await this.fetchWithBrowser(url)
      : await fetchPage(url, {
          proxy,
          userAgent: this.options.userAgent,
          timeout: this.options.timeout,
          headers: { Referer: referrer || '' },
          retries: this.options.retries,
        })

    this.stats.visited++

    // 调用用户处理器
    await handler({ url, html, headers, status, depth })

    // 发现并入队新链接
    if (depth < this.options.maxDepth) {
      const links = extractLinks(html, url, this.options.allowedDomains)
      for (const link of links) {
        if (this.shouldFollow(link)) {
          requestQueue.enqueue({ url: link, depth: depth + 1, referrer: url })
        }
      }
    }

    this.emit('page', { url, status, depth })
  }

  isAllowed(url) {
    if (this.options.allowedDomains.length === 0) return true

    try {
      const hostname = new URL(url).hostname
      return this.options.allowedDomains.some(domain =>
        hostname === domain || hostname.endsWith('.' + domain)
      )
    } catch {
      return false
    }
  }

  shouldFollow(url) {
    if (this.options.blockedPatterns.length === 0) return true

    // 检查 URL 扩展名
    try {
      const pathname = new URL(url).pathname
      return !this.options.blockedPatterns.some(pattern => pattern.test(pathname))
    } catch {
      return false
    }
  }

  normalizeUrl(url) {
    try {
      const u = new URL(url)
      u.hash = ''
      // 移除常见追踪参数
      u.searchParams.delete('utm_source')
      u.searchParams.delete('utm_medium')
      u.searchParams.delete('utm_campaign')
      u.searchParams.delete('fbclid')
      u.searchParams.delete('ref')
      return u.toString().replace(/\/$/, '')
    } catch {
      return url
    }
  }

  async checkRobots(url) {
    // robots.txt 检查（简化实现）
    return true
  }

  async fetchWithBrowser(url) {
    if (!this.browserPool) throw new Error('BrowserPool not initialized')

    const browser = await this.browserPool.acquire()
    try {
      const page = await browser.newPage()

      await page.setUserAgent(this.options.userAgent)
      await page.setExtraHTTPHeaders({ 'Accept-Language': 'zh-CN,zh;q=0.9' })

      const response = await page.goto(url, {
        waitUntil: 'networkidle2',
        timeout: this.options.timeout,
      })

      const html = await page.content()
      const headers = response.headers()
      const status = response.status()

      await page.close()

      return { html, headers, status }
    } finally {
      await this.browserPool.release(browser)
    }
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}

module.exports = { CrawlerEngine }
