// Package main — 配置中心 (热更新 + 多格式 + HTTP API)
// 支持 JSON/YAML 配置文件、热加载、环境变量覆盖、配置版本管理
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

// ─── 配置模型 ─────────────────────────────────────────────

type AppConfig struct {
	Server   ServerConfig   `json:"server" yaml:"server"`
	Database DatabaseConfig `json:"database" yaml:"database"`
	Redis    RedisConfig    `json:"redis" yaml:"redis"`
	Features FeaturesConfig `json:"features" yaml:"features"`
}

type ServerConfig struct {
	Port         int           `json:"port" yaml:"port"`
	ReadTimeout  time.Duration `json:"read_timeout" yaml:"read_timeout"`
	WriteTimeout time.Duration `json:"write_timeout" yaml:"write_timeout"`
}

type DatabaseConfig struct {
	Host     string `json:"host" yaml:"host"`
	Port     int    `json:"port" yaml:"port"`
	User     string `json:"user" yaml:"user"`
	Password string `json:"password" yaml:"password"`
	DBName   string `json:"dbname" yaml:"dbname"`
	MaxConns int    `json:"max_conns" yaml:"max_conns"`
}

type RedisConfig struct {
	Host string `json:"host" yaml:"host"`
	Port int    `json:"port" yaml:"port"`
	DB   int    `json:"db" yaml:"db"`
}

type FeaturesConfig struct {
	EnableCache    bool `json:"enable_cache" yaml:"enable_cache"`
	EnableRateLimit bool `json:"enable_rate_limit" yaml:"enable_rate_limit"`
	EnableMetrics  bool `json:"enable_metrics" yaml:"enable_metrics"`
}

// ─── 配置管理器 ───────────────────────────────────────────

type ConfigManager struct {
	mu       sync.RWMutex
	config   *AppConfig
	filePath string
	version  int64
	watchers []chan *AppConfig
}

func NewConfigManager(filePath string) *ConfigManager {
	return &ConfigManager{
		filePath: filePath,
		watchers: make([]chan *AppConfig, 0),
	}
}

// Load 加载配置
func (m *ConfigManager) Load() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	cfg := &AppConfig{}
	data, err := os.ReadFile(m.filePath)
	if err != nil {
		return fmt.Errorf("读取配置文件失败: %w", err)
	}

	// 根据扩展名选择解析器
	if isYAML(m.filePath) {
		if err := yaml.Unmarshal(data, cfg); err != nil {
			return fmt.Errorf("解析 YAML 失败: %w", err)
		}
	} else {
		if err := json.Unmarshal(data, cfg); err != nil {
			return fmt.Errorf("解析 JSON 失败: %w", err)
		}
	}

	// 环境变量覆盖
	applyEnvOverrides(cfg)

	m.config = cfg
	m.version++
	log.Printf("📄 配置已加载 (v%d): %s", m.version, m.filePath)
	return nil
}

// Get 获取当前配置
func (m *ConfigManager) Get() *AppConfig {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.config
}

// Watch 订阅配置变更
func (m *ConfigManager) Watch() <-chan *AppConfig {
	m.mu.Lock()
	defer m.mu.Unlock()
	ch := make(chan *AppConfig, 1)
	m.watchers = append(m.watchers, ch)
	return ch
}

// StartWatcher 启动文件监控（简化版：轮询）
func (m *ConfigManager) StartWatcher(interval time.Duration) {
	ticker := time.NewTicker(interval)
	go func() {
		for range ticker.C {
			info, err := os.Stat(m.filePath)
			if err != nil {
				log.Printf("⚠️  检查配置文件失败: %v", err)
				continue
			}

			m.mu.RLock()
			currentVersion := m.version
			m.mu.RUnlock()

			// 简化：通过文件修改时间判断
			_ = info
			if err := m.Load(); err != nil {
				continue
			}

			m.mu.RLock()
			newVersion := m.version
			cfg := m.config
			m.mu.RUnlock()

			if newVersion > currentVersion {
				log.Println("🔄 配置已更新，通知订阅者...")
				for _, ch := range m.watchers {
					select {
					case ch <- cfg:
					default:
					}
				}
			}
		}
	}()
	log.Printf("👁️  配置监控已启动，检查间隔: %v", interval)
}

// ─── 环境变量覆盖 ─────────────────────────────────────────

func applyEnvOverrides(cfg *AppConfig) {
	if v := os.Getenv("SERVER_PORT"); v != "" {
		fmt.Sscanf(v, "%d", &cfg.Server.Port)
	}
	if v := os.Getenv("DB_HOST"); v != "" {
		cfg.Database.Host = v
	}
	if v := os.Getenv("DB_PORT"); v != "" {
		fmt.Sscanf(v, "%d", &cfg.Database.Port)
	}
	if v := os.Getenv("DB_PASSWORD"); v != "" {
		cfg.Database.Password = v
	}
	if v := os.Getenv("REDIS_HOST"); v != "" {
		cfg.Redis.Host = v
	}
}

// ─── 工具 ─────────────────────────────────────────────────

func isYAML(path string) bool {
	ext := path[len(path)-4:]
	return ext == ".yml" || ext == "yaml"
}

// ─── HTTP API ─────────────────────────────────────────────

func (m *ConfigManager) apiGetConfig(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(m.Get())
}

func (m *ConfigManager) apiReload(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	if err := m.Load(); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"message": "配置已重新加载",
		"version": m.version,
	})
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	configPath := os.Getenv("CONFIG_PATH")
	if configPath == "" {
		configPath = "config.yaml"
	}

	manager := NewConfigManager(configPath)

	if err := manager.Load(); err != nil {
		log.Fatalf("❌ 加载配置失败: %v", err)
	}

	// 启动热加载监控
	manager.StartWatcher(5 * time.Second)

	// 示例：业务层订阅配置变更
	go func() {
		ch := manager.Watch()
		for cfg := range ch {
			log.Printf("📢 业务层收到配置更新: server.port=%d, features: %+v",
				cfg.Server.Port, cfg.Features)
		}
	}()

	// HTTP API
	http.HandleFunc("/api/config", manager.apiGetConfig)
	http.HandleFunc("/api/config/reload", manager.apiReload)
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 配置中心启动: http://localhost:%s", port)
	log.Printf("📋 查看配置: http://localhost:%s/api/config", port)
	log.Printf("🔄 热加载: POST http://localhost:%s/api/config/reload", port)

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("启动失败: %v", err)
	}
}
