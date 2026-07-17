// ─── src/mailer.js ────────────────────────────────────────
const nodemailer = require('nodemailer')
const handlebars = require('handlebars')
const fs = require('fs').promises
const path = require('path')
const juice = require('juice')

class MailService {
  constructor(config = {}) {
    this.config = {
      from: config.from || '"App" <noreply@example.com>',
      replyTo: config.replyTo,
      templatesDir: config.templatesDir || path.join(__dirname, '../templates'),
      transport: config.transport || 'smtp',
      ...config,
    }

    // 注册 Handlebars helpers
    handlebars.registerHelper('formatDate', (date) => {
      return new Date(date).toLocaleDateString('zh-CN')
    })

    handlebars.registerHelper('ifCond', function (v1, operator, v2, options) {
      switch (operator) {
        case '==': return (v1 == v2) ? options.fn(this) : options.inverse(this)
        case '===': return (v1 === v2) ? options.fn(this) : options.inverse(this)
        case '!=': return (v1 != v2) ? options.fn(this) : options.inverse(this)
        case '>': return (v1 > v2) ? options.fn(this) : options.inverse(this)
        case '<': return (v1 < v2) ? options.fn(this) : options.inverse(this)
        default: return options.inverse(this)
      }
    })

    this.transporter = this.createTransporter()
    this.templates = new Map() // 缓存编译后的模板
  }

  createTransporter() {
    switch (this.config.transport) {
      case 'sendgrid': {
        const sgTransport = require('nodemailer-sendgrid-transport')
        return nodemailer.createTransport(sgTransport({
          auth: { api_key: this.config.sendgridApiKey || process.env.SENDGRID_API_KEY },
        }))
      }

      case 'resend': {
        // Resend transport
        return nodemailer.createTransport({
          host: 'smtp.resend.com',
          port: 465,
          secure: true,
          auth: {
            user: 'resend',
            pass: this.config.resendApiKey || process.env.RESEND_API_KEY,
          },
        })
      }

      case 'ses': {
        const aws = require('@aws-sdk/client-ses')
        const ses = new aws.SESClient({
          region: this.config.awsRegion || 'us-east-1',
        })
        return nodemailer.createTransport({
          SES: { ses, aws },
        })
      }

      case 'smtp':
      default:
        return nodemailer.createTransport({
          host: this.config.smtpHost || process.env.SMTP_HOST || 'smtp.mailtrap.io',
          port: parseInt(this.config.smtpPort || process.env.SMTP_PORT) || 587,
          secure: this.config.smtpSecure ?? false,
          auth: {
            user: this.config.smtpUser || process.env.SMTP_USER,
            pass: this.config.smtpPass || process.env.SMTP_PASS,
          },
          pool: true,          // 连接池
          maxConnections: 5,
          maxMessages: 100,
          rateDelta: 1000,
          rateLimit: 5,        // 每秒最多 5 封
        })
    }
  }

  /** 加载并编译模板 */
  async loadTemplate(name) {
    if (this.templates.has(name)) return this.templates.get(name)

    const htmlPath = path.join(this.config.templatesDir, `${name}.html`)
    const textPath = path.join(this.config.templatesDir, `${name}.txt`)

    const [htmlSource, textSource] = await Promise.all([
      fs.readFile(htmlPath, 'utf-8').catch(() => null),
      fs.readFile(textPath, 'utf-8').catch(() => null),
    ])

    const compiled = {
      html: htmlSource ? handlebars.compile(htmlSource) : null,
      text: textSource ? handlebars.compile(textSource) : null,
    }

    this.templates.set(name, compiled)
    return compiled
  }

  /** 渲染模板并内联 CSS */
  async renderTemplate(name, data, options = {}) {
    const compiled = await this.loadTemplate(name)

    // 基础数据
    const baseData = {
      siteName: this.config.siteName || 'My App',
      siteUrl: this.config.siteUrl || 'https://example.com',
      currentYear: new Date().getFullYear(),
      unsubscribeUrl: options.unsubscribeUrl || '',
      logoUrl: this.config.logoUrl || '',
      ...data,
    }

    let html = compiled.html ? compiled.html(baseData) : ''
    let text = compiled.text ? compiled.text(baseData) : ''

    // 内联 CSS（使邮件在各种客户端中一致渲染）
    if (html) {
      const layoutPath = path.join(this.config.templatesDir, '_layout.html')
      try {
        const layoutSource = await fs.readFile(layoutPath, 'utf-8')
        const layoutTemplate = handlebars.compile(layoutSource)
        html = layoutTemplate({ ...baseData, content: html, bodyClass: options.bodyClass || '' })
      } catch { /* 无布局模板则使用原 HTML */ }

      // 内联 CSS
      html = juice(html)
    }

    return { html, text }
  }

