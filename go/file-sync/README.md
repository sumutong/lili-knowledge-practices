# 文件同步工具 (Go)

rsync 风格的文件同步工具，支持增量同步、SHA256 哈希比对、并发复制、定时同步。

## 功能
- ✅ 增量同步（大小+修改时间+哈希三重校验）
- ✅ SHA256 哈希比对
- ✅ 并发复制（Worker Pool）
- ✅ 排除模式（glob 匹配）
- ✅ 目标清理（删除多余文件）
- ✅ 预览模式（Dry Run）
- ✅ 定时同步

## 运行
```bash
# 基本同步
go run . -s ./source -t ./target

# 预览模式
go run . -s ./source -t ./target --dry-run

# 排除文件 + 删除多余 + 8并发
go run . -s ./source -t ./target --exclude "*.tmp,*.log" --delete --workers 8

# 定时同步（每30秒）
go run . -s ./source -t ./target --interval 30s
```

## 技术要点
- `crypto/sha256` 文件哈希
- Worker Pool 并发模型
- `filepath.Walk` 目录遍历
- 文件修改时间保留 (`os.Chtimes`)
- `time.Ticker` 定时同步
