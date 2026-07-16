// Package main — 微服务 API 网关
// 反向代理、负载均衡、服务发现、限流、熔断
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

// ─── 服务实例 ─────────────────────────────────────────────

type ServiceInstance struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Host    string `json:"host"`
	Port    int    `json:"port"`
	Healthy bool   `json:"healthy"`
}

func (s *ServiceInstance) URL() string {
	return "http://" + s.Host + ":" + itoa(s.Port)
}

// ─── 服务注册表 ───────────────────────────────────────────

type ServiceRegistry struct {
	services map[string][]*ServiceInstance
	mu       sync.RWMutex
}

func NewServiceRegistry() *ServiceRegistry {
	return &ServiceRegistry{services: make(map[string][]*ServiceInstance)}
}

func (r *ServiceRegistry) Register(svc *ServiceInstance) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.services[svc.Name] = append(r.services[svc.Name], svc)
	log.Printf("📝 注册服务: %s → %s (%s)", svc.Name, svc.URL(), svc.ID)
}

func (r *ServiceRegistry) GetService(name string) ([]*ServiceInstance, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	svcs, ok := r.services[name]
	return svcs, ok
}

func (r *ServiceRegistry) ListServices() map[string][]*ServiceInstance {
	r.mu.RLock()
	defer r.mu.RUnlock()
	result := make(map[string][]*ServiceInstance)
	for k, v := range r.services {
		result[k] = v
	}
	return result
}

// ─── 负载均衡器（轮询）────────────────────────────────────

type RoundRobinBalancer struct {
	counter uint64
}

func (b *RoundRobinBalancer) Next(instances []*ServiceInstance) *ServiceInstance {
	if len(instances) == 0 {
		return nil
	}
	// 只选健康的实例
	healthy := make([]*ServiceInstance, 0)
	for _, inst := range instances {
		if inst.Healthy {
			healthy = append(healthy, inst)
		}
	}
	if len(healthy) == 0 {
		return nil
	}
	idx := atomic.AddUint64(&b.counter, 1) % uint64(len(healthy))
	return healthy[idx]
}

// ─── 反向代理 ─────────────────────────────────────────────

type Gateway struct {
	registry *ServiceRegistry
	balancer *RoundRobinBalancer
	// 限流: 简单令牌桶
	rateLimiters map[string]*TokenBucket
	rlMu         sync.Mutex
}

func NewGateway() *Gateway {
	return &Gateway{
		registry:     NewServiceRegistry(),
		balancer:     &RoundRobinBalancer{},
		rateLimiters: make(map[string]*TokenBucket),
	}
}

// 限流器
type TokenBucket struct {
	rate       float64
	capacity   float64
	tokens     float64
	lastRefill time.Time
	mu         sync.Mutex
}

func NewTokenBucket(rate, capacity float64) *TokenBucket {
	return &TokenBucket{
		rate:       rate,
		capacity:   capacity,
		tokens:     capacity,
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens += elapsed * tb.rate
	if tb.tokens > tb.capacity {
		tb.tokens = tb.capacity
	}
	tb.lastRefill = now
	if tb.tokens >= 1 {
		tb.tokens--
		return true
	}
	return false
}

// ─── 路由处理 ─────────────────────────────────────────────

func (g *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// 限流检查
	clientIP := r.RemoteAddr
	if !g.getRateLimiter(clientIP).Allow() {
		writeJSON(w, http.StatusTooManyRequests, map[string]string{
			"error": "rate limit exceeded, try again later",
		})
		return
	}

	// 路径: /api/<service-name>/...
	path := r.URL.Path
	if len(path) < 5 || path[:5] != "/api/" {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}

	// 提取服务名
	rest := path[5:]
	slashIdx := 0
	for i, c := range rest {
		if c == '/' {
			slashIdx = i
			break
		}
	}
	var serviceName, remainingPath string
	if slashIdx > 0 {
		serviceName = rest[:slashIdx]
		remainingPath = rest[slashIdx:]
	} else {
		serviceName = rest
		remainingPath = "/"
	}

	instances, ok := g.registry.GetService(serviceName)
	if !ok || len(instances) == 0 {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{
			"error": "service not found: " + serviceName,
		})
		return
	}

	instance := g.balancer.Next(instances)
	if instance == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{
			"error": "no healthy instance for: " + serviceName,
		})
		return
	}

	// 反向代理
	target, _ := url.Parse(instance.URL())
	proxy := httputil.NewSingleHostReverseProxy(target)
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.URL.Path = remainingPath
		req.Host = target.Host
	}

	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("❌ 代理错误 [%s]: %v", serviceName, err)
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "bad gateway"})
	}

	log.Printf("🔄 %s %s → %s%s", r.Method, r.URL.Path, instance.URL(), remainingPath)
	proxy.ServeHTTP(w, r)
}

func (g *Gateway) getRateLimiter(key string) *TokenBucket {
	g.rlMu.Lock()
	defer g.rlMu.Unlock()
	if rl, ok := g.rateLimiters[key]; ok {
		return rl
	}
	rl := NewTokenBucket(10, 20) // 每秒10个请求, 突发20
	g.rateLimiters[key] = rl
	return rl
}

// ─── 管理 API ─────────────────────────────────────────────

func (g *Gateway) adminHandler(w http.ResponseWriter, r *http.Request) {
	switch r.URL.Path {
	case "/admin/services":
		writeJSON(w, http.StatusOK, g.registry.ListServices())
	case "/admin/register":
		if r.Method != http.MethodPost {
			writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
			return
		}
		var svc ServiceInstance
		if err := json.NewDecoder(r.Body).Decode(&svc); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON"})
			return
		}
		svc.Healthy = true
		g.registry.Register(&svc)
		writeJSON(w, http.StatusCreated, svc)
	default:
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
	}
}

// ─── 工具 ─────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func itoa(i int) string {
	return fmt.Sprintf("%d", i)
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	gateway := NewGateway()

	// 预注册示例服务
	gateway.registry.Register(&ServiceInstance{
		ID: "user-1", Name: "user-service",
		Host: "localhost", Port: 8081, Healthy: true,
	})
	gateway.registry.Register(&ServiceInstance{
		ID: "user-2", Name: "user-service",
		Host: "localhost", Port: 8082, Healthy: true,
	})
	gateway.registry.Register(&ServiceInstance{
		ID: "order-1", Name: "order-service",
		Host: "localhost", Port: 8083, Healthy: true,
	})

	mux := http.NewServeMux()
	mux.Handle("/api/", gateway)
	mux.HandleFunc("/admin/", gateway.adminHandler)
	mux.HandleFunc("/admin/services", gateway.adminHandler)
	mux.HandleFunc("/admin/register", gateway.adminHandler)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 微服务网关启动: http://localhost:%s", port)
	log.Printf("📋 管理端点: http://localhost:%s/admin/services", port)
	log.Printf("🔄 代理路径: /api/<service-name>/<path>")

	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("启动失败: %v", err)
	}
}
