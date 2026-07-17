// ─── src/strategies/fixed-window.js ──────────────────────
class FixedWindowStore {
  constructor() {
    this.windows = new Map() // key -> { count, resetAt }
  }

  async increment(key, windowMs, maxRequests) {
    const now = Date.now()
    let window = this.windows.get(key)

    if (!window || now >= window.resetAt) {
      window = { count: 1, resetAt: now + windowMs }
      this.windows.set(key, window)
      return { allowed: true, remaining: maxRequests - 1, resetAt: window.resetAt }
    }

    window.count++
    const remaining = maxRequests - window.count
    return {
      allowed: remaining >= 0,
      remaining: Math.max(0, remaining),
      resetAt: window.resetAt,
    }
  }

  reset(key) {
    this.windows.delete(key)
  }
}

// ─── src/strategies/sliding-window.js ─────────────────────
class SlidingWindowStore {
  constructor() {
    this.entries = new Map() // key -> [timestamps]
  }

  async increment(key, windowMs, maxRequests) {
    const now = Date.now()
    const windowStart = now - windowMs
    let timestamps = this.entries.get(key) || []

    // 清理过期时间戳
    timestamps = timestamps.filter(ts => ts > windowStart)

    if (timestamps.length >= maxRequests) {
      this.entries.set(key, timestamps)
      return {
        allowed: false,
        remaining: 0,
        resetAt: timestamps[0] + windowMs,
        retryAfter: Math.ceil((timestamps[0] + windowMs - now) / 1000),
      }
    }

    timestamps.push(now)
    this.entries.set(key, timestamps)

    const remaining = maxRequests - timestamps.length
    return {
      allowed: true,
      remaining,
      resetAt: timestamps[0] + windowMs,
    }
  }

  reset(key) {
    this.entries.delete(key)
  }
}

// ─── src/strategies/token-bucket.js ───────────────────────
class TokenBucketStore {
  constructor() {
    this.buckets = new Map() // key -> { tokens, lastRefill }
  }

  async consume(key, capacity, refillRate, refillIntervalMs, tokensPerRefill = 1) {
    const now = Date.now()
    let bucket = this.buckets.get(key)

    if (!bucket) {
      bucket = { tokens: capacity, lastRefill: now }
      this.buckets.set(key, bucket)
    }

    // 计算应补充的令牌
    const elapsed = now - bucket.lastRefill
    const refillCount = Math.floor(elapsed / refillIntervalMs)
    if (refillCount > 0) {
      bucket.tokens = Math.min(capacity, bucket.tokens + refillCount * tokensPerRefill)
      bucket.lastRefill += refillCount * refillIntervalMs
    }

    if (bucket.tokens <= 0) {
      return {
        allowed: false,
        remaining: 0,
        retryAfter: Math.ceil(refillIntervalMs / 1000),
      }
    }

    bucket.tokens -= 1
    return {
      allowed: true,
      remaining: Math.floor(bucket.tokens),
      resetAt: Date.now() + (capacity - bucket.tokens) * refillIntervalMs,
    }
  }

  reset(key) {
    this.buckets.delete(key)
  }
}

// ─── src/strategies/leaky-bucket.js ───────────────────────
class LeakyBucketStore {
  constructor() {
    this.buckets = new Map() // key -> { queueSize, lastLeak }
  }

  async add(key, capacity, leakRatePerSecond) {
    const now = Date.now()
    let bucket = this.buckets.get(key)

    if (!bucket) {
      bucket = { queueSize: 0, lastLeak: now }
      this.buckets.set(key, bucket)
    }

    // 计算泄漏
    const elapsedSeconds = (now - bucket.lastLeak) / 1000
    const leaked = Math.floor(elapsedSeconds * leakRatePerSecond)
    bucket.queueSize = Math.max(0, bucket.queueSize - leaked)
    bucket.lastLeak = now

    if (bucket.queueSize >= capacity) {
      return {
        allowed: false,
        remaining: 0,
        retryAfter: Math.ceil((bucket.queueSize - capacity + 1) / leakRatePerSecond),
      }
    }

    bucket.queueSize += 1
    return {
      allowed: true,
      remaining: capacity - bucket.queueSize,
    }
  }

  reset(key) {
    this.buckets.delete(key)
  }
}
