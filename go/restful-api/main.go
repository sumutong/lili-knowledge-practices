// Package main — RESTful API 实战 (Go标准库 net/http)
// 完整的 CRUD API + 中间件 + JSON 序列化 + 优雅关闭
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

// ─── 数据模型 ─────────────────────────────────────────────

type Task struct {
	ID        int       `json:"id"`
	Title     string    `json:"title"`
	Completed bool      `json:"completed"`
	CreatedAt time.Time `json:"created_at"`
}

// ─── 数据存储 ─────────────────────────────────────────────

type TaskStore struct {
	mu    sync.RWMutex
	tasks map[int]*Task
	nextID int
}

func NewTaskStore() *TaskStore {
	return &TaskStore{
		tasks: make(map[int]*Task),
		nextID: 1,
	}
}

func (s *TaskStore) Create(title string) *Task {
	s.mu.Lock()
	defer s.mu.Unlock()
	t := &Task{
		ID:        s.nextID,
		Title:     title,
		Completed: false,
		CreatedAt: time.Now(),
	}
	s.tasks[t.ID] = t
	s.nextID++
	return t
}

func (s *TaskStore) List() []*Task {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := make([]*Task, 0, len(s.tasks))
	for _, t := range s.tasks {
		result = append(result, t)
	}
	return result
}

func (s *TaskStore) Get(id int) (*Task, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	t, ok := s.tasks[id]
	return t, ok
}

func (s *TaskStore) Update(id int, title string, completed *bool) (*Task, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.tasks[id]
	if !ok {
		return nil, false
	}
	if title != "" {
		t.Title = title
	}
	if completed != nil {
		t.Completed = *completed
	}
	return t, true
}

func (s *TaskStore) Delete(id int) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, ok := s.tasks[id]
	if ok {
		delete(s.tasks, id)
	}
	return ok
}

// ─── JSON 响应工具 ─────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("JSON encode error: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

// ─── 中间件 ───────────────────────────────────────────────

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %v", r.Method, r.URL.Path, time.Since(start))
	})
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// ─── 路由处理 ─────────────────────────────────────────────

type APIHandler struct {
	store *TaskStore
}

func (h *APIHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// 路径解析: /api/tasks 或 /api/tasks/{id}
	path := strings.TrimPrefix(r.URL.Path, "/api/tasks")
	path = strings.TrimSuffix(path, "/")

	switch {
	case path == "" && r.Method == http.MethodGet:
		h.listTasks(w, r)
	case path == "" && r.Method == http.MethodPost:
		h.createTask(w, r)
	case path != "" && r.Method == http.MethodGet:
		h.getTask(w, r, path)
	case path != "" && r.Method == http.MethodPut:
		h.updateTask(w, r, path)
	case path != "" && r.Method == http.MethodDelete:
		h.deleteTask(w, r, path)
	default:
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func (h *APIHandler) listTasks(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, h.store.List())
}

func (h *APIHandler) createTask(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Title string `json:"title"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if req.Title == "" {
		writeError(w, http.StatusBadRequest, "title is required")
		return
	}
	task := h.store.Create(req.Title)
	writeJSON(w, http.StatusCreated, task)
}

func (h *APIHandler) getTask(w http.ResponseWriter, r *http.Request, path string) {
	id, err := strconv.Atoi(strings.TrimPrefix(path, "/"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid task ID")
		return
	}
	task, ok := h.store.Get(id)
	if !ok {
		writeError(w, http.StatusNotFound, "task not found")
		return
	}
	writeJSON(w, http.StatusOK, task)
}

func (h *APIHandler) updateTask(w http.ResponseWriter, r *http.Request, path string) {
	id, err := strconv.Atoi(strings.TrimPrefix(path, "/"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid task ID")
		return
	}
	var req struct {
		Title     *string `json:"title"`
		Completed *bool   `json:"completed"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	var title string
	if req.Title != nil {
		title = *req.Title
	}
	task, ok := h.store.Update(id, title, req.Completed)
	if !ok {
		writeError(w, http.StatusNotFound, "task not found")
		return
	}
	writeJSON(w, http.StatusOK, task)
}

func (h *APIHandler) deleteTask(w http.ResponseWriter, r *http.Request, path string) {
	id, err := strconv.Atoi(strings.TrimPrefix(path, "/"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid task ID")
		return
	}
	if !h.store.Delete(id) {
		writeError(w, http.StatusNotFound, "task not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"message": "deleted"})
}

// ─── 健康检查 ─────────────────────────────────────────────

func healthHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status": "ok",
		"time":   time.Now().Format(time.RFC3339),
	})
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	store := NewTaskStore()
	// 预置示例数据
	store.Create("学习 Go RESTful API")
	store.Create("编写中间件")
	store.Create("实现优雅关闭")

	apiHandler := &APIHandler{store: store}

	mux := http.NewServeMux()
	mux.Handle("/api/tasks", apiHandler)
	mux.Handle("/api/tasks/", apiHandler)
	mux.HandleFunc("/health", healthHandler)

	// 组合中间件
	var handler http.Handler = mux
	handler = loggingMiddleware(handler)
	handler = corsMiddleware(handler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      handler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// 优雅关闭
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		log.Println("正在关闭服务器...")
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		srv.Shutdown(ctx)
	}()

	log.Printf("🚀 RESTful API 服务启动: http://localhost:%s", port)
	log.Printf("📋 API 端点: GET/POST /api/tasks, GET/PUT/DELETE /api/tasks/{id}")
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("服务器启动失败: %v", err)
	}
	log.Println("服务器已关闭")
}
