// ─── src/deep-utils.ts ────────────────────────────────────

/** 深层只读 */
export type DeepReadonly<T> = T extends Function
  ? T
  : T extends Array<infer R>
    ? ReadonlyArray<DeepReadonly<R>>
    : T extends object
      ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
      : T

/** 深层可选 */
export type DeepPartial<T> = T extends Array<infer R>
  ? Array<DeepPartial<R>>
  : T extends object
    ? { [K in keyof T]?: DeepPartial<T[K]> }
    : T

/** 深层必选 */
export type DeepRequired<T> = T extends Array<infer R>
  ? Array<DeepRequired<R>>
  : T extends object
    ? { [K in keyof T]-?: DeepRequired<T[K]> }
    : T

/** 深层非空 */
export type DeepNonNullable<T> = T extends Array<infer R>
  ? Array<DeepNonNullable<R>>
  : T extends object
    ? { [K in keyof T]: DeepNonNullable<T[K]> }
    : NonNullable<T>

/** 深层冻结 (只读 + 可选标记为只读) */
export type DeepFreeze<T> = T extends Function
  ? T
  : T extends Array<infer R>
    ? readonly DeepFreeze<R>[]
    : T extends object
      ? { readonly [K in keyof T]: DeepFreeze<T[K]> }
      : T
