# Rust CLI 工具实战

基于 `clap` 的命令行工具箱，支持文件搜索、代码行数统计与批量内容替换。

## 功能

- **search** — 正则搜索文件内容（类似 grep）
- **count** — 统计代码行数
- **replace** — 批量替换文件内容（支持预览模式）

## 技术栈

- `clap` — 命令行参数解析
- `walkdir` — 递归目录遍历
- `regex` — 正则表达式匹配
- `colored` — 彩色终端输出
- `indicatif` — 进度条（扩展预留）

## 运行

```bash
cd cli-tool
cargo run -- search "fn main" -e rs
cargo run -- count -e rs
cargo run -- replace "old" "new" -e txt --dry-run
```

## 编译

```bash
cargo build --release
./target/release/cli-tool search "hello" .
```
