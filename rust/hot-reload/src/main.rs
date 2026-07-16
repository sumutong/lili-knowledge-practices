//! Rust 热加载实战
//! 基于 notify 的文件监控 + 配置热重载

use notify::{Event, EventKind, RecursiveMode, Watcher};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::sync::{Arc, RwLock};
use std::thread;
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AppConfig {
    server: ServerConfig,
    features: Vec<String>,
    limits: LimitsConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ServerConfig {
    host: String,
    port: u16,
    workers: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct LimitsConfig {
    max_connections: u32,
    timeout_seconds: u64,
    rate_limit: u32,
}

impl Default for AppConfig {
    fn default() -> Self {
        AppConfig {
            server: ServerConfig {
                host: "127.0.0.1".into(),
                port: 8080,
                workers: 4,
            },
            features: vec!["auth".into(), "logging".into()],
            limits: LimitsConfig {
                max_connections: 1000,
                timeout_seconds: 30,
                rate_limit: 100,
            },
        }
    }
}

type SharedConfig = Arc<RwLock<AppConfig>>;

fn load_config(path: &str) -> AppConfig {
    let content = fs::read_to_string(path).expect("无法读取配置文件");

    if path.ends_with(".json") {
        serde_json::from_str(&content).expect("JSON解析失败")
    } else if path.ends_with(".toml") {
        toml::from_str(&content).expect("TOML解析失败")
    } else {
        panic!("不支持的配置格式（仅支持 .json/.toml）");
    }
}

fn save_config(path: &str, config: &AppConfig) {
    let content = if path.ends_with(".json") {
        serde_json::to_string_pretty(config).unwrap()
    } else {
        toml::to_string_pretty(config).unwrap()
    };
    fs::write(path, content).expect("写入配置失败");
}

fn watch_config(path: String, shared_config: SharedConfig) -> notify::Result<()> {
    let (tx, rx) = std::sync::mpsc::channel();
    let mut watcher = notify::recommended_watcher(tx)?;
    let watch_path = Path::new(&path).parent().unwrap_or(Path::new("."));

    watcher.watch(watch_path, RecursiveMode::NonRecursive)?;

    println!("👀 正在监控配置文件: {}", path);

    for event in rx {
        match event {
            Ok(Event { kind: EventKind::Modify(_), paths, .. }) => {
                for p in &paths {
                    if p.to_string_lossy().ends_with(
                        Path::new(&path).file_name().unwrap().to_string_lossy().as_ref(),
                    ) {
                        println!("\n📝 配置变更检测: {}", p.display());
                        // 短暂延迟避免读取不完整
                        thread::sleep(Duration::from_millis(100));

                        match load_config(&path) {
                            Ok(new_config) => {
                                let mut cfg = shared_config.write().unwrap();
                                println!("  🏠 服务地址: {}:{}", new_config.server.host, new_config.server.port);
                                println!("  👷 工作线程: {}", new_config.server.workers);
                                println!("  📊 最大连接: {}", new_config.limits.max_connections);
                                println!("  ⚡ 速率限制: {}", new_config.limits.rate_limit);
                                *cfg = new_config;
                                println!("✅ 配置已热加载");
                            }
                            Err(e) => {
                                eprintln!("❌ 配置解析失败: {}", e);
                            }
                        }
                    }
                }
            }
            Err(e) => eprintln!("监控错误: {}", e),
            _ => {}
        }
    }

    Ok(())
}

fn main() {
    let config_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "config.toml".to_string());

    // 如果配置文件不存在，生成默认配置
    if !Path::new(&config_path).exists() {
        let default = AppConfig::default();
        save_config(&config_path, &default);
        println!("✅ 已生成默认配置: {}", config_path);
    }

    let config = load_config(&config_path);
    println!("📋 初始配置:");
    println!("  服务: {}:{}", config.server.host, config.server.port);
    println!("  工作线程: {} | 最大连接: {}", config.server.workers, config.limits.max_connections);

    let shared_config: SharedConfig = Arc::new(RwLock::new(config));

    // 启动文件监控
    let config_clone = shared_config.clone();
    let path_clone = config_path.clone();

    thread::spawn(move || {
        watch_config(path_clone, config_clone).expect("文件监控失败");
    });

    // 模拟服务运行，每3秒打印当前配置
    println!("\n🟢 服务运行中... (修改 {} 后自动重载)", config_path);
    println!("   按 Ctrl+C 退出\n");

    loop {
        thread::sleep(Duration::from_secs(3));
        let cfg = shared_config.read().unwrap();
        println!(
            "💚 [运行中] {}:{} | 连接数上限: {} | QPS限制: {}",
            cfg.server.host,
            cfg.server.port,
            cfg.limits.max_connections,
            cfg.limits.rate_limit
        );
    }
}
