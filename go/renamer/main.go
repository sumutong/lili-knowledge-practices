// Package main — 智能文件重命名工具
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"text/tabwriter"
	// "time"
)

// Version 版本号
const Version = "1.0.0"

// ─── 重命名规则 ───────────────────────────────────────────
type RenameRule struct {
	Pattern     string // 匹配模式（正则或普通字符串）
	Replacement string // 替换内容
	IsRegex     bool   // 是否正则模式
}

type Operation struct {
	OldPath string
	NewPath string
	OldName string
	NewName string
}

// ─── 核心引擎 ─────────────────────────────────────────────
type Renamer struct {
	DryRun      bool
	Recursive   bool
	Verbose     bool
	UseExifDate bool
	Rules       []RenameRule
	Operations  []Operation
}

func NewRenamer() *Renamer {
	return &Renamer{Rules: make([]RenameRule, 0)}
}

func (r *Renamer) AddRule(pattern, replacement string, isRegex bool) {
	r.Rules = append(r.Rules, RenameRule{
		Pattern:     pattern,
		Replacement: replacement,
		IsRegex:     isRegex,
	})
}

// Plan 收集所有操作但不执行，返回操作列表和错误
func (r *Renamer) Plan(rootDir string) ([]Operation, []error) {
	var ops []Operation
	var errs []error

	walkFn := func(path string, info os.FileInfo, err error) error {
		if err != nil {
			errs = append(errs, fmt.Errorf("access error %s: %w", path, err))
			return nil
		}

		if !r.Recursive && path != rootDir && info.IsDir() {
			return filepath.SkipDir
		}

		if info.IsDir() {
			return nil
		}

		dir := filepath.Dir(path)
		oldName := info.Name()
		newName := oldName

		// 应用所有规则
		for _, rule := range r.Rules {
			if rule.IsRegex {
				re, err := regexp.Compile(rule.Pattern)
				if err != nil {
					errs = append(errs, fmt.Errorf("invalid regex %q: %w", rule.Pattern, err))
					continue
				}
				newName = re.ReplaceAllString(newName, rule.Replacement)
			} else {
				newName = strings.ReplaceAll(newName, rule.Pattern, rule.Replacement)
			}
		}

		// EXIF 日期重命名
		if r.UseExifDate {
			if dateName := exifDateName(path); dateName != "" {
				ext := filepath.Ext(oldName)
				newName = dateName + ext
			}
		}

		if newName != oldName {
			newPath := filepath.Join(dir, newName)
			ops = append(ops, Operation{
				OldPath: path,
				NewPath: newPath,
				OldName: oldName,
				NewName: newName,
			})
		}

		return nil
	}

	_ = filepath.Walk(rootDir, walkFn)
	r.Operations = ops
	return ops, errs
}

// Execute 执行重命名
func (r *Renamer) Execute() (int, []error) {
	count := 0
	var errs []error

	for _, op := range r.Operations {
		if r.DryRun {
			r.printOp(op, "DRY-RUN")
			count++
			continue
		}

		// 确保目标目录存在
		destDir := filepath.Dir(op.NewPath)
		if err := os.MkdirAll(destDir, 0755); err != nil {
			errs = append(errs, fmt.Errorf("mkdir %s: %w", destDir, err))
			continue
		}

		// 检查目标文件是否存在
		if _, err := os.Stat(op.NewPath); err == nil {
			if r.Verbose {
				fmt.Printf("⚠️  跳过 (目标已存在): %s\n", op.NewName)
			}
			continue
		}

		if err := os.Rename(op.OldPath, op.NewPath); err != nil {
			errs = append(errs, fmt.Errorf("rename %s: %w", op.OldName, err))
			continue
		}

		if r.Verbose {
			r.printOp(op, "RENAMED")
		}
		count++
	}
	return count, errs
}

func (r *Renamer) printOp(op Operation, tag string) {
	fmt.Printf("[%s] %s → %s\n", tag, op.OldName, op.NewName)
}

// ─── EXIF 日期提取 ────────────────────────────────────────
func exifDateName(path string) string {
	// 简化实现：通过文件修改时间生成日期名
	// 实际可使用 github.com/rwcarlsen/goexif/exif 解析 EXIF
	info, err := os.Stat(path)
	if err != nil {
		return ""
	}
	t := info.ModTime()
	if isImageExt(filepath.Ext(path)) {
		return t.Format("2006-01-02_150405")
	}
	return ""
}

func isImageExt(ext string) bool {
	ext = strings.ToLower(ext)
	switch ext {
	case ".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".tiff", ".raw":
		return true
	}
	return false
}

