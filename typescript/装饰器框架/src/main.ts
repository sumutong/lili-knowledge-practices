// ─── src/container.ts ─────────────────────────────────────
import 'reflect-metadata'

// 元数据键
const INJECTABLE_KEY = Symbol('di:injectable')
const INJECT_KEY = Symbol('di:inject')
const POST_CONSTRUCT_KEY = Symbol('di:post-construct')

export type ScopeType = 'singleton' | 'transient' | 'request'

interface Provider<T = any> {
  token: any
  useClass?: new (...args: any[]) => T
  useFactory?: () => T
  useValue?: T
  scope?: ScopeType
}

// ─── 装饰器 ────────────────────────────────────────────

/** 标记为可注入 */
export function Injectable(options?: { scope?: ScopeType }) {
  return function <T extends new (...args: any[]) => any>(target: T, context: ClassDecoratorContext) {
    Reflect.defineMetadata(INJECTABLE_KEY, {
      scope: options?.scope || 'singleton',
      token: target,
    }, target)
    return target
  }
}

/** 注入依赖 */
export function Inject(token?: any) {
  return function (target: any, context: ClassFieldDecoratorContext) {
    const type = Reflect.getMetadata('design:type', target, context.name as string)
    Reflect.defineMetadata(INJECT_KEY, token || type, target, context.name as string)
  }
}

/** 构造函数后回调 */
export function PostConstruct() {
  return function (target: any, context: ClassMethodDecoratorContext) {
    Reflect.defineMetadata(POST_CONSTRUCT_KEY, context.name, target)
  }
}

// ─── 容器 ──────────────────────────────────────────────

export class Container {
  private static instance: Container
  private providers = new Map<any, Provider>()
  private instances = new Map<any, any>()

  static getInstance(): Container {
    if (!Container.instance) Container.instance = new Container()
    return Container.instance
  }

  /** 注册 Provider */
  register<T>(provider: Provider<T>): this {
    this.providers.set(provider.token, provider)
    return this
  }

  /** 获取实例 */
  resolve<T>(token: any): T {
    const provider = this.providers.get(token)

    if (!provider) {
      // 尝试从类本身提取
      if (typeof token === 'function' && Reflect.hasMetadata(INJECTABLE_KEY, token)) {
        return this.createInstance(token)
      }
      throw new Error(`No provider registered for token: ${String(token)}`)
    }

    if (provider.useValue !== undefined) {
      return provider.useValue as T
    }

    if (provider.useFactory) {
      return provider.useFactory() as T
    }

    if (provider.useClass) {
      return this.createInstance(provider.useClass, provider.scope) as T
    }

    throw new Error(`Invalid provider for token: ${String(token)}`)
  }

  /** 创建类实例并注入依赖 */
  private createInstance<T>(target: new (...args: any[]) => T, scope?: ScopeType): T {
    const effectiveScope = scope || this.getScope(target) || 'singleton'

    // 单例缓存
    if (effectiveScope === 'singleton') {
      if (this.instances.has(target)) return this.instances.get(target)
    }

    // 解析构造函数参数
    const paramTypes: any[] = Reflect.getMetadata('design:paramtypes', target) || []
    const params = paramTypes.map(pt => this.resolve(pt))

    const instance = new target(...params)

    // 属性注入
    const proto = target.prototype
    for (const key of Object.getOwnPropertyNames(proto)) {
      const injectToken = Reflect.getMetadata(INJECT_KEY, proto, key)
      if (injectToken) {
        ;(instance as any)[key] = this.resolve(injectToken)
      }
    }

    // PostConstruct 调用
    const postConstructMethod = Reflect.getMetadata(POST_CONSTRUCT_KEY, proto)
    if (postConstructMethod && typeof (instance as any)[postConstructMethod] === 'function') {
      (instance as any)[postConstructMethod]()
    }

    if (effectiveScope === 'singleton') {
      this.instances.set(target, instance)
    }

    return instance
  }

  private getScope(target: any): ScopeType | undefined {
    const meta = Reflect.getMetadata(INJECTABLE_KEY, target)
    return meta?.scope
  }
}
