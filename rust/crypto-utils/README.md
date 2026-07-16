# Rust 加密实战

多功能加密工具箱：AES-256-GCM 加解密、SHA-256 哈希、Base64 编解码。

## 功能

- **encrypt** — AES-256-GCM 加密（输出 nonce:ciphertext 格式）
- **decrypt** — AES-256-GCM 解密
- **gen-key** — 生成随机 256 位密钥
- **hash** — SHA-256 哈希摘要
- **encode** — Base64 编码
- **decode** — Base64 解码

## 技术栈

- `aes-gcm` — AES-GCM 认证加密
- `sha2` — SHA-256 哈希
- `base64` — Base64 编解码
- `hex` — 十六进制编码

## 运行

```bash
cd crypto-utils

# 生成密钥
cargo run -- gen-key

# 加密
cargo run -- encrypt "Hello World" -k <your-key>

# 解密
cargo run -- decrypt "nonce:ciphertext" -k <your-key>

# 哈希
cargo run -- hash "data to hash"
```
