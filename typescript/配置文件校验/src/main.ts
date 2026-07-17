// ─── src/config/schema.ts ─────────────────────────────────
import { z } from 'zod'

// 基础配置 Schema
export const serverConfigSchema = z.object({
  // 服务器配置
  port: z.coerce.number().int().min(1).max(65535).default(3000),
  host: z.string().default('0.0.0.0'),
  nodeEnv: z.enum(['development', 'test', 'staging', 'production']).default('development'),

  // 数据库配置
  database: z.object({
    type: z.enum(['postgres', 'mysql', 'sqlite', 'mongodb']).default('postgres'),
    host: z.string().default('localhost'),
    port: z.coerce.number().int().min(1).max(65535).default(5432),
    name: z.string().min(1).default('myapp'),
    user: z.string().default('postgres'),
    password: z.string().min(1).default('postgres'),
    poolMin: z.coerce.number().int().min(0).max(50).default(2),
    poolMax: z.coerce.number().int().min(1).max(100).default(10),
    ssl: z.boolean().default(false),
    // 连接字符串自动推导
    url: z.string().url().optional(),
  }),

  // Redis 配置
  redis: z.object({
    host: z.string().default('localhost'),
    port: z.coerce.number().int().min(1).max(65535).default(6379),
    password: z.string().optional(),
    db: z.coerce.number().int().min(0).max(15).default(0),
    keyPrefix: z.string().default('myapp:'),
    ttl: z.coerce.number().int().positive().default(3600),
  }),

  // JWT 认证
  auth: z.object({
    jwtSecret: z.string().min(32).default('change-me-to-a-random-secret-at-least-32-chars'),
    jwtExpiresIn: z.string().default('7d'),
    refreshExpiresIn: z.string().default('30d'),
    bcryptRounds: z.coerce.number().int().min(4).max(14).default(12),
  }),

  // 日志
  logging: z.object({
    level: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
    format: z.enum(['json', 'pretty']).default('json'),
    enableConsole: z.boolean().default(true),
    enableFile: z.boolean().default(false),
    filePath: z.string().optional(),
    maxFileSize: z.string().default('10m'),
    maxFiles: z.coerce.number().int().min(1).max(100).default(10),
    // 敏感字段脱敏
    redactKeys: z.array(z.string()).default(['password', 'token', 'secret', 'key']),
  }),

  // 文件上传
  upload: z.object({
    type: z.enum(['local', 's3']).default('local'),
    localPath: z.string().default('./uploads'),
    maxFileSize: z.coerce.number().int().positive().default(10 * 1024 * 1024), // 10MB
    allowedMimes: z.array(z.string()).default([
      'image/jpeg', 'image/png', 'image/gif', 'image/webp',
      'application/pdf',
    ]),
    s3: z.object({
      region: z.string().default('us-east-1'),
      bucket: z.string().optional(),
      accessKeyId: z.string().optional(),
      secretAccessKey: z.string().optional(),
      endpoint: z.string().url().optional(),
      cdnUrl: z.string().url().optional(),
    }).optional(),
  }),

  // CORS
  cors: z.object({
    origins: z.array(z.string()).default(['http://localhost:3000']),
    methods: z.array(z.string()).default(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']),
    allowedHeaders: z.array(z.string()).default(['Content-Type', 'Authorization']),
    credentials: z.boolean().default(true),
    maxAge: z.coerce.number().int().positive().default(86400),
  }),

  // 限流
  rateLimit: z.object({
    enabled: z.boolean().default(true),
    windowMs: z.coerce.number().int().positive().default(15 * 60 * 1000),
    max: z.coerce.number().int().positive().default(100),
    skipSuccessfulRequests: z.boolean().default(false),
  }),

  // 邮件
  email: z.object({
    from: z.string().email().default('noreply@example.com'),
    transport: z.enum(['smtp', 'sendgrid', 'resend']).default('smtp'),
    smtp: z.object({
      host: z.string().default('smtp.mailtrap.io'),
      port: z.coerce.number().int().min(1).max(65535).default(587),
      user: z.string().optional(),
      password: z.string().optional(),
    }).optional(),
    sendgrid: z.object({ apiKey: z.string().optional() }).optional(),
  }),

  // 第三方服务
  services: z.object({
    openai: z.object({ apiKey: z.string().optional(), model: z.string().default('gpt-4') }).optional(),
    aws: z.object({
      region: z.string().default('us-east-1'),
      accessKeyId: z.string().optional(),
      secretAccessKey: z.string().optional(),
    }).optional(),
    slack: z.object({ webhookUrl: z.string().url().optional() }).optional(),
  }),
})

// 环境变量重写 Schema
export const envOverridesSchema = z.object({
  PORT: z.string().optional(),
  NODE_ENV: z.string().optional(),
  DATABASE_URL: z.string().optional(),
  DB_HOST: z.string().optional(),
  DB_PORT: z.string().optional(),
  DB_NAME: z.string().optional(),
  DB_USER: z.string().optional(),
  DB_PASSWORD: z.string().optional(),
  DB_SSL: z.string().optional(),
  REDIS_HOST: z.string().optional(),
  REDIS_PORT: z.string().optional(),
  REDIS_PASSWORD: z.string().optional(),
  REDIS_DB: z.string().optional(),
  JWT_SECRET: z.string().optional(),
  LOG_LEVEL: z.string().optional(),
  CORS_ORIGINS: z.string().optional(),
  AWS_ACCESS_KEY_ID: z.string().optional(),
  AWS_SECRET_ACCESS_KEY: z.string().optional(),
  S3_BUCKET: z.string().optional(),
  S3_REGION: z.string().optional(),
  S3_ENDPOINT: z.string().optional(),
  OPENAI_API_KEY: z.string().optional(),
  SLACK_WEBHOOK: z.string().optional(),
  SENDGRID_API_KEY: z.string().optional(),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z.string().optional(),
  SMTP_USER: z.string().optional(),
  SMTP_PASS: z.string().optional(),
})

// 完整导出类型
export type ServerConfig = z.infer<typeof serverConfigSchema>
export type EnvOverrides = z.infer<typeof envOverridesSchema>
