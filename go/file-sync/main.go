// Package main — 文件同步工具 (rsync 风格)
// 支持增量同步、文件哈希比对、定时同步、排除规则
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// ─── 配置 ─────────────────────────────────────────────────

type SyncConfig struct {
	Source   string
	Target   string
	Excludes []string
	DryRun   bool
	Delete   bool
	Workers  int
	Interval time.Duration // 定时同步间隔
}

// ─── 文件信息 ─────────────────────────────────────────────

type FileInfo struct {
	Path    string
	Size    int64
	ModTime time.Time
	IsDir   bool
}

type SyncResult struct {
	Total     int
	Copied    int
	Skipped   int
	Deleted   int
	Errors    int
	Duration  time.Duration
}

// ─── 同步引擎 ─────────────────────────────────────────────

type Syncer struct {
	cfg SyncConfig
}

func NewSyncer(cfg SyncConfig) *Syncer {
	return &Syncer{cfg: cfg}
}

// HashFile 计算文件 SHA256
func (s *Syncer) HashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// IsExcluded 检查是否在排除列表中
func (s *Syncer) IsExcluded(path string) bool {
	name := filepath.Base(path)
	for _, pattern := range s.cfg.Excludes {
		matched, err := filepath.Match(pattern, name)
		if err == nil && matched {
			return true
		}
		if strings.HasPrefix(pattern, "*.") {
			if strings.HasSuffix(name, pattern[1:]) {
				return true
			}
		}
	}
	return false
}

// ScanSource 扫描源目录
func (s *Syncer) ScanSource() (map[string]*FileInfo, error) {
	files := make(map[string]*FileInfo)

	err := filepath.Walk(s.cfg.Source, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		relPath, _ := filepath.Rel(s.cfg.Source, path)
		if relPath == "." {
			return nil
		}

		if s.IsExcluded(relPath) {
			if info.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		files[relPath] = &FileInfo{
			Path:    relPath,
			Size:    info.Size(),
			ModTime: info.ModTime(),
			IsDir:   info.IsDir(),
		}
		return nil
	})

	return files, err
}

// Sync 执行同步
func (s *Syncer) Sync() (*SyncResult, error) {
	result := &SyncResult{}
	start := time.Now()

	// 扫描源
	srcFiles, err := s.ScanSource()
	if err != nil {
		return nil, fmt.Errorf("扫描源目录失败: %w", err)
	}
	result.Total = len(srcFiles)

	// 创建工作池
	type job struct {
		relPath string
		info    *FileInfo
	}

	jobs := make(chan job, len(srcFiles))
	results := make(chan error, len(srcFiles))

	var wg sync.WaitGroup
	for i := 0; i < s.cfg.Workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobs {
				err := s.syncFile(j.relPath, j.info)
				results <- err
			}
		}()
	}

	for path, info := range srcFiles {
		jobs <- job{relPath: path, info: info}
	}
	close(jobs)
	wg.Wait()
	close(results)

	for err := range results {
		if err != nil {
			result.Errors++
			log.Printf("❌ %v", err)
		} else {
			result.Copied++
		}
	}

	// 删除目标多余文件（如果启用）
	if s.cfg.Delete {
		deleted, _ := s.cleanTarget(srcFiles)
		result.Deleted = deleted
	}

	result.Duration = time.Since(start)
	return result, nil
}

func (s *Syncer) syncFile(relPath string, info *FileInfo) error {
	srcPath := filepath.Join(s.cfg.Source, relPath)
	targetPath := filepath.Join(s.cfg.Target, relPath)

	if info.IsDir {
		if s.cfg.DryRun {
			log.Printf("[DRY-RUN] 创建目录: %s", relPath)
			return nil
		}
		return os.MkdirAll(targetPath, 0755)
	}

	// 检查是否需要同步
	needSync := true
	if targetInfo, err := os.Stat(targetPath); err == nil {
		if targetInfo.Size() == info.Size && targetInfo.ModTime().Equal(info.ModTime) {
			// 大小和修改时间相同，进一步校验哈希
			srcHash, _ := s.HashFile(srcPath)
			targetHash, _ := s.HashFile(targetPath)
			if srcHash == targetHash {
				needSync = false
			}
		}
	}

	if !needSync {
		result := &SyncResult{Skipped: 1}
		_ = result
		return nil
	}

	if s.cfg.DryRun {
		log.Printf("[DRY-RUN] 同步: %s", relPath)
		return nil
	}

	// 确保目标目录存在
	if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
		return fmt.Errorf("创建目录失败 %s: %w", filepath.Dir(targetPath), err)
	}

	// 复制文件
	if err := s.copyFile(srcPath, targetPath); err != nil {
		return fmt.Errorf("复制失败 %s: %w", relPath, err)
	}

	log.Printf("✅ 同步: %s", relPath)
	return nil
}

