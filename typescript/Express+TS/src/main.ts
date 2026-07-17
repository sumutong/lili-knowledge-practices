// ─── src/types/index.ts ───────────────────────────────────
export interface User {
  id: string
  username: string
  email: string
  role: 'admin' | 'editor' | 'user'
  active: boolean
  createdAt: Date
  updatedAt: Date
}

export interface CreateUserInput {
  username: string
  email: string
  password: string
  role?: 'admin' | 'editor' | 'user'
}

export interface UpdateUserInput {
  username?: string
  email?: string
  password?: string
  role?: 'admin' | 'editor' | 'user'
  active?: boolean
}

export interface PaginationQuery {
  page?: number
  pageSize?: number
  sort?: string
  order?: 'asc' | 'desc'
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface ApiResponse<T = unknown> {
  success: boolean
  message: string
  data?: T
  errors?: string[]
}

export interface TokenPayload {
  userId: string
  role: string
  iat?: number
  exp?: number
}
