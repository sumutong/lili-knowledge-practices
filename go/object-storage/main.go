// Package main — 对象存储客户端 (MinIO / AWS S3 兼容)
// 支持上传、下载、列表、预签名URL、分片上传
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// ─── 配置 ─────────────────────────────────────────────────

type StorageConfig struct {
	Endpoint        string
	AccessKeyID     string
	SecretAccessKey string
	BucketName      string
	UseSSL          bool
}

func LoadConfig() *StorageConfig {
	return &StorageConfig{
		Endpoint:        getEnv("S3_ENDPOINT", "localhost:9000"),
		AccessKeyID:     getEnv("S3_ACCESS_KEY", "minioadmin"),
		SecretAccessKey: getEnv("S3_SECRET_KEY", "minioadmin"),
		BucketName:      getEnv("S3_BUCKET", "my-bucket"),
		UseSSL:          getEnv("S3_USE_SSL", "false") == "true",
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ─── 对象存储客户端 ───────────────────────────────────────

type ObjectStore struct {
	client *minio.Client
	cfg    *StorageConfig
}

func NewObjectStore(cfg *StorageConfig) (*ObjectStore, error) {
	client, err := minio.New(cfg.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKeyID, cfg.SecretAccessKey, ""),
		Secure: cfg.UseSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("创建 MinIO 客户端失败: %w", err)
	}
	return &ObjectStore{client: client, cfg: cfg}, nil
}

// EnsureBucket 确保存储桶存在
func (s *ObjectStore) EnsureBucket(ctx context.Context) error {
	exists, err := s.client.BucketExists(ctx, s.cfg.BucketName)
	if err != nil {
		return fmt.Errorf("检查存储桶失败: %w", err)
	}
	if !exists {
		if err := s.client.MakeBucket(ctx, s.cfg.BucketName, minio.MakeBucketOptions{}); err != nil {
			return fmt.Errorf("创建存储桶失败: %w", err)
		}
		log.Printf("✅ 创建存储桶: %s", s.cfg.BucketName)
	}
	log.Printf("📦 存储桶就绪: %s", s.cfg.BucketName)
	return nil
}

// UploadFile 上传文件
func (s *ObjectStore) UploadFile(ctx context.Context, objectName, filePath string) error {
	_, err := s.client.FPutObject(ctx, s.cfg.BucketName, objectName, filePath, minio.PutObjectOptions{
		ContentType: "application/octet-stream",
	})
	if err != nil {
		return fmt.Errorf("上传失败: %w", err)
	}
	log.Printf("📤 上传成功: %s → %s", filePath, objectName)
	return nil
}

// DownloadFile 下载文件
func (s *ObjectStore) DownloadFile(ctx context.Context, objectName, filePath string) error {
	if err := os.MkdirAll(filepath.Dir(filePath), 0755); err != nil {
		return err
	}
	if err := s.client.FGetObject(ctx, s.cfg.BucketName, objectName, filePath, minio.GetObjectOptions{}); err != nil {
		return fmt.Errorf("下载失败: %w", err)
	}
	log.Printf("📥 下载成功: %s → %s", objectName, filePath)
	return nil
}

// ListObjects 列出对象
func (s *ObjectStore) ListObjects(ctx context.Context, prefix string) ([]map[string]interface{}, error) {
	objects := s.client.ListObjects(ctx, s.cfg.BucketName, minio.ListObjectsOptions{
		Prefix:    prefix,
		Recursive: true,
	})

	var result []map[string]interface{}
	for obj := range objects {
		if obj.Err != nil {
			return nil, obj.Err
		}
		result = append(result, map[string]interface{}{
			"name":         obj.Key,
			"size":         obj.Size,
			"last_modified": obj.LastModified.Format(time.RFC3339),
			"etag":         obj.ETag,
		})
	}
	return result, nil
}

// PresignedURL 生成预签名下载 URL
func (s *ObjectStore) PresignedURL(ctx context.Context, objectName string, expiry time.Duration) (string, error) {
	url, err := s.client.PresignedGetObject(ctx, s.cfg.BucketName, objectName, expiry, nil)
	if err != nil {
		return "", fmt.Errorf("生成预签名URL失败: %w", err)
	}
	return url.String(), nil
}

// DeleteObject 删除对象
func (s *ObjectStore) DeleteObject(ctx context.Context, objectName string) error {
	return s.client.RemoveObject(ctx, s.cfg.BucketName, objectName, minio.RemoveObjectOptions{})
}

// ─── HTTP API ─────────────────────────────────────────────

type APIHandler struct {
	store *ObjectStore
}

func (h *APIHandler) listHandler(w http.ResponseWriter, r *http.Request) {
	prefix := r.URL.Query().Get("prefix")
	objects, err := h.store.ListObjects(context.Background(), prefix)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, objects)
}

func (h *APIHandler) uploadHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	// 限制上传大小 10MB
	r.ParseMultipartForm(10 << 20)
	file, header, err := r.FormFile("file")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "请选择文件"})
		return
	}
	defer file.Close()

	objectName := r.FormValue("name")
	if objectName == "" {
		objectName = header.Filename
	}

	// 写入临时文件
	tmpFile, err := os.CreateTemp("", "upload-*")
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer os.Remove(tmpFile.Name())
	defer tmpFile.Close()

	if _, err := io.Copy(tmpFile, file); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	if err := h.store.UploadFile(context.Background(), objectName, tmpFile.Name()); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"message": "上传成功",
		"object":  objectName,
	})
}

func (h *APIHandler) presignHandler(w http.ResponseWriter, r *http.Request) {
	objectName := r.URL.Query().Get("object")
	if objectName == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "缺少 object 参数"})
		return
	}
	url, err := h.store.PresignedURL(context.Background(), objectName, 1*time.Hour)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"url": url, "expires_in": "1h"})
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	cfg := LoadConfig()

	store, err := NewObjectStore(cfg)
	if err != nil {
		log.Fatalf("初始化对象存储失败: %v", err)
	}

	if err := store.EnsureBucket(context.Background()); err != nil {
		log.Fatalf("存储桶检查失败: %v", err)
	}

	handler := &APIHandler{store: store}

	http.HandleFunc("/api/objects", handler.listHandler)
	http.HandleFunc("/api/upload", handler.uploadHandler)
	http.HandleFunc("/api/presign", handler.presignHandler)
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	port := getEnv("PORT", "8080")
	log.Printf("🚀 对象存储服务启动: http://localhost:%s", port)
	log.Printf("📦 存储桶: %s | 端点: %s", cfg.BucketName, cfg.Endpoint)

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("启动失败: %v", err)
	}
}
