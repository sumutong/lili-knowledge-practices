// ─── src/queue-manager.js ─────────────────────────────────
const { Queue, Worker, QueueScheduler, FlowProducer } = require('bullmq')
const Redis = require('ioredis')

const connection = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT) || 6379,
  password: process.env.REDIS_PASSWORD,
  maxRetriesPerRequest: null, // BullMQ 需要
})

class QueueManager {
  constructor() {
    this.queues = new Map()
    this.workers = new Map()
    this.handlers = new Map()
  }

  /** 注册队列 */
  registerQueue(name, options = {}) {
    if (this.queues.has(name)) return this.queues.get(name)

    const queue = new Queue(name, {
      connection,
      defaultJobOptions: {
        attempts: options.attempts ?? 3,
        backoff: options.backoff ?? {
          type: 'exponential',
          delay: 1000,
        },
        removeOnComplete: options.removeOnComplete ?? { count: 1000 },
        removeOnFail: options.removeOnFail ?? { count: 5000 },
        timeout: options.timeout ?? 30000,
        ...options.defaultJobOptions,
      },
    })

    this.queues.set(name, queue)
    console.log(`📦 Queue registered: ${name}`)
    return queue
  }

  /** 注册任务处理器 */
  registerHandler(queueName, handlerName, handlerFn, options = {}) {
    const workerName = `${queueName}:${handlerName}`

    if (this.workers.has(workerName)) return this.workers.get(workerName)

    const worker = new Worker(queueName, async (job) => {
      const startTime = Date.now()
      console.log(`⚡ Processing: ${job.name} [${job.id}]`)

      try {
        // 进度
        await job.updateProgress(10)

        const result = await handlerFn(job)

        await job.updateProgress(100)

        const duration = Date.now() - startTime
        console.log(`✅ Completed: ${job.name} [${job.id}] in ${duration}ms`)
        return result
      } catch (err) {
        const duration = Date.now() - startTime
        console.error(`❌ Failed: ${job.name} [${job.id}] (attempt ${job.attemptsMade + 1}/${job.opts.attempts}) in ${duration}ms:`, err.message)
        throw err
      }
    }, {
      connection,
      concurrency: options.concurrency ?? 5,
      limiter: options.limiter ? {
        max: options.limiter.max,
        duration: options.limiter.duration,
      } : undefined,
    })

    // 事件监听
    worker.on('completed', (job) => {
      console.log(`🏁 Completed: ${job.id}`)
    })

    worker.on('failed', (job, err) => {
      console.error(`💥 Failed: ${job?.id}`, err.message)
      // 可以在此触发告警
    })

    worker.on('error', (err) => {
      console.error('Worker error:', err)
    })

    this.workers.set(workerName, worker)
    this.handlers.set(workerName, handlerFn)
    console.log(`🔧 Worker registered: ${workerName}`)
    return worker
  }

  /** 添加任务到队列 */
  async addJob(queueName, jobName, data, options = {}) {
    const queue = this.queues.get(queueName)
    if (!queue) throw new Error(`Queue "${queueName}" not registered`)

    const job = await queue.add(jobName, data, options)
    console.log(`📥 Job added: ${jobName} [${job.id}] to queue ${queueName}`)
    return job
  }

  /** 批量添加 */
  async addBulk(queueName, jobs) {
    const queue = this.queues.get(queueName)
    if (!queue) throw new Error(`Queue "${queueName}" not registered`)

    return queue.addBulk(jobs.map(j => ({
      name: j.name,
      data: j.data,
      opts: j.options,
    })))
  }

  /** 添加定时/延迟任务 */
  async addDelayed(queueName, jobName, data, delayMs, options = {}) {
    return this.addJob(queueName, jobName, data, { ...options, delay: delayMs })
  }

  /** 添加周期性重复任务 */
  async addRepeatable(queueName, jobName, data, pattern, options = {}) {
    return this.addJob(queueName, jobName, data, {
      ...options,
      repeat: { pattern },
    })
  }

  /** 获取队列统计 */
  async getStats(queueName) {
    const queue = this.queues.get(queueName)
    if (!queue) return null

    const [waiting, active, delayed, completed, failed] = await Promise.all([
      queue.getWaitingCount(),
      queue.getActiveCount(),
      queue.getDelayedCount(),
      queue.getCompletedCount(),
      queue.getFailedCount(),
    ])

    return { waiting, active, delayed, completed, failed }
  }

  /** 暂停/恢复队列 */
  async pauseQueue(queueName) {
    const queue = this.queues.get(queueName)
    await queue.pause()
  }

  async resumeQueue(queueName) {
    const queue = this.queues.get(queueName)
    await queue.resume()
  }

  /** 清理 */
  async clean(queueName, graceMs = 24 * 60 * 60 * 1000) {
    const queue = this.queues.get(queueName)
    await queue.clean(graceMs, 1000, 'completed')
    await queue.clean(graceMs, 1000, 'failed')
    console.log(`🧹 Cleaned queue ${queueName}`)
  }

  /** 优雅关闭 */
  async shutdown() {
    for (const [name, worker] of this.workers) {
      await worker.close()
      console.log(`Worker ${name} closed`)
    }
    for (const [name, queue] of this.queues) {
      await queue.close()
      console.log(`Queue ${name} closed`)
    }
  }
}

// 单例
let instance = null

function getQueueManager() {
  if (!instance) instance = new QueueManager()
  return instance
}

module.exports = { QueueManager, getQueueManager }
