//! Rust 序列化实战
//! JSON、TOML、YAML、MessagePack 多格式序列化/反序列化对比

use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Config {
    app: AppConfig,
    database: DatabaseConfig,
    features: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct AppConfig {
    name: String,
    version: String,
    port: u16,
    debug: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct DatabaseConfig {
    url: String,
    max_connections: u32,
    timeout_seconds: u64,
}

#[derive(Parser)]
#[command(name = "lili-serde")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// 生成示例配置
    Gen,
    /// JSON ↔ TOML 互转
    Convert {
        /// 源文件
        input: String,
        /// 输出文件
        output: String,
    },
    /// 从一种格式转换为 MessagePack
    ToMsgPack {
        input: String,
        output: String,
    },
    /// 从 MessagePack 转换为 JSON
    FromMsgPack {
        input: String,
        output: String,
    },
}

fn generate_sample() -> Config {
    Config {
        app: AppConfig {
            name: "lili-app".into(),
            version: "1.0.0".into(),
            port: 8080,
            debug: true,
        },
        database: DatabaseConfig {
            url: "postgres://localhost/lili".into(),
            max_connections: 20,
            timeout_seconds: 30,
        },
        features: vec!["auth".into(), "logging".into(), "metrics".into()],
    }
}

fn detect_format(path: &str) -> &str {
    if path.ends_with(".json") {
        "json"
    } else if path.ends_with(".toml") {
        "toml"
    } else if path.ends_with(".yaml") || path.ends_with(".yml") {
        "yaml"
    } else if path.ends_with(".msgpack") || path.ends_with(".mp") {
        "msgpack"
    } else {
        "json"
    }
}

fn read_config(path: &str) -> Config {
    let data = fs::read_to_string(path).expect("无法读取文件");
    match detect_format(path) {
        "json" => serde_json::from_str(&data).expect("JSON解析失败"),
        "toml" => toml::from_str(&data).expect("TOML解析失败"),
        "yaml" => serde_yaml::from_str(&data).expect("YAML解析失败"),
        _ => panic!("不支持从该格式读取"),
    }
}

fn write_config(config: &Config, path: &str) {
    match detect_format(path) {
        "json" => {
            let s = serde_json::to_string_pretty(config).expect("JSON序列化失败");
            fs::write(path, s).expect("写入失败");
        }
        "toml" => {
            let s = toml::to_string_pretty(config).expect("TOML序列化失败");
            fs::write(path, s).expect("写入失败");
        }
        "yaml" => {
            let s = serde_yaml::to_string(config).expect("YAML序列化失败");
            fs::write(path, s).expect("写入失败");
        }
        "msgpack" => {
            let buf = rmp_serde::to_vec(config).expect("MessagePack序列化失败");
            fs::write(path, buf).expect("写入失败");
        }
        _ => panic!("不支持的输出格式"),
    }
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Gen => {
            let config = generate_sample();
            let paths = ["sample.json", "sample.toml", "sample.yaml"];
            for path in &paths {
                write_config(&config, path);
                println!("✅ 已生成 {}", path);
            }
            // MessagePack
            let buf = rmp_serde::to_vec(&config).unwrap();
            fs::write("sample.msgpack", buf).unwrap();
            println!("✅ 已生成 sample.msgpack");
        }
        Commands::Convert { input, output } => {
            let config = read_config(&input);
            write_config(&config, &output);
            println!(
                "✅ 已转换: {} → {}",
                detect_format(&input),
                detect_format(&output)
            );
        }
        Commands::ToMsgPack { input, output } => {
            let config = read_config(&input);
            let buf = rmp_serde::to_vec(&config).expect("MessagePack序列化失败");
            fs::write(&output, buf).expect("写入失败");
            println!("✅ 已转换为 MessagePack: {}", output);
        }
        Commands::FromMsgPack { input, output } => {
            let buf = fs::read(&input).expect("无法读取文件");
            let config: Config =
                rmp_serde::from_slice(&buf).expect("MessagePack反序列化失败");
            write_config(&config, &output);
            println!("✅ 已从 MessagePack 转换为 {}", detect_format(&output));
        }
    }
}
