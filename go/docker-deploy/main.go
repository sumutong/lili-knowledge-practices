// Package main — 容器化 Go 应用
// 演示多阶段构建、健康检查、环境变量配置、优雅关闭
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"
)

// ─── 应用配置 ─────────────────────────────────────────────

type Config struct {
	Port    string
	Env     string
	Version string
	DBHost  string
	DBPort  string
}

func LoadConfig() *Config {
	return &Config{
		Port:    getEnv("PORT", "8080"),
		Env:     getEnv("APP_ENV", "development"),
		Version: getEnv("APP_VERSION", "1.0.0"),
		DBHost:  getEnv("DB_HOST", "localhost"),
		DBPort:  getEnv("DB_PORT", "5432"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ─── 系统信息 ─────────────────────────────────────────────

type SystemInfo struct {
	GoVersion  string `json:"go_version"`
	NumCPU     int    `json:"num_cpu"`
	NumGoroutine int  `json:"num_goroutine"`
	Hostname   string `json:"hostname"`
	Uptime     string `json:"uptime"`
}

// ─── HTTP 处理器 ──────────────────────────────────────────

type App struct {
	config    *Config
	startTime time.Time
}

func NewApp(cfg *Config) *App {
	return &App{config: cfg, startTime: time.Now()}
}

func (a *App) healthHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":  "healthy",
		"version": a.config.Version,
		"env":     a.config.Env,
		"uptime":  time.Since(a.startTime).String(),
	})
}

func (a *App) infoHandler(w http.ResponseWriter, r *http.Request) {
	hostname, _ := os.Hostname()
	info := SystemInfo{
		GoVersion:    runtime.Version(),
		NumCPU:       runtime.NumCPU(),
		NumGoroutine: runtime.NumGoroutine(),
		Hostname:     hostname,
		Uptime:       time.Since(a.startTime).String(),
	}
	writeJSON(w, http.StatusOK, info)
}

func (a *App) configHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"port":    a.config.Port,
		"env":     a.config.Env,
		"version": a.config.Version,
		"db": map[string]string{
			"host": a.config.DBHost,
			"port": a.config.DBPort,
		},
	})
}

func (a *App) rootHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"message": "🚀 容器化 Go 应用运行中",
		"docs":    "/health /info /config",
	})
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// ─── 中间件 ───────────────────────────────────────────────

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(wrapped, r)
		log.Printf("[%s] %s %s %d %v",
			r.RemoteAddr, r.Method, r.URL.Path,
			wrapped.statusCode, time.Since(start))
	})
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	cfg := LoadConfig()
	app := NewApp(cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("/", app.rootHandler)
	mux.HandleFunc("/health", app.healthHandler)
	mux.HandleFunc("/info", app.infoHandler)
	mux.HandleFunc("/config", app.configHandler)

	var handler http.Handler = mux
	handler = loggingMiddleware(handler)

	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      handler,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  30 * time.Second,
	}

	// 优雅关闭
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		sig := <-sigCh
		log.Printf("收到信号 %v, 正在关闭...", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("关闭错误: %v", err)
		}
	}()

	fmt.Printf(`
╔══════════════════════════════════════╗
║   🐳 容器化 Go 应用 v%s          ║
║   环境: %s                    ║
║   端口: %s                     ║
╚══════════════════════════════════════╝
`, cfg.Version, cfg.Env, cfg.Port)

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("启动失败: %v", err)
	}
	log.Println("服务器已关闭")
}
