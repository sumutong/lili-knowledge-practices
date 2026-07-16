// Package main — 定时任务调度器 (robfig/cron)
// 支持 Cron 表达式、秒级精度、任务管理 API
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/robfig/cron/v3"
)

// ─── 任务模型 ─────────────────────────────────────────────

type ScheduledJob struct {
	ID       cron.EntryID `json:"id"`
	Name     string       `json:"name"`
	CronExpr string       `json:"cron_expr"`
	Enabled  bool         `json:"enabled"`
	LastRun  *time.Time   `json:"last_run,omitempty"`
	NextRun  time.Time    `json:"next_run"`
}

// ─── 任务管理器 ───────────────────────────────────────────

type JobManager struct {
	cron *cron.Cron
	jobs map[cron.EntryID]*ScheduledJob
	mu   sync.RWMutex
}

func NewJobManager() *JobManager {
	return &JobManager{
		cron: cron.New(cron.WithSeconds()),
		jobs: make(map[cron.EntryID]*ScheduledJob),
	}
}

func (m *JobManager) AddJob(name, cronExpr string, fn func()) (*ScheduledJob, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	var entryID cron.EntryID
	entryID, err := m.cron.AddFunc(cronExpr, func() {
		now := time.Now()
		m.mu.Lock()
		if job, ok := m.jobs[entryID]; ok {
			job.LastRun = &now
		}
		m.mu.Unlock()
		log.Printf("⏰ [%s] 执行中...", name)
		fn()
		log.Printf("✅ [%s] 执行完成", name)
	})
	if err != nil {
		return nil, fmt.Errorf("添加任务失败: %w", err)
	}

	entry := m.cron.Entry(entryID)
	job := &ScheduledJob{
		ID:       entryID,
		Name:     name,
		CronExpr: cronExpr,
		Enabled:  true,
		NextRun:  entry.Next,
	}
	m.jobs[entryID] = job
	return job, nil
}

func (m *JobManager) RemoveJob(id cron.EntryID) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.cron.Remove(id)
	delete(m.jobs, id)
	return nil
}

func (m *JobManager) ListJobs() []*ScheduledJob {
	m.mu.RLock()
	defer m.mu.RUnlock()
	jobs := make([]*ScheduledJob, 0, len(m.jobs))
	for _, j := range m.jobs {
		jobs = append(jobs, j)
	}
	return jobs
}

func (m *JobManager) Start() {
	m.cron.Start()
	log.Println("🕐 定时任务调度器已启动")
}

func (m *JobManager) Stop() {
	m.cron.Stop()
}

// ─── HTTP API ─────────────────────────────────────────────

func (m *JobManager) apiListJobs(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(m.ListJobs())
}

// ─── 示例任务 ─────────────────────────────────────────────

func cleanupLogs() {
	log.Println("  📋 清理过期日志...")
}

func healthReport() {
	log.Println("  💚 发送健康报告...")
}

func dataBackup() {
	log.Println("  💾 执行数据备份...")
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	manager := NewJobManager()

	// 注册示例定时任务
	manager.AddJob("日志清理", "0 0 2 * * *", cleanupLogs)       // 每天凌晨2点
	manager.AddJob("健康报告", "0 */5 * * * *", healthReport)    // 每5分钟
	manager.AddJob("数据备份", "0 0 0 * * 1", dataBackup)       // 每周一凌晨

	manager.Start()

	// HTTP API
	http.HandleFunc("/api/jobs", manager.apiListJobs)
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "ok",
			"jobs":   len(manager.ListJobs()),
		})
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 定时任务服务启动: http://localhost:%s", port)
	log.Printf("📋 查看任务: http://localhost:%s/api/jobs", port)

	// 打印注册的任务
	fmt.Println("\n📅 已注册定时任务:")
	for _, j := range manager.ListJobs() {
		fmt.Printf("  • %s | %s | 下次执行: %s\n",
			j.Name, j.CronExpr, j.NextRun.Format("2006-01-02 15:04:05"))
	}
	fmt.Println()

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("服务器启动失败: %v", err)
	}
}