func (s *Syncer) copyFile(src, dst string) error {
	srcFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer srcFile.Close()

	dstFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer dstFile.Close()

	if _, err := io.Copy(dstFile, srcFile); err != nil {
		return err
	}

	// 保留修改时间
	srcInfo, _ := os.Stat(src)
	return os.Chtimes(dst, srcInfo.ModTime(), srcInfo.ModTime())
}

func (s *Syncer) cleanTarget(srcFiles map[string]*FileInfo) (int, error) {
	deleted := 0
	err := filepath.Walk(s.cfg.Target, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		relPath, _ := filepath.Rel(s.cfg.Target, path)
		if relPath == "." {
			return nil
		}
		if _, exists := srcFiles[relPath]; !exists {
			log.Printf("🗑️  删除多余文件: %s", relPath)
			if !s.cfg.DryRun {
				os.RemoveAll(path)
			}
			deleted++
		}
		return nil
	})
	return deleted, err
}

// ─── 定时同步 ─────────────────────────────────────────────

func (s *Syncer) WatchAndSync() {
	ticker := time.NewTicker(s.cfg.Interval)
	defer ticker.Stop()

	log.Printf("⏰ 定时同步已启动，间隔: %v", s.cfg.Interval)
	for range ticker.C {
		log.Println("🔄 开始定时同步...")
		result, err := s.Sync()
		if err != nil {
			log.Printf("❌ 同步失败: %v", err)
			continue
		}
		log.Printf("✅ 同步完成: 总计 %d, 复制 %d, 跳过 %d, 删除 %d, 错误 %d, 耗时 %v",
			result.Total, result.Copied, result.Skipped, result.Deleted, result.Errors, result.Duration)
	}
}

// ─── CLI 入口 ─────────────────────────────────────────────

func main() {
	var (
		source   string
		target   string
		excludes string
		dryRun   bool
		delete   bool
		workers  int
		interval string
	)

	flag.StringVar(&source, "source", "", "源目录路径")
	flag.StringVar(&source, "s", "", "同 --source")
	flag.StringVar(&target, "target", "", "目标目录路径")
	flag.StringVar(&target, "t", "", "同 --target")
	flag.StringVar(&excludes, "exclude", "", "排除模式（逗号分隔）: *.tmp,*.log")
	flag.BoolVar(&dryRun, "dry-run", false, "预览模式")
	flag.BoolVar(&dryRun, "n", false, "同 --dry-run")
	flag.BoolVar(&delete, "delete", false, "删除目标多余文件")
	flag.IntVar(&workers, "workers", 4, "并发工作协程数")
	flag.StringVar(&interval, "interval", "", "定时同步间隔（如 30s, 5m）")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, `🔄 文件同步工具

用法:
  filesync -s <源目录> -t <目标目录> [选项]

选项:
`)
		flag.PrintDefaults()
	}

	flag.Parse()

	if source == "" || target == "" {
		fmt.Fprintln(os.Stderr, "错误: 必须指定源和目标目录")
		flag.Usage()
		os.Exit(1)
	}

	var excludeList []string
	if excludes != "" {
		excludeList = strings.Split(excludes, ",")
	}

	var intervalDuration time.Duration
	if interval != "" {
		var err error
		intervalDuration, err = time.ParseDuration(interval)
		if err != nil {
			log.Fatalf("无效的间隔: %v", err)
		}
	}

	cfg := SyncConfig{
		Source:   source,
		Target:   target,
		Excludes: excludeList,
		DryRun:   dryRun,
		Delete:   delete,
		Workers:  workers,
		Interval: intervalDuration,
	}

	syncer := NewSyncer(cfg)

	if dryRun {
		log.Println("🔍 预览模式 — 不会实际修改文件")
	}

	// 执行一次同步
	result, err := syncer.Sync()
	if err != nil {
		log.Fatalf("同步失败: %v", err)
	}

	log.Printf("✅ 同步完成: 总计 %d, 复制 %d, 跳过 %d, 删除 %d, 错误 %d, 耗时 %v",
		result.Total, result.Copied, result.Skipped, result.Deleted, result.Errors, result.Duration)

	// 定时同步
	if intervalDuration > 0 {
		syncer.WatchAndSync()
	}
}
