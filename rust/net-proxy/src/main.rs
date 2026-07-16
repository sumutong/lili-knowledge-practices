//! Rust 网络代理实战
//! HTTP 正向代理服务器，支持请求转发、日志记录、访问控制

use bytes::Bytes;
use clap::Parser;
use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Method, Request, Response, StatusCode};
use hyper_util::rt::TokioIo;
use std::net::SocketAddr;
use tokio::net::TcpListener;
use tracing::{error, info, warn};

/// 立里网络代理
#[derive(Parser)]
#[command(name = "lili-proxy")]
struct Cli {
    /// 监听地址
    #[arg(short, long, default_value = "127.0.0.1:8888")]
    bind: String,
    /// 允许的域名白名单 (逗号分隔)，为空则允许所有
    #[arg(short, long)]
    allow: Option<String>,
    /// 日志级别
    #[arg(short, long, default_value = "info")]
    log_level: String,
}

async fn proxy(
    req: Request<Incoming>,
    allow_list: Vec<String>,
) -> Result<Response<Full<Bytes>>, hyper::Error> {
    let method = req.method().clone();
    let uri = req.uri().clone();

    info!("📥 {} {}", method, uri);

    // 访问控制
    if !allow_list.is_empty() {
        let host = uri.host().unwrap_or("");
        let allowed = allow_list.iter().any(|a| host.contains(a.as_str()));
        if !allowed {
            warn!("🚫 拒绝访问: {}", host);
            return Ok(Response::builder()
                .status(StatusCode::FORBIDDEN)
                .body(Full::new(Bytes::from("403 Forbidden - 域名未授权")))
                .unwrap());
        }
    }

    // 禁止 CONNECT 方法（HTTPS 隧道）
    if method == Method::CONNECT {
        warn!("🔒 CONNECT 方法不支持");
        return Ok(Response::builder()
            .status(StatusCode::METHOD_NOT_ALLOWED)
            .body(Full::new(Bytes::from("405 CONNECT method not supported")))
            .unwrap());
    }

    // 构建目标 URL
    let target_url = uri.to_string();
    info!("🔗 转发至: {}", target_url);

    // 创建到目标服务器的连接
    let target_uri: hyper::Uri = match target_url.parse() {
        Ok(u) => u,
        Err(e) => {
            error!("无效的目标URL: {}", e);
            return Ok(Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .body(Full::new(Bytes::from(format!("400 Bad Request: {}", e))))
                .unwrap());
        }
    };

    let host = target_uri.host().unwrap_or("localhost");
    let port = target_uri.port_u16().unwrap_or(80);

    let stream = match tokio::net::TcpStream::connect(format!("{}:{}", host, port)).await {
        Ok(s) => s,
        Err(e) => {
            error!("连接目标失败: {}", e);
            return Ok(Response::builder()
                .status(StatusCode::BAD_GATEWAY)
                .body(Full::new(Bytes::from(format!("502 Bad Gateway: {}", e))))
                .unwrap());
        }
    };

    let io = TokioIo::new(stream);
    let (mut sender, conn) = hyper::client::conn::http1::handshake(io).await?;
    tokio::spawn(async move {
        if let Err(e) = conn.await {
            error!("客户端连接错误: {}", e);
        }
    });

    // 转发请求
    let (parts, body) = req.into_parts();
    let new_req = Request::from_parts(parts, body);

    match sender.send_request(new_req).await {
        Ok(resp) => {
            let status = resp.status();
            info!("✅ {} {} → {}", method, uri, status);
            let (parts, body) = resp.into_parts();
            let collected = body.collect().await?;
            let bytes = collected.to_bytes();
            Ok(Response::from_parts(parts, Full::new(bytes)))
        }
        Err(e) => {
            error!("转发请求失败: {}", e);
            Ok(Response::builder()
                .status(StatusCode::BAD_GATEWAY)
                .body(Full::new(Bytes::from(format!("502 Bad Gateway: {}", e))))
                .unwrap())
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    tracing_subscriber::fmt::init();

    let allow_list: Vec<String> = cli
        .allow
        .unwrap_or_default()
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let addr: SocketAddr = cli.bind.parse().expect("无效的绑定地址");
    let listener = TcpListener::bind(addr).await?;

    info!("🚀 立里网络代理启动于 http://{}", addr);
    if !allow_list.is_empty() {
        info!("🔐 白名单: {:?}", allow_list);
    }

    loop {
        let (stream, peer) = listener.accept().await?;
        info!("🔌 新连接: {}", peer);

        let allow = allow_list.clone();
        tokio::spawn(async move {
            let io = TokioIo::new(stream);
            if let Err(e) = http1::Builder::new()
                .serve_connection(
                    io,
                    service_fn(move |req| {
                        let a = allow.clone();
                        async move { proxy(req, a).await }
                    }),
                )
                .await
            {
                error!("连接处理错误: {}", e);
            }
        });
    }
}
