//! Rust 全栈实战项目
//! 博客系统: Actix-web + SQLite + Tera模板引擎

use actix_files::Files;
use actix_web::{web, App, HttpResponse, HttpServer, middleware};
use chrono::Utc;
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tera::{Context, Tera};
use uuid::Uuid;

// ── 数据模型 ──

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Article {
    id: String,
    title: String,
    content: String,
    author: String,
    created_at: String,
}

#[derive(Debug, Deserialize)]
struct ArticleForm {
    title: String,
    content: String,
    author: String,
}

// ── 应用状态 ──

struct AppState {
    db: Mutex<Connection>,
    templates: Tera,
}

// ── 数据库操作 ──

fn init_db(conn: &Connection) {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL DEFAULT '匿名',
            created_at TEXT NOT NULL
        );"
    ).expect("数据库初始化失败");

    // 插入示例数据
    let count: i64 = conn
        .query_row("SELECT COUNT(*) FROM articles", [], |row| row.get(0))
        .unwrap_or(0);

    if count == 0 {
        let samples = vec![
            ("Rust异步编程入门", "Rust的异步编程基于Future trait和async/await语法。本文详细介绍tokio运行时和异步IO模型...", "立里"),
            ("Actix-web框架实战", "Actix-web是Rust生态中最流行的Web框架之一，基于Actor模型构建，性能卓越...", "立里"),
            ("SQLite在Rust中的应用", "SQLite是一个轻量级的嵌入式数据库，通过rusqlite库可以在Rust中方便地操作SQLite...", "立里"),
        ];

        for (title, content, author) in samples {
            let id = Uuid::new_v4().to_string();
            let now = Utc::now().format("%Y-%m-%d %H:%M").to_string();
            conn.execute(
                "INSERT INTO articles (id, title, content, author, created_at) VALUES (?1, ?2, ?3, ?4, ?5)",
                params![id, title, content, author, now],
            ).ok();
        }
    }
}

fn get_articles(conn: &Connection) -> Vec<Article> {
    let mut stmt = conn
        .prepare("SELECT id, title, content, author, created_at FROM articles ORDER BY created_at DESC")
        .unwrap();
    stmt.query_map([], |row| {
        Ok(Article {
            id: row.get(0)?,
            title: row.get(1)?,
            content: row.get(2)?,
            author: row.get(3)?,
            created_at: row.get(4)?,
        })
    })
    .unwrap()
    .filter_map(|r| r.ok())
    .collect()
}

fn get_article(conn: &Connection, id: &str) -> Option<Article> {
    conn.query_row(
        "SELECT id, title, content, author, created_at FROM articles WHERE id = ?1",
        params![id],
        |row| {
            Ok(Article {
                id: row.get(0)?,
                title: row.get(1)?,
                content: row.get(2)?,
                author: row.get(3)?,
                created_at: row.get(4)?,
            })
        },
    )
    .ok()
}

fn create_article(conn: &Connection, form: &ArticleForm) -> Article {
    let id = Uuid::new_v4().to_string();
    let now = Utc::now().format("%Y-%m-%d %H:%M").to_string();
    conn.execute(
        "INSERT INTO articles (id, title, content, author, created_at) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![id, form.title, form.content, form.author, now],
    ).unwrap();

    Article {
        id,
        title: form.title.clone(),
        content: form.content.clone(),
        author: form.author.clone(),
        created_at: now,
    }
}

// ── 路由处理 ──

async fn index(data: web::Data<AppState>) -> HttpResponse {
    let conn = data.db.lock().unwrap();
    let articles = get_articles(&conn);

    let mut ctx = Context::new();
    ctx.insert("title", "立里博客");
    ctx.insert("articles", &articles);

    let rendered = data.templates.render("index.html", &ctx).unwrap_or_else(|e| {
        format!("模板渲染错误: {}", e)
    });
    HttpResponse::Ok().content_type("text/html; charset=utf-8").body(rendered)
}

async fn article_detail(
    data: web::Data<AppState>,
    path: web::Path<String>,
) -> HttpResponse {
    let conn = data.db.lock().unwrap();
    let article = get_article(&conn, &path.into_inner());

    let mut ctx = Context::new();
    match article {
        Some(a) => {
            ctx.insert("title", &a.title);
            ctx.insert("article", &a);
            let rendered = data.templates.render("detail.html", &ctx).unwrap_or_else(|e| format!("错误: {}", e));
            HttpResponse::Ok().content_type("text/html; charset=utf-8").body(rendered)
        }
        None => {
            HttpResponse::NotFound().body("文章不存在")
        }
    }
}

async fn new_article_page(data: web::Data<AppState>) -> HttpResponse {
    let mut ctx = Context::new();
    ctx.insert("title", "写文章");
    let rendered = data.templates.render("new.html", &ctx).unwrap_or_else(|e| format!("错误: {}", e));
    HttpResponse::Ok().content_type("text/html; charset=utf-8").body(rendered)
}

async fn create_article_handler(
    data: web::Data<AppState>,
    form: web::Form<ArticleForm>,
) -> HttpResponse {
    let conn = data.db.lock().unwrap();
    let article = create_article(&conn, &form);
    HttpResponse::Found()
        .append_header(("Location", format!("/article/{}", article.id)))
        .finish()
}