  /** 发送邮件 */
  async send(options) {
    const {
      to, cc, bcc,
      subject,
      template, templateData,
      html, text,
      attachments,
      trackOpens,
      trackClicks,
      headers,
      category,
      replyTo,
      from,
    } = options

    const mailOptions = {
      from: from || this.config.from,
      to: Array.isArray(to) ? to.join(', ') : to,
      cc: cc,
      bcc: bcc,
      subject,
      replyTo: replyTo || this.config.replyTo,
      headers: {
        ...(trackOpens && { 'X-Track-Open': '1' }),
        ...(trackClicks && { 'X-Track-Click': '1' }),
        ...(category && { 'X-Mail-Category': category }),
        ...headers,
      },
    }

    // 模板渲染
    if (template) {
      const rendered = await this.renderTemplate(template, templateData || {}, options)
      mailOptions.html = rendered.html
      mailOptions.text = rendered.text || rendered.html?.replace(/<[^>]*>/g, '')
    } else {
      mailOptions.html = html
      mailOptions.text = text
    }

    // 附件处理
    if (attachments) {
      mailOptions.attachments = attachments.map(att => {
        if (typeof att === 'string') return { path: att }
        if (att.content) {
          return {
            filename: att.filename,
            content: att.content,
            contentType: att.contentType,
            encoding: att.encoding || 'base64',
            cid: att.cid, // 内嵌图片
          }
        }
        return att
      })
    }

    const info = await this.transporter.sendMail(mailOptions)

    return {
      messageId: info.messageId,
      accepted: info.accepted,
      rejected: info.rejected,
      response: info.response,
    }
  }

  /** 批量发送 */
  async sendBulk(options) {
    const { recipients, template, templateDataFn, subject, ...rest } = options
    const results = { sent: 0, failed: 0, errors: [] }

    // 每个收件人独立发送（可追踪取消订阅链接）
    for (const recipient of recipients) {
      try {
        const data = typeof templateDataFn === 'function'
          ? templateDataFn(recipient)
          : { ...(templateDataFn || {}), ...recipient }

        // 添加退订链接
        data.unsubscribeUrl = `${this.config.siteUrl}/unsubscribe?email=${encodeURIComponent(recipient.email)}&token=${recipient.unsubscribeToken || ''}`

        const rendered = await this.renderTemplate(template, data)

        await this.transporter.sendMail({
          from: rest.from || this.config.from,
          to: recipient.email,
          subject: typeof subject === 'function' ? subject(recipient) : subject,
          html: rendered.html,
          text: rendered.text,
          headers: {
            'List-Unsubscribe': `<${data.unsubscribeUrl}>`,
          },
        })

        results.sent++
      } catch (err) {
        results.failed++
        results.errors.push({ recipient: recipient.email, error: err.message })
      }
    }

    return results
  }

  /** 发送验证邮件 */
  async sendVerification(user, token) {
    return this.send({
      to: user.email,
      subject: '验证您的邮箱地址',
      template: 'verify-email',
      templateData: {
        username: user.username,
        verificationUrl: `${this.config.siteUrl}/verify-email?token=${token}`,
        expiryHours: 24,
      },
    })
  }

  /** 发送密码重置邮件 */
  async sendPasswordReset(user, token) {
    return this.send({
      to: user.email,
      subject: '重置您的密码',
      template: 'reset-password',
      templateData: {
        username: user.username,
        resetUrl: `${this.config.siteUrl}/reset-password?token=${token}`,
        expiryMinutes: 30,
      },
    })
  }

  /** 发送欢迎邮件 */
  async sendWelcome(user) {
    return this.send({
      to: user.email,
      subject: `欢迎加入 ${this.config.siteName}!`,
      template: 'welcome',
      templateData: {
        username: user.username,
        loginUrl: `${this.config.siteUrl}/login`,
        gettingStartedUrl: `${this.config.siteUrl}/docs/getting-started`,
      },
    })
  }

  /** 发送通知邮件 */
  async sendNotification(to, subject, data, template = 'notification') {
    return this.send({
      to,
      subject,
      template,
      templateData: data,
    })
  }

  /** 发送账单/收据 */
  async sendInvoice(user, invoice) {
    return this.send({
      to: user.email,
      subject: `发票 #${invoice.number}`,
      template: 'invoice',
      templateData: {
        username: user.username,
        invoiceNumber: invoice.number,
        invoiceDate: invoice.date,
        dueDate: invoice.dueDate,
        items: invoice.items,
        subtotal: invoice.subtotal,
        tax: invoice.tax,
        total: invoice.total,
        currency: invoice.currency || 'USD',
        downloadUrl: `${this.config.siteUrl}/invoices/${invoice.id}/pdf`,
      },
    })
  }

  /** 健康检查 */
  async verify() {
    try {
      await this.transporter.verify()
      return { ok: true, transport: this.config.transport }
    } catch (err) {
      return { ok: false, error: err.message }
    }
  }

  /** 关闭连接 */
  async close() {
    this.transporter.close()
  }
}

module.exports = { MailService }
