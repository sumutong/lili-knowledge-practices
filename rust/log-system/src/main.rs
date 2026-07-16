//! Rust 日志系统实战
//! tracing 结构化日志，支持 JSON/文本输出、文件滚动、分级过滤

use std::fs;
use std::thread;
use std::time::Duration;
use tracing::{info, warn, error, debug, Level, span};
use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

mod services {
    use tracing::{info, error, instrument};

    #[instrument]
    pub fn process_order(order_id: u64, amount: f64) -> Result<String, String> {
        info!(order_id, amount, "开始处理订单");

        // 模拟业务逻辑
        let result = validate_order(order_id, amount)?;
        info!(order_id, status = "validated", "订单验证通过");

        let payment_id = process_payment(order_id, amount)?;
        info!(order_id, payment_id, "支付处理完成");

        Ok(payment_id)
    }

    #[instrument]
    fn validate_order(order_id: u64, amount: f64) -> Result<(), String> {
        if amount <= 0.0 {
            error!(order_id, amount, "无效的订单金额");
            return Err("金额必须大于0".into());
        }
        if amount > 100000.0 {
            warn!(order_id, amount, "大额订单需要审核");
        }
        Ok(())
    }

    #[instrument]
    fn process_payment(order_id: u64, amount: f64) -> Result<String, String> {
        info!(order_id, amount, "调用支付网关");
        // 模拟支付
        thread::sleep(Duration::from_millis(50));
        Ok(format!("PAY_{}", order_id))
    }
}

fn main() {
    // 确保日志目录存在
    fs::create_dir_all("logs").ok();

    // 文件日志 (JSON格式)
    let file_appender = tracing_appender::rolling::daily("logs", "lili.log");
    let (non_blocking, _guard) = tracing_appender::non_blocking(file_appender);

    // 控制台输出
    let console_layer = fmt::layer()
        .with_target(true)
        .with_thread_ids(true)
        .pretty();

    // 文件输出 (JSON)
    let file_layer = fmt::layer()
        .json()
        .with_writer(non_blocking);

    // 过滤器: 默认 info 级别，特定模块可调
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| {
            EnvFilter::new("info,log_system=debug")
        });

    tracing_subscriber::registry()
        .with(filter)
        .with(console_layer)
        .with(file_layer)
        .init();

    info!("🚀 立里日志系统启动");

    // 模拟业务流程
    let orders = vec![
        (1, 99.99),
        (2, 50000.0),
        (3, -10.0),  // 会触发错误
        (4, 150000.0), // 会触发警告
        (5, 299.0),
    ];

    for (id, amount) in &orders {
        let span = span!(Level::INFO, "order_processing", order_id = id);
        let _enter = span.enter();

        match services::process_order(*id, *amount) {
            Ok(payment_id) => info!(order_id = id, payment_id, "订单处理成功 ✅"),
            Err(e) => error!(order_id = id, error = %e, "订单处理失败 ❌"),
        }
    }

    info!("📊 处理完成: {} 个订单", orders.len());

    // 保持程序运行以确保日志写入
    thread::sleep(Duration::from_millis(100));
    println!("\n📁 日志文件: logs/");
}