// ── 主函数 ──

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("🚀 立里博客系统启动于 http://127.0.0.1:3000");

    let conn = Connection::open("blog.db").expect("无法打开数据库");
    init_db(&conn);

    let mut tera = Tera::default();
    tera.add_raw_template("index.html", INDEX_TEMPLATE).unwrap();
    tera.add_raw_template("detail.html", DETAIL_TEMPLATE).unwrap();
    tera.add_raw_template("new.html", NEW_TEMPLATE).unwrap();

    let state = web::Data::new(AppState {
        db: Mutex::new(conn),
        templates: tera,
    });

    HttpServer::new(move || {
        App::new()
            .app_data(state.clone())
            .wrap(middleware::Logger::default())
            .route("/", web::get().to(index))
            .route("/article/new", web::get().to(new_article_page))
            .route("/article/new", web::post().to(create_article_handler))
            .route("/article/{id}", web::get().to(article_detail))
            .service(Files::new("/static", "static/").show_files_listing())
    })
    .bind("127.0.0.1:3000")?
    .run()
    .await
}

// ── HTML 模板 ──

const INDEX_TEMPLATE: &str = r#"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui; background: #f8fafc; color: #1e293b; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  color: white; padding: 2rem; text-align: center; }
        .header h1 { font-size: 2rem; }
        .header p { opacity: 0.9; margin-top: 0.5rem; }
        .container { max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .article { background: white; border-radius: 12px; padding: 1.5rem;
                   margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .article h2 { color: #1e40af; margin-bottom: 0.5rem; }
        .article h2 a { color: inherit; text-decoration: none; }
        .article h2 a:hover { color: #3b82f6; }
        .article .meta { color: #64748b; font-size: 0.875rem; margin-bottom: 0.5rem; }
        .article .excerpt { color: #475569; }
        .btn { display: inline-block; padding: 0.75rem 1.5rem; background: #667eea;
               color: white; text-decoration: none; border-radius: 8px; margin-top: 1rem; }
        .btn:hover { background: #5a67d8; }
        .footer { text-align: center; color: #94a3b8; padding: 2rem; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🦀 立里博客</h1>
        <p>Rust + Actix-web 全栈实战</p>
    </div>
    <div class="container">
        <a href="/article/new" class="btn">✍️ 写文章</a>
        {% for article in articles %}
        <div class="article">
            <h2><a href="/article/{{ article.id }}">{{ article.title }}</a></h2>
            <div class="meta">{{ article.author }} · {{ article.created_at }}</div>
            <div class="excerpt">{{ article.content | truncate(length=150) }}</div>
        </div>
        {% endfor %}
    </div>
    <div class="footer">Powered by Rust 🦀</div>
</body>
</html>
"#;

const DETAIL_TEMPLATE: &str = r#"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ article.title }} - 立里博客</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui; background: #f8fafc; color: #1e293b; }
        .container { max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .back { color: #667eea; text-decoration: none; margin-bottom: 1rem; display: inline-block; }
        .article { background: white; border-radius: 12px; padding: 2rem;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .article h1 { font-size: 2rem; color: #1e40af; margin-bottom: 0.5rem; }
        .article .meta { color: #64748b; margin-bottom: 1.5rem; padding-bottom: 1rem;
                         border-bottom: 1px solid #e2e8f0; }
        .article .content { line-height: 1.8; white-space: pre-wrap; }
        .footer { text-align: center; color: #94a3b8; padding: 2rem; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back">← 返回首页</a>
        <div class="article">
            <h1>{{ article.title }}</h1>
            <div class="meta">{{ article.author }} · {{ article.created_at }}</div>
            <div class="content">{{ article.content }}</div>
        </div>
    </div>
    <div class="footer">Powered by Rust 🦀</div>
</body>
</html>
"#;

const NEW_TEMPLATE: &str = r#"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>写文章 - 立里博客</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui; background: #f8fafc; color: #1e293b; }
        .container { max-width: 700px; margin: 2rem auto; padding: 0 1rem; }
        .back { color: #667eea; text-decoration: none; margin-bottom: 1rem; display: inline-block; }
        .form-card { background: white; border-radius: 12px; padding: 2rem;
                     box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .form-card h1 { color: #1e40af; margin-bottom: 1.5rem; }
        label { display: block; font-weight: 600; margin: 1rem 0 0.25rem; }
        input, textarea { width: 100%; padding: 0.75rem; border: 1px solid #e2e8f0;
                         border-radius: 8px; font-size: 1rem; font-family: inherit; }
        textarea { min-height: 200px; resize: vertical; }
        button { margin-top: 1.5rem; padding: 0.75rem 2rem; background: #667eea;
                 color: white; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }
        button:hover { background: #5a67d8; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back">← 返回首页</a>
        <div class="form-card">
            <h1>✍️ 写文章</h1>
            <form method="POST" action="/article/new">
                <label for="title">标题</label>
                <input type="text" id="title" name="title" required>
                <label for="author">作者</label>
                <input type="text" id="author" name="author" value="匿名" required>
                <label for="content">内容</label>
                <textarea id="content" name="content" required></textarea>
                <button type="submit">发布文章</button>
            </form>
        </div>
    </div>
</body>
</html>
"#;