// ─── 预览输出 ─────────────────────────────────────────────
func (r *Renamer) PrintPlan() {
	if len(r.Operations) == 0 {
		fmt.Println("没有需要重命名的文件")
		return
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "当前文件名\t→\t新文件名")
	fmt.Fprintln(w, "───────\t─\t───────")
	for _, op := range r.Operations {
		fmt.Fprintf(w, "%s\t→\t%s\n", op.OldName, op.NewName)
	}
	w.Flush()
	fmt.Printf("\n共 %d 个文件需要重命名\n", len(r.Operations))
}

// ─── CLI 入口 ─────────────────────────────────────────────
func main() {
	var (
		dryRun      bool
		recursive   bool
		verbose     bool
		useExifDate bool
		pattern     string
		replace     string
		regexMode   bool
		showVersion bool
		showHelp    bool
	)

	flag.BoolVar(&dryRun, "dry-run", false, "预览模式（不实际执行）")
	flag.BoolVar(&dryRun, "n", false, "同 --dry-run")
	flag.BoolVar(&recursive, "recursive", false, "递归处理子目录")
	flag.BoolVar(&recursive, "r", false, "同 --recursive")
	flag.BoolVar(&verbose, "verbose", false, "详细输出")
	flag.BoolVar(&verbose, "v", false, "同 --verbose")
	flag.BoolVar(&useExifDate, "exif-date", false, "使用 EXIF/修改日期重命名图片")
	flag.StringVar(&pattern, "pattern", "", "匹配模式")
	flag.StringVar(&pattern, "p", "", "同 --pattern")
	flag.StringVar(&replace, "replace", "", "替换字符串")
	flag.StringVar(&replace, "R", "", "同 --replace")
	flag.BoolVar(&regexMode, "regex", false, "使用正则表达式匹配")
	flag.BoolVar(&regexMode, "e", false, "同 --regex")
	flag.BoolVar(&showVersion, "version", false, "显示版本信息")
	flag.BoolVar(&showHelp, "help", false, "显示帮助")
	flag.BoolVar(&showHelp, "h", false, "同 --help")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, `🚀 ren — 智能文件批量重命名工具 v%s

用法:
  ren [选项] <目录>

选项:
`, Version)
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, `
示例:
  ren -n -p " " -R "_" ./photos          # 预览：将所有空格替换为下划线
  ren -e -p "(?i)\.jpeg$" -R ".jpg" -r . # 递归将 .JPEG 改为 .jpg
  ren --exif-date ./DCIM                  # 按 EXIF 日期重命名照片
  ren -n -p "old_" -R "" ./docs           # 预览：删除文件名中的 "old_" 前缀
`)
	}

	flag.Parse()

	if showVersion {
		fmt.Printf("ren v%s\n", Version)
		os.Exit(0)
	}
	if showHelp {
		flag.Usage()
		os.Exit(0)
	}

	args := flag.Args()
	if len(args) < 1 {
		fmt.Fprintln(os.Stderr, "错误: 请指定目录路径")
		flag.Usage()
		os.Exit(1)
	}
	rootDir := args[0]

	// 检查目录是否存在
	info, err := os.Stat(rootDir)
	if err != nil || !info.IsDir() {
		fmt.Fprintf(os.Stderr, "错误: %s 不是有效目录\n", rootDir)
		os.Exit(1)
	}

	renamer := NewRenamer()
	renamer.DryRun = dryRun
	renamer.Recursive = recursive
	renamer.Verbose = verbose
	renamer.UseExifDate = useExifDate

	if pattern != "" || replace != "" {
		if pattern == "" {
			fmt.Fprintln(os.Stderr, "错误: 指定了 --replace 但未提供 --pattern")
			os.Exit(1)
		}
		renamer.AddRule(pattern, replace, regexMode)
	}

	if !useExifDate && pattern == "" {
		fmt.Fprintln(os.Stderr, "错误: 请至少指定一种重命名规则 (--pattern 或 --exif-date)")
		flag.Usage()
		os.Exit(1)
	}

	// 规划操作
	ops, errs := renamer.Plan(rootDir)
	for _, e := range errs {
		fmt.Fprintf(os.Stderr, "⚠️  %v\n", e)
	}

	if dryRun {
		renamer.PrintPlan()
		return
	}

	// 执行重命名
	count, errs := renamer.Execute()
	for _, e := range errs {
		fmt.Fprintf(os.Stderr, "❌ %v\n", e)
	}

	fmt.Printf("\n✅ 完成! 重命名 %d 个文件, %d 个错误\n", count, len(errs))
	if len(ops) > count+len(errs) {
		fmt.Printf("⚠️  跳过 %d 个文件（目标已存在）\n", len(ops)-count-len(errs))
	}
}
