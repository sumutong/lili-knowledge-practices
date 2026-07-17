// ─── src/types.ts ─────────────────────────────────────────
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'

export type RequestHeaders = Record<string, string>

export interface RequestConfig<TBody = unknown> {
  baseURL?: string
  url: string
  method: HttpMethod
  headers?: RequestHeaders
  params?: Record<string, string | number | boolean | undefined>
  body?: TBody
  timeout?: number
  signal?: AbortSignal
  responseType?: 'json' | 'text' | 'blob' | 'arraybuffer'
  withCredentials?: boolean
  retry?: number
  retryDelay?: number
}

export interface ApiResponse<T> {
  data: T
  status: number
  statusText: string
  headers: Record<string, string>
  config: RequestConfig
}

export interface ApiError<T = unknown> extends Error {
  status?: number
  statusText?: string
  data?: T
  config?: RequestConfig
  isCancel?: boolean
  isTimeout?: boolean
}

// 拦截器类型
export type Interceptor<T> = {
  onFulfilled?: (value: T) => T | Promise<T>
  onRejected?: (error: ApiError) => ApiError | Promise<ApiError>
}

// 中间件类型
export type Middleware = {
  request?: (config: RequestConfig) => RequestConfig | Promise<RequestConfig>
  response?: <T>(response: ApiResponse<T>) => ApiResponse<T> | Promise<ApiResponse<T>>
  error?: (error: ApiError) => ApiError | Promise<ApiError>
}

export interface HttpClientOptions {
  baseURL?: string
  timeout?: number
  headers?: RequestHeaders
  retry?: number
  retryDelay?: number
  withCredentials?: boolean
}
