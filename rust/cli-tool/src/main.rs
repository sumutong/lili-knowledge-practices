//! Rust CLI 工具实战
//! 基于 clap 的命令行工具，支持文件搜索、行数统计与内容替换

use clap::{Parser, Subcommand};
use colored::*;
use regex::Regex;
use std::fs;
use std::io::{self, BufRead, BufReader};
use std::path::Path;
use walkdir::WalkDir;

/// 立里CLI工具箱 — 高效命令行工具
#[derive(Parser)]
#[command(name = "lili-cli", version, about, long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// 搜索文件内容（类似 grep）
    Search {
        /// 搜索模式（支持正则）
        pattern: String,
        /// 目标目录
        #[arg(default_value = ".")]
        path: String,
        /// 文件扩展名过滤
        #[arg(short = 'e', long)]
        ext: Option<String>,
        /// 忽略大小写
        #[arg(short = 'i', long)]
        ignore_case: bool,
    },
    /// 统计代码行数
    Count {
        /// 目标目录
        #[arg(default_value = ".")]
        path: String,
        /// 文件扩展名过滤
        #[arg(short = 'e', long)]
        ext: Option<String>,
    },
    /// 批量替换文件内容
    Replace {
        /// 查找模式
        pattern: String,
        /// 替换内容
        replacement: String,
        /// 目标目录
        #[arg(default_value = ".")]
        path: String,
        /// 文件扩展名过滤
        #[arg(short = 'e', long)]
        ext: Option<String>,
        /// 是否预览（不实际修改）
        #[arg(short = 'n', long)]
        dry_run: bool,
    },
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Search { pattern, path, ext, ignore_case } => {
            search_files(&pattern, &path, ext.as_deref(), ignore_case);
        }
        Commands::Count { path, ext } => {
            count_lines(&path, ext.as_deref());
        }
        Commands::Replace { pattern, replacement, path, ext, dry_run } => {
            replace_content(&pattern, &replacement, &path, ext.as_deref(), dry_run);
        }
    }
}

fn matches_ext(entry: &Path, ext: Option<&str>) -> bool {
    match ext {
        Some(e) => entry.extension().map_or(false, |x| x == e.trim_start_matches('.')),
        None => true,
    }
}

fn search_files(pattern: &str, path: &str, ext: Option<&str>, ignore_case: bool) {
    let re = Regex::new(pattern).expect("无效的正则表达式");
    let mut count = 0;

    for entry in WalkDir::new(path).into_iter().filter_map(|e| e.ok()) {
        if !entry.file_type().is_file() || !matches_ext(entry.path(), ext) {
            continue;
        }

        let file = match fs::File::open(entry.path()) {
            Ok(f) => f,
            Err(_) => continue,
        };

        for (line_num, line) in BufReader::new(file).lines().filter_map(|l| l.ok()).enumerate() {
            let haystack = if ignore_case { line.to_lowercase() } else { line.clone() };
            let needle = if ignore_case { pattern.to_lowercase() } else { pattern.to_string() };

            if re.is_match(&haystack) {
                count += 1;
                println!("{}:{}: {}", 
                    entry.path().display().to_string().green(),
                    (line_num + 1).to_string().yellow(),
                    line.trim());
            }
        }
    }

    println!("\n{}: 找到 {} 处匹配", "搜索完成".blue().bold(), count);
}

fn count_lines(path: &str, ext: Option<&str>) {
    let mut total_files = 0;
    let mut total_lines = 0;

    for entry in WalkDir::new(path).into_iter().filter_map(|e| e.ok()) {
        if !entry.file_type().is_file() || !matches_ext(entry.path(), ext) {
            continue;
        }

        if let Ok(content) = fs::read_to_string(entry.path()) {
            total_files += 1;
            let lines = content.lines().count();
            total_lines += lines;
            println!("{:>6}  {}", lines.to_string().cyan(), entry.path().display());
        }
    }

    println!("\n{}: {} 个文件, {} 行代码",
        "统计完成".blue().bold(), total_files, total_lines);
}

fn replace_content(pattern: &str, replacement: &str, path: &str, ext: Option<&str>, dry_run: bool) {
    let re = Regex::new(pattern).expect("无效的正则表达式");
    let mut changed = 0;

    for entry in WalkDir::new(path).into_iter().filter_map(|e| e.ok()) {
        if !entry.file_type().is_file() || !matches_ext(entry.path(), ext) {
            continue;
        }

        let content = match fs::read_to_string(entry.path()) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let new_content = re.replace_all(&content, replacement);
        if new_content != content {
            changed += 1;
            if dry_run {
                println!("{} [预览] {}", "将要修改".yellow(), entry.path().display());
            } else {
                if let Err(e) = fs::write(entry.path(), new_content.as_ref()) {
                    eprintln!("写入失败 {}: {}", entry.path().display(), e);
                } else {
                    println!("{} {}", "已修改".green(), entry.path().display());
                }
            }
        }
    }

    let mode = if dry_run { "预览" } else { "完成" };
    println!("\n{}{}: 修改了 {} 个文件", mode.green().bold(), "".clear(), changed);
}
