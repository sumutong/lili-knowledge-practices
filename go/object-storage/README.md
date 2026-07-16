# 对象存储实战 (Go)

基于 MinIO SDK 的 S3 兼容对象存储客户端，支持上传/下载/列表/预签名URL。

## 功能
- ✅ 文件上传 (multipart)
- ✅ 文件下载
- ✅ 对象列表（支持前缀过滤）
- ✅ 预签名下载 URL（临时访问链接）
- ✅ 自动创建 Bucket
- ✅ S3 兼容（MinIO/AWS S3/阿里云 OSS）

## 环境变量
```bash
export S3_ENDPOINT=localhost:9000
export S3_ACCESS_KEY=minioadmin
export S3_SECRET_KEY=minioadmin
export S3_BUCKET=my-bucket
export S3_USE_SSL=false
```

## 启动 MinIO（可选）
```bash
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

## 运行
```bash
go mod tidy
go run .
```

## API
```bash
# 上传文件
curl -X POST http://localhost:8080/api/upload \
  -F "file=@./test.txt" \
  -F "name=docs/test.txt"

# 列出对象
curl http://localhost:8080/api/objects?prefix=docs/

# 生成预签名URL (1小时有效)
curl "http://localhost:8080/api/presign?object=docs/test.txt"
```

## 技术要点
- `minio-go/v7` SDK
- 分片上传 (PutObject)
- 预签名 URL (PresignedGetObject)
- `multipart/form-data` 文件上传
- 环境变量灵活配置
